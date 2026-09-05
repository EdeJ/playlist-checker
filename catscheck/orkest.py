"""Parser voor de tekstweergave van Orkestoverzicht Cats.xlsx.

De weergave die Drive teruggeeft is geen CSV: alle rijen staan achter elkaar
op één regel, gescheiden door spaties. De laatste cel van een rij loopt daardoor
tegen de eerste cel van de volgende aan. Er wordt geknipt op het weekdagpatroon
waarmee elke datarij begint.
"""

import re
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

MAANDEN = {
    "januari": 1, "februari": 2, "maart": 3, "april": 4,
    "mei": 5, "juni": 6, "juli": 7, "augustus": 8,
    "september": 9, "oktober": 10, "november": 11, "december": 12,
}

# Begin van een tabblad: de maandnaam twee keer achter elkaar, bijvoorbeeld
# "Oktober OKTOBER" of "Januari Januari". De Mamma Mia-blokken beginnen met
# "Feb Mamma Mia" en "Ma Mamma Mia" en matchen dus niet.
_BLOK = re.compile(
    r"\b(" + "|".join(MAANDEN) + r")\s+\1\b(?=\s*,)",
    re.IGNORECASE,
)

# Onderaan het bestand staan tabbladen van een andere productie. Die hebben een
# andere kolomindeling en Engelse weekdagen; alles vanaf hier hoort niet bij
# Cats. Expliciet afkappen is veiliger dan hopen dat de rijen niet matchen.
_ANDERE_PRODUCTIE = re.compile(r"Mamma\s*Mia", re.IGNORECASE)

# Begin van een datarij: weekdag, komma, dagnummer, komma.
_RIJ = re.compile(
    r"(?:(?<=\s)|^)(" + "|".join(sorted(WEEKDAGEN, key=len, reverse=True)) + r")\s*,\s*(\d{1,2})\s*,",
    re.IGNORECASE,
)


def parse_orkest(tekst, startjaar=2026):
    """Lees de orkestlijst en geef alle voorstellingen terug.

    Dagen zonder type worden overgeslagen: dat zijn lege dagen in het rooster.
    """
    grens = _ANDERE_PRODUCTIE.search(tekst)
    if grens:
        tekst = tekst[:grens.start()]

    voorstellingen = []
    blokken = _splits_blokken(tekst)
    if not blokken:
        raise ParseFout("geen enkel tabblad gevonden in de orkestlijst")

    jaar = startjaar
    vorige_maand = None
    for maandnaam, inhoud in blokken:
        maand = MAANDEN[maandnaam.lower()]
        if vorige_maand is not None and maand < vorige_maand:
            jaar += 1
        vorige_maand = maand

        kop, body = _splits_kop(inhoud)
        if "Reed 2" not in kop:
            # Geen Reed 2-kolom: dit blok hoort bij een andere productie.
            continue
        reed2_index = kop.index("Reed 2")

        for weekdag, dagnummer, velden, ruw in _splits_rijen(body):
            dag = _maak_datum(jaar, maand, dagnummer, weekdag, ruw)
            soort = velden[3].strip() if len(velden) > 3 else ""
            if not soort:
                continue
            voorstellingen.append(
                Voorstelling(
                    datum=dag,
                    tijd=normaliseer_tijd(velden[2] if len(velden) > 2 else None),
                    type=soort.upper(),
                    plaats=normaliseer_plaats(velden[4] if len(velden) > 4 else None),
                    theater=None,
                    reed2=normaliseer_naam(
                        velden[reed2_index] if len(velden) > reed2_index else None
                    ),
                    bron="orkest",
                    herkomst=f"{maandnaam.lower()} {weekdag} {dagnummer}",
                )
            )
    if not voorstellingen:
        raise ParseFout("geen voorstellingen gevonden; klopt de kolom Reed 2 nog?")
    return voorstellingen


def _splits_blokken(tekst):
    """Geef (maandnaam, inhoud) per tabblad."""
    treffers = list(_BLOK.finditer(tekst))
    blokken = []
    for i, t in enumerate(treffers):
        einde = treffers[i + 1].start() if i + 1 < len(treffers) else len(tekst)
        blokken.append((t.group(1), tekst[t.start():einde]))
    return blokken


def _splits_kop(inhoud):
    """Scheid de kopregel van het blok van de datarijen eronder."""
    eerste_rij = _RIJ.search(inhoud)
    grens = eerste_rij.start() if eerste_rij else len(inhoud)
    kop = [k.strip() for k in inhoud[:grens].split(",")]
    return kop, inhoud[grens:] if eerste_rij else ""


def _splits_rijen(body):
    """Knip de aaneengeplakte datarijen los op het weekdagpatroon."""
    treffers = list(_RIJ.finditer(body))
    for i, t in enumerate(treffers):
        einde = treffers[i + 1].start() if i + 1 < len(treffers) else len(body)
        ruw = body[t.start():einde]
        velden = ruw.split(",")
        yield t.group(1).strip().lower(), int(t.group(2)), velden, ruw


def _maak_datum(jaar, maand, dagnummer, weekdag, ruw):
    """Bouw de datum en toets hem tegen de weekdag die in de rij staat.

    Klopt de weekdag niet, dan is het jaartal misgelopen of is de rij verkeerd
    geknipt. In beide gevallen is doorgaan gevaarlijker dan stoppen.
    """
    try:
        dag = date(jaar, maand, dagnummer)
    except ValueError:
        raise ParseFout(f"onmogelijke datum {dagnummer}-{maand}-{jaar} in rij: {ruw[:60]!r}") from None
    verwacht = WEEKDAGEN[weekdag]
    if dag.weekday() != verwacht:
        raise ParseFout(
            f"weekdag klopt niet: rij zegt {weekdag!r} maar {dag} is een "
            f"{WEEKDAG_NAMEN[dag.weekday()]}. Rij: {ruw[:60]!r}"
        )
    return dag
