from dataclasses import dataclass


@dataclass
class TypSkleniku:
    """tsd03 - Skleníková sestava (master)"""
    kod: int = 0
    nazev: str = ""
    cena: float = 0.0
    nazev_img: str = ""  # CENTRAL/OPTIMAL/MAXIMAL/SATELIT...


@dataclass
class DilSestavy:
    """tsd03a - Díl patřící do sestavy (detail)"""
    kod_sestavy: int = 0
    kod: int = 0
    nazev: str = ""
    cena: float = 0.0
    mnozstvi: int = 0
