from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass
class Objednavka:
    """tsd04/tsd04a/tsd04b - Objednávka + zákazník"""
    cislo_obj: str = ""
    status: int = 0
    # Zákazník
    z_jmeno: str = ""
    z_ulice: str = ""
    z_psc: str = ""
    z_posta: str = ""
    # Místo určení
    m_jmeno: str = ""
    m_ulice: str = ""
    m_psc: str = ""
    m_posta: str = ""
    # Kontakt
    telefon: str = ""
    mobil: str = ""
    e_mail: str = ""
    # Parametry
    vl_odvoz: bool = False
    zprava_typ: int = 1     # 1=Poštou, 2=SMS, 3=e-Mail, 4=telefonicky
    uhrada: int = 1         # 1=hotovost, 2=úvěr
    # Data
    datum_prij: Optional[date] = None
    dodat_po: Optional[date] = None
    dodaci_lhuta: str = ""
    datum_vyzvy: Optional[date] = None
    vyzva_den: Optional[date] = None
    datum_vyriz: Optional[date] = None
    # Poznámky (memo)
    pozn_intern: str = ""
    pozn_zakaz: str = ""
    # Trasa
    trasa_datum: Optional[date] = None
    trasa_smer: str = ""
    zmena: bool = False
    # Plánky základů
    plan_central: bool = False
    plan_optimal: bool = False
    plan_maximal: bool = False
    plan_satelit2: bool = False
    plan_satelit25: bool = False
    # Finanční
    cena_sestavy: float = 0.0
    cena_doplnky: float = 0.0
    cena_dopravne: float = 0.0
    cena_celkem: float = 0.0
