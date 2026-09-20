from dataclasses import dataclass


@dataclass
class SablonaZpravy:
    """tsd07 - Šablona textu zprávy"""
    typ: str = ""
    text_mail: str = ""
    text_sms: str = ""
    predmet_e: str = ""
    predmet_s: str = ""
