from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass
class Rozvoz:
    """tsd05/tsd05a/tsd05b - Rozvozní plán / trasa"""
    cislo: int = 0
    datum: Optional[date] = None
    smer: str = ""
    status: int = 0
    pocet_obj: int = 0
