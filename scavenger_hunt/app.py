import io
import json
from datetime import datetime, timezone
from functools import wraps
from flask import (
    Flask, render_template, request, redirect, url_for, session, 
    jsonify, send_file, send_from_directory, flash, abort
)
import qrcode
from qrcode.image.pil import PilImage

from config import SECRET_KEY, DEFAULT_MASTER_PIN
import database

app = Flask(__name__)
app.secret_key = SECRET_KEY

# Ensure tables and initial seeds are present
database.init_db()


def get_client_ip():
    if request.headers.get("X-Forwarded-For"):
        return request.headers.get("X-Forwarded-For").split(",")[0].strip()
    return request.remote_addr or "127.0.0.1"


def get_logged_in_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    user = database.get_user_by_id(user_id)
    if not user:
        session.pop("user_id", None)
        return None
    return user


def require_admin(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("admin_login", next=request.path))
        return f(*args, **kwargs)
    return decorated_function


@app.route('/favicon.ico')
def favicon():
    return send_from_directory('static', 'favicon.ico', mimetype='image/vnd.microsoft.icon')


# -------------------------------------------------------------
# User Journey Routes (Treasure Hunt)
# -------------------------------------------------------------

@app.route("/")
def index():
    user = get_logged_in_user()
    if not user:
        return redirect(url_for("register"))

    status = user["status"]
    if status == "waiting_approval":
        return redirect(url_for("waiting"))
    elif status == "approved":
        return redirect(url_for("terms"))
    elif status == "terms_accepted":
        return redirect(url_for("quiz"))
    elif status == "quiz_passed":
        return redirect(url_for("hunt"))
    elif status == "completed":
        return redirect(url_for("victory"))
    elif status == "rejected":
        flash("ඔබගේ ලියාපදිංචිය ප්‍රතික්ෂේප විය. (Your registration was declined).", "danger")
        return redirect(url_for("register"))
    
    return redirect(url_for("register"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        user = get_logged_in_user()
        if user and user["status"] != "rejected":
            return redirect(url_for("index"))
        return render_template("register.html")

    username = request.form.get("username", "").strip()
    id_number = request.form.get("id_number", "").strip()
    whatsapp = request.form.get("whatsapp", "").strip()
    age_category = request.form.get("age_category", "").strip()

    if not username or not id_number or not whatsapp or not age_category:
        flash("කරුණාකර සියලු විස්තර නිවැරදිව පුරවන්න. (Please fill in all required fields).", "danger")
        return render_template("register.html", form=request.form)

    if age_category not in ["under_18", "18_plus"]:
        flash("වලංගු වයස් කාණ්ඩයක් තෝරන්න. (Please select a valid age category).", "danger")
        return render_template("register.html", form=request.form)

    ip = get_client_ip()
    user_id = database.create_user(username, id_number, whatsapp, age_category, ip)
    session["user_id"] = user_id
    session["username"] = username

    return redirect(url_for("waiting"))


@app.route("/waiting")
def waiting():
    user = get_logged_in_user()
    if not user:
        return redirect(url_for("register"))

    if user["status"] != "waiting_approval":
        return redirect(url_for("index"))

    return render_template("waiting.html", user=user)


@app.route("/terms")
def terms():
    user = get_logged_in_user()
    if not user:
        return redirect(url_for("register"))

    if user["status"] == "waiting_approval":
        return redirect(url_for("waiting"))
    if user["status"] in ["quiz_passed", "completed"]:
        return redirect(url_for("index"))

    terms_text = database.get_setting("terms_conditions")
    return render_template("terms.html", user=user, terms_text=terms_text)


@app.route("/api/terms/accept", methods=["POST"])
def api_terms_accept():
    user = get_logged_in_user()
    if not user:
        return jsonify({"success": False, "error": "Not authenticated"}), 401

    database.update_terms_accepted(user["id"])
    return jsonify({"success": True, "redirect": url_for("quiz")})


@app.route("/quiz")
def quiz():
    user = get_logged_in_user()
    if not user:
        return redirect(url_for("register"))

    if user["status"] == "waiting_approval":
        return redirect(url_for("waiting"))
    if user["status"] == "approved":
        return redirect(url_for("terms"))
    if user["status"] == "quiz_passed":
        return redirect(url_for("hunt"))
    if user["status"] == "completed":
        return redirect(url_for("victory"))

    questions = database.get_user_assigned_questions(user["id"])
    return render_template("quiz.html", user=user, questions=questions)


@app.route("/api/quiz/submit", methods=["POST"])
def api_quiz_submit():
    user = get_logged_in_user()
    if not user:
        return jsonify({"success": False, "error": "Not authenticated"}), 401

    data = request.get_json(silent=True) or request.form.to_dict()
    answers = data.get("answers", {})

    all_correct, score, message = database.check_and_save_quiz_answers(user["id"], answers)

    if all_correct:
        return jsonify({
            "success": True,
            "all_correct": True,
            "score": score,
            "message": message,
            "redirect": url_for("hunt")
        })
    else:
        return jsonify({
            "success": False,
            "all_correct": False,
            "score": score,
            "message": message
        })


@app.route("/hunt")
def hunt():
    user = get_logged_in_user()
    if not user:
        return redirect(url_for("register"))

    if user["status"] in ["waiting_approval", "approved", "terms_accepted"]:
        return redirect(url_for("index"))

    if user["status"] == "completed":
        return redirect(url_for("victory"))

    assigned_qrs = database.get_user_assigned_qr_codes(user["id"])
    scanned_ids = json.loads(user["scanned_qr_ids"] or "[]")
    current_step = len(scanned_ids) + 1 if len(scanned_ids) < len(assigned_qrs) else len(assigned_qrs)

    return render_template(
        "hunt.html",
        user=user,
        assigned_qrs=assigned_qrs,
        scanned_ids=scanned_ids,
        scanned_count=len(scanned_ids),
        total_count=len(assigned_qrs),
        current_step=current_step
    )


@app.route("/api/hunt/scan", methods=["POST"])
def api_hunt_scan():
    user = get_logged_in_user()
    if not user:
        return jsonify({"success": False, "message": "Not authenticated"}), 401

    data = request.get_json(silent=True) or request.form.to_dict()
    code = data.get("code", "").strip()

    if not code:
        return jsonify({"success": False, "message": "කරුණාකර වලංගු QR කේතයක් ලබා දෙන්න (Please provide a QR code)."}), 400

    result = database.process_qr_scan(user["id"], code)
    if result.get("status") == "completed":
        result["redirect"] = url_for("victory")

    return jsonify(result)


@app.route("/victory")
def victory():
    user = get_logged_in_user()
    if not user:
        return redirect(url_for("register"))

    if user["status"] != "completed":
        return redirect(url_for("index"))

    assigned_qrs = database.get_user_assigned_qr_codes(user["id"])
    return render_template("victory.html", user=user, assigned_qrs=assigned_qrs)


@app.route("/logout")
def logout():
    session.pop("user_id", None)
    session.pop("username", None)
    flash("ඔබ සාර්ථකව ඉවත් විය. (You have signed out).", "info")
    return redirect(url_for("register"))


@app.route("/api/user/status")
def api_user_status():
    user = get_logged_in_user()
    if not user:
        return jsonify({"logged_in": False})

    scanned_ids = json.loads(user["scanned_qr_ids"] or "[]")
    assigned_ids = json.loads(user["assigned_qr_ids"] or "[]")

    return jsonify({
        "logged_in": True,
        "user_id": user["id"],
        "username": user["username"],
        "status": user["status"],
        "scanned_count": len(scanned_ids),
        "total_count": len(assigned_ids),
        "next_url": url_for("index")
    })


# -------------------------------------------------------------
# Dynamic QR Code Image Generator (PNG)
# -------------------------------------------------------------

@app.route("/api/qr-image/<string:code_str>")
def api_qr_image(code_str):
    """
    Renders high-quality PNG QR code containing the raw code string.
    Can be scanned by our web camera scanner or standard QR scanner.
    """
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=3,
    )
    qr.add_data(code_str)
    qr.make(fit=True)

    img = qr.make_image(fill_color="#0f172a", back_color="#ffffff")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return send_file(buffer, mimetype="image/png")


# -------------------------------------------------------------
# Admin Routes (Protected with Master PIN)
# -------------------------------------------------------------

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if session.get("is_admin"):
        return redirect(url_for("admin_dashboard"))

    if request.method == "POST":
        pin = request.form.get("pin", "").strip()
        if database.verify_master_pin(pin):
            session["is_admin"] = True
            flash("Admin access granted.", "success")
            next_url = request.args.get("next")
            return redirect(next_url or url_for("admin_dashboard"))
        else:
            flash("Master PIN එක වැරදියි! Invalid Master PIN.", "danger")

    return render_template("admin_login.html")


@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    flash("Admin logged out.", "info")
    return redirect(url_for("admin_login"))


@app.route("/admin")
@require_admin
def admin_dashboard():
    users = database.get_all_users()
    questions = database.get_questions()
    qr_codes = database.get_qr_codes()
    terms = database.get_setting("terms_conditions")
    master_pin = database.get_setting("master_pin", DEFAULT_MASTER_PIN)

    stats = {
        "total": len(users),
        "waiting": sum(1 for u in users if u["status"] == "waiting_approval"),
        "active": sum(1 for u in users if u["status"] in ["approved", "terms_accepted", "quiz_passed"]),
        "completed": sum(1 for u in users if u["status"] == "completed"),
        "in_raffle": sum(1 for u in users if u.get("in_raffle_pool"))
    }

    return render_template(
        "admin_dashboard.html",
        users=users,
        questions=questions,
        qr_codes=qr_codes,
        terms=terms,
        master_pin=master_pin,
        stats=stats
    )


@app.route("/admin/print-qr")
@require_admin
def admin_print_qr():
    qr_codes = database.get_qr_codes()
    return render_template("admin_print_qr.html", qr_codes=qr_codes)


# --- Admin Live JSON APIs ---

@app.route("/api/admin/users")
@require_admin
def api_admin_users():
    users = database.get_all_users()
    stats = {
        "total": len(users),
        "waiting": sum(1 for u in users if u["status"] == "waiting_approval"),
        "active": sum(1 for u in users if u["status"] in ["approved", "terms_accepted", "quiz_passed"]),
        "completed": sum(1 for u in users if u["status"] == "completed"),
        "in_raffle": sum(1 for u in users if u.get("in_raffle_pool"))
    }
    return jsonify({"success": True, "users": users, "stats": stats})


@app.route("/api/admin/user/<int:user_id>/details")
@require_admin
def api_admin_user_details(user_id):
    """
    Returns live activity audit trail, question-by-question quiz analysis,
    and QR code hunt status for the requested contestant.
    """
    details = database.get_user_detailed_profile(user_id)
    if not details:
        return jsonify({"success": False, "message": "User not found"}), 404
    return jsonify({"success": True, "details": details})


@app.route("/api/admin/user/<int:user_id>/approve", methods=["POST"])
@require_admin
def api_admin_approve_user(user_id):
    database.approve_user(user_id)
    return jsonify({"success": True, "message": f"User #{user_id} approved."})


@app.route("/api/admin/user/<int:user_id>/reject", methods=["POST"])
@require_admin
def api_admin_reject_user(user_id):
    database.reject_user(user_id)
    return jsonify({"success": True, "message": f"User #{user_id} rejected."})


@app.route("/api/admin/user/<int:user_id>/delete", methods=["POST"])
@require_admin
def api_admin_delete_user(user_id):
    database.delete_user(user_id)
    return jsonify({"success": True, "message": f"User #{user_id} permanently deleted."})


@app.route("/api/admin/terms", methods=["POST"])
@require_admin
def api_admin_save_terms():
    data = request.get_json(silent=True) or request.form.to_dict()
    terms = data.get("terms", "").strip()
    if terms:
        database.set_setting("terms_conditions", terms)
        return jsonify({"success": True, "message": "Terms and conditions updated."})
    return jsonify({"success": False, "message": "Terms cannot be empty."}), 400


@app.route("/api/admin/questions/add", methods=["POST"])
@require_admin
def api_admin_add_question():
    data = request.get_json(silent=True) or request.form.to_dict()
    q = data.get("question", "").strip()
    opt_a = data.get("option_a", "").strip()
    opt_b = data.get("option_b", "").strip()
    opt_c = data.get("option_c", "").strip()
    opt_d = data.get("option_d", "").strip()
    correct = data.get("correct_option", "").strip().upper()

    if not (q and opt_a and opt_b and opt_c and opt_d and correct in ["A", "B", "C", "D"]):
        return jsonify({"success": False, "message": "All question fields and valid correct option (A/B/C/D) are required."}), 400

    database.add_question(q, opt_a, opt_b, opt_c, opt_d, correct)
    return jsonify({"success": True, "message": "Question added successfully."})


@app.route("/api/admin/questions/<int:qid>/delete", methods=["POST"])
@require_admin
def api_admin_delete_question(qid):
    database.delete_question(qid)
    return jsonify({"success": True, "message": f"Question #{qid} deleted."})


@app.route("/api/admin/qrcodes/add", methods=["POST"])
@require_admin
def api_admin_add_qrcode():
    data = request.get_json(silent=True) or request.form.to_dict()
    code = data.get("code", "").strip().upper()
    title = data.get("title", "").strip()
    hint = data.get("hint", "").strip()
    is_trap = int(data.get("is_trap", 0))

    if not code or not title:
        return jsonify({"success": False, "message": "Code identifier and Title are required."}), 400

    existing = database.get_qr_code_by_code(code)
    if existing:
        return jsonify({"success": False, "message": f"QR Code '{code}' already exists."}), 400

    database.add_qr_code(code, title, hint, is_trap)
    return jsonify({"success": True, "message": "QR Code added successfully."})


@app.route("/api/admin/qrcodes/<int:qrid>/delete", methods=["POST"])
@require_admin
def api_admin_delete_qrcode(qrid):
    database.delete_qr_code(qrid)
    return jsonify({"success": True, "message": f"QR Code #{qrid} deleted."})


@app.route("/api/admin/settings/pin", methods=["POST"])
@require_admin
def api_admin_change_pin():
    data = request.get_json(silent=True) or request.form.to_dict()
    new_pin = data.get("pin", "").strip()
    if len(new_pin) < 4:
        return jsonify({"success": False, "message": "PIN must be at least 4 digits."}), 400

    database.set_setting("master_pin", new_pin)
    return jsonify({"success": True, "message": "Master PIN updated successfully."})


# -------------------------------------------------------------
# Raffle Draw / Lucky Draw (Top 50 Contestants Stage View)
# -------------------------------------------------------------

@app.route("/admin/raffle")
@require_admin
def admin_raffle():
    participants = database.get_raffle_eligible_participants(limit=50)
    winners = database.get_raffle_winners()
    return render_template(
        "admin_raffle.html",
        participants=participants,
        winners=winners,
        total_eligible=len(participants)
    )


@app.route("/api/raffle/participants")
@require_admin
def api_raffle_participants():
    participants = database.get_raffle_eligible_participants(limit=50)
    return jsonify({"success": True, "participants": participants, "total": len(participants)})


@app.route("/api/raffle/save-winner", methods=["POST"])
@require_admin
def api_raffle_save_winner():
    data = request.get_json(silent=True) or request.form.to_dict()
    user_id = data.get("user_id")
    prize_title = data.get("prize_title", "Grand Prize").strip()

    if not user_id:
        return jsonify({"success": False, "message": "User ID is required."}), 400

    winner_id = database.save_raffle_winner(int(user_id), prize_title)
    winners = database.get_raffle_winners()
    return jsonify({"success": True, "winner_id": winner_id, "winners": winners})


@app.route("/api/raffle/seed-50", methods=["POST"])
@require_admin
def api_raffle_seed_50():
    added = database.seed_sample_raffle_participants(target_total=50)
    participants = database.get_raffle_eligible_participants(limit=50)
    return jsonify({
        "success": True,
        "added": added,
        "total": len(participants),
        "participants": participants,
        "message": f"Successfully ensured 50 eligible contestants (Added {added} demo participants)."
    })


@app.route("/api/raffle/clear-winners", methods=["POST"])
@require_admin
def api_raffle_clear_winners():
    database.clear_raffle_winners()
    return jsonify({"success": True, "message": "Winners history cleared."})


@app.route("/api/admin/raffle/add-user", methods=["POST"])
@require_admin
def api_admin_raffle_add_user():
    data = request.get_json(silent=True) or request.form.to_dict()
    user_id = data.get("user_id")
    if not user_id:
        return jsonify({"success": False, "message": "User ID is required."}), 400
    success, msg = database.add_user_to_raffle_pool(int(user_id))
    return jsonify({"success": success, "message": msg})


@app.route("/api/admin/raffle/remove-user", methods=["POST"])
@require_admin
def api_admin_raffle_remove_user():
    data = request.get_json(silent=True) or request.form.to_dict()
    user_id = data.get("user_id")
    if not user_id:
        return jsonify({"success": False, "message": "User ID is required."}), 400
    success, msg = database.remove_user_from_raffle_pool(int(user_id))
    return jsonify({"success": success, "message": msg})


@app.route("/api/admin/raffle/add-all", methods=["POST"])
@require_admin
def api_admin_raffle_add_all():
    success, msg = database.add_all_completed_to_raffle_pool()
    return jsonify({"success": success, "message": msg})


@app.route("/api/admin/raffle/clear-pool", methods=["POST"])
@require_admin
def api_admin_raffle_clear_pool():
    success, msg = database.clear_raffle_pool()
    return jsonify({"success": success, "message": msg})


# -------------------------------------------------------------
# Admin Data Backup & Restore (JSON Export & Import)
# -------------------------------------------------------------

@app.route("/api/admin/export-backup")
@require_admin
def api_admin_export_backup():
    backup_data = database.export_backup_data()
    filename = f"treasure_hunt_backup_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    mem = io.BytesIO()
    mem.write(json.dumps(backup_data, indent=2, ensure_ascii=False).encode('utf-8'))
    mem.seek(0)
    return send_file(
        mem,
        as_attachment=True,
        download_name=filename,
        mimetype="application/json"
    )


@app.route("/api/admin/import-backup", methods=["POST"])
@require_admin
def api_admin_import_backup():
    if "file" in request.files:
        f = request.files["file"]
        if not f or not f.filename.endswith(".json"):
            return jsonify({"success": False, "message": "JSON ගොනුවක් පමණක් තෝරන්න (Only .json file allowed)."}), 400
        try:
            content = f.read().decode("utf-8")
            payload = json.loads(content)
        except Exception as e:
            return jsonify({"success": False, "message": f"වලංගු නොවන JSON ගොනුවකි: {str(e)}"}), 400
    else:
        payload = request.get_json(silent=True) or {}

    if not payload:
        return jsonify({"success": False, "message": "දත්ත කිසිවක් හමු නොවීය."}), 400

    stats = database.import_backup_data(payload)
    return jsonify({
        "success": True,
        "message": f"සාර්ථකව දත්ත ප්‍රතිස්ථාපනය කළා! (QR කේත: {stats['qrs_imported']}, ප්‍රශ්න: {stats['questions_imported']})",
        "stats": stats
    })


# -------------------------------------------------------------
# Error Handlers
# -------------------------------------------------------------

@app.errorhandler(404)
def not_found_error(error):
    return render_template("base.html", page_title="Page Not Found", main_content="<div class='text-center py-12'><h2 class='text-3xl font-bold text-red-500'>404</h2><p class='text-slate-400 mt-2'>Page not found.</p><a href='/' class='mt-4 inline-block px-4 py-2 bg-indigo-600 text-white rounded-lg'>Back to Home</a></div>"), 404


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
