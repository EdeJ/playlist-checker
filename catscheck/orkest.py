"""Parser voor Orkestoverzicht Cats.xlsx.

Leest de xlsx rechtstreeks. Elk maandtabblad heeft dezelfde indeling: kolom A
weekdag, B dagnummer, C aanvangstijd, D type, E plaats, en daarachter een
kolom per stoel. Welke kolom Reed 2 is wordt uit de kopregel gehaald en niet
vastgelegd — dat hij vandaag overal Q is, is een waarneming en geen aanname.
"""

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
from catscheck.xlsx import lees_tabbladen

MAANDEN = {
    "januari": 1, "februari": 2, "maart": 3, "april": 4,
    "mei": 5, "juni": 6, "juli": 7, "augustus": 8,
    "september": 9, "oktober": 10, "november": 11, "december": 12,
}

_REED2_KOP = "reed 2"


def parse_orkest(data, startjaar=2026):
    """Lees de orkestlijst en geef alle voorstellingen terug.

    Dagen zonder type worden overgeslagen: dat zijn lege dagen in het rooster.
    """
    voorstellingen = []
    jaar = startjaar
    vorige_maand = None

    for naam, rijen in lees_tabbladen(data):
        maand = MAANDEN.get(naam.strip().lower())
        if maand is None:
            # INPUT en al wat verder geen maandnaam draagt.
            continue
        if vorige_maand is not None and maand < vorige_maand:
            jaar += 1
        vorige_maand = maand

        kop_rij, reed2_index = _zoek_kop(rijen)
        datarijen = [r for r in rijen[kop_rij + 1:] if _is_datarij(r)]
        if reed2_index is None:
            if not datarijen:
                # Geen datarijen en geen Reed 2-kop: niets in dit tabblad dat
                # gemist kan worden.
                continue
            # Wel datarijen, maar geen Reed 2-kolom in de kop: dit tabblad is
            # kapot of verschoven. Stilzwijgend overslaan zou een hele maand
            # laten verdwijnen zonder dat iemand het merkt.
            raise ParseFout(
                f"tabblad {naam.strip()} heeft datarijen maar geen kolom "
                f"'Reed 2' in de kop; is de kop verschoven of ontbreekt hij?"
            )

        for rij in datarijen:
            weekdag = _cel(rij, 0).strip().lower()
            dag = _maak_datum(jaar, maand, _dagnummer(_cel(rij, 1), rij), weekdag, rij)
            soort = _cel(rij, 3).strip()
            if not soort:
                continue
            voorstellingen.append(
                Voorstelling(
                    datum=dag,
                    tijd=_tijd_uit_cel(_cel(rij, 2)),
                    type=soort.upper(),
                    plaats=normaliseer_plaats(_cel(rij, 4)),
                    theater=None,
                    reed2=normaliseer_naam(_cel(rij, reed2_index)),
                    bron="orkest",
                    herkomst=f"{naam.strip().lower()} {weekdag} {dag.day}",
                )
            )

    if not voorstellingen:
        raise ParseFout("geen voorstellingen gevonden; klopt de kolom Reed 2 nog?")
    return voorstellingen


def _zoek_kop(rijen):
    """Geef (rijnummer, kolomindex van Reed 2) van de kopregel.

    De kop staat niet overal op dezelfde rij: in Oktober op rij 2, in de
    overige maanden op rij 1. Daarom opzoeken in plaats van vastleggen.
    """
    for nummer, rij in enumerate(rijen):
        for index, cel in enumerate(rij):
            if cel.strip().lower() == _REED2_KOP:
                return nummer, index
    return -1, None


def _is_datarij(rij):
    """Een datarij begint met een weekdag en een dagnummer."""
    if len(rij) < 2 or _cel(rij, 0).strip().lower() not in WEEKDAGEN:
        return False
    try:
        float(_cel(rij, 1).strip())
    except ValueError:
        return False
    return True


def _cel(rij, index):
    """Excel laat lege cellen achteraan weg; die rijen zijn dus korter."""
    return rij[index] if index < len(rij) else ""


def _dagnummer(ruw, rij):
    try:
        return int(float(ruw.strip()))
    except ValueError:
        raise ParseFout(f"onbegrijpelijk dagnummer {ruw!r} in rij: {rij[:6]!r}") from None


def _tijd_uit_cel(ruw):
    """Reken een Excel-dagfractie om naar "HH:MM".

    Excel bewaart 20:15 als 0.84375 van een etmaal. Staat er tekst in de cel,
    dan gaat die ongewijzigd naar de normalisatie die alle bronnen delen.
    """
    tekst = ruw.strip()
    if not tekst:
        return None
    try:
        fractie = float(tekst)
    except ValueError:
        return normaliseer_tijd(tekst)
    if not 0 <= fractie < 1:
        raise ParseFout(f"tijd buiten bereik: {ruw!r}")
    minuten = round(fractie * 24 * 60)
    return normaliseer_tijd(f"{minuten // 60:02d}:{minuten % 60:02d}")


def _maak_datum(jaar, maand, dagnummer, weekdag, rij):
    """Bouw de datum en toets hem tegen de weekdag die in de rij staat.

    Klopt de weekdag niet, dan is het jaartal misgelopen of staat de rij op de
    verkeerde plek. In beide gevallen is doorgaan gevaarlijker dan stoppen.
    """
    try:
        dag = date(jaar, maand, dagnummer)
    except ValueError:
        raise ParseFout(
            f"onmogelijke datum {dagnummer}-{maand}-{jaar} in rij: {rij[:6]!r}"
        ) from None
    verwacht = WEEKDAGEN[weekdag]
    if dag.weekday() != verwacht:
        raise ParseFout(
            f"weekdag klopt niet: rij zegt {weekdag!r} maar {dag} is een "
            f"{WEEKDAG_NAMEN[dag.weekday()]}. Rij: {rij[:6]!r}"
        )
    return dag
