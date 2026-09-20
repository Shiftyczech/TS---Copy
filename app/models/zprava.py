from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Zprava:
    """tsd08 - Odeslaná/připravená zpráva"""
    cislo_obj: str = ""
    komu_jmeno: str = ""
    komu_mail: str = ""
    predmet: str = ""
    zprava: str = ""
    vytvoreno: Optional[datetime] = None
    odeslano: Optional[datetime] = None
    typ: str = ""  # Mail/SMS
