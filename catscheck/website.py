"""Parser voor de speellijst op musicalcats.nl.

De site is niet de bron, maar een extra paar ogen: verschillen met de
orkestlijst worden alleen ter informatie gemeld.
"""

import html as htmlmod
import re
from datetime import date

from catscheck.model import (
    ParseFout,
    Voorstelling,
    normaliseer_plaats,
    normaliseer_tijd,
)

_RIJ = re.compile(
    r'<td class="date"[^>]*>\s*<strong>\s*(\d{2})-(\d{2})-(\d{4})\s*</strong>\s*'
    r'<br\s*/?>\s*([\d]{1,2}[:.]\d{2})\s*</td>\s*'
    r'<td class="location"[^>]*>(.*?)</td>\s*'
    r'<td class="city"[^>]*>(.*?)</td>',
    re.S | re.I,
)


def parse_website(html):
    """Lees de speellijstpagina en geef alle voorstellingen terug."""
    treffers = _RIJ.findall(html)
    if not treffers:
        raise ParseFout(
            "geen voorstellingen gevonden op de pagina; de opmaak van "
            "musicalcats.nl is waarschijnlijk gewijzigd"
        )
    voorstellingen = []
    for dag, maand, jaar, tijd, theater, plaats in treffers:
        voorstellingen.append(
            Voorstelling(
                datum=date(int(jaar), int(maand), int(dag)),
                tijd=normaliseer_tijd(tijd),
                type=None,
                plaats=normaliseer_plaats(_tekst(plaats)),
                theater=_tekst(theater),
                reed2=None,
                bron="website",
                herkomst=f"{dag}-{maand}-{jaar} {tijd}",
            )
        )
    return voorstellingen


def _tekst(fragment):
    """Haal tags en entiteiten weg, houd de leestekens heel."""
    kaal = re.sub(r"<[^>]+>", "", fragment)
    return " ".join(htmlmod.unescape(kaal).split())
