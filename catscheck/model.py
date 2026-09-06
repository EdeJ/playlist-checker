"""Gedeeld model en normalisatie voor de Cats speellijst-checker."""

from dataclasses import dataclass
from datetime import date, time
from enum import IntEnum


class ParseFout(Exception):
    """Een bron heeft niet de structuur die we verwachtten.

    Wordt bewust gegooid in plaats van doorgaan met een gok: een stille
    misparse levert een rapport op dat er goed uitziet en niet klopt.
    """


# De weekdagafkortingen die in de bronnen voorkomen; beide sheets gebruiken
# meerdere schrijfwijzen voor dezelfde dag.
WEEKDAGEN = {
    "ma": 0, "di": 1, "wo": 2, "woe": 2, "do": 3,
    "vr": 4, "vrij": 4, "za": 5, "zo": 6,
}

WEEKDAG_NAMEN = ("ma", "di", "wo", "do", "vr", "za", "zo")

# De vier spelers die de Reed 2-stoel delen. Elke andere naam in die kolom
# is een fout of een verschoven kolom.
REED2_NAMEN = frozenset({"emiel", "christof", "coen", "michiel"})

# Voorstellingen met publiek.
SPEEL_TYPES = frozenset({"TO", "PREM", "REG", "VP", "S-OPT"})

# Werkdagen zonder publiek waar wel iemand moet zijn.
WERK_TYPES = frozenset({"MON", "BESL"})

# Dagen waarop niemand van reed 2 hoeft te spelen, inclusief de reisdag
# waarop de productie naar een ander theater verhuist.
NEGEER_TYPES = frozenset({"BOUW", "VRIJ", "OVERSTA DAG"})

# Typecodes die per bron anders geschreven worden. Sleutel is de
# genormaliseerde (hoofdletters, getrimde) vorm. De reed 2-sheet schrijft de
# superoptie eenmalig voluit; de orkestlijst gebruikt altijd de afkorting.
# Zonder deze alias viel die voorstelling als "onbekend type" buiten de
# controle in plaats van vergeleken te worden.
TYPE_ALIAS = {
    "S-OPTIE": "S-OPT",
}

# Plaatsnamen die per bron anders geschreven worden. Sleutel is de
# genormaliseerde (lowercase, getrimde) vorm.
PLAATS_ALIAS = {
    # De orkestlijst schrijft de stad en het theater in één cel ("Amterdam
    # DLM", met typefout). De reed 2-sheet schrijft alleen de stad
    # ("AMSTERDAM") en noemt het theater apart in de Theater-kolom. Zonder
    # deze alias normaliseerde de orkestlijst-waarde naar iets dat nooit
    # gelijk kon zijn aan wat de reed 2-sheet noteert, en werd elke
    # DeLaMar-dag ten onrechte als "plaats verschilt" gemeld.
    "amterdam dlm": "AMSTERDAM",
    "amsterdam dlm": "AMSTERDAM",
}

# Markeringen die in de sheets "leeg" betekenen.
_LEEG = {"", "(leeg)", "leeg", "-", "?"}


def normaliseer_naam(ruw):
    """Maak een naam vergelijkbaar: getrimd en in kleine letters, of None."""
    if ruw is None:
        return None
    schoon = " ".join(str(ruw).split()).lower()
    if schoon in _LEEG:
        return None
    return schoon


def normaliseer_plaats(ruw):
    """Maak een plaatsnaam vergelijkbaar: hoofdletters, aliassen opgelost."""
    if ruw is None:
        return None
    schoon = " ".join(str(ruw).split()).lower()
    if schoon in _LEEG:
        return None
    return PLAATS_ALIAS.get(schoon, schoon.upper())


def normaliseer_type(ruw):
    """Maak een typecode vergelijkbaar: hoofdletters, aliassen opgelost.

    Een onbekende code blijft staan; vergelijk.py meldt hem dan als
    onbekend type. Raden zou een voorstelling stil verkeerd indelen.
    """
    if ruw is None:
        return None
    schoon = " ".join(str(ruw).split()).upper()
    if schoon.lower() in _LEEG:
        return None
    return TYPE_ALIAS.get(schoon, schoon)


def normaliseer_tijd(ruw):
    """Maak een aanvangstijd vergelijkbaar als "HH:MM", of None."""
    if ruw is None:
        return None
    schoon = str(ruw).strip().replace(".", ":")
    if schoon in _LEEG:
        return None
    if ":" not in schoon:
        raise ParseFout(f"onbegrijpelijke tijd: {ruw!r}")
    uur, _, minuut = schoon.partition(":")
    try:
        u, m = int(uur), int(minuut)
    except ValueError:
        raise ParseFout(f"onbegrijpelijke tijd: {ruw!r}") from None
    if not (0 <= u <= 23 and 0 <= m <= 59):
        raise ParseFout(f"tijd buiten bereik: {ruw!r}")
    return f"{u:02d}:{m:02d}"


@dataclass(frozen=True)
class Voorstelling:
    """Eén voorstelling of werkdag, zoals één bron hem beschrijft."""

    datum: date
    tijd: str | None          # "20:15", of None bij dagen zonder aanvangstijd
    type: str | None          # TO, PREM, REG, VP, S-OPT, MON, BESL, BOUW, VRIJ, OVERSTA DAG
    plaats: str | None        # genormaliseerd, hoofdletters
    theater: str | None       # de orkestlijst noemt geen theater
    reed2: str | None         # genormaliseerde naam, of None
    bron: str                 # "orkest" | "reed2" | "website"
    herkomst: str             # waar in de bron, zodat een melding vindbaar is


@dataclass(frozen=True)
class AgendaItem:
    """Eén afspraak uit de iCal-export."""

    datum: date
    start: time | None        # None betekent: hele dag, tijd niet te toetsen
    titel: str
    herkomst: str             # UID of regelnummer


class Ernst(IntEnum):
    """Lager getal is ernstiger; bepaalt de volgorde in het rapport."""

    KRITIEK = 0     # raakt Emiel direct
    VERSCHIL = 1    # orkestlijst en reed 2-sheet spreken elkaar tegen
    WEBSITE = 2     # musicalcats.nl wijkt af, informatief
    OPEN = 3        # nog in te vullen


@dataclass(frozen=True)
class Melding:
    """Eén bevinding voor het rapport."""

    ernst: Ernst
    datum: date
    tekst: str
    details: tuple = ()   # extra regels, ingesprongen onder de melding
