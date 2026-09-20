from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Dodavatel:
    """tsd00 - Firma / dodavatel"""
    ico: str = ""
    dic: str = ""
    nazev1: str = ""
    nazev2: str = ""
    ulice: str = ""
    psc: str = ""
    obec: str = ""
    telefon: str = ""
    fax: str = ""
    mail: str = ""
    logo: str = ""
    postserver: str = ""
    odesilatel: str = ""
    dopravne: float = 0.0
    tisk: int = 1          # 1=výchozí, 2=zvolit, 3=netisknout
    pripojeni: int = 3     # 1=žádné, 2=vytáčené, 3=pevné
    www: str = ""
    dodat_po: int = 5
    zamena: bool = True
