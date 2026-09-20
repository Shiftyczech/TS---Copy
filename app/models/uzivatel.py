from dataclasses import dataclass


@dataclass
class Uzivatel:
    """tsd01a - Uživatelé a práva"""
    kod: int = 0
    jmeno: str = ""
    heslo: str = ""
    pravo: int = 0
