"""Parser voor de concept-planning 'Cats reed 2' (CSV-export van de Sheet)."""

import csv
import io
from datetime import date

from catscheck.model import (
    ParseFout,
    Voorstelling,
    WEEKDAG_NAMEN,
    WEEKDAGEN,
    normaliseer_naam,
    normaliseer_plaats,
    normaliseer_tijd,
)

# De kopregel staat niet altijd op regel 1: er kan een titelregel boven staan.
_KOPWOORD = "Speeldatum"

# De kolommen die iets over de planning zeggen. Drie collega's typen vrij in
# de Opmerking-kolommen (een voetnoot als "laatste update 5-9" bijvoorbeeld);
# inhoud dáár op een rij zonder datum is geen structurele verrassing. Inhoud
# in een van deze kolommen zonder datum wel.
_PLANNING_SLEUTELS = ("type", "aanvang", "theater", "plaats", "wie")


def parse_reed2(csv_tekst):
    """Lees de reed 2-planning en geef alle dagen terug, ook VRIJ en BOUW."""
    rijen = list(csv.reader(io.StringIO(csv_tekst)))
    kopindex = _zoek_kopregel(rijen)
    kop = [k.strip() for k in rijen[kopindex]]
    idx = _kolomindexen(kop)

    voorstellingen = []
    for nummer, rij in enumerate(rijen[kopindex + 1:], start=kopindex + 2):
        if not any(cel.strip() for cel in rij):
            continue
        ruwe_datum = _cel(rij, idx["datum"])
        if not ruwe_datum:
            # De regel hierboven ving al de echt lege rijen af. Staat er op
            # zo'n rij alleen iets in een Opmerking-kolom (een voetnoot,
            # gedeeld door drie collega's), dan is dat geen structurele
            # verrassing — gewoon overslaan. Staat er wel iets in een
            # planningskolom zonder speeldatum, dan is dat dat wel: elke
            # andere misvorming in deze parser gooit al een ParseFout, en
            # stil overslaan hoort hier geen uitzondering te zijn.
            if any(_cel(rij, idx[sleutel]) for sleutel in _PLANNING_SLEUTELS):
                raise ParseFout(f"regel {nummer} heeft inhoud maar geen speeldatum")
            continue
        dag = _maak_datum(ruwe_datum, nummer)
        voorstellingen.append(
            Voorstelling(
                datum=dag,
                tijd=normaliseer_tijd(_cel(rij, idx["aanvang"])),
                type=(_cel(rij, idx["type"]) or "").upper() or None,
                plaats=normaliseer_plaats(_cel(rij, idx["plaats"])),
                theater=_cel(rij, idx["theater"]) or None,
                reed2=normaliseer_naam(_cel(rij, idx["wie"])),
                bron="reed2",
                herkomst=f"regel {nummer}",
            )
        )
    if not voorstellingen:
        raise ParseFout("geen regels gevonden onder de kopregel van de reed 2-sheet")
    return voorstellingen


def _zoek_kopregel(rijen):
    for i, rij in enumerate(rijen):
        if any(cel.strip() == _KOPWOORD for cel in rij):
            return i
    raise ParseFout(f"kopregel met {_KOPWOORD!r} niet gevonden in de reed 2-sheet")


def _kolomindexen(kop):
    """Zoek de kolommen op hun kop, niet op hun positie."""
    gezocht = {
        "datum": "Speeldatum",
        "type": "Type",
        "aanvang": "Aanvang",
        "theater": "Theater",
        "plaats": "Plaats",
        "wie": "Wie ?",
    }
    idx = {}
    for sleutel, koptekst in gezocht.items():
        if koptekst not in kop:
            raise ParseFout(f"kolom {koptekst!r} niet gevonden in de reed 2-sheet")
        idx[sleutel] = kop.index(koptekst)
    return idx


def _cel(rij, index):
    return rij[index].strip() if index < len(rij) else ""


def _maak_datum(ruw, regelnummer):
    """Lees "do 24-09-2026" en toets de weekdag die erbij staat."""
    delen = ruw.split()
    if len(delen) != 2:
        raise ParseFout(f"onbegrijpelijke speeldatum {ruw!r} op regel {regelnummer}")
    weekdag, datumtekst = delen[0].strip().lower(), delen[1]
    try:
        d, m, j = (int(x) for x in datumtekst.split("-"))
        dag = date(j, m, d)
    except ValueError:
        raise ParseFout(f"onbegrijpelijke speeldatum {ruw!r} op regel {regelnummer}") from None
    if weekdag not in WEEKDAGEN:
        raise ParseFout(f"onbekende weekdag {weekdag!r} op regel {regelnummer}")
    if dag.weekday() != WEEKDAGEN[weekdag]:
        raise ParseFout(
            f"weekdag klopt niet op regel {regelnummer}: {ruw!r} is in werkelijkheid een "
            f"{WEEKDAG_NAMEN[dag.weekday()]}"
        )
    return dag
