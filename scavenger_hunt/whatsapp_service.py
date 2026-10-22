"""
WhatsApp Service for Scavenger Hunt
Handles phone normalization, WhatsApp message dispatching across multiple gateway providers,
and OTP lifecycle management.
"""

import re
import json
import random
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta
import database


def normalize_phone(phone_str: str) -> str:
    """
    Normalizes phone numbers to standard 10-digit local format: 07XXXXXXXX.
    Handles +94, 94, spaces, dashes, parentheses.
    """
    if not phone_str:
        return ""
    digits = re.sub(r"\D", "", str(phone_str).strip())
    if digits.startswith("94") and len(digits) == 11:
        digits = "0" + digits[2:]
    elif digits.startswith("0") and len(digits) == 10:
        pass
    elif len(digits) == 9 and not digits.startswith("0"):
        digits = "0" + digits
    return digits


def to_international_phone(phone_str: str, with_plus: bool = True) -> str:
    """
    Converts phone number to international format: +947XXXXXXXX or 947XXXXXXXX.
    """
    norm = normalize_phone(phone_str)
    if norm.startswith("0") and len(norm) == 10:
        int_num = "94" + norm[1:]
    else:
        int_num = norm
    return ("+" + int_num) if with_plus else int_num


def normalize_id(id_str: str) -> str:
    """
    Normalizes NIC / University Student ID by stripping whitespace and converting to uppercase.
    e.g. ' 200115999183v ' -> '200115999183V'
    e.g. ' se/2021/045 ' -> 'SE/2021/045'
    """
    if not id_str:
        return ""
    return re.sub(r"\s+", "", str(id_str).strip()).upper()


def send_whatsapp_message(to_number: str, text: str) -> dict:
    """
    Sends WhatsApp message via the configured gateway in settings.
    Supported gateways:
      - 'simulation': Demo / local test mode (instant, no setup needed)
      - 'cloud_api': Meta WhatsApp Business Cloud API
      - 'twilio': Twilio WhatsApp API
      - 'ultramsg': UltraMsg WhatsApp Gateway
      - 'custom_url': Custom HTTP GET/POST Webhook
    """
    gateway_type = database.get_setting("whatsapp_gateway_type", "simulation").lower()
    norm_phone = normalize_phone(to_number)
    int_phone_plus = to_international_phone(norm_phone, with_plus=True)
    int_phone_raw = to_international_phone(norm_phone, with_plus=False)

    if gateway_type == "simulation" or not gateway_type:
        print(f"[WHATSAPP SIMULATION] To: {int_phone_plus} | Message: {text}")
        return {
            "success": True,
            "mode": "simulation",
            "message": "Message logged in simulation mode."
        }

    try:
        if gateway_type == "cloud_api":
            phone_number_id = database.get_setting("whatsapp_phone_number_id", "")
            token = database.get_setting("whatsapp_api_token", "")
            if not phone_number_id or not token:
                return {
                    "success": False,
                    "mode": "cloud_api",
                    "message": "Meta Cloud API configuration missing (phone_number_id or api_token)."
                }

            url = f"https://graph.facebook.com/v19.0/{phone_number_id}/messages"
            
            # Check if template mode is configured (e.g. 'hello_world' or custom)
            template_name = database.get_setting("whatsapp_template_name", "").strip()

            def _build_meta_payload(as_template=False, tmpl="hello_world"):
                if as_template:
                    if tmpl == "hello_world":
                        return {
                            "messaging_product": "whatsapp",
                            "recipient_type": "individual",
                            "to": int_phone_raw,
                            "type": "template",
                            "template": {
                                "name": "hello_world",
                                "language": {"code": "en_US"}
                            }
                        }
                    else:
                        return {
                            "messaging_product": "whatsapp",
                            "recipient_type": "individual",
                            "to": int_phone_raw,
                            "type": "template",
                            "template": {
                                "name": tmpl,
                                "language": {"code": "en_US"},
                                "components": [
                                    {
                                        "type": "body",
                                        "parameters": [{"type": "text", "text": text}]
                                    }
                                ]
                            }
                        }
                else:
                    return {
                        "messaging_product": "whatsapp",
                        "recipient_type": "individual",
                        "to": int_phone_raw,
                        "type": "text",
                        "text": {"body": text}
                    }

            # In test mode or when template is set, start with template if configured, otherwise text
            use_template = bool(template_name)
            tmpl_to_use = template_name or "hello_world"
            payload_dict = _build_meta_payload(as_template=use_template, tmpl=tmpl_to_use)

            req = urllib.request.Request(
                url,
                data=json.dumps(payload_dict).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                },
                method="POST"
            )

            try:
                with urllib.request.urlopen(req, timeout=10) as resp:
                    resp_data = resp.read().decode("utf-8")
                    return {"success": True, "mode": "cloud_api", "response": resp_data}
            except urllib.error.HTTPError as he:
                err_text = he.read().decode("utf-8", errors="ignore")
                # Fallback: if text failed because outside 24h window (code 131047), retry with hello_world template
                if not use_template and ("131047" in err_text or "template" in err_text.lower()):
                    try:
                        fallback_payload = _build_meta_payload(as_template=True, tmpl="hello_world")
                        fallback_req = urllib.request.Request(
                            url,
                            data=json.dumps(fallback_payload).encode("utf-8"),
                            headers={
                                "Authorization": f"Bearer {token}",
                                "Content-Type": "application/json"
                            },
                            method="POST"
                        )
                        with urllib.request.urlopen(fallback_req, timeout=10) as fb_resp:
                            fb_data = fb_resp.read().decode("utf-8")
                            return {"success": True, "mode": "cloud_api", "response": fb_data, "note": "Delivered via Meta hello_world template"}
                    except Exception:
                        pass

                # Parse detailed Meta error JSON
                try:
                    err_json = json.loads(err_text)
                    err_info = err_json.get("error", {})
                    msg = err_info.get("message", err_text)
                    code = err_info.get("code", "")
                    details = err_info.get("error_data", {}).get("details", "")
                    return {
                        "success": False,
                        "mode": "cloud_api",
                        "error_code": code,
                        "error": msg,
                        "message": f"Meta Error ({code}): {msg} {details}".strip()
                    }
                except Exception:
                    return {"success": False, "mode": "cloud_api", "error": err_text, "message": err_text}

        elif gateway_type == "twilio":
            account_sid = database.get_setting("whatsapp_account_sid", "")
            auth_token = database.get_setting("whatsapp_api_token", "")
            from_number = database.get_setting("whatsapp_sender_number", "")
            if not account_sid or not auth_token or not from_number:
                return {
                    "success": False,
                    "mode": "twilio",
                    "message": "Twilio configuration missing (account_sid, token, or sender number)."
                }

            url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
            sender = from_number if from_number.startswith("whatsapp:") else f"whatsapp:{from_number}"
            receiver = f"whatsapp:{int_phone_plus}"
            data = urllib.parse.urlencode({
                "From": sender,
                "To": receiver,
                "Body": text
            }).encode("utf-8")

            import base64
            auth_str = base64.b64encode(f"{account_sid}:{auth_token}".encode("utf-8")).decode("utf-8")

            req = urllib.request.Request(
                url,
                data=data,
                headers={"Authorization": f"Basic {auth_str}"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                resp_data = resp.read().decode("utf-8")
                return {"success": True, "mode": "twilio", "response": resp_data}

        elif gateway_type == "ultramsg":
            instance_id = database.get_setting("whatsapp_instance_id", "")
            token = database.get_setting("whatsapp_api_token", "")
            if not instance_id or not token:
                return {
                    "success": False,
                    "mode": "ultramsg",
                    "message": "UltraMsg configuration missing (instance_id or token)."
                }

            url = f"https://api.ultramsg.com/{instance_id}/messages/chat"
            data = urllib.parse.urlencode({
                "token": token,
                "to": int_phone_plus,
                "body": text
            }).encode("utf-8")

            req = urllib.request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded", "User-Agent": "TreasureHuntBot/1.0"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                resp_data = resp.read().decode("utf-8")
                return {"success": True, "mode": "ultramsg", "response": resp_data}

        elif gateway_type in ["green_api", "greenapi"]:
            id_instance = database.get_setting("greenapi_id_instance", "").strip() or database.get_setting("whatsapp_phone_number_id", "").strip() or database.get_setting("whatsapp_instance_id", "").strip()
            api_token = database.get_setting("greenapi_token", "").strip() or database.get_setting("whatsapp_api_token", "").strip()
            host_url = database.get_setting("greenapi_host", "").strip() or database.get_setting("whatsapp_custom_url", "").strip() or "https://api.green-api.com"
            if not host_url.startswith("http"):
                host_url = f"https://{host_url}"
            host_url = host_url.rstrip("/")

            if not id_instance or not api_token:
                return {
                    "success": False,
                    "mode": "green_api",
                    "message": "Green-API configuration missing: idInstance or apiTokenInstance."
                }

            # GreenAPI destination format: 947XXXXXXXX@c.us
            chat_id = f"{int_phone_raw}@c.us"
            url = f"{host_url}/waInstance{id_instance}/sendMessage/{api_token}"

            payload = json.dumps({
                "chatId": chat_id,
                "message": text
            }).encode("utf-8")

            req = urllib.request.Request(
                url,
                data=payload,
                headers={"Content-Type": "application/json", "User-Agent": "TreasureHuntBot/1.0"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=12) as resp:
                resp_data = resp.read().decode("utf-8")
                return {"success": True, "mode": "green_api", "response": resp_data}

        elif gateway_type in ["notifylk", "notify_lk"]:
            user_id = database.get_setting("notifylk_user_id", "").strip() or database.get_setting("whatsapp_account_sid", "").strip() or database.get_setting("whatsapp_phone_number_id", "").strip()
            api_key = database.get_setting("notifylk_api_key", "").strip() or database.get_setting("whatsapp_api_token", "").strip()
            sender_id = database.get_setting("notifylk_sender_id", "").strip() or "NotifyDEMO"

            if not user_id or not api_key:
                return {
                    "success": False,
                    "mode": "notifylk",
                    "message": "Notify.lk configuration missing: User ID or API Key."
                }

            params = urllib.parse.urlencode({
                "user_id": user_id,
                "api_key": api_key,
                "sender_id": sender_id,
                "to": int_phone_raw,
                "message": text
            })
            url = f"https://app.notify.lk/api/v1/send?{params}"
            req = urllib.request.Request(url, headers={"User-Agent": "TreasureHuntBot/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                resp_data = resp.read().decode("utf-8")
                return {"success": True, "mode": "notifylk", "response": resp_data}

        elif gateway_type == "custom_url":
            custom_url = database.get_setting("whatsapp_custom_url", "")
            if not custom_url:
                return {
                    "success": False,
                    "mode": "custom_url",
                    "message": "Custom Webhook URL missing."
                }

            # Replace placeholders {phone}, {text}
            target_url = custom_url.replace("{phone}", urllib.parse.quote(int_phone_plus))
            target_url = target_url.replace("{text}", urllib.parse.quote(text))
            target_url = target_url.replace("{raw_phone}", urllib.parse.quote(norm_phone))

            req = urllib.request.Request(target_url, headers={"User-Agent": "TreasureHunt-WhatsApp-Bot"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                resp_data = resp.read().decode("utf-8")
                return {"success": True, "mode": "custom_url", "response": resp_data}

        else:
            return {
                "success": False,
                "mode": gateway_type,
                "message": f"Unknown gateway type: {gateway_type}"
            }

    except urllib.error.HTTPError as he:
        err_body = he.read().decode("utf-8", errors="ignore")
        print(f"[WHATSAPP HTTP ERROR] Status {he.code}: {err_body}")
        try:
            err_json = json.loads(err_body)
            err_msg = ""
            err_code = str(he.code)
            if isinstance(err_json, dict):
                if isinstance(err_json.get("error"), dict):
                    err_msg = err_json["error"].get("message")
                    err_code = err_json["error"].get("code", str(he.code))
                elif isinstance(err_json.get("error"), str):
                    err_msg = err_json.get("error")
                if not err_msg:
                    err_msg = err_json.get("message") or err_json.get("description") or err_body
                if "statusCode" in err_json:
                    err_code = str(err_json.get("statusCode"))
            else:
                err_msg = str(err_json)

            return {
                "success": False,
                "mode": gateway_type,
                "error": err_msg,
                "message": f"API Error ({err_code}): {err_msg}"
            }
        except Exception:
            return {
                "success": False,
                "mode": gateway_type,
                "error": err_body,
                "message": f"HTTP {he.code}: {err_body}"
            }
    except Exception as e:
        print(f"[WHATSAPP ERROR] Failed sending to {int_phone_plus}: {e}")
        return {
            "success": False,
            "mode": gateway_type,
            "error": str(e),
            "message": f"WhatsApp API delivery failed: {str(e)}"
        }


def generate_and_send_otp(whatsapp: str, id_number: str = "") -> dict:
    """
    Generates a 6-digit numeric OTP, saves to otp_verifications, and dispatches via WhatsApp.
    """
    norm_phone = normalize_phone(whatsapp)
    if not norm_phone or len(norm_phone) < 9:
        return {
            "success": False,
            "message": "වලංගු WhatsApp දුරකථන අංකයක් ඇතුල් කරන්න. (Please enter a valid phone number)."
        }

    norm_id = normalize_id(id_number)

    # 1. Check for duplicates in existing registered users
    is_dup, dup_field, dup_msg = database.check_duplicate_user(norm_id, norm_phone)
    if is_dup:
        return {
            "success": False,
            "is_duplicate": True,
            "duplicate_field": dup_field,
            "message": dup_msg
        }

    # 2. Generate 6-digit OTP
    otp_code = f"{random.randint(100000, 999999)}"

    # 3. Store OTP in database (Valid for 10 minutes in Sri Lanka Standard Time)
    now = datetime.now(database.SRI_LANKA_TZ)
    expires = now + timedelta(minutes=10)
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")
    expires_str = expires.strftime("%Y-%m-%d %H:%M:%S")

    conn = database.get_db()
    with conn:
        # Invalidate any previous pending OTPs for this phone number
        conn.execute("UPDATE otp_verifications SET status = 'expired' WHERE whatsapp = ? AND status = 'pending'", (norm_phone,))
        conn.execute("""
            INSERT INTO otp_verifications (whatsapp, id_number, otp_code, status, attempts, created_at, expires_at)
            VALUES (?, ?, ?, 'pending', 0, ?, ?)
        """, (norm_phone, norm_id, otp_code, now_str, expires_str))
    conn.close()

    # 4. Construct message
    template = database.get_setting(
        "whatsapp_msg_template",
        "ඔබගේ Treasure Hunt ලියාපදිංචි OTP කේතය: {otp} වේ. මෙය කිසිවෙකු සමඟ බෙදා නොගන්න. (Your Scavenger Hunt registration OTP is: {otp})."
    )
    msg_text = template.replace("{otp}", otp_code)

    # 5. Dispatch message
    send_result = send_whatsapp_message(norm_phone, msg_text)

    gateway_type = database.get_setting("whatsapp_gateway_type", "simulation").lower()
    is_simulation = gateway_type == "simulation" or not send_result.get("success", False)

    return {
        "success": True,
        "phone_formatted": to_international_phone(norm_phone, with_plus=True),
        "phone_normalized": norm_phone,
        "expires_in_seconds": 600,
        "gateway_mode": gateway_type,
        "is_simulation": is_simulation,
        # In simulation mode, expose OTP code so user can test without real API keys
        "simulated_otp": otp_code if is_simulation else None,
        "message": "WhatsApp අංකයට සාර්ථකව OTP කේතය යවන ලදී. (OTP sent to WhatsApp)."
    }


def verify_otp_code(whatsapp: str, entered_otp: str) -> dict:
    """
    Verifies the user-entered OTP against the database record.
    """
    norm_phone = normalize_phone(whatsapp)
    clean_otp = str(entered_otp or "").strip()

    if not norm_phone or not clean_otp:
        return {"success": False, "message": "කරුණාකර දුරකථන අංකය සහ OTP කේතය ඇතුල් කරන්න."}

    conn = database.get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM otp_verifications
        WHERE whatsapp = ? AND status = 'pending'
        ORDER BY id DESC LIMIT 1
    """, (norm_phone,))
    row = cur.fetchone()

    if not row:
        conn.close()
        return {
            "success": False,
            "message": "වලංගු OTP කේතයක් හමු නොවීය. කරුණාකර නැවත OTP කේතයක් ලබාගන්න. (No pending OTP found. Please request a new OTP)."
        }

    otp_rec = dict(row)
    now_str = datetime.now(database.SRI_LANKA_TZ).strftime("%Y-%m-%d %H:%M:%S")

    # Check expiry
    if otp_rec["expires_at"] < now_str:
        with conn:
            conn.execute("UPDATE otp_verifications SET status = 'expired' WHERE id = ?", (otp_rec["id"],))
        conn.close()
        return {
            "success": False,
            "message": "OTP කේතයේ වලංගු කාලය (10 min) ඉකුත් වී ඇත. කරුණාකර නැවත කේතයක් ලබාගන්න. (OTP has expired)."
        }

    # Check attempts (max 5)
    if otp_rec["attempts"] >= 5:
        with conn:
            conn.execute("UPDATE otp_verifications SET status = 'blocked' WHERE id = ?", (otp_rec["id"],))
        conn.close()
        return {
            "success": False,
            "message": "OTP උත්සාහයන් සීමාව ඉක්මවා ඇත. කරුණාකර අලුත් OTP එකක් ඉල්ලන්න. (Too many attempts. Request a new OTP)."
        }

    # Verify code
    if otp_rec["otp_code"] != clean_otp:
        with conn:
            conn.execute("UPDATE otp_verifications SET attempts = attempts + 1 WHERE id = ?", (otp_rec["id"],))
        conn.close()
        return {
            "success": False,
            "message": "ඇතුල් කළ OTP කේතය වැරදියි. කරුණාකර නැවත පරීක්ෂා කරන්න. (Incorrect OTP code)."
        }

    # Success: Mark as verified
    with conn:
        conn.execute("UPDATE otp_verifications SET status = 'verified' WHERE id = ?", (otp_rec["id"],))
    conn.close()

    return {
        "success": True,
        "message": "WhatsApp අංකය සාර්ථකව තහවුරු විය! (WhatsApp verified successfully)."
    }
