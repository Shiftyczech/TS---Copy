from dataclasses import dataclass


@dataclass
class Psc:
    """tsd01b - PSČ"""
    psc: str = ""
    naz_posty: str = ""
