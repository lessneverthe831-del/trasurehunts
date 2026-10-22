"""
Sri Lankan National Identity Card (NIC) Decoder and Validator
Supports both Old Format (9 digits + V/X) and New Format (12 digits)
Extracts: Birth Year, Birth Month, Birth Day, Gender, and validates against contestant's Date of Birth.
"""

from datetime import datetime, date

def decode_sri_lankan_nic(nic: str):
    """
    Decodes a Sri Lankan National Identity Card number into birth date and gender.
    Returns dictionary with details or None if invalid format.
    """
    if not nic:
        return None
    
    nic = nic.strip().upper()
    
    # 1. Format check
    if len(nic) == 10 and nic[:-1].isdigit() and nic[-1] in ['V', 'X']:
        # Old NIC: YYDDD####V
        year = 1900 + int(nic[:2])
        days = int(nic[2:5])
        format_type = "old"
    elif len(nic) == 12 and nic.isdigit():
        # New NIC: YYYYDDD#####
        year = int(nic[:4])
        days = int(nic[4:7])
        format_type = "new"
    else:
        return None

    # 2. Gender determination & day count normalization
    gender = "Female" if days > 500 else "Male"
    d_val = days - 500 if days > 500 else days

    # 3. Day range check (1 to 366)
    if d_val < 1 or d_val > 366:
        return None

    # 4. Standard Sri Lankan DRP 366-day calendar mapping (Feb is 29 days)
    month_days = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    m = 1
    d = d_val
    for idx, m_len in enumerate(month_days):
        if d <= m_len:
            m = idx + 1
            break
        d -= m_len

    dob_str = f"{year:04d}-{m:02d}-{d:02d}"

    return {
        "nic": nic,
        "format": format_type,
        "year": year,
        "month": m,
        "day": d,
        "gender": gender,
        "dob": dob_str,
        "day_of_year": d_val
    }


def validate_nic_with_dob(nic: str, dob: str):
    """
    Validates whether the given NIC matches the contestant's Date of Birth (YYYY-MM-DD).
    Returns (is_valid: bool, message: str, details: dict or None)
    """
    if not nic:
        return False, "හැඳුනුම්පත් අංකය ඇතුළත් කිරීම අනිවාර්ය වේ. (NIC is required).", None
    
    if not dob:
        return False, "උපන්දිනය තේරීම අනිවාර්ය වේ. (Date of Birth is required).", None

    details = decode_sri_lankan_nic(nic)
    if not details:
        return False, "වලංගු ශ්‍රී ලාංකික හැඳුනුම්පත් අංකයක් ඇතුල් කරන්න (ඉලක්කම් 9ක් සමග V/X හෝ නව ඉලක්කම් 12). (Invalid NIC format).", None

    try:
        parts = [int(p) for p in dob.strip().split("-")]
        if len(parts) != 3:
            return False, "වලංගු උපන්දිනයක් තෝරන්න (YYYY-MM-DD).", None
        u_y, u_m, u_d = parts[0], parts[1], parts[2]
    except Exception:
        return False, "වලංගු උපන්දිනයක් තෝරන්න. (Invalid Date of Birth).", None

    nic_dob = details["dob"]
    user_dob = f"{u_y:04d}-{u_m:02d}-{u_d:02d}"

    # Exact Match
    if nic_dob == user_dob:
        return True, f"හැඳුනුම්පත සහ උපන්දිනය තහවුරුයි ({nic_dob} • {details['gender']})", details

    # Non-leap year day 60 exception (Feb 28 vs Feb 29)
    if details["day_of_year"] == 60 and u_y == details["year"] and u_m == 2 and u_d in [28, 29]:
        return True, f"හැඳුනුම්පත සහ උපන්දිනය තහවුරුයි ({user_dob} • {details['gender']})", details

    return False, f"හැඳුනුම්පත් අංකයෙන් ලැබෙන උපන්දිනය ({nic_dob}) ඔබ ඇතුළත් කළ උපන්දිනය ({user_dob}) හා නොගැලපේ! කරුණාකර සැබෑ හැඳුනුම්පත සහ උපන්දිනය ඇතුල් කරන්න.", details


def get_age_category_from_dob(dob: str) -> str:
    """
    Calculates whether the person is 'under_18' or '18_plus' from their DOB.
    """
    try:
        b_date = datetime.strptime(dob.strip(), "%Y-%m-%d").date()
        today = date.today()
        age = today.year - b_date.year - ((today.month, today.day) < (b_date.month, b_date.day))
        return "18_plus" if age >= 18 else "under_18"
    except Exception:
        return "18_plus"

# Convenient aliases
decode_nic = decode_sri_lankan_nic
validate_nic_and_dob = validate_nic_with_dob

