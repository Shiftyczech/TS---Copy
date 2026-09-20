import re

def format_phone_number(phone: str) -> str:
    """
    Formats phone numbers in a string by grouping digits into blocks of 3.
    Leaves other text as is. Looks for sequences of 9 or more digits (with optional + and spaces).
    """
    if not phone:
        return ""
        
    def format_match(text):
        stripped = text.replace(" ", "")
        is_plus = stripped.startswith("+")
        digits = stripped[1:] if is_plus else stripped
        
        chunks = []
        while len(digits) > 0:
            chunks.insert(0, digits[-3:])
            digits = digits[:-3]
            
        formatted = " ".join(chunks)
        if is_plus:
            formatted = "+" + formatted
        return formatted

    # Pattern matches optional '+', then at least 8 digits (with optional spaces), ending in a digit
    pattern = r'(\+?(?:\d[ \t]*){8,}\d)'
    
    parts = re.split(pattern, str(phone))
    result = ""
    for part in parts:
        if re.fullmatch(pattern, part):
            result += format_match(part)
        else:
            result += part
    return result.strip()


def get_effective_address(record: dict) -> dict:
    """
    Returns the effective address preferring delivery address (U_*) over billing address (Z_*).
    Falls back per field if a delivery field is empty.
    """
    if not record:
        return {
            "jmeno": "",
            "ulice": "",
            "psc": "",
            "posta": "",
            "has_delivery": False,
        }

    u_jmeno = str(record.get("U_JMENO", "") or "").strip()
    u_ulice = str(record.get("U_ULICE", "") or "").strip()
    u_psc = str(record.get("U_PSC", "") or "").strip()
    u_posta = str(record.get("U_POSTA", "") or "").strip()

    z_jmeno = str(record.get("Z_JMENO", "") or "").strip()
    z_ulice = str(record.get("Z_ULICE", "") or "").strip()
    z_psc = str(record.get("Z_PSC", "") or "").strip()
    z_posta = str(record.get("Z_POSTA", "") or "").strip()

    has_delivery = bool(u_jmeno or u_ulice or u_psc or u_posta)

    return {
        "jmeno": u_jmeno or z_jmeno,
        "ulice": u_ulice or z_ulice,
        "psc": u_psc or z_psc,
        "posta": u_posta or z_posta,
        "has_delivery": has_delivery,
    }
