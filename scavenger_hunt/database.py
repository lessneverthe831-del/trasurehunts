import sqlite3
import json
import random
from datetime import datetime, timezone, timedelta
from config import DATABASE_PATH, DEFAULT_MASTER_PIN

# Sri Lanka Standard Time (Asia/Colombo, UTC +05:30)
SRI_LANKA_TZ = timezone(timedelta(hours=5, minutes=30))

def get_now_sl() -> datetime:
    """Returns current datetime in Sri Lanka Standard Time (UTC+05:30)."""
    return datetime.now(SRI_LANKA_TZ)

def get_now_sl_str() -> str:
    """Returns formatted 'YYYY-MM-DD HH:MM:SS' string in Sri Lanka Standard Time."""
    return datetime.now(SRI_LANKA_TZ).strftime("%Y-%m-%d %H:%M:%S")


def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    with conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT NOT NULL,
            option_a TEXT NOT NULL,
            option_b TEXT NOT NULL,
            option_c TEXT NOT NULL,
            option_d TEXT NOT NULL,
            correct_option TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS qr_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            hint TEXT,
            is_trap INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            id_number TEXT NOT NULL,
            whatsapp TEXT NOT NULL,
            age_category TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'waiting_approval',
            assigned_question_ids TEXT,
            assigned_qr_ids TEXT,
            scanned_qr_ids TEXT DEFAULT '[]',
            quiz_score INTEGER DEFAULT 0,
            quiz_answers TEXT DEFAULT '{}',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            approved_at TIMESTAMP,
            completed_at TIMESTAMP,
            ip_address TEXT
        );

        CREATE TABLE IF NOT EXISTS scan_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            scanned_code TEXT NOT NULL,
            result TEXT NOT NULL,
            message TEXT,
            scanned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS activity_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            action_type TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            details_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS raffle_winners (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            prize_title TEXT DEFAULT 'Grand Prize',
            draw_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS raffle_pool (
            user_id INTEGER PRIMARY KEY,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS otp_verifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            whatsapp TEXT NOT NULL,
            id_number TEXT,
            otp_code TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            attempts INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NOT NULL
        );
        """)

        # Migration: Ensure is_phone_verified column in users table
        try:
            conn.execute("ALTER TABLE users ADD COLUMN is_phone_verified INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass # already exists

        # One-time Migration: Convert any legacy UTC timestamps to Sri Lanka Standard Time (+05:30)
        try:
            cur = conn.cursor()
            cur.execute("SELECT value FROM settings WHERE key = 'timezone_migrated_sl'")
            if not cur.fetchone():
                conn.execute("UPDATE activity_logs SET created_at = datetime(created_at, '+5 hours', '+30 minutes') WHERE created_at IS NOT NULL AND created_at != ''")
                conn.execute("UPDATE users SET created_at = datetime(created_at, '+5 hours', '+30 minutes') WHERE created_at IS NOT NULL AND created_at != ''")
                conn.execute("UPDATE users SET approved_at = datetime(approved_at, '+5 hours', '+30 minutes') WHERE approved_at IS NOT NULL AND approved_at != ''")
                conn.execute("UPDATE users SET completed_at = datetime(completed_at, '+5 hours', '+30 minutes') WHERE completed_at IS NOT NULL AND completed_at != ''")
                conn.execute("UPDATE scan_logs SET scanned_at = datetime(scanned_at, '+5 hours', '+30 minutes') WHERE scanned_at IS NOT NULL AND scanned_at != ''")
                conn.execute("UPDATE otp_verifications SET created_at = datetime(created_at, '+5 hours', '+30 minutes') WHERE created_at IS NOT NULL AND created_at != ''")
                conn.execute("UPDATE otp_verifications SET expires_at = datetime(expires_at, '+5 hours', '+30 minutes') WHERE expires_at IS NOT NULL AND expires_at != ''")
                conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('timezone_migrated_sl', 'true')")
        except Exception as e:
            print(f"[TIMEZONE MIGRATION] Notice: {e}")

        # Seed Settings if not present
        cur = conn.cursor()
        cur.execute("SELECT value FROM settings WHERE key = 'master_pin'")
        if not cur.fetchone():
            cur.execute("INSERT INTO settings (key, value) VALUES ('master_pin', ?)", (DEFAULT_MASTER_PIN,))

        cur.execute("SELECT value FROM settings WHERE key = 'terms_conditions'")
        if not cur.fetchone():
            default_terms = (
                "💠Treasure Hunt තරඟ නීති සහ සහභාගීත්ව ගිවිසුම \n"
                "    (Treasure Hunt Rules & Participation Agreement)\n\n\n"
                "⭕වංචා කිරීමෙන්, QR කේතවලට හානි කිරීමෙන් හෝ වෙනස් කිරීමෙන් සහ සීමා කර ඇති ඉඟි වෙනත් සහභාගිවන්නන් සමඟ බෙදාගැනීමෙන් වළකින්න.(Do not cheat, tamper with QR codes, or share restricted clues.)\n\n"
                "⭕විශ්වවිද්‍යාල දේපළ, ප්‍රදර්ශන කුටි සහ අනෙකුත් සහභාගිවන්නන්ට ගරු කරන්න.(Respect university property, exhibition stalls, and other participants.)\n\n"
                "⭕නිධන් සෙවීමේ ක්‍රීඩාව සාර්ථකව සම්පූර්ණ කරන පළමු සුදුසුකම්ලත් සහභාගිවන්නන් 50 දෙනාට ත්‍යාග හිමි වේ. ඔවුන් අවසන් දිනයේ පැවැත්වෙන දිනුම් ඇදීමට (Raffle Draw) ඇතුළත් කරනු ලැබේ.(The first 50 eligible participants who successfully complete the Treasure Hunt will qualify for gifts. These 50 participants will then be entered into a raffle draw held on the final day of the exhibition to determine the winners of the special prizes.)\n\n"
                "⭕සහභාගිවන්නන්ගේ සුදුසුකම් සහ ක්‍රීඩාවේ ප්‍රතිඵල සම්බන්ධයෙන් සංවිධායක මණ්ඩලය ගනු ලබන තීරණ අවසාන තීරණ වේ.(The organizers’ decisions on eligibility and game results are final.)"
            )
            cur.execute("INSERT INTO settings (key, value) VALUES ('terms_conditions', ?)", (default_terms,))

        # Seed WhatsApp Gateway Settings if not present
        whatsapp_defaults = [
            ("whatsapp_otp_enabled", "true"),
            ("whatsapp_gateway_type", "simulation"),
            ("whatsapp_api_token", ""),
            ("whatsapp_phone_number_id", ""),
            ("whatsapp_account_sid", ""),
            ("whatsapp_instance_id", ""),
            ("whatsapp_sender_number", ""),
            ("whatsapp_custom_url", ""),
            ("whatsapp_msg_template", "ඔබගේ Treasure Hunt ලියාපදිංචි OTP කේතය: {otp} වේ. මෙය කිසිවෙකු සමඟ බෙදා නොගන්න. (Your Scavenger Hunt registration OTP is: {otp}).")
        ]
        for k, v in whatsapp_defaults:
            cur.execute("SELECT value FROM settings WHERE key = ?", (k,))
            if not cur.fetchone():
                cur.execute("INSERT INTO settings (key, value) VALUES (?, ?)", (k, v))

        # Seed initial question bank if empty
        cur.execute("SELECT COUNT(*) as cnt FROM questions")
        if cur.fetchone()["cnt"] == 0:
            initial_questions = [
                (
                    "ශ්‍රී ලංකාවේ ප්‍රථම විධායක ජනාධිපතිවරයා කවුද? (Who was the first Executive President of Sri Lanka?)",
                    "ඩී. එස්. සේනානායක (D. S. Senanayake)",
                    "ජේ. ආර්. ජයවර්ධන (J. R. Jayewardene)",
                    "ආර්. ප්‍රේමදාස (R. Premadasa)",
                    "විලියම් ගොපල්ලව (William Gopallawa)",
                    "B"
                ),
                (
                    "පරිගණක ජාලකරණයේදී 'IP' යන්නෙහි සම්පූර්ණ අර්ථය කුමක්ද? (What does 'IP' stand for in computer networking?)",
                    "Internet Protocol",
                    "Internal Program",
                    "Instant Packet",
                    "Interconnected Path",
                    "A"
                ),
                (
                    "ලෝකයේ උසම කන්ද කුමක්ද? (What is the highest mountain in the world?)",
                    "කේ2 (K2)",
                    "කන්චෙන්ජුන්ගා (Kangchenjunga)",
                    "එවරස්ට් කන්ද (Mount Everest)",
                    "කිලිමන්ජාරෝ (Kilimanjaro)",
                    "C"
                ),
                (
                    "සාර්ථක HTTP ප්‍රතිචාරයක් දැක්වෙන කේතය කුමක්ද? (Which HTTP status code indicates a successful response?)",
                    "404 Not Found",
                    "500 Internal Error",
                    "200 OK",
                    "301 Moved",
                    "C"
                ),
                (
                    "ශ්‍රී ලංකාවේ දිගම ගංගාව කුමක්ද? (What is the longest river in Sri Lanka?)",
                    "කැළණි ගඟ (Kelani River)",
                    "මහවැලි ගඟ (Mahaweli River)",
                    "කළු ගඟ (Kalu River)",
                    "වලවේ ගඟ (Walawe River)",
                    "B"
                ),
                (
                    "පයිතන් (Python) ක්‍රමලේඛන භාෂාව නිර්මාණය කළේ කවුද? (Who created Python?)",
                    "Guido van Rossum",
                    "James Gosling",
                    "Dennis Ritchie",
                    "Bjarne Stroustrup",
                    "A"
                ),
                (
                    "මිනිස් සිරුරේ ඇති විශාලතම අභ්‍යන්තර ඉන්ද්‍රිය කුමක්ද? (What is the largest internal organ in human body?)",
                    "හෘදය (Heart)",
                    "පෙණහලු (Lungs)",
                    "අක්මාව (Liver)",
                    "වකුගඩු (Kidneys)",
                    "C"
                ),
                (
                    "වෙබ් බ්‍රව්සරයක අඩංගු අංග ලේඛනය හැඩගැන්වීමට (Styling) යොදාගන්නේ කුමක්ද? (What is used for styling web documents?)",
                    "HTML",
                    "SQL",
                    "CSS",
                    "XML",
                    "C"
                )
            ]
            cur.executemany("""
                INSERT INTO questions (question, option_a, option_b, option_c, option_d, correct_option)
                VALUES (?, ?, ?, ?, ?, ?)
            """, initial_questions)

        # Seed initial QR Codes (Targets & Traps) from organizer setup
        cur.execute("SELECT COUNT(*) as cnt FROM qr_codes")
        if cur.fetchone()["cnt"] == 0:
            initial_qrs = [
                ("TRAP-DEC-901", "අන්තරායකාරී උගුල (Trap: Decoy Alpha)", "උගුල් කේතයකි - ස්කෑන් නොකරන්න!", 1),
                ("TRAP-DEC-902", "වැරදි මාර්ගය (Trap: Wrong Route Beta)", "උගුල් කේතයකි - වැරදි මාර්ගයකි!", 1),
                ("TRAP-DEC-903", "ව්‍යාජ ඉලක්කය (Trap: Fake Target Gamma)", "උගුල් කේතයකි - මෙය ව්‍යාජ ඉලක්කයකි!", 1),
                ("TARGET P001", "BMart (Projector & CCTV)", "\"“One makes the unseen visible, another makes the invisible appear. One throws images onto a wall, the other keeps watch without standing tall. Find the place where both eyes and images serve a purpose.”\"  \"එකක් නොපෙනෙන දේ දකින්න උපකාරී වෙයි. අනෙක රූප බිත්තියක් මත දිස් කරයි. එකක් අවට සිදුවන දේ නිරීක්ෂණය කරයි, අනෙක අදහස් විශාල තිරයක් මත පෙන්වයි. මේ දෙකම තම කාර්යයට යොදාගන්නා ස්ථානය සොයාගන්න.\"", 0),
                ("TARGET P002", "Smart Dustbin – Smart Dustbin Stall", "\"“I welcome what others throw away, but I may react before your hand touches me. I help keep our surroundings clean, using technology in an unexpected place. Find me where waste meets intelligence.”\"  \"අන් අය ඉවත දමන දේ මම භාරගනිමි. නමුත් සමහරවිට ඔබේ අත මා ස්පර්ශ කිරීමටත් පෙර මම ක්‍රියාත්මක වෙමි. තාක්ෂණය භාවිතයෙන් පරිසරය පිරිසිදුව තබාගැනීමට මම උදව් කරමි. අපද්‍රව්‍ය සහ බුද්ධිමත් තාක්ෂණය හමුවන ස්ථානය සොයාගන්න.\"", 0),
                ("TARGET P003", "International Marine Services", "\"“I cross borders without passports and carry the world's business across the blue. My roads are waves, my highways are oceans, and my cargo connects distant lands. Find the stall that keeps global trade moving.”\"  \"මම ගමන් කරන්නේ දේශසීමා හරහාය, නමුත් මට ගමන් බලපත්‍රයක් අවශ්‍ය නැත. මගේ මාර්ගය සාගරයයි, මගේ මහාමාර්ගය රළ පහරයි. දුරස්ථ රටවල් අතර භාණ්ඩ ගෙනයමින් ලෝක වෙළෙඳාම සම්බන්ධ කරන්නේ මමයි. එම කාර්යය සිදුකරන ස්ථානය සොයාගන්න.\"", 0),
                ("TARGET P004", "SmartLock.lk – Smart Door Locks", "\"“I guard an entrance without carrying a key in my pocket. A secret code, a touch, or a digital signal may grant you passage. Find the place where security gets smarter and the traditional key loses its power.”\"  \"මම දොරටුවක් ආරක්ෂා කරමි, නමුත් මගේ සාක්කුවේ යතුරක් නැත. රහස් අංකයක්, ස්පර්ශයක් හෝ ඩිජිටල් සංඥාවක් මඟින් මට දොර විවෘත කිරීමට අවසර දිය හැකිය. සාම්ප්‍රදායික යතුරට නව අභියෝගයක් එල්ල කරන බුද්ධිමත් ආරක්ෂාව සොයාගන්න.\"", 0),
                ("TARGET P005", "DUSU Clothing", "\"“I have no voice, yet I express your identity. I change with trends, seasons, and moods, and I turn ordinary people into their own style statements. Find the place where fabric speaks without words.”\"  \" මට කතා කළ නොහැකි වුවත්, ඔබ කවුදැයි ලෝකයට පෙන්වීමට මට හැකිය. විලාසිතා, කාලගුණය සහ ඔබේ මනෝභාවය අනුව මම වෙනස් වෙමි. සාමාන්‍ය පෙනුමක් විශේෂ පෙනුමක් බවට පත් කරමි. රෙදිපිළි වචන නොමැතිව ඔබ වෙනුවෙන් කතා කරන ස්ථානය සොයාගන්න.\"", 0),
                ("TARGET P006", "Innovation Lab – Hardware Museum", "\"“Before smart screens and clever software, there were the parts that made everything possible. I preserve the building blocks of digital progress, where yesterday's technology tells tomorrow's story. Find the place where machines reveal their past.”\"  \"බුද්ධිමත් තිර සහ දක්ෂ මෘදුකාංග බිහිවීමට පෙර, ඒවාට අවශ්‍ය මූලික කොටස් තිබුණි. ඩිජිටල් ලෝකයේ දියුණුව ගොඩනැඟූ තාක්ෂණික කොටස් මම රැකගනිමි. අතීතයේ යන්ත්‍ර අද දවසට කතා කරන, හෙට දවසේ තාක්ෂණයට මඟ පෙන්වන ස්ථානය සොයාගන්න.\"", 0),
                ("TARGET P007", "Smart Classroom (Gaming Zone)", "\"“Here, lessons may feel like missions and controllers become your tools. You can enter another world without leaving this one, and compete without stepping onto a real field. Find the place where learning meets play.”\"  \"මෙහි පාඩම් මෙහෙයුම් බවටත්, පාලක උපකරණ ඔබේ මෙවලම් බවටත් පත්වේ. ඔබ සිටින ස්ථානයෙන් පිටතට නොගොස් වෙනත් ලෝකයකට පිවිසිය හැකිය. සැබෑ ක්‍රීඩා පිටියකට නොගොස් තරග කළ හැකිය. ඉගෙනීම සහ විනෝදය එකට හමුවන ස්ථානය සොයාගන්න\"", 0),
                ("TARGET P008", "Studio – 3D Films and Live Demo", "\"“What seems flat may suddenly gain depth; what looks distant may feel close enough to touch. Behind the illusion are cameras, creativity, and technology. Find the place where moving images step beyond the ordinary screen.”\"  \"පැතලි දෙයක් ගැඹුරු බවක් ගනී. දුරින් පෙනෙන දෙයක් ඔබට ළඟින්ම ඇති බවක් දැනේ. මේ මායාව පිටුපස කැමරා, නිර්මාණශීලීත්වය සහ තාක්ෂණය ඇත. සාමාන්‍ය තිරයක සීමාවෙන් ඔබ්බට ගොස් රූප ජීවමාන වන ස්ථානය සොයාගන්න.\"", 0),
                ("TARGET P009", "Lite Cinema (Film Company)", "\"“I turn moments into memories and stories into experiences. I need no book to tell a tale, yet millions may follow mine. Find the place where imagination meets the screen.”\"  \"මම මොහොතක් මතකයක් බවටත්, කතාවක් අත්දැකීමක් බවටත් පත් කරමි. පොතක් නොමැතිව කතා කියමි. මිලියන ගණනක් මගේ කතා සමඟ ගමන් කරති. පරිකල්පනය සහ තිරය එකට හමුවන ස්ථානය සොයාගන්න.\"", 0),
                ("TRAP-DEC-904", "wrong qr -4", "Wrong Target", 1)
            ]
            cur.executemany("""
                INSERT INTO qr_codes (code, title, hint, is_trap)
                VALUES (?, ?, ?, ?)
            """, initial_qrs)

    conn.close()


# -------------------------------------------------------------
# Activity Logging
# -------------------------------------------------------------

def log_user_activity(user_id: int, action_type: str, title: str, description: str = "", details_dict: dict = None):
    """
    Records an activity audit log entry for the contestant.
    """
    conn = get_db()
    now_str = get_now_sl_str()
    with conn:
        conn.execute("""
            INSERT INTO activity_logs (user_id, action_type, title, description, details_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, action_type, title, description, json.dumps(details_dict) if details_dict else None, now_str))
    conn.close()


def get_user_activities(user_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM activity_logs WHERE user_id = ? ORDER BY id DESC", (user_id,))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# -------------------------------------------------------------
# Settings & Configuration
# -------------------------------------------------------------

def get_setting(key: str, default: str = "") -> str:
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cur.fetchone()
    conn.close()
    return row["value"] if row else default


def set_setting(key: str, value: str):
    conn = get_db()
    with conn:
        conn.execute("""
            INSERT INTO settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """, (key, value))
    conn.close()


def verify_master_pin(entered_pin: str) -> bool:
    master_pin = get_setting("master_pin", DEFAULT_MASTER_PIN)
    return str(entered_pin).strip() == str(master_pin).strip()


# -------------------------------------------------------------
# User Functions
# -------------------------------------------------------------

def check_duplicate_user(id_number: str, whatsapp: str, exclude_user_id: int = None):
    """
    Checks if a user with the given ID number or WhatsApp number already exists.
    Returns (is_duplicate: bool, field: str, message: str)
    """
    import re

    def _norm_phone(p):
        d = re.sub(r"\D", "", str(p or "").strip())
        if d.startswith("94") and len(d) == 11:
            d = "0" + d[2:]
        elif d.startswith("0") and len(d) == 10:
            pass
        elif len(d) == 9 and not d.startswith("0"):
            d = "0" + d
        return d

    def _norm_id(i):
        return re.sub(r"\s+", "", str(i or "").strip()).upper()

    clean_id = _norm_id(id_number)
    clean_phone = _norm_phone(whatsapp)

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, username, id_number, whatsapp FROM users")
    all_users = cur.fetchall()
    conn.close()

    for u in all_users:
        if exclude_user_id and u["id"] == exclude_user_id:
            continue

        # Check National / University ID number
        if clean_id and _norm_id(u["id_number"]) == clean_id:
            return True, "id_number", f"මෙම හැඳුනුම්පත් / විශ්වවිද්‍යාල අංකය ({id_number}) දැනටමත් ලියාපදිංචි කර ඇත. එක් අයෙකුට ලියාපදිංචි විය හැක්කේ එක් වරක් පමණි. (This ID number is already registered)."

        # Check WhatsApp phone number
        if clean_phone and _norm_phone(u["whatsapp"]) == clean_phone:
            return True, "whatsapp", f"මෙම WhatsApp අංකය ({whatsapp}) දැනටමත් ලියාපදිංචි කර ඇත. කරුණාකර වෙනත් අංකයක් භාවිතා කරන්න. (This WhatsApp number is already registered)."

    return False, "", ""


def create_user(username: str, id_number: str, whatsapp: str, age_category: str, ip: str = None, is_phone_verified: int = 1) -> int:
    conn = get_db()
    now_str = get_now_sl_str()
    with conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO users (username, id_number, whatsapp, age_category, status, ip_address, is_phone_verified, created_at)
            VALUES (?, ?, ?, ?, 'waiting_approval', ?, ?, ?)
        """, (username.strip(), id_number.strip(), whatsapp.strip(), age_category.strip(), ip, is_phone_verified, now_str))
        user_id = cur.lastrowid
    conn.close()

    age_label = "18ට අඩු (Under 18)" if age_category == "under_18" else "18ට වැඩි (18+)"
    phone_label = "තහවුරු විය (Verified ✓)" if is_phone_verified else "තහවුරු කර නැත"
    log_user_activity(
        user_id=user_id,
        action_type="registered",
        title="ලියාපදිංචි විය (Registered for Treasure Hunt)",
        description=f"තරඟකරු ලියාපදිංචි වී Admin අනුමැතිය අපේක්ෂාවෙන් රැඳී සිටියි. (ID: {id_number}, WhatsApp: {whatsapp} [{phone_label}], වයස: {age_label})"
    )
    return user_id


def get_recent_otps(limit: int = 50):
    """
    Returns the most recent OTP verifications for the Admin monitor.
    """
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM otp_verifications
        ORDER BY id DESC LIMIT ?
    """, (limit,))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_user_by_id(user_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_users():
    """
    Returns list of all users, enriched with latest activity status, counts, and raffle pool status.
    """
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users ORDER BY id DESC")
    user_rows = cur.fetchall()

    cur.execute("SELECT user_id FROM raffle_pool")
    raffle_set = {r[0] for r in cur.fetchall()}

    users = []
    for u in user_rows:
        ud = dict(u)
        ud["in_raffle_pool"] = ud["id"] in raffle_set
        # Fetch latest activity
        cur.execute("SELECT title, action_type, created_at FROM activity_logs WHERE user_id = ? ORDER BY id DESC LIMIT 1", (ud["id"],))
        latest = cur.fetchone()
        if latest:
            ud["latest_activity"] = latest["title"]
            ud["latest_activity_type"] = latest["action_type"]
            ud["latest_activity_time"] = latest["created_at"]
        else:
            ud["latest_activity"] = "ලියාපදිංචි විය (Registered)"
            ud["latest_activity_type"] = "registered"
            ud["latest_activity_time"] = ud.get("created_at")

        # Scanned and assigned QR counts
        try:
            scanned = json.loads(ud.get("scanned_qr_ids") or "[]")
            assigned = json.loads(ud.get("assigned_qr_ids") or "[]")
            ud["scanned_count"] = len(scanned)
            ud["assigned_count"] = len(assigned)
            ud["current_step"] = len(scanned) + 1 if len(scanned) < len(assigned) else len(assigned)
        except Exception:
            ud["scanned_count"] = 0
            ud["assigned_count"] = 5
            ud["current_step"] = 1

        users.append(ud)

    conn.close()
    return users


def randomize_user_questions(user_id: int):
    """
    Randomizes a fresh set of 5 active questions for the user from the question pool.
    Resets quiz_answers and quiz_score.
    """
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id FROM questions WHERE is_active = 1")
    q_rows = cur.fetchall()
    all_q_ids = [r["id"] for r in q_rows]
    sample_q_count = min(5, len(all_q_ids))
    assigned_q_ids = random.sample(all_q_ids, sample_q_count) if all_q_ids else []

    with conn:
        conn.execute("""
            UPDATE users
            SET assigned_question_ids = ?,
                quiz_score = 0,
                quiz_answers = '{}'
            WHERE id = ?
        """, (json.dumps(assigned_q_ids), user_id))
    conn.close()
    return assigned_q_ids


def approve_user(user_id: int):
    """
    Approves user, assigns 5 randomized questions and 5 randomized valid QR codes.
    """
    conn = get_db()
    cur = conn.cursor()

    # 1. Randomize 5 active questions
    cur.execute("SELECT id FROM questions WHERE is_active = 1")
    q_rows = cur.fetchall()
    all_q_ids = [r["id"] for r in q_rows]
    sample_q_count = min(5, len(all_q_ids))
    assigned_q_ids = random.sample(all_q_ids, sample_q_count) if all_q_ids else []

    # 2. Randomize 5 valid QR codes (is_trap = 0)
    cur.execute("SELECT id FROM qr_codes WHERE is_trap = 0")
    qr_rows = cur.fetchall()
    all_qr_ids = [r["id"] for r in qr_rows]
    sample_qr_count = min(5, len(all_qr_ids))
    assigned_qr_ids = random.sample(all_qr_ids, sample_qr_count) if all_qr_ids else []

    now_str = get_now_sl_str()

    with conn:
        conn.execute("""
            UPDATE users
            SET status = 'approved',
                approved_at = ?,
                assigned_question_ids = ?,
                assigned_qr_ids = ?,
                scanned_qr_ids = '[]'
            WHERE id = ?
        """, (now_str, json.dumps(assigned_q_ids), json.dumps(assigned_qr_ids), user_id))
    conn.close()

    log_user_activity(
        user_id=user_id,
        action_type="approved",
        title="Admin විසින් අනුමත කරන ලදී (Approved by Admin)",
        description=f"තරඟකරුට අහඹු ප්‍රශ්න 5ක් (IDs: {assigned_q_ids}) සහ අනුපිළිවෙලින් සෙවිය යුතු QR ඉලක්ක 5ක් (IDs: {assigned_qr_ids}) පවරන ලදී."
    )


def reject_user(user_id: int):
    conn = get_db()
    with conn:
        conn.execute("UPDATE users SET status = 'rejected' WHERE id = ?", (user_id,))
    conn.close()

    log_user_activity(
        user_id=user_id,
        action_type="rejected",
        title="ලියාපදිංචිය ප්‍රතික්ෂේප විය (Declined by Admin)",
        description="Admin විසින් මෙම තරඟකරුගේ ප්‍රවේශය ප්‍රතික්ෂේප කරන ලදී."
    )


def delete_user(user_id: int):
    conn = get_db()
    with conn:
        conn.execute("DELETE FROM raffle_winners WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM raffle_pool WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM activity_logs WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM scan_logs WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.close()


def delete_all_users():
    """
    Permanently deletes all registered contestants and their logs.
    """
    conn = get_db()
    with conn:
        conn.execute("DELETE FROM raffle_winners")
        conn.execute("DELETE FROM raffle_pool")
        conn.execute("DELETE FROM activity_logs")
        conn.execute("DELETE FROM scan_logs")
        conn.execute("DELETE FROM otp_verifications")
        conn.execute("DELETE FROM users")
    conn.close()


def delete_selected_users(user_ids: list):
    """
    Permanently deletes a selected list of contestants.
    """
    if not user_ids:
        return
    conn = get_db()
    placeholders = ",".join("?" for _ in user_ids)
    with conn:
        conn.execute(f"DELETE FROM raffle_winners WHERE user_id IN ({placeholders})", user_ids)
        conn.execute(f"DELETE FROM raffle_pool WHERE user_id IN ({placeholders})", user_ids)
        conn.execute(f"DELETE FROM activity_logs WHERE user_id IN ({placeholders})", user_ids)
        conn.execute(f"DELETE FROM scan_logs WHERE user_id IN ({placeholders})", user_ids)
        conn.execute(f"DELETE FROM users WHERE id IN ({placeholders})", user_ids)
    conn.close()


def update_terms_accepted(user_id: int):
    conn = get_db()
    with conn:
        conn.execute("UPDATE users SET status = 'terms_accepted' WHERE id = ? AND status = 'approved'", (user_id,))
    conn.close()

    log_user_activity(
        user_id=user_id,
        action_type="terms_accepted",
        title="නීති සහ කොන්දේසි පිළිගත්තා (Accepted Terms & Conditions)",
        description="තරඟකරු නීති සහ කොන්දේසි කියවා පිළිගෙන ප්‍රශ්නාවලිය ආරම්භ කළේය."
    )


# -------------------------------------------------------------
# Questions & Quiz Evaluation (With Retry Re-Randomization)
# -------------------------------------------------------------

def get_questions(active_only=False):
    conn = get_db()
    cur = conn.cursor()
    if active_only:
        cur.execute("SELECT * FROM questions WHERE is_active = 1 ORDER BY id ASC")
    else:
        cur.execute("SELECT * FROM questions ORDER BY id DESC")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_user_assigned_questions(user_id: int):
    user = get_user_by_id(user_id)
    if not user or not user["assigned_question_ids"]:
        return []
    
    try:
        q_ids = json.loads(user["assigned_question_ids"])
    except Exception:
        q_ids = []

    if not q_ids:
        return []

    placeholders = ",".join("?" for _ in q_ids)
    conn = get_db()
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM questions WHERE id IN ({placeholders})", q_ids)
    rows = cur.fetchall()
    conn.close()
    
    # Maintain assigned order
    rows_dict = {r["id"]: dict(r) for r in rows}
    return [rows_dict[qid] for qid in q_ids if qid in rows_dict]


def check_and_save_quiz_answers(user_id: int, answers_dict: dict) -> tuple[bool, int, str]:
    """
    Validates answers against the user's assigned questions.
    Logs detailed question-by-question breakdown.
    If score < 5, re-randomizes a fresh set of 5 questions for retry.
    """
    user_questions = get_user_assigned_questions(user_id)
    if not user_questions:
        return False, 0, "No questions found assigned to this user."

    score = 0
    total = len(user_questions)
    breakdown = []

    for idx, q in enumerate(user_questions, start=1):
        qid_str = str(q["id"])
        user_choice = str(answers_dict.get(qid_str, "")).strip().upper()
        correct_choice = q["correct_option"].strip().upper()
        is_corr = (user_choice == correct_choice)

        if is_corr:
            score += 1

        breakdown.append({
            "number": idx,
            "question_id": q["id"],
            "question": q["question"],
            "user_choice": user_choice,
            "correct_choice": correct_choice,
            "is_correct": is_corr
        })

    all_correct = (score == total and total > 0)

    conn = get_db()
    with conn:
        conn.execute("""
            UPDATE users
            SET quiz_score = ?,
                quiz_answers = ?,
                status = CASE WHEN ? THEN 'quiz_passed' ELSE status END
            WHERE id = ?
        """, (score, json.dumps(answers_dict), all_correct, user_id))
    conn.close()

    # Log rich activity
    if all_correct:
        log_title = f"🧠 ප්‍රශ්නාවලිය සාර්ථකව නිම කළා ({score}/{total} හරි)"
        log_desc = f"ප්‍රශ්න 5ටම නිවැරදි පිළිතුරු (5/5) ලබාදී QR Hunt අදියර විවෘත කරගත්තා."
        log_user_activity(
            user_id=user_id,
            action_type="quiz_attempt",
            title=log_title,
            description=log_desc,
            details_dict={"score": score, "total": total, "all_correct": True, "breakdown": breakdown}
        )
        return True, score, "නියමයි! සියලු ප්‍රශ්න 5ටම නිවැරදි පිළිතුරු ලබා දුන්නා! (All 5 questions answered correctly! You unlocked the Treasure Hunt!)"

    else:
        # Failed quiz: Even one wrong answer means user cannot proceed.
        # Automatically re-randomize a fresh set of 5 questions for retry!
        wrong_count = total - score
        new_random_ids = randomize_user_questions(user_id)

        log_title = f"🧠 ප්‍රශ්නාවලිය ඉදිරිපත් කළා ({score}/{total} හරි, {wrong_count}ක් වැරදියි - නව ප්‍රශ්න පවරන ලදී)"
        log_desc = f"තරඟකරු ප්‍රශ්න {total}න් {score}කට හරි පිළිතුරු දුන් අතර {wrong_count}ක් වැරදි විය. නැවත උත්සාහය සඳහා නව ප්‍රශ්න 5ක් (IDs: {new_random_ids}) ස්වයංක්‍රීයව පවරන ලදී."

        log_user_activity(
            user_id=user_id,
            action_type="quiz_attempt",
            title=log_title,
            description=log_desc,
            details_dict={"score": score, "total": total, "all_correct": False, "breakdown": breakdown, "new_random_ids": new_random_ids}
        )

        msg = (
            f"ඔබ නිවැරදි පිළිතුරු ලබා දුන්නේ {score}/{total}කට පමණි ({wrong_count}ක් වැරදියි). "
            f"QR Hunt අදියරට පිවිසීමට ප්‍රශ්න 5ම නිවැරදි විය යුතුය. "
            f"ඔබගේ නැවත උත්සාහය සඳහා නව ප්‍රශ්න 5ක් සකස් කර ඇත (A fresh set of 5 randomized questions has been assigned). "
            f"කරුණාකර නැවත උත්සාහ කරන්න!"
        )
        return False, score, msg


def add_question(question: str, opt_a: str, opt_b: str, opt_c: str, opt_d: str, correct_opt: str):
    conn = get_db()
    with conn:
        conn.execute("""
            INSERT INTO questions (question, option_a, option_b, option_c, option_d, correct_option)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (question.strip(), opt_a.strip(), opt_b.strip(), opt_c.strip(), opt_d.strip(), correct_opt.strip().upper()))
    conn.close()


def delete_question(qid: int):
    conn = get_db()
    with conn:
        conn.execute("DELETE FROM questions WHERE id = ?", (qid,))
    conn.close()


# -------------------------------------------------------------
# QR Codes & Sequential Scavenger Hunt Evaluation
# -------------------------------------------------------------

def get_qr_codes():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM qr_codes ORDER BY is_trap ASC, id ASC")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_qr_code_by_id(qrid: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM qr_codes WHERE id = ?", (qrid,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def get_qr_code_by_code(code_str: str):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM qr_codes WHERE code = ? COLLATE NOCASE", (code_str.strip(),))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def add_qr_code(code: str, title: str, hint: str, is_trap: int = 0):
    conn = get_db()
    with conn:
        conn.execute("""
            INSERT INTO qr_codes (code, title, hint, is_trap)
            VALUES (?, ?, ?, ?)
        """, (code.strip().upper(), title.strip(), hint.strip() if hint else "", is_trap))
    conn.close()


def delete_qr_code(qrid: int):
    conn = get_db()
    with conn:
        conn.execute("DELETE FROM qr_codes WHERE id = ?", (qrid,))
    conn.close()


def get_user_assigned_qr_codes(user_id: int):
    user = get_user_by_id(user_id)
    if not user or not user["assigned_qr_ids"]:
        return []

    try:
        qr_ids = json.loads(user["assigned_qr_ids"])
    except Exception:
        qr_ids = []

    if not qr_ids:
        return []

    placeholders = ",".join("?" for _ in qr_ids)
    conn = get_db()
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM qr_codes WHERE id IN ({placeholders})", qr_ids)
    rows = cur.fetchall()
    conn.close()

    rows_dict = {r["id"]: dict(r) for r in rows}
    # Maintain assigned order (1st, 2nd, 3rd, 4th, 5th)
    return [rows_dict[qid] for qid in qr_ids if qid in rows_dict]


def process_qr_scan(user_id: int, scanned_code_raw: str) -> dict:
    """
    Evaluates scanned QR code against user's assigned QRs, enforcing SEQUENTIAL PROGRESSION:
    The user MUST find Checkpoint 1 first, then 2, then 3, then 4, then 5!
    """
    code_str = str(scanned_code_raw).strip().upper()
    user = get_user_by_id(user_id)
    if not user:
        return {"success": False, "status": "error", "message": "User not found"}

    if user["status"] == "completed":
        return {
            "success": True,
            "status": "already_completed",
            "message": "ඔබ දැනටමත් තරඟය ජයග්‍රහණය කර ඇත! (You have already won the Treasure Hunt!)",
            "scanned_count": 5,
            "total": 5
        }

    try:
        assigned_qr_ids = json.loads(user["assigned_qr_ids"] or "[]")
        scanned_qr_ids = json.loads(user["scanned_qr_ids"] or "[]")
    except Exception:
        assigned_qr_ids = []
        scanned_qr_ids = []

    total_target = len(assigned_qr_ids)
    current_index = len(scanned_qr_ids)
    current_step_num = current_index + 1

    qr_obj = get_qr_code_by_code(code_str)
    conn = get_db()
    now_str = get_now_sl_str()

    # Case 1: Trap / Decoy QR Code!
    if qr_obj and qr_obj["is_trap"] == 1:
        msg = f"⚠️ වැරදි QR කේතයකි! ({qr_obj['title']}) මෙය උගුල් කේතයකි! (Trap / Wrong QR Code detected!)"
        with conn:
            conn.execute("""
                INSERT INTO scan_logs (user_id, scanned_code, result, message, scanned_at)
                VALUES (?, ?, 'trap', ?, ?)
            """, (user_id, code_str, msg, now_str))
        conn.close()

        log_user_activity(
            user_id=user_id,
            action_type="qr_scan_trap",
            title=f"⚠️ උගුල් QR කේතයක් ස්කෑන් කළා: {code_str}",
            description=f"තරඟකරු වැරදි උගුල් කේතයක් ස්කෑන් කළේය: {qr_obj['title']}",
            details_dict={"code": code_str, "qr_title": qr_obj["title"], "is_trap": True}
        )

        return {
            "success": False,
            "status": "trap",
            "message": msg,
            "scanned_count": current_index,
            "total": total_target,
            "current_step": current_step_num
        }

    # Case 2: Code not found in system at all
    if not qr_obj:
        msg = f"❌ අවලංගු QR කේතයකි! '{code_str}' වලංගු නොවේ. (Invalid / Unknown QR code!)"
        with conn:
            conn.execute("""
                INSERT INTO scan_logs (user_id, scanned_code, result, message, scanned_at)
                VALUES (?, ?, 'invalid', ?, ?)
            """, (user_id, code_str, msg, now_str))
        conn.close()

        log_user_activity(
            user_id=user_id,
            action_type="qr_scan_wrong",
            title=f"❌ නොදන්නා QR කේතයක් ස්කෑන් කළා: {code_str}",
            description=f"පද්ධතියට අයත් නොවන අවලංගු QR කේතයක් ස්කෑන් කිරීමට උත්සාහ කළේය: {code_str}",
            details_dict={"code": code_str, "is_unknown": True}
        )

        return {
            "success": False,
            "status": "invalid",
            "message": msg,
            "scanned_count": current_index,
            "total": total_target,
            "current_step": current_step_num
        }

    # Case 3: Already scanned earlier
    if qr_obj["id"] in scanned_qr_ids:
        msg = f"ℹ️ ඔබ මෙම ඉලක්කය ({qr_obj['title']}) දැනටමත් ස්කෑන් කර අවසන්. කරුණාකර වත්මන් ඉලක්ක අංක {current_step_num} සොයන්න. (Already scanned! Look for active Checkpoint #{current_step_num})."
        conn.close()

        log_user_activity(
            user_id=user_id,
            action_type="qr_scan_repeat",
            title=f"ℹ️ දැනටමත් සොයාගත් ඉලක්කයක් නැවත ස්කෑන් කළා: {code_str}",
            description=f"තරඟකරු දැනටමත් සම්පූර්ණ කර ඇති {qr_obj['title']} නැවත ස්කෑන් කළේය.",
            details_dict={"code": code_str, "title": qr_obj["title"]}
        )

        return {
            "success": False,
            "status": "already_scanned",
            "message": msg,
            "scanned_count": current_index,
            "total": total_target,
            "current_step": current_step_num
        }

    # Sequential Validation: What is the current expected checkpoint ID?
    if current_index >= total_target:
        conn.close()
        return {
            "success": True,
            "status": "already_completed",
            "message": "ඔබ සියලු ඉලක්ක සම්පූර්ණ කර ඇත!",
            "scanned_count": total_target,
            "total": total_target
        }

    expected_qr_id = assigned_qr_ids[current_index]

    # Case 4: Skipping ahead in sequence (e.g. scanning #3 before #1)
    if qr_obj["id"] in assigned_qr_ids and qr_obj["id"] != expected_qr_id:
        target_step_for_this_qr = assigned_qr_ids.index(qr_obj["id"]) + 1
        msg = (
            f"🔒 මෙම ඉලක්කය තවමත් අගුළු දමා ඇත! (Stage Locked!) "
            f"මෙය {target_step_for_this_qr} වන ඉලක්කයයි. ඔබ පළමුව {current_step_num} වන ඉලක්කය සම්පූර්ණ කළ යුතුය. "
            f"(You must clear Checkpoint #{current_step_num} before unlocking this)."
        )
        with conn:
            conn.execute("""
                INSERT INTO scan_logs (user_id, scanned_code, result, message, scanned_at)
                VALUES (?, ?, 'out_of_order', ?, ?)
            """, (user_id, code_str, msg, now_str))
        conn.close()

        log_user_activity(
            user_id=user_id,
            action_type="qr_scan_out_of_order",
            title=f"🔒 අනුපිළිවෙලට නොවන ඉලක්කයක් ස්කෑන් කළා: {code_str}",
            description=f"තරඟකරු {current_step_num} වන ඉලක්කය සෙවීම වෙනුවට අනාගත {target_step_for_this_qr} වන ඉලක්කය ({qr_obj['title']}) ස්කෑන් කිරීමට උත්සාහ කළේය.",
            details_dict={"code": code_str, "title": qr_obj["title"], "current_step": current_step_num, "target_step": target_step_for_this_qr}
        )

        return {
            "success": False,
            "status": "out_of_order",
            "message": msg,
            "scanned_count": current_index,
            "total": total_target,
            "current_step": current_step_num
        }

    # Case 5: Valid system QR code, but NOT in this user's assigned 5 list
    if qr_obj["id"] not in assigned_qr_ids:
        msg = f"⚠️ වැරදියි! මෙම QR කේතය ඔබගේ ඉලක්ක ලැයිස්තුවට අයත් නොවේ. (Wrong QR! Not part of your 5 targets)."
        with conn:
            conn.execute("""
                INSERT INTO scan_logs (user_id, scanned_code, result, message, scanned_at)
                VALUES (?, ?, 'unassigned', ?, ?)
            """, (user_id, code_str, msg, now_str))
        conn.close()

        log_user_activity(
            user_id=user_id,
            action_type="qr_scan_wrong",
            title=f"⚠️ වැරදි QR කේතයක් ස්කෑන් කළා (තමාගේ ඉලක්කයක් නොවේ): {code_str}",
            description=f"තරඟකරු තමාගේ ඉලක්ක ලැයිස්තුවට අයත් නොවන වෙනත් QR කේතයක් ({qr_obj['title']}) ස්කෑන් කළේය.",
            details_dict={"code": code_str, "title": qr_obj["title"]}
        )

        return {
            "success": False,
            "status": "wrong",
            "message": msg,
            "scanned_count": current_index,
            "total": total_target,
            "current_step": current_step_num
        }

    # Case 6: SUCCESS! User scanned the exact current sequential target!
    scanned_qr_ids.append(qr_obj["id"])
    new_count = len(scanned_qr_ids)
    is_finished = (new_count >= total_target)
    now_str = get_now_sl_str()

    with conn:
        if is_finished:
            conn.execute("""
                UPDATE users
                SET scanned_qr_ids = ?,
                    status = 'completed',
                    completed_at = ?
                WHERE id = ?
            """, (json.dumps(scanned_qr_ids), now_str, user_id))
        else:
            conn.execute("""
                UPDATE users
                SET scanned_qr_ids = ?
                WHERE id = ?
            """, (json.dumps(scanned_qr_ids), user_id))

        log_msg = f"Sequential Checkpoint Cleared: #{current_step_num} - {qr_obj['title']} ({new_count}/{total_target})"
        conn.execute("""
            INSERT INTO scan_logs (user_id, scanned_code, result, message, scanned_at)
            VALUES (?, ?, 'valid', ?, ?)
        """, (user_id, code_str, log_msg, now_str))
    conn.close()

    # Determine next checkpoint object if not finished
    next_cp_obj = None
    if not is_finished:
        next_cp_id = assigned_qr_ids[new_count]
        next_cp_obj = get_qr_code_by_id(next_cp_id)

    if is_finished:
        log_user_activity(
            user_id=user_id,
            action_type="completed",
            title=f"🏆 Treasure Hunt තරඟය ජයග්‍රහණය කළා! (5/5 සම්පූර්ණයි)",
            description=f"අවසාන 5 වන ඉලක්කය ({qr_obj['title']}) සාර්ථකව ස්කෑන් කර සියලු ඉලක්ක අනුපිළිවෙලින් සම්පූර්ණ කළේය!",
            details_dict={"code": code_str, "scanned_count": new_count, "total": total_target}
        )

        return {
            "success": True,
            "status": "completed",
            "scanned_count": new_count,
            "total": total_target,
            "current_step": 5,
            "cleared_checkpoint": qr_obj,
            "message": f"🎉 සුභ පැතුම්! ඔබ 5 වන ඉලක්කය ({qr_obj['title']}) සාර්ථකව සොයාගෙන Treasure Hunt තරඟය ජයග්‍රහණය කළා! (Congratulations! You won the Treasure Hunt!)"
        }
    else:
        next_step_num = new_count + 1
        log_user_activity(
            user_id=user_id,
            action_type="qr_scan_success",
            title=f"🎯 {current_step_num} වන ඉලක්කය සම්පූර්ණ කළා: {qr_obj['title']} ({new_count}/{total_target})",
            description=f"තරඟකරු {current_step_num} වන ඉලක්කය සාර්ථකව සොයාගත් අතර, {next_step_num} වන රහස් ඉඟිය විවෘත විය. ප්‍රගතිය: {new_count}/{total_target}.",
            details_dict={"code": code_str, "cleared_title": qr_obj["title"], "scanned_count": new_count, "total": total_target, "next_step": next_step_num}
        )

        return {
            "success": True,
            "status": "valid",
            "scanned_count": new_count,
            "total": total_target,
            "current_step": next_step_num,
            "cleared_checkpoint": qr_obj,
            "next_checkpoint": {
                "id": next_cp_obj["id"],
                "hint": next_cp_obj["hint"],
                "step_num": next_step_num
            } if next_cp_obj else None,
            "message": f"✅ නියමයි! {current_step_num} වන ඉලක්කය ({qr_obj['title']}) සාර්ථකව සොයාගත්තා. ඊළඟ {next_step_num} වන රහස් ඉඟිය දැන් විවෘතයි! (Checkpoint #{current_step_num} verified! Clue #{next_step_num} unlocked!)"
        }


def get_user_detailed_profile(user_id: int) -> dict:
    """
    Returns full profile for Admin modal: user info, question-by-question breakdown,
    assigned QR codes with sequential scan status, and full chronological activity logs.
    """
    user = get_user_by_id(user_id)
    if not user:
        return None

    # Assigned questions breakdown
    assigned_questions = get_user_assigned_questions(user_id)
    try:
        user_answers = json.loads(user["quiz_answers"] or "{}")
    except Exception:
        user_answers = {}

    quiz_breakdown = []
    for idx, q in enumerate(assigned_questions, start=1):
        user_ans = user_answers.get(str(q["id"]), "")
        is_correct = (user_ans.strip().upper() == q["correct_option"].strip().upper())
        quiz_breakdown.append({
            "number": idx,
            "id": q["id"],
            "question": q["question"],
            "option_a": q["option_a"],
            "option_b": q["option_b"],
            "option_c": q["option_c"],
            "option_d": q["option_d"],
            "user_answer": user_ans,
            "correct_option": q["correct_option"],
            "is_correct": is_correct
        })

    # Assigned QR codes breakdown in sequential order
    assigned_qrs = get_user_assigned_qr_codes(user_id)
    try:
        scanned_ids = json.loads(user["scanned_qr_ids"] or "[]")
    except Exception:
        scanned_ids = []

    current_step_num = len(scanned_ids) + 1 if len(scanned_ids) < len(assigned_qrs) else len(assigned_qrs)

    qr_breakdown = []
    for idx, qr in enumerate(assigned_qrs, start=1):
        is_scanned = (qr["id"] in scanned_ids)
        is_active = (idx == current_step_num and not is_scanned)
        is_locked = (idx > current_step_num)
        qr_breakdown.append({
            "number": idx,
            "id": qr["id"],
            "code": qr["code"],
            "title": qr["title"],
            "hint": qr["hint"],
            "is_scanned": is_scanned,
            "is_active": is_active,
            "is_locked": is_locked
        })

    # Full activity logs
    activities = get_user_activities(user_id)

    return {
        "user": user,
        "quiz_breakdown": quiz_breakdown,
        "qr_breakdown": qr_breakdown,
        "activities": activities,
        "scanned_count": len(scanned_ids),
        "total_targets": len(assigned_qrs),
        "current_step": current_step_num
    }


# -------------------------------------------------------------
# Raffle Draw / Lucky Draw Functions (Selective Admin Control)
# -------------------------------------------------------------

def get_raffle_eligible_participants(limit: int = 150):
    """
    Retrieves participants who completed all 5 QR codes AND were explicitly approved/selected
    by Admin into `raffle_pool`, ordered by selection time, up to `limit` (default 150).
    """
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT u.id, u.username, u.id_number, u.whatsapp, u.age_category, u.status,
               u.completed_at, u.created_at, rp.added_at as raffle_selected_at
        FROM users u
        JOIN raffle_pool rp ON u.id = rp.user_id
        WHERE u.status = 'completed'
        ORDER BY rp.added_at ASC, u.completed_at ASC
        LIMIT ?
    """, (limit,))
    rows = cur.fetchall()
    conn.close()

    result = []
    for rank, r in enumerate(rows, start=1):
        d = dict(r)
        d["rank"] = rank
        result.append(d)
    return result


def add_user_to_raffle_pool(user_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT username, status FROM users WHERE id = ?", (user_id,))
    u = cur.fetchone()
    if not u:
        conn.close()
        return False, "තරඟකරු හමු නොවීය (Contestant not found)."
    if u["status"] != "completed":
        conn.close()
        return False, "තරඟකරු තවමත් QR කේත 5 සම්පූර්ණ කර නොමැත. (Must complete all 5 QR codes first)."

    with conn:
        conn.execute("INSERT OR IGNORE INTO raffle_pool (user_id) VALUES (?)", (user_id,))
    conn.close()

    log_user_activity(
        user_id=user_id,
        action_type="raffle_eligible",
        title="🎟️ වාසනා දිනුම් ඇදීමට තෝරා ගන්නා ලදී (Accepted for Raffle Draw)",
        description="Admin විසින් මෙම තරඟකරුව වාසනා දිනුම් ඇදීමේ (Raffle Draw) ලැයිස්තුවට අනුමත කරන ලදී."
    )
    return True, f"'{u['username']}' වාසනා දිනුම් ඇදීමට සාර්ථකව එක් කළා! (Added to Raffle Pool)"


def remove_user_from_raffle_pool(user_id: int):
    conn = get_db()
    with conn:
        conn.execute("DELETE FROM raffle_pool WHERE user_id = ?", (user_id,))
    conn.close()
    return True, "වාසනා දිනුම් ඇදීමෙන් ඉවත් කරන ලදී. (Removed from Raffle Pool)"


def add_all_completed_to_raffle_pool():
    conn = get_db()
    with conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT OR IGNORE INTO raffle_pool (user_id)
            SELECT id FROM users WHERE status = 'completed'
        """)
        added = cur.rowcount
    conn.close()
    return True, f"සම්පූර්ණ කළ සියලු තරඟකරුවන් ({added}) සාර්ථකව Raffle එකට එක් කළා!"


def clear_raffle_pool():
    conn = get_db()
    with conn:
        conn.execute("DELETE FROM raffle_pool")
    conn.close()
    return True, "Raffle ලැයිස්තුව හිස් කළා (Raffle Pool Cleared)."


def get_completed_contestants_summary():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT u.id, u.username, u.id_number, u.whatsapp, u.age_category, u.completed_at,
               CASE WHEN rp.user_id IS NOT NULL THEN 1 ELSE 0 END as in_raffle
        FROM users u
        LEFT JOIN raffle_pool rp ON u.id = rp.user_id
        WHERE u.status = 'completed'
        ORDER BY in_raffle DESC, u.completed_at ASC, u.id ASC
    """)
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_raffle_winner(user_id: int, prize_title: str = "Grand Prize"):
    conn = get_db()
    now_str = get_now_sl_str()
    with conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO raffle_winners (user_id, prize_title, draw_timestamp)
            VALUES (?, ?, ?)
        """, (user_id, prize_title, now_str))
        winner_id = cur.lastrowid
    conn.close()

    user = get_user_by_id(user_id)
    if user:
        log_user_activity(
            user_id=user_id,
            action_type="raffle_won",
            title=f"🎉 වාසනා දිනුම් ඇදීමෙන් ජයග්‍රහණය කළා! ({prize_title})",
            description=f"තරඟකරු 50 දෙනාගේ වාසනා දිනුම් ඇදීමේ ({prize_title}) ජයග්‍රාහකයා ලෙස තේරී පත් විය!",
            details_dict={"prize_title": prize_title, "draw_timestamp": now_str}
        )
    return winner_id


def get_raffle_winners():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT rw.id as raffle_id, rw.prize_title, rw.draw_timestamp,
               u.id as user_id, u.username, u.id_number, u.whatsapp, u.age_category, u.completed_at
        FROM raffle_winners rw
        JOIN users u ON rw.user_id = u.id
        ORDER BY rw.id DESC
    """)
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def clear_raffle_winners():
    conn = get_db()
    with conn:
        conn.execute("DELETE FROM raffle_winners")
    conn.close()


def seed_sample_raffle_participants(target_total: int = 150):
    """
    Populates sample completed contestants up to `target_total` (150)
    so the administrator can test and showcase the full 150-person
    raffle wheel immediately without waiting for 150 real players to finish.
    """
    sample_first_names = [
        "Kasun", "Nuwan", "Amila", "Chamari", "Dinesh", "Kavindu", "Sithara", "Buddhika",
        "Rashmi", "Pathum", "Sachini", "Tharindu", "Hiruni", "Malinda", "Nisansala",
        "Janith", "Dilani", "Pradeep", "Supun", "Chathurika", "Ravindu", "Imasha",
        "Sandeepa", "Oshada", "Piyumi", "Maduranga", "Senuri", "Gayan", "Anjali",
        "Danushka", "Sewwandi", "Isuru", "Upeksha", "Harsha", "Nadeesha", "Lakshan",
        "Shalika", "Vishwa", "Ishara", "Suresh", "Gayani", "Naveen", "Tharaka",
        "Ruwan", "Hasini", "Dinuka", "Yashodha", "Asanka", "Purnima", "Charith",
        "Sahan", "Kaveesha", "Ruwani", "Chathura", "Sanduni", "Lahiru", "Supuni",
        "Vindya", "Roshan", "Madusha", "Shehan", "Poornima", "Mahesh", "Hansika"
    ]
    sample_last_names = [
        "Perera", "Silva", "Fernando", "Jayasinghe", "Bandara", "Wickramasinghe",
        "Gunasekara", "Herath", "Dissanayake", "Senanayake", "Rajapaksha", "Fonseka",
        "Karunaratne", "Amarasinghe", "Abeysekara", "Alwis", "Kulathunga", "Weerasinghe",
        "Samarasinghe", "Rathnayake", "Wijesinghe", "Liyanage", "Ranasinghe", "Cooray"
    ]

    current_completed = get_raffle_eligible_participants(limit=target_total)
    needed = max(0, target_total - len(current_completed))
    if needed <= 0:
        return 0

    conn = get_db()
    now_str = get_now_sl_str()

    # Fetch 5 valid QRs and 5 Qs to mock assignment
    cur = conn.cursor()
    cur.execute("SELECT id FROM questions LIMIT 5")
    q_ids = [r["id"] for r in cur.fetchall()]
    cur.execute("SELECT id FROM qr_codes WHERE is_trap = 0 LIMIT 5")
    qr_ids = [r["id"] for r in cur.fetchall()]

    added = 0
    with conn:
        for i in range(needed):
            fname = sample_first_names[(i + len(current_completed)) % len(sample_first_names)]
            lname = sample_last_names[((i + len(current_completed)) * 3) % len(sample_last_names)]
            full_name = f"{fname} {lname}"
            id_num = f"200{random.randint(1, 4)}{random.randint(10000000, 99999999)}"
            phone = f"07{random.choice(['7', '1', '2', '5', '8'])}{random.randint(1000000, 9999999)}"
            age_cat = random.choice(["under_18", "18_plus"])

            cur.execute("""
                INSERT INTO users (
                    username, id_number, whatsapp, age_category, status,
                    assigned_question_ids, assigned_qr_ids, scanned_qr_ids,
                    quiz_score, completed_at, ip_address
                ) VALUES (?, ?, ?, ?, 'completed', ?, ?, ?, 5, ?, '127.0.0.1')
            """, (
                full_name, id_num, phone, age_cat,
                json.dumps(q_ids), json.dumps(qr_ids), json.dumps(qr_ids),
                now_str
            ))
            added += 1
            new_user_id = cur.lastrowid
            cur.execute("INSERT OR IGNORE INTO raffle_pool (user_id) VALUES (?)", (new_user_id,))
        
        # Also ensure up to target_total completed users are in raffle_pool
        cur.execute("""
            INSERT OR IGNORE INTO raffle_pool (user_id)
            SELECT id FROM users WHERE status = 'completed'
            LIMIT ?
        """, (target_total,))
    conn.close()
    return added


# -------------------------------------------------------------
# Backup & Restore (JSON Export & Import)
# -------------------------------------------------------------

def export_backup_data():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, code, title, hint, is_trap, created_at FROM qr_codes ORDER BY id ASC")
    qrs = [dict(r) for r in cur.fetchall()]
    
    cur.execute("SELECT id, question, option_a, option_b, option_c, option_d, correct_option, is_active FROM questions ORDER BY id ASC")
    questions = [dict(r) for r in cur.fetchall()]
    
    cur.execute("SELECT key, value FROM settings")
    settings = [dict(r) for r in cur.fetchall()]
    conn.close()
    
    return {
        "version": "1.0",
        "app": "Treasure Hunt",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "qr_codes": qrs,
        "questions": questions,
        "settings": settings
    }


def import_backup_data(payload: dict):
    conn = get_db()
    stats = {"qrs_imported": 0, "questions_imported": 0, "settings_imported": 0}
    with conn:
        # Import QR codes
        if "qr_codes" in payload and isinstance(payload["qr_codes"], list):
            for qr in payload["qr_codes"]:
                if qr.get("code") and qr.get("title"):
                    conn.execute("""
                        INSERT INTO qr_codes (code, title, hint, is_trap)
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(code) DO UPDATE SET
                            title = excluded.title,
                            hint = excluded.hint,
                            is_trap = excluded.is_trap
                    """, (
                        str(qr["code"]).strip().upper(),
                        str(qr["title"]).strip(),
                        str(qr.get("hint") or "").strip(),
                        int(qr.get("is_trap") or 0)
                    ))
                    stats["qrs_imported"] += 1

        # Import Questions
        if "questions" in payload and isinstance(payload["questions"], list):
            for q in payload["questions"]:
                if q.get("question") and q.get("correct_option"):
                    # Check if already exists to avoid exact duplicates
                    cur = conn.cursor()
                    cur.execute("SELECT id FROM questions WHERE question = ?", (str(q["question"]).strip(),))
                    existing = cur.fetchone()
                    if not existing:
                        conn.execute("""
                            INSERT INTO questions (question, option_a, option_b, option_c, option_d, correct_option, is_active)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (
                            str(q["question"]).strip(),
                            str(q.get("option_a") or "").strip(),
                            str(q.get("option_b") or "").strip(),
                            str(q.get("option_c") or "").strip(),
                            str(q.get("option_d") or "").strip(),
                            str(q.get("correct_option") or "A").strip().upper(),
                            int(q.get("is_active") if "is_active" in q else 1)
                        ))
                    stats["questions_imported"] += 1

        # Import Settings
        if "settings" in payload and isinstance(payload["settings"], list):
            for s in payload["settings"]:
                if s.get("key") and s.get("value"):
                    conn.execute("""
                        INSERT INTO settings (key, value) VALUES (?, ?)
                        ON CONFLICT(key) DO UPDATE SET value = excluded.value
                    """, (str(s["key"]), str(s["value"])))
                    stats["settings_imported"] += 1

    conn.close()
    return stats


