"""Bouwt een minimale xlsx voor de tests.

Zo staat een fixture als tabel in de test in plaats van als binair bestand,
en is een kapotte variant (kop weg, verborgen tabblad) met één regel te maken.
"""

import io
import zipfile
from xml.sax.saxutils import escape

_RELS = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Target="xl/workbook.xml" '
    'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"/>'
    "</Relationships>"
)


def kolomnaam(index):
    """Zet 0 om naar "A" en 26 naar "AA"."""
    naam = ""
    index += 1
    while index:
        index, rest = divmod(index - 1, 26)
        naam = chr(65 + rest) + naam
    return naam


def maak_xlsx(tabbladen, verborgen=()):
    """Bouw een xlsx uit {naam: [[cel, cel], ...]}.

    Namen in `verborgen` krijgen state="hidden" — zo werken de tests met
    verborgen tabbladen zonder een echt bestand nodig te hebben.
    """
    bladen = list(tabbladen.items())
    werkmap = ['<?xml version="1.0" encoding="UTF-8"?>',
               '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" ',
               'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">',
               "<sheets>"]
    relaties = ['<?xml version="1.0" encoding="UTF-8"?>',
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">']
    for nummer, (naam, _) in enumerate(bladen, start=1):
        staat = "hidden" if naam in verborgen else "visible"
        werkmap.append(
            f'<sheet name="{escape(naam)}" sheetId="{nummer}" state="{staat}" r:id="rId{nummer}"/>'
        )
        relaties.append(
            f'<Relationship Id="rId{nummer}" Target="worksheets/sheet{nummer}.xml" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"/>'
        )
    werkmap.append("</sheets></workbook>")
    relaties.append("</Relationships>")

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        z.writestr("_rels/.rels", _RELS)
        z.writestr("xl/workbook.xml", "".join(werkmap))
        z.writestr("xl/_rels/workbook.xml.rels", "".join(relaties))
        for nummer, (_, rijen) in enumerate(bladen, start=1):
            z.writestr(f"xl/worksheets/sheet{nummer}.xml", _blad(rijen))
    return buffer.getvalue()


def _blad(rijen):
    uit = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">',
           "<sheetData>"]
    for nummer, rij in enumerate(rijen, start=1):
        uit.append(f'<row r="{nummer}">')
        for index, waarde in enumerate(rij):
            if waarde == "" or waarde is None:
                # Lege cellen weglaten, zoals Excel dat ook doet: de lezer
                # moet met gaten in de rij overweg kunnen.
                continue
            verwijzing = f"{kolomnaam(index)}{nummer}"
            uit.append(
                f'<c r="{verwijzing}" t="inlineStr"><is><t>{escape(str(waarde))}</t></is></c>'
            )
        uit.append("</row>")
    uit.append("</sheetData></worksheet>")
    return "".join(uit)
