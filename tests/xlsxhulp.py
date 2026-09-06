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


def maak_xlsx(tabbladen, verborgen=(), inline=False):
    """Bouw een xlsx uit {naam: [[cel, cel], ...]}.

    Namen in `verborgen` krijgen state="hidden" — zo werken de tests met
    verborgen tabbladen zonder een echt bestand nodig te hebben.

    Cellen worden standaard geschreven zoals het echte werkboek ze bewaart:
    tekst via een gedeelde-tekstentabel (xl/sharedStrings.xml, t="s") en
    getallen als kale <v> zonder t-attribuut. Het echte bestand heeft nul
    inline strings; alle tekst — ook de namen in de Reed 2-kolom — loopt via
    die tabel. Met inline=True gaat tekst in plaats daarvan als t="inlineStr"
    de zip in; die tak bestaat nog in xlsx.py maar komt in het echte bestand
    niet voor, en heeft dus een eigen, expliciete test nodig in plaats van
    dekking via deze fixture.
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

    gedeeld = {} if inline else _verzamel_gedeelde_teksten(tabbladen)

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        z.writestr("_rels/.rels", _RELS)
        z.writestr("xl/workbook.xml", "".join(werkmap))
        z.writestr("xl/_rels/workbook.xml.rels", "".join(relaties))
        for nummer, (_, rijen) in enumerate(bladen, start=1):
            inhoud = _blad_inline(rijen) if inline else _blad(rijen, gedeeld)
            z.writestr(f"xl/worksheets/sheet{nummer}.xml", inhoud)
        if gedeeld:
            z.writestr("xl/sharedStrings.xml", _sharedstrings_xml(gedeeld))
    return buffer.getvalue()


def _is_numeriek(waarde):
    """Zo bewaart het echte bestand dagnummer en tijd: als kaal getal."""
    try:
        float(waarde)
    except (TypeError, ValueError):
        return False
    return True


def _verzamel_gedeelde_teksten(tabbladen):
    """Verzamel elke niet-numerieke celwaarde één keer, in eerste-gebruik-volgorde."""
    tabel = {}
    for rijen in tabbladen.values():
        for rij in rijen:
            for waarde in rij:
                if waarde == "" or waarde is None or _is_numeriek(waarde):
                    continue
                tabel.setdefault(str(waarde), len(tabel))
    return tabel


def _sharedstrings_xml(tabel):
    items = sorted(tabel.items(), key=lambda kv: kv[1])
    si = "".join(f"<si><t>{escape(tekst)}</t></si>" for tekst, _ in items)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"{si}</sst>"
    )


def _blad(rijen, gedeeld):
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
            if _is_numeriek(waarde):
                uit.append(f"<c r=\"{verwijzing}\"><v>{escape(str(waarde))}</v></c>")
            else:
                index_gedeeld = gedeeld[str(waarde)]
                uit.append(f'<c r="{verwijzing}" t="s"><v>{index_gedeeld}</v></c>')
        uit.append("</row>")
    uit.append("</sheetData></worksheet>")
    return "".join(uit)


def _blad_inline(rijen):
    """De oude schrijfwijze: alle tekst als t="inlineStr".

    Alleen nog voor de test die de inlineStr-tak in xlsx.py dekt — het
    echte bestand gebruikt dit nooit, zie de uitleg bij maak_xlsx.
    """
    uit = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">',
           "<sheetData>"]
    for nummer, rij in enumerate(rijen, start=1):
        uit.append(f'<row r="{nummer}">')
        for index, waarde in enumerate(rij):
            if waarde == "" or waarde is None:
                continue
            verwijzing = f"{kolomnaam(index)}{nummer}"
            uit.append(
                f'<c r="{verwijzing}" t="inlineStr"><is><t>{escape(str(waarde))}</t></is></c>'
            )
        uit.append("</row>")
    uit.append("</sheetData></worksheet>")
    return "".join(uit)
