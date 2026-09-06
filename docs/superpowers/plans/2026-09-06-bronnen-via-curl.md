# Alle bronnen via curl — implementatieplan

> **Voor agentische werkers:** VEREISTE SUB-SKILL: gebruik
> superpowers:subagent-driven-development (aanbevolen) of
> superpowers:executing-plans om dit plan taak voor taak uit te voeren.
> Stappen gebruiken checkbox-syntax (`- [ ]`) voor het bijhouden.

**Doel:** Alle vier de bronnen met `curl` naar `cache/` halen, zodat er geen
bronbestand meer door het model gaat, en de orkestlijst als xlsx lezen in
plaats van als Drive's tekstweergave.

**Architectuur:** Er komt een kleine xlsx-lezer op de standaardbibliotheek
(`catscheck/xlsx.py`) die per zichtbaar tabblad rijen met tekst teruggeeft.
`catscheck/orkest.py` bouwt daarop en verliest zijn drie regex-hacks.
`scripts/ophalen.sh` haalt er twee bronnen bij en faalt hard als er één niet
op te halen is.

**Techniek:** Python 3, uitsluitend standaardbibliotheek (`zipfile`,
`xml.etree.ElementTree`, `unittest`). Bash met `curl`.

## Globale randvoorwaarden

- Geen dependencies. Alles draait op een kale `python3`; `pip install` is geen
  optie.
- Alles is alleen-lezen. Er wordt nooit naar een bron geschreven, en de
  schrijvende Drive-tools blijven geblokkeerd in `.claude/settings.json`.
- Code, commentaar, foutmeldingen, tests en commitberichten zijn Nederlands.
- Tests draaien met `python3 -m unittest discover -s tests` vanuit de
  projectmap. Testmodules importeren elkaar met het `tests.`-voorvoegsel
  (`from tests.xlsxhulp import maak_xlsx`).
- De afsluitcodes van `python3 -m catscheck` blijven: 0 geen verschillen,
  1 meldingen, 2 een bron kon niet gelezen worden.
- Commits: `feat:`, `fix:`, `docs:` of `test:` met een Nederlandse tekst, en
  aan het eind `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`.

---

### Taak 1: xlsx-lezer

**Bestanden:**
- Aanmaken: `catscheck/xlsx.py`
- Aanmaken: `tests/xlsxhulp.py`
- Test: `tests/test_xlsx.py`

**Interfaces:**
- Gebruikt: `ParseFout` uit `catscheck.model`
- Levert:
  - `lees_tabbladen(data: bytes) -> list[tuple[str, list[list[str]]]]` —
    per zichtbaar tabblad de naam en zijn rijen, in bladvolgorde. Elke rij is
    een lijst tekst; ontbrekende cellen zijn `""` en houden hun kolompositie.
  - `maak_xlsx(tabbladen: dict[str, list[list[str]]], verborgen: tuple = ()) -> bytes`
    (testgereedschap)
  - `kolomnaam(index: int) -> str` (testgereedschap; 0 → `"A"`, 26 → `"AA"`)

- [ ] **Stap 1: Schrijf het testgereedschap**

Zonder dit gereedschap zijn de tests binaire bestanden. Hiermee staat een
fixture als tabel in de test. Maak `tests/xlsxhulp.py`:

```python
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
```

- [ ] **Stap 2: Schrijf de falende tests**

Maak `tests/test_xlsx.py`:

```python
import unittest

from catscheck.model import ParseFout
from catscheck.xlsx import lees_tabbladen
from tests.xlsxhulp import kolomnaam, maak_xlsx


class TestKolomnaam(unittest.TestCase):
    def test_eerste_kolommen(self):
        self.assertEqual(kolomnaam(0), "A")
        self.assertEqual(kolomnaam(16), "Q")
        self.assertEqual(kolomnaam(25), "Z")

    def test_voorbij_z(self):
        self.assertEqual(kolomnaam(26), "AA")


class TestLeesTabbladen(unittest.TestCase):
    def test_geeft_tabbladen_in_bladvolgorde(self):
        data = maak_xlsx({"INPUT": [["a"]], "Oktober": [["b"]]})
        self.assertEqual([naam for naam, _ in lees_tabbladen(data)], ["INPUT", "Oktober"])

    def test_verborgen_tabbladen_komen_er_niet_in(self):
        # De Mamma Mia-tabbladen staan op hidden en horen bij een andere
        # productie; die mogen nooit als Cats-voorstellingen meetellen.
        data = maak_xlsx({"Oktober": [["b"]], "Feb": [["x"]]}, verborgen=("Feb",))
        self.assertEqual([naam for naam, _ in lees_tabbladen(data)], ["Oktober"])

    def test_lege_cellen_houden_hun_kolompositie(self):
        # Excel laat lege cellen weg. Wie de rij dan gewoon achter elkaar
        # plakt, schuift elke naam een kolom op en leest de verkeerde stoel.
        data = maak_xlsx({"Oktober": [["Di", "", "", "TO"]]})
        (_, rijen), = lees_tabbladen(data)
        self.assertEqual(rijen[0], ["Di", "", "", "TO"])

    def test_rij_zonder_cellen_blijft_een_lege_rij(self):
        data = maak_xlsx({"Oktober": [[], ["Di"]]})
        (_, rijen), = lees_tabbladen(data)
        self.assertEqual(rijen, [[], ["Di"]])

    def test_kolommen_voorbij_z_komen_op_de_juiste_plek(self):
        rij = ["x"] * 27
        rij[26] = "BIJZITTERS"
        data = maak_xlsx({"Oktober": [rij]})
        (_, rijen), = lees_tabbladen(data)
        self.assertEqual(rijen[0][26], "BIJZITTERS")


class TestOnleesbaar(unittest.TestCase):
    def test_geen_zip_geeft_een_parsefout(self):
        # Wordt de linkdeling ingetrokken, dan levert curl een inlogpagina op
        # in plaats van het bestand. Dat moet stoppen, niet stil doorgaan.
        with self.assertRaises(ParseFout) as ctx:
            lees_tabbladen(b"<html>Sign in to continue</html>")
        self.assertIn("xlsx", str(ctx.exception))

    def test_zip_zonder_werkmap_geeft_een_parsefout(self):
        import io
        import zipfile

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as z:
            z.writestr("iets.txt", "geen xlsx")
        with self.assertRaises(ParseFout):
            lees_tabbladen(buffer.getvalue())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Stap 3: Draai de tests en controleer dat ze falen**

Draai: `python3 -m unittest tests.test_xlsx -v`
Verwacht: FAIL met `ModuleNotFoundError: No module named 'catscheck.xlsx'`

- [ ] **Stap 4: Schrijf de lezer**

Maak `catscheck/xlsx.py`:

```python
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
```

- [ ] **Stap 5: Draai de tests en controleer dat ze slagen**

Draai: `python3 -m unittest tests.test_xlsx -v`
Verwacht: PASS, 9 tests

- [ ] **Stap 6: Commit**

```bash
git add catscheck/xlsx.py tests/xlsxhulp.py tests/test_xlsx.py
git commit -m "feat: lees xlsx-tabbladen met de standaardbibliotheek

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Taak 2: De orkestparser leest de xlsx

**Bestanden:**
- Herschrijven: `catscheck/orkest.py`
- Aanmaken: `tests/orkestblad.py`
- Herschrijven: `tests/test_orkest.py`
- Verwijderen: `tests/fixtures/orkest.txt`

**Interfaces:**
- Gebruikt: `lees_tabbladen` uit `catscheck.xlsx`, `maak_xlsx` uit
  `tests.xlsxhulp`, en uit `catscheck.model`: `ParseFout`, `Voorstelling`,
  `WEEKDAGEN`, `WEEKDAG_NAMEN`, `normaliseer_naam`, `normaliseer_plaats`,
  `normaliseer_tijd`
- Levert:
  - `parse_orkest(data: bytes, startjaar: int = 2026) -> list[Voorstelling]` —
    let op: **bytes**, waar de oude versie tekst nam
  - `ORKEST_TABBLADEN: dict`, `VERBORGEN: tuple`, `orkest_xlsx() -> bytes`
    uit `tests/orkestblad.py`

- [ ] **Stap 1: Schrijf de fixture als tabel**

Maak `tests/orkestblad.py`. Dit is dezelfde inhoud als de oude
`tests/fixtures/orkest.txt`, maar nu als rijen en kolommen. De tijden staan
als Excel-dagfractie, precies zoals het echte bestand ze bewaart: `0.84375`
is 20:15.

```python
"""De orkestlijst-fixture als tabel.

Kolom 14 is Reed 1 en kolom 16 is Reed 2; die twee liggen naast elkaar en
worden makkelijk verwisseld, dus ze staan in bijna elke rij ingevuld.
"""

from tests.xlsxhulp import maak_xlsx

KOP = [
    "OKTOBER", "", "", "", "", "",
    "MD", "Overnachten MD",
    "Toetsen 1", "Overnachten Toetsen 1",
    "Toetsen 2", "Overnachten Toetsen 2",
    "Toetsen 3", "Overnachten Toetsen 3",
    "Reed 1", "Overnachten Reed 1",
    "Reed 2", "Overnachten Reed 2",
    "Drums", "Overnachten Drums",
    "Gitaar", "Overnachten Gitaar",
    "Bass", "Overnachten Bass",
    "", "OPMERKINGEN", "BIJZITTERS",
]


def kop(maand, extra=()):
    return [maand] + KOP[1:] + list(extra)


def rij(weekdag, dag, tijd, soort, plaats, reed1="", reed2="", staart=()):
    return ([weekdag, dag, tijd, soort, plaats, "", "", "", "Hajo ", "", "Hans", "",
             "Charles ", "", reed1, "", reed2] + list(staart))


ORKEST_TABBLADEN = {
    "INPUT": [["Namen", "MD/Keys"], ["", "Steven"]],
    "Oktober": [
        [],
        kop("OKTOBER"),
        rij("Di", "6.0", "0.84375", "TO", "Almere", "Marielle", "Emiel",
            staart=["", "", "", "Jurgen", "", "Marijn", "Nee", "", "", "hans"]),
        rij("Woe", "7.0", "0.84375", "TO", "Almere", "Marielle", "Emiel"),
        ["Ma", "12.0"],
        rij("Vr", "23.0", "0.625", "REG", "Amsterdam", "Marielle", "Emiel"),
        rij("Vr", "23.0", "0.833333333333333", "REG", "Amsterdam", "Marielle", "Emiel"),
    ],
    "December": [
        kop("DECEMBER"),
        ["Zo", "13.0", "0.604166666666667", "REG", "Zoetermeer", "", "", "", "Hajo ", "",
         "Hans", "Nee", "(leeg)", "", "Marielle", "", "Emiel"],
    ],
    "Januari ": [
        kop("Januari", extra=["BIJZITTERS"]),
        ["Za", "2.0", "0.604166666666667", "REG", "Breda", "", "", "", "Tom", "", "", "",
         "", "", "Coen"],
    ],
    "Maart ": [
        kop("Maart", extra=["BIJZITTERS"]),
        rij("Woe ", "31.0", "0.833333333333333", "REG", "Amterdam DLM", "Marielle", "Michiel "),
    ],
    "Feb": [["FEBRUARI", "", "", "", "MD/Keys", "Guitar 1"],
            ["Sun", "1.0", "0.479166666666667", "", "", "Max"]],
    "Ma": [["MAART", "", "", "", "MD/Keys", "Guitar 1"]],
}

VERBORGEN = ("Feb", "Ma")


def orkest_xlsx(tabbladen=None):
    return maak_xlsx(tabbladen or ORKEST_TABBLADEN, verborgen=VERBORGEN)
```

- [ ] **Stap 2: Schrijf de falende tests**

Vervang de inhoud van `tests/test_orkest.py` volledig:

```python
import copy
import unittest
from datetime import date

from catscheck.model import ParseFout
from catscheck.orkest import parse_orkest
from tests.orkestblad import ORKEST_TABBLADEN, VERBORGEN, orkest_xlsx
from tests.xlsxhulp import maak_xlsx


def aangepast(wijziging):
    """Geef de fixture terug met één ding eraan veranderd."""
    tabbladen = copy.deepcopy(ORKEST_TABBLADEN)
    wijziging(tabbladen)
    return maak_xlsx(tabbladen, verborgen=VERBORGEN)


class TestParseOrkest(unittest.TestCase):
    def setUp(self):
        self.vs = parse_orkest(orkest_xlsx())

    def test_lege_dagen_komen_er_niet_in(self):
        # Ma 12 oktober heeft geen type en geen tijd; dat is geen voorstelling.
        self.assertNotIn(date(2026, 10, 12), [v.datum for v in self.vs])

    def test_leest_de_eerste_voorstelling(self):
        v = self.vs[0]
        self.assertEqual(v.datum, date(2026, 10, 6))
        self.assertEqual(v.tijd, "20:15")
        self.assertEqual(v.type, "TO")
        self.assertEqual(v.plaats, "ALMERE")
        self.assertEqual(v.reed2, "emiel")
        self.assertEqual(v.bron, "orkest")

    def test_excel_bewaart_de_tijd_als_dagfractie(self):
        # 0.84375 van een etmaal is 20:15. Wie die kolom als tekst leest,
        # krijgt "0.84375" in het rapport te zien.
        self.assertEqual([v.tijd for v in self.vs][:2], ["20:15", "20:15"])

    def test_een_rij_die_korter_is_dan_de_kop_levert_geen_indexerror(self):
        # Excel laat cellen achteraan weg. Staat Reed 2 voorbij het einde van
        # de rij, dan is die stoel leeg — en mag het geen IndexError geven.
        def kort(t):
            t["Oktober"][2] = t["Oktober"][2][:6]

        vs = parse_orkest(aangepast(kort))
        eerste = [v for v in vs if v.datum == date(2026, 10, 6)][0]
        self.assertIsNone(eerste.reed2)
        self.assertEqual(eerste.type, "TO")

    def test_twee_voorstellingen_op_een_dag_blijven_allebei_staan(self):
        op_23 = [v for v in self.vs if v.datum == date(2026, 10, 23)]
        self.assertEqual([v.tijd for v in op_23], ["15:00", "20:00"])

    def test_jaartal_loopt_door_over_de_jaargrens(self):
        datums = [v.datum for v in self.vs]
        self.assertIn(date(2026, 12, 13), datums)   # december blijft 2026
        self.assertIn(date(2027, 1, 2), datums)     # januari wordt 2027
        self.assertIn(date(2027, 3, 31), datums)    # maart blijft 2027

    def test_naam_in_de_reed1_kolom_wordt_niet_voor_reed2_aangezien(self):
        # Coen bespeelt beide stoelen. Staat hij in Reed 1 terwijl Reed 2 leeg
        # is, dan pikt een parser die op een vaste kolompositie werkt hem hier
        # ten onrechte op.
        za2 = [v for v in self.vs if v.datum == date(2027, 1, 2)][0]
        self.assertEqual(za2.tijd, "14:30")
        self.assertEqual(za2.plaats, "BREDA")
        self.assertIsNone(za2.reed2)

    def test_leeg_tussen_haakjes_in_een_andere_kolom_verstoort_niets(self):
        zo13 = [v for v in self.vs if v.datum == date(2026, 12, 13)][0]
        self.assertEqual(zo13.reed2, "emiel")

    def test_delamar_typefout_wordt_genormaliseerd(self):
        wo31 = [v for v in self.vs if v.datum == date(2027, 3, 31)][0]
        self.assertEqual(wo31.plaats, "AMSTERDAM")
        self.assertEqual(wo31.reed2, "michiel")

    def test_verborgen_tabbladen_worden_overgeslagen(self):
        # Feb en Ma zijn Mamma Mia: een andere productie, andere kolommen,
        # Engelse weekdagen.
        self.assertTrue(all(v.datum.year in (2026, 2027) for v in self.vs))
        self.assertEqual(len(self.vs), 7)

    def test_tabblad_zonder_maandnaam_levert_niets_op(self):
        # INPUT draagt geen maandnaam; wat daar staat is nooit een
        # voorstelling, ook niet als het op een datarij lijkt.
        def input_met_datarij(t):
            t["INPUT"].append(["Di", "6.0", "0.84375", "TO", "Almere"])

        self.assertEqual(len(parse_orkest(aangepast(input_met_datarij))), 7)


class TestValidatie(unittest.TestCase):
    def test_verkeerde_weekdag_geeft_een_parsefout(self):
        # 6 oktober 2026 is een dinsdag; "Wo" hoort te stoppen, want dat
        # betekent dat de jaartal-afleiding is misgelopen.
        def kapot(t):
            t["Oktober"][2][0] = "Wo"

        with self.assertRaises(ParseFout) as ctx:
            parse_orkest(aangepast(kapot))
        self.assertIn("weekdag", str(ctx.exception).lower())

    def test_ontbrekende_reed2_kolom_geeft_een_parsefout(self):
        # Alleen Oktober raakt zijn kop kwijt; de andere tabbladen houden hun
        # datarijen, zodat dit het per-tabblad-pad test en niet het
        # "geen enkele voorstelling gevonden"-pad.
        def kapot(t):
            t["Oktober"][1][16] = "Riet 2"

        with self.assertRaises(ParseFout) as ctx:
            parse_orkest(aangepast(kapot))
        self.assertIn("Oktober", str(ctx.exception))

    def test_ontbrekende_reed2_kolom_in_alle_tabbladen_geeft_ook_een_parsefout(self):
        def kapot(t):
            for rijen in t.values():
                for rij in rijen:
                    if len(rij) > 16 and rij[16] == "Reed 2":
                        rij[16] = "Riet 2"

        with self.assertRaises(ParseFout) as ctx:
            parse_orkest(aangepast(kapot))
        self.assertIn("Oktober", str(ctx.exception))

    def test_tabblad_zonder_datarijen_en_zonder_reed2_kop_wordt_stil_overgeslagen(self):
        # Een tabblad zonder enige datarij levert niets op om te missen.
        def leeg_tabblad(t):
            t["November"] = [["NOVEMBER", "", "Riet 2"]]

        vs = parse_orkest(aangepast(leeg_tabblad))
        self.assertEqual(len(vs), 7)

    def test_tijd_buiten_bereik_geeft_een_parsefout(self):
        def kapot(t):
            t["Oktober"][2][2] = "1.5"

        with self.assertRaises(ParseFout) as ctx:
            parse_orkest(aangepast(kapot))
        self.assertIn("tijd", str(ctx.exception).lower())

    def test_tijd_als_tekst_blijft_gewoon_werken(self):
        # Wordt de cel ooit als tekst opgeslagen, dan mag de parser daar niet
        # over vallen.
        def als_tekst(t):
            t["Oktober"][2][2] = "20:15"

        vs = parse_orkest(aangepast(als_tekst))
        self.assertEqual(vs[0].tijd, "20:15")

    def test_een_bestand_dat_geen_xlsx_is_geeft_een_parsefout(self):
        with self.assertRaises(ParseFout):
            parse_orkest(b"<html>Sign in to continue</html>")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Stap 3: Draai de tests en controleer dat ze falen**

Draai: `python3 -m unittest tests.test_orkest -v`
Verwacht: FAIL — `ModuleNotFoundError: No module named 'tests.orkestblad'` of,
zodra dat bestand er is, fouten omdat `parse_orkest` nog tekst verwacht en
`bytes` krijgt.

- [ ] **Stap 4: Herschrijf de parser**

Vervang de inhoud van `catscheck/orkest.py` volledig:

```python
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
```

- [ ] **Stap 5: Draai de tests en controleer dat ze slagen**

Draai: `python3 -m unittest tests.test_orkest -v`
Verwacht: PASS, 18 tests

- [ ] **Stap 6: Verwijder de oude fixture en commit**

```bash
git rm tests/fixtures/orkest.txt
git add catscheck/orkest.py tests/orkestblad.py tests/test_orkest.py
git commit -m "feat: lees de orkestlijst uit de xlsx in plaats van uit Drive's tekstweergave

De tekstweergave plakt alle rijen achter elkaar op één regel, waardoor de
parser op weekdagpatronen moest knippen en tabbladen aan een maandnaam-dubbel
moest herkennen. De xlsx houdt tabbladen, rijen en kolommen uit elkaar; drie
regex-hacks kunnen weg.

Belangrijker: de tekstweergave laat cellen vallen. Zeven Reed 2-cellen in
december kwamen er niet in, waardoor de checker dacht dat de orkestlijst daar
leeg was en vier KRITIEK-meldingen als 'nog in te vullen' wegzette.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Taak 3: De commandoregel leest het xlsx-bestand

**Bestanden:**
- Wijzigen: `catscheck/__main__.py:51` en de hulpfunctie `_lees` rond regel 79
- Wijzigen: `tests/test_main.py:9` en de plekken die `FIXTURES` als cachemap
  doorgeven

**Interfaces:**
- Gebruikt: `parse_orkest(data: bytes)` uit taak 2, `orkest_xlsx()` uit
  `tests.orkestblad`
- Levert: `python3 -m catscheck` leest `cache/orkest.xlsx`

- [ ] **Stap 1: Pas de test aan zodat hij een cachemap bouwt**

`tests/fixtures` bevat straks geen orkestbestand meer; de xlsx wordt in een
tijdelijke map gezet, uit dezelfde tabel die `tests/test_orkest.py` gebruikt.
Zo is er één bron van waarheid en staat er geen binair bestand in git.

Voeg in `tests/test_main.py` bovenaan `import shutil` toe aan de bestaande
importregels (`io`, `json`, `tempfile` en `unittest` staan er al), en daaronder:

```python
from tests.orkestblad import orkest_xlsx
```

Vervang vervolgens de regel

```python
FIXTURES = str(Path(__file__).parent / "fixtures")
```

door

```python
_TIJDELIJK = None
FIXTURES = None


def setUpModule():
    """Bouw een cachemap met alle vier de bronnen.

    De drie tekstbronnen komen uit tests/fixtures; de orkestlijst wordt uit
    tests/orkestblad.py opgebouwd, zodat de fixture leesbaar blijft en niet
    als binair bestand in git belandt.
    """
    global _TIJDELIJK, FIXTURES
    _TIJDELIJK = tempfile.TemporaryDirectory()
    FIXTURES = _TIJDELIJK.name
    bron = Path(__file__).parent / "fixtures"
    for naam in ("reed2.csv", "website.html", "agenda.ics"):
        shutil.copy(bron / naam, Path(FIXTURES) / naam)
    (Path(FIXTURES) / "orkest.xlsx").write_bytes(orkest_xlsx())


def tearDownModule():
    _TIJDELIJK.cleanup()
```

Alle `["--cache", FIXTURES, ...]`-aanroepen blijven ongewijzigd: `FIXTURES`
wijst nu naar de tijdelijke map in plaats van naar `tests/fixtures`.

- [ ] **Stap 2: Draai de test en controleer dat hij faalt**

Draai: `python3 -m unittest tests.test_main -v`
Verwacht: FAIL op `test_rapport_op_de_fixtures` met afsluitcode 2 en
"Bronbestand ontbreekt: .../orkest.txt" — `__main__` zoekt nog het oude
bestand.

- [ ] **Stap 3: Laat de commandoregel de xlsx lezen**

In `catscheck/__main__.py`, vervang

```python
        orkest = parse_orkest(_lees(args.cache / "orkest.txt"))
```

door

```python
        orkest = parse_orkest(_lees_bytes(args.cache / "orkest.xlsx"))
```

en zet naast `_lees` een tweede hulpfunctie:

```python
def _lees_bytes(pad):
    """De orkestlijst is een xlsx en dus geen tekst."""
    return Path(pad).read_bytes()
```

Pas ook de melding bij een ontbrekend bestand aan: `/cats-check` haalt de
bronnen niet meer op, het script doet dat. Vervang

```python
        print(
            f"Bronbestand ontbreekt: {fout.filename}\n"
            f"Vraag Claude de bronnen op te halen (/cats-check).",
            file=sys.stderr,
        )
```

door

```python
        print(
            f"Bronbestand ontbreekt: {fout.filename}\n"
            f"Draai eerst ./scripts/ophalen.sh.",
            file=sys.stderr,
        )
```

Werk tot slot de moduledocstring bij: het ophalen gebeurt niet meer door
Claude maar door `scripts/ophalen.sh`. Vervang

```python
"""Commandoregel voor de Cats speellijst-checker.

Leest uitsluitend lokale bestanden uit de cachemap. Doet zelf geen enkel
netwerkverzoek: het ophalen van de bronnen gebeurt door Claude, met alleen-
lees-tools.
"""
```

door

```python
"""Commandoregel voor de Cats speellijst-checker.

Leest uitsluitend lokale bestanden uit de cachemap. Doet zelf geen enkel
netwerkverzoek: het ophalen van de bronnen gebeurt door scripts/ophalen.sh.
"""
```

- [ ] **Stap 4: Draai de hele testsuite**

Draai: `python3 -m unittest discover -s tests -v`
Verwacht: PASS, alles groen

- [ ] **Stap 5: Commit**

```bash
git add catscheck/__main__.py tests/test_main.py
git commit -m "feat: lees cache/orkest.xlsx in plaats van cache/orkest.txt

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Taak 4: Het ophaalscript haalt alle vier de bronnen

**Bestanden:**
- Wijzigen: `scripts/ophalen.sh`

**Interfaces:**
- Levert: `cache/orkest.xlsx` en `cache/reed2.csv` naast de bestaande
  `cache/website.html` en `cache/agenda.ics`; afsluitcode 1 zodra één bron
  niet ververst kon worden

- [ ] **Stap 1: Voeg de twee Drive-bronnen toe**

Voeg in `scripts/ophalen.sh`, ná het ophalen van de website en vóór het blok
van de agenda, deze twee blokken toe:

```bash
# De twee Drive-bestanden zijn met hun link leesbaar; er is geen inloggen aan
# te pas. Wordt die deling ooit ingetrokken, dan levert curl een inlogpagina
# op met code 200 — daarom wordt niet op de HTTP-code gecontroleerd maar op
# de inhoud.
orkest_id="1qXIFu7Wq9SBKrBxjPqoTOqCccH65fpcg"
reed2_id="1jOjspqJjxHZdwBPgiBsyDMsyw_gy0caEHucaV5eP1rI"

echo "orkestlijst ophalen..."
if curl -sSL --fail --max-time 60 \
        "https://drive.google.com/uc?export=download&id=${orkest_id}" \
        -o "$werkmap/orkest.xlsx" \
   && python3 -c 'import sys, zipfile; sys.exit(0 if zipfile.is_zipfile(sys.argv[1]) else 1)' \
        "$werkmap/orkest.xlsx"; then
  mv "$werkmap/orkest.xlsx" cache/orkest.xlsx
else
  echo "orkestlijst ophalen mislukt; cache/orkest.xlsx blijft ongewijzigd." \
       "Is de linkdeling van het bestand gewijzigd?" >&2
  mislukt=1
fi

echo "reed 2-sheet ophalen..."
if curl -sSL --fail --max-time 30 \
        "https://docs.google.com/spreadsheets/d/${reed2_id}/export?format=csv" \
        -o "$werkmap/reed2.csv" \
   && head -1 "$werkmap/reed2.csv" | grep -q '^Speeldatum,Type'; then
  mv "$werkmap/reed2.csv" cache/reed2.csv
else
  echo "reed 2-sheet ophalen mislukt; cache/reed2.csv blijft ongewijzigd." \
       "Is de linkdeling van het bestand gewijzigd?" >&2
  mislukt=1
fi
```

- [ ] **Stap 2: Maak van elke mislukking een harde fout**

Een verouderde cache parseert vrolijk door en levert een rapport op dat
nergens over gaat. Dat mag niet stil gebeuren.

Zet boven het eerste ophaalblok:

```bash
mislukt=0
```

Voeg in de `else`-tak van het website-blok een `mislukt=1` toe onder de
bestaande melding, zodat die tak er zo uitziet:

```bash
  echo "website ophalen mislukt; cache/website.html blijft ongewijzigd" >&2
  mislukt=1
```

Vervang in het agenda-blok de directe `exit 1` door `mislukt=1`, zodat de
overige bronnen nog wel opgehaald worden. De tak eronder, die meldt dat
`config/ical_url.txt` ontbreekt, blijft een waarschuwing zonder `mislukt=1`:
zonder dat bestand is de agendacontrole bewust uitgeschakeld en is er niets
mislukt.

```bash
    echo "agenda ophalen mislukt of onvolledig; cache/agenda.ics blijft" \
         "ongewijzigd. Controleer de URL in config/ical_url.txt." >&2
    mislukt=1
```

Vervang de slotregel `echo "klaar."` door:

```bash
if [[ $mislukt -ne 0 ]]; then
  echo "een of meer bronnen zijn niet ververst; de controle draait dan op" \
       "verouderde gegevens." >&2
  exit 1
fi

echo "klaar."
```

- [ ] **Stap 3: Draai het script en controleer de uitkomst**

```bash
./scripts/ophalen.sh
echo "afsluitcode: $?"
ls -la cache/
```

Verwacht: afsluitcode 0, en `cache/orkest.xlsx` (ruim 180 kB) plus
`cache/reed2.csv` met een verse tijdstempel.

- [ ] **Stap 4: Controleer dat een kapotte bron hard faalt**

De kopie moet in `scripts/` blijven staan: het script doet
`cd "$(dirname "$0")/.."` en zou vanuit `/tmp` in een heel andere map gaan
schrijven.

```bash
cp cache/orkest.xlsx /tmp/orkest-terug.xlsx
sed 's|drive.google.com/uc|drive.google.com/bestaat-niet|' \
  scripts/ophalen.sh > scripts/ophalen-kapot.sh
chmod +x scripts/ophalen-kapot.sh
./scripts/ophalen-kapot.sh; echo "afsluitcode: $?"
cmp cache/orkest.xlsx /tmp/orkest-terug.xlsx && echo "cache ongewijzigd gebleven"
rm scripts/ophalen-kapot.sh
```

Verwacht: afsluitcode 1, een melding over de orkestlijst op stderr, en een
`cache/orkest.xlsx` die ongewijzigd is gebleven.

- [ ] **Stap 5: Verwijder de stempels en commit**

```bash
rm -f cache/stempels.json
git add scripts/ophalen.sh
git commit -m "feat: haal ook de orkestlijst en de reed 2-sheet met curl op

Beide Drive-bestanden zijn met hun link leesbaar zonder inloggen, dus hoeven
ze niet meer via het model naar de cache. Mislukt een bron, dan blijft de
cache staan en eindigt het script met code 1: doorgaan op verouderde
gegevens levert een rapport op dat nergens over gaat.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Taak 5: Skill en documentatie

**Bestanden:**
- Wijzigen: `.claude/skills/cats-check/SKILL.md`
- Wijzigen: `README.md`
- Wijzigen: `docs/superpowers/specs/2026-09-05-cats-speellijst-checker-design.md`
- Wijzigen: `docs/superpowers/specs/2026-09-06-bronnen-via-curl-design.md`

- [ ] **Stap 1: Herschrijf de werkwijze in de skill**

Let op: er staat een niet-gecommitte wijziging in dit bestand die stap 1 en 2
splitste. Die wordt hier volledig vervangen.

Vervang het hele blok van `## Werkwijze` tot en met `**Stap 4 — toelichten**`
en zijn alinea door:

```markdown
## Werkwijze

**Stap 1 — bronnen ophalen**

```bash
./scripts/ophalen.sh
```

Haalt alle vier de bronnen op naar `cache/`. Eindigt het script met code 1,
dan is er minstens één bron niet ververst; meld dan wat er misging en ga niet
verder. De controle zou dan op verouderde gegevens draaien.

**Stap 2 — controleren**

```bash
python3 -m catscheck
```

Afsluitcode 0 betekent geen verschillen, 1 betekent meldingen, 2 betekent dat
een bron niet gelezen kon worden.

**Stap 3 — toelichten**

Druk het rapport af en licht de KRITIEK-meldingen toe. Zeg er per melding bij
wat Emiel eraan kan doen: zelf zijn agenda bijwerken, het met Christof en
Michiel opnemen, of het bij Ryanne melden omdat de orkestlijst aangepast moet
worden. Dat laatste doet Emiel zelf — jij past niets aan.
```

Pas ook de alinea over alleen-lezen aan. Vervang

```markdown
Toegestaan zijn uitsluitend `read_file_content`, `download_file_content` en
`get_file_metadata`. De schrijvende Drive-tools zijn geblokkeerd in
`.claude/settings.json`; probeer die blokkade nooit te omzeilen. Vraagt iemand
om iets in te vullen, aan te passen of over te nemen in een sheet, weiger dan
en verwijs naar deze regel.
```

door

```markdown
De bronnen worden met `curl` opgehaald; er komt geen Drive-tool meer aan te
pas. De schrijvende Drive-tools zijn daarnaast geblokkeerd in
`.claude/settings.json`; probeer die blokkade nooit te omzeilen. Vraagt iemand
om iets in te vullen, aan te passen of over te nemen in een sheet, weiger dan
en verwijs naar deze regel.
```

- [ ] **Stap 2: Werk de modelparagraaf in de skill bij**

De reden wordt sterker: er gaat nu helemaal geen brondata meer door het model.
Vervang in `## Welk model hiervoor nodig is` de eerste alinea door:

```markdown
De uitkomst van deze controle hangt niet af van het model. Het ophalen doet
`scripts/ophalen.sh`, het vergelijken doet `python3 -m catscheck` — een gewoon
script zonder AI: dezelfde bronnen leveren altijd hetzelfde rapport op. Er
passeert geen enkel bronbestand het model; het start twee commando's en licht
de uitkomst toe. Het model vindt de verschillen niet — het script doet dat.
```

- [ ] **Stap 3: Werk de README bij**

Vervang in `README.md` de sectie `## Welk model` door:

```markdown
## Welk model

De controle zelf is een gewoon Python-script zonder AI; het model start het
ophalen en licht het rapport toe. Een middelzwaar model volstaat dus
ruimschoots — op dit moment Sonnet. Wisselen kan met `/model`.

Geen van de vier bronnen passeert het model. `scripts/ophalen.sh` zet ze
allemaal met `curl` rechtstreeks in `cache/`; alleen het rapport komt in het
gesprek terecht.
```

Vervang in de sectie `## Gebruiken` de regel

```markdown
./scripts/ophalen.sh          # website en agenda
```

door

```markdown
./scripts/ophalen.sh          # alle vier de bronnen
```

- [ ] **Stap 4: Markeer het oude ontwerp als achterhaald**

Zet in `docs/superpowers/specs/2026-09-05-cats-speellijst-checker-design.md`
direct onder de `Status:`-regel:

```markdown
Achterhaald op 2026-09-06 wat het ophalen betreft: alle vier de bronnen gaan
nu met `curl` naar `cache/` en de orkestlijst wordt als xlsx gelezen. Zie
`2026-09-06-bronnen-via-curl-design.md`.
```

Zet in `docs/superpowers/specs/2026-09-06-bronnen-via-curl-design.md` de
`Status:`-regel op `gebouwd (2026-09-06)`.

- [ ] **Stap 5: Commit**

```bash
git add .claude/skills/cats-check/SKILL.md README.md docs/superpowers/specs/
git commit -m "docs: werk skill en documentatie bij voor het ophalen met curl

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Taak 6: Eindcontrole op de echte bronnen

**Bestanden:** geen wijzigingen; dit is een controle.

- [ ] **Stap 1: Draai de hele keten vers**

```bash
rm -f cache/orkest.txt cache/stempels.json
./scripts/ophalen.sh && python3 -m catscheck --vanaf 2026-12-15 --alles | head -20
```

Verwacht: er staat een KRITIEK-blok in het rapport, en daarin staan in elk
geval deze twee regels:

```
  19-12-2026  jij staat ingeroosterd maar er staat niets in je agenda — 19-12-2026 14:30 REG BREDA
  19-12-2026  jij staat ingeroosterd maar er staat niets in je agenda — 19-12-2026 20:00 REG BREDA
```

Die twee kwamen er in de oude tekstroute niet uit, omdat Drive's
tekstweergave zeven Reed 2-cellen in december liet vallen; ze stonden onder
"NOG IN TE VULLEN". Het aantal meldingen eromheen ligt niet vast — dat hangt
af van wat er op dat moment in de agenda en op de website staat.

Ontbreken deze twee regels, dan leest de parser de Reed 2-kolom niet goed; ga
niet verder maar zoek dat eerst uit.

- [ ] **Stap 2: Controleer dat de hele suite groen is**

Draai: `python3 -m unittest discover -s tests -v`
Verwacht: PASS

- [ ] **Stap 3: Controleer dat er geen verwijzingen naar de oude route zijn**

```bash
grep -rn "orkest.txt\|stempels.json\|read_file_content\|download_file_content" \
  --include=*.py --include=*.sh --include=*.md --include=*.json . \
  | grep -v "docs/superpowers/"
```

Verwacht: geen enkele regel. `docs/superpowers/` is uitgesloten omdat daar de
ontwerpen en dit plan zelf staan: die citeren de oude namen met opzet, als
beschrijving van de situatie die we juist aan het vervangen zijn.

- [ ] **Stap 4: Meld de decembervondst aan Emiel**

Dit is geen code maar hoort wel bij de oplevering: hij staat op zaterdag
19 december 2026 voor twee voorstellingen in Breda ingeroosterd zonder dat er
iets in zijn agenda staat, en er staan twee agenda-items in december die bij
geen speelbeurt van hem horen. Dat kwam pas boven water door deze migratie.
