import re

def format_phone_number(phone: str) -> str:
    """
    Formats phone numbers in a string by grouping digits into blocks of 3.
    Leaves other text as is. Supports prefixes (+420, 00420) and cleans hyphens.
    """
    if not phone:
        return ""
        
    def format_single(text: str) -> str:
        s = text.strip()
        is_plus = s.startswith("+")
        raw = s[1:] if is_plus else s
        digits = "".join(c for c in raw if c.isdigit())
        if not digits:
            return "+" if is_plus else ""

        parts = []
        if is_plus:
            prefix_len = min(3, len(digits))
            parts.append("+" + digits[:prefix_len])
            rest = digits[prefix_len:]
        elif digits.startswith("00") and len(digits) >= 5:
            parts.append("00" + digits[2:5])
            rest = digits[5:]
        else:
            rest = digits

        for i in range(0, len(rest), 3):
            parts.append(rest[i:i + 3])

        return " ".join(parts)

    pattern = r'(\+?(?:[0-9][ \t\-]*){8,}[0-9])'
    parts = re.split(pattern, str(phone))
    res = []
    for part in parts:
        if re.fullmatch(pattern, part):
            res.append(format_single(part))
        else:
            res.append(part)
    return "".join(res).strip()


def get_effective_address(record: dict, prefer_delivery: bool = True) -> dict:
    """
    Returns the effective address.
    If prefer_delivery=True (default), prefers delivery address (U_*) over billing address (Z_*).
    If prefer_delivery=False, prefers billing address (Z_*) over delivery address (U_*).
    Falls back per field if the preferred field is empty.
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

    if prefer_delivery:
        return {
            "jmeno": u_jmeno or z_jmeno,
            "ulice": u_ulice or z_ulice,
            "psc": u_psc or z_psc,
            "posta": u_posta or z_posta,
            "has_delivery": has_delivery,
        }
    else:
        return {
            "jmeno": z_jmeno or u_jmeno,
            "ulice": z_ulice or u_ulice,
            "psc": z_psc or u_psc,
            "posta": z_posta or u_posta,
            "has_delivery": has_delivery,
        }


def get_free_order_numbers(ctx, max_lookback: int = 500) -> tuple[int, list[int]]:
    """
    Finds existing order numbers across active (tsd04) and archive (tsd06) orders,
    detects gaps (freed / cancelled order numbers), and returns (next_recommended_num, list_of_gaps).
    """
    all_nums = set()
    active_nums = set()

    for table in ("tsd04", "tsd06"):
        try:
            if hasattr(ctx.db, "get_column_values"):
                vals = ctx.db.get_column_values(table, "CISLO_OBJ")
            else:
                rows = ctx.db.read_all(table)
                vals = [r.get("CISLO_OBJ") for r in rows]
            for raw in vals:
                if raw is not None and str(raw).strip():
                    try:
                        val = int(float(str(raw).strip()))
                        all_nums.add(val)
                        if table == "tsd04":
                            active_nums.add(val)
                    except (ValueError, TypeError):
                        pass
        except Exception:
            pass

    if not all_nums:
        return 1, []

    min_all = min(all_nums)
    max_num = max(all_nums)

    if active_nums:
        # Look from active orders start (with small buffer to catch lowest deleted active order)
        start_num = max(min_all, min(active_nums) - 20)
    else:
        start_num = max(min_all, max_num - max_lookback)

    gaps = [n for n in range(start_num, max_num + 1) if n not in all_nums]
    next_num = gaps[0] if gaps else (max_num + 1)
    return next_num, gaps
