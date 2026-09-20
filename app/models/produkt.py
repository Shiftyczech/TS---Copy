from dataclasses import dataclass


@dataclass
class Produkt:
    """tsd02/tsd02a - Základní díly a doplňky"""
    kod: int = 0
    nazev: str = ""
    cena: float = 0.0
    symbol: str = ""
    pozice: str = ""
    typ_zaklad: str = ""
    mnozstvi: int = 0
    dopravne: float = 0.0
