"""Minimale xlsx-lezer op de standaardbibliotheek.

Geeft per zichtbaar tabblad de rijen terug als lijsten met tekst, met lege
cellen op hun plek. Alleen wat deze checker nodig heeft: geen opmaak, geen
datumconversie — de orkestlijst zet dagnummer en tijd in gewone cellen.
"""

import io
import re
import zipfile
import xml.etree.ElementTree as ET

from catscheck.model import ParseFout

_HOOFD = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
_PAKKET_REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"

_KOLOM = re.compile(r"([A-Z]+)")


def lees_tabbladen(data):
    """Geef [(naam, rijen)] voor elk zichtbaar tabblad, in bladvolgorde."""
    try:
        bestand = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise ParseFout(
            "de orkestlijst is geen leesbare xlsx; is het ophalen misgegaan "
            "en staat er een inlogpagina in de cache?"
        ) from None

    with bestand as z:
        namen = set(z.namelist())
        if "xl/workbook.xml" not in namen:
            raise ParseFout("de orkestlijst mist xl/workbook.xml; geen geldige xlsx")
        gedeeld = _lees_gedeelde_teksten(z, namen)
        doelen = _lees_relaties(z, namen)
        tabbladen = []
        for blad in ET.fromstring(z.read("xl/workbook.xml")).iter(_HOOFD + "sheet"):
            if blad.get("state", "visible") != "visible":
                continue
            pad = doelen.get(blad.get(_REL + "id"))
            if pad is None or pad not in namen:
                continue
            tabbladen.append((blad.get("name", ""), _lees_rijen(z.read(pad), gedeeld)))
        return tabbladen


def _lees_gedeelde_teksten(z, namen):
    """Xlsx bewaart herhaalde tekst één keer; cellen verwijzen met een index."""
    if "xl/sharedStrings.xml" not in namen:
        return []
    root = ET.fromstring(z.read("xl/sharedStrings.xml"))
    return ["".join(t.text or "" for t in si.iter(_HOOFD + "t")) for si in root]


def _lees_relaties(z, namen):
    """Koppel de r:id uit de werkmap aan het pad van het tabblad in de zip."""
    if "xl/_rels/workbook.xml.rels" not in namen:
        return {}
    doelen = {}
    for rel in ET.fromstring(z.read("xl/_rels/workbook.xml.rels")).iter(
        _PAKKET_REL + "Relationship"
    ):
        doel = rel.get("Target", "").lstrip("/")
        doelen[rel.get("Id")] = doel if doel.startswith("xl/") else "xl/" + doel
    return doelen


def _lees_rijen(xml, gedeeld):
    rijen = []
    for rij in ET.fromstring(xml).iter(_HOOFD + "row"):
        cellen = {}
        for cel in rij.findall(_HOOFD + "c"):
            index = _kolomindex(cel.get("r", ""))
            if index is not None:
                cellen[index] = _celwaarde(cel, gedeeld)
        breedte = max(cellen) + 1 if cellen else 0
        rijen.append([cellen.get(i, "") for i in range(breedte)])
    return rijen


def _celwaarde(cel, gedeeld):
    if cel.get("t") == "inlineStr":
        blok = cel.find(_HOOFD + "is")
        return "".join(t.text or "" for t in blok.iter(_HOOFD + "t")) if blok is not None else ""
    waarde = cel.find(_HOOFD + "v")
    if waarde is None or waarde.text is None:
        return ""
    if cel.get("t") == "s":
        try:
            return gedeeld[int(waarde.text)]
        except (ValueError, IndexError):
            return ""
    return waarde.text


def _kolomindex(verwijzing):
    """Zet "Q3" om naar 16.

    Cellen mogen ontbreken; de index houdt de kopregel en de datarijen op
    dezelfde plek, zodat de kolom van Reed 2 niet verschuift.
    """
    treffer = _KOLOM.match(verwijzing)
    if not treffer:
        return None
    index = 0
    for teken in treffer.group(1):
        index = index * 26 + (ord(teken) - 64)
    return index - 1
