from dataclasses import dataclass


@dataclass
class PolozkaObjednavky:
    """tsd06/tsd06a/tsd06b - Položka objednávky (sestava nebo díl)"""
    cislo_obj: str = ""
    kod: int = 0
    nazev: str = ""
    cena: float = 0.0
    mnozstvi: int = 0
    dopravne: float = 0.0
    final: bool = False
