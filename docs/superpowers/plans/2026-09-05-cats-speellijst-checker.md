# Cats speellijst-checker — implementatieplan

> **Voor agentic workers:** VERPLICHTE SUB-SKILL: gebruik superpowers:subagent-driven-development (aanbevolen) of superpowers:executing-plans om dit plan taak voor taak uit te voeren. Stappen gebruiken checkbox-syntaxis (`- [ ]`) voor het bijhouden van voortgang.

**Doel:** Een alleen-lezend commandoregelprogramma dat inconsistenties opspoort tussen de orkestlijst van Cats, de reed 2-planning, musicalcats.nl en Emiels Google Agenda.

**Architectuur:** Claude haalt vier bronnen op naar `cache/` met alleen-lees-tools; het Python-pakket `catscheck` leest uitsluitend die lokale bestanden. Vier parsers vertalen elke bron naar hetzelfde `Voorstelling`-formaat, `vergelijk.py` levert `Melding`-objecten op en `rapport.py` maakt daar Nederlandse terminaltekst van.

**Tech Stack:** Python 3.14, uitsluitend standaardbibliotheek, tests met `unittest`.

## Globale randvoorwaarden

Deze gelden voor élke taak.

- **Nooit schrijven naar een bron.** Geen enkele Drive-schrijfactie, geen wijziging aan een sheet, geen agenda-item aanmaken. Het pakket doet geen enkel netwerkverzoek richting Google.
- **Uitsluitend standaardbibliotheek.** Geen pip, geen venv, geen `requirements.txt`. `pytest` is niet geïnstalleerd; tests draaien met `python3 -m unittest`.
- **Python 3.14** is aanwezig als `python3`.
- **Alle uitvoer in het Nederlands.** Meldingen, koppen en foutteksten.
- **Geheimen nooit afdrukken.** De iCal-URL uit `config/ical_url.txt` mag niet in uitvoer, logs of foutmeldingen verschijnen.
- **Bij twijfel luidruchtig falen.** Een parser die zijn structuur niet herkent gooit `ParseFout` met de betreffende regel. Nooit stilzwijgend doorgaan met een gok, want een stille misparse levert vals vertrouwen op.
- **Commit na elke taak.**

## Bestandsindeling

```
catscheck/
  __init__.py       leeg
  model.py          Voorstelling, AgendaItem, Melding, normalisatie, ParseFout
  orkest.py         parse_orkest(tekst)   -> list[Voorstelling]
  reed2.py          parse_reed2(csv_tekst)-> list[Voorstelling]
  website.py        parse_website(html)   -> list[Voorstelling]
  agenda.py         parse_agenda(ics)     -> list[AgendaItem]
  vergelijk.py      vergelijk(...)        -> list[Melding]
  rapport.py        maak_rapport(...)     -> str
  __main__.py       CLI: leest cache/, drukt rapport af
tests/
  test_model.py test_orkest.py test_reed2.py test_website.py
  test_agenda.py test_vergelijk.py test_rapport.py
  fixtures/orkest.txt reed2.csv website.html agenda.ics
scripts/ophalen.sh  curl voor website + agenda
config/trefwoorden.json
.claude/skills/cats-check/SKILL.md
.claude/settings.json
```

---

### Taak 1: Skelet, read-only blokkade en het gedeelde model

**Bestanden:**
- Aanmaken: `.claude/settings.json`
- Aanmaken: `catscheck/__init__.py` (leeg)
- Aanmaken: `catscheck/model.py`
- Aanmaken: `tests/__init__.py` (leeg)
- Aanmaken: `tests/test_model.py`

**Interfaces:**
- Levert: `ParseFout`, `Voorstelling`, `AgendaItem`, `Melding`, `Ernst`,
  `REED2_NAMEN`, `SPEEL_TYPES`, `WERK_TYPES`, `NEGEER_TYPES`,
  `normaliseer_naam(str|None) -> str|None`,
  `normaliseer_plaats(str|None) -> str|None`,
  `normaliseer_tijd(str|None) -> str|None`, `WEEKDAGEN` (afkorting -> 0..6) en
  `WEEKDAG_NAMEN` (0..6 -> afkorting).
  Alle latere taken importeren hieruit.

- [ ] **Stap 1: Zet de read-only blokkade**

Maak `.claude/settings.json`:

```json
{
  "permissions": {
    "deny": [
      "mcp__claude_ai_Google_Drive__update_file",
      "mcp__claude_ai_Google_Drive__create_file",
      "mcp__claude_ai_Google_Drive__trash_file",
      "mcp__claude_ai_Google_Drive__share_file",
      "mcp__claude_ai_Google_Drive__copy_file"
    ]
  }
}
```

- [ ] **Stap 2: Schrijf de falende test**

Maak `tests/test_model.py`:

```python
import unittest
from datetime import date

from catscheck.model import (
    Voorstelling,
    normaliseer_naam,
    normaliseer_plaats,
    normaliseer_tijd,
)


class TestNormaliseerNaam(unittest.TestCase):
    def test_spaties_en_hoofdletters_verdwijnen(self):
        self.assertEqual(normaliseer_naam("Michiel "), "michiel")

    def test_lege_waarden_worden_none(self):
        self.assertIsNone(normaliseer_naam(""))
        self.assertIsNone(normaliseer_naam("   "))
        self.assertIsNone(normaliseer_naam(None))

    def test_leeg_tussen_haakjes_telt_als_leeg(self):
        # De orkestlijst gebruikt "(leeg)" als expliciete markering.
        self.assertIsNone(normaliseer_naam("(leeg)"))


class TestNormaliseerPlaats(unittest.TestCase):
    def test_hoofdletters(self):
        self.assertEqual(normaliseer_plaats("Almere"), "ALMERE")

    def test_delamar_typefout_wordt_rechtgezet(self):
        # De orkestlijst schrijft "Amterdam DLM" met een typefout.
        self.assertEqual(normaliseer_plaats("Amterdam DLM"), "AMSTERDAM DELAMAR")
        self.assertEqual(normaliseer_plaats("Amsterdam DLM"), "AMSTERDAM DELAMAR")

    def test_gewoon_amsterdam_blijft_amsterdam(self):
        self.assertEqual(normaliseer_plaats("Amsterdam"), "AMSTERDAM")


class TestNormaliseerTijd(unittest.TestCase):
    def test_punt_wordt_dubbele_punt(self):
        self.assertEqual(normaliseer_tijd("11.30"), "11:30")

    def test_uur_krijgt_voorloopnul(self):
        self.assertEqual(normaliseer_tijd("9:00"), "09:00")

    def test_leeg_wordt_none(self):
        self.assertIsNone(normaliseer_tijd(""))
        self.assertIsNone(normaliseer_tijd(None))


class TestVoorstelling(unittest.TestCase):
    def test_is_hashbaar_zodat_hij_in_een_set_kan(self):
        v = Voorstelling(
            datum=date(2026, 10, 6), tijd="20:15", type="TO",
            plaats="ALMERE", theater=None, reed2="emiel",
            bron="orkest", herkomst="oktober rij 1",
        )
        self.assertIn(v, {v})


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Stap 3: Draai de test en stel vast dat hij faalt**

Draai: `python3 -m unittest tests.test_model -v`
Verwacht: FAIL met `ModuleNotFoundError: No module named 'catscheck'`

- [ ] **Stap 4: Schrijf `catscheck/model.py`**

```python
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

# Dagen waarop niemand van reed 2 hoeft te spelen.
NEGEER_TYPES = frozenset({"BOUW", "VRIJ"})

# Plaatsnamen die per bron anders geschreven worden. Sleutel is de
# genormaliseerde (lowercase, getrimde) vorm.
PLAATS_ALIAS = {
    "amterdam dlm": "AMSTERDAM DELAMAR",   # typefout in de orkestlijst
    "amsterdam dlm": "AMSTERDAM DELAMAR",
    "amsterdam delamar": "AMSTERDAM DELAMAR",
    "delamar": "AMSTERDAM DELAMAR",
    "'s-hertogenbosch": "DEN BOSCH",
    "s-hertogenbosch": "DEN BOSCH",
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
    type: str | None          # TO, PREM, REG, VP, S-OPT, MON, BESL, BOUW, VRIJ
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
```

- [ ] **Stap 5: Draai de tests en stel vast dat ze slagen**

Draai: `python3 -m unittest tests.test_model -v`
Verwacht: PASS, 10 tests.

- [ ] **Stap 6: Commit**

```bash
git add .claude/settings.json catscheck/ tests/
git commit -m "feat: gedeeld model en read-only blokkade"
```

---

### Taak 2: Parser voor de orkestlijst

De lastigste parser. De tekstweergave van het xlsx-bestand is géén CSV: rijen
worden gescheiden door een spatie, waardoor de laatste cel van een rij tegen de
eerste cel van de volgende aanloopt (`...,,,hans Woe,7,20:15,...`). Er wordt
daarom geknipt op het weekdagpatroon aan het begin van elke rij.

**Bestanden:**
- Aanmaken: `catscheck/orkest.py`
- Aanmaken: `tests/test_orkest.py`
- Aanmaken: `tests/fixtures/orkest.txt`

**Interfaces:**
- Gebruikt: `Voorstelling`, `ParseFout`, `normaliseer_naam`, `normaliseer_plaats`, `normaliseer_tijd` uit `catscheck.model`
- Levert: `parse_orkest(tekst: str, startjaar: int = 2026) -> list[Voorstelling]`

- [ ] **Stap 1: Leg de fixture vast**

Maak `tests/fixtures/orkest.txt` met precies deze inhoud, één regel
(overgenomen uit de echte bron, met de jaargrens en de Mamma Mia-staart erin):

```
Oktober OKTOBER,,,,,,MD,Overnachten MD,Toetsen 1,Overnachten Toetsen 1,Toetsen 2,Overnachten Toetsen 2,Toetsen 3,Overnachten Toetsen 3,Reed 1,Overnachten Reed 1,Reed 2,Overnachten Reed 2,Drums,Overnachten Drums,Gitaar,Overnachten Gitaar,Bass,Overnachten Bass,,OPMERKINGEN,BIJZITTERS Di,6,20:15,TO,Almere,,Steven,Nee,Hajo ,,Simon,,Charles ,,Marielle,,Emiel,,,,Jurgen,,Marijn,Nee,,,hans Woe,7,20:15,TO,Almere,,Steven,Nee,Hajo ,,Simon,,Charles ,,Marielle,,Emiel,,,,Jurgen,,Marijn,Nee,,, Ma,12,,,,,,,,,,,,,,,,,,,,,,,,, Vr,23,15:00,REG,Amsterdam,,Steven,Nee,Hajo ,,Hans,,Hilde,,Marielle,,Emiel,,,,Harmen,,Tim ,,,, Vr,23,20:00,REG,Amsterdam,,Steven,Nee,Hajo ,,Hans,,Hilde,,Marielle,,Emiel,,,,Harmen,,Tim ,,,, December DECEMBER,,,,,,MD,Overnachten MD,Toetsen 1,Overnachten Toetsen 1,Toetsen 2,Overnachten Toetsen 2,Toetsen 3,Overnachten Toetsen 3,Reed 1,Overnachten Reed 1,Reed 2,Overnachten Reed 2,Drums,Overnachten Drums,Gitaar,Overnachten Gitaar,Bass,Overnachten Bass,,OPMERKINGEN,BIJZITTERS Zo,13,14:30,REG,Zoetermeer,,,,Hajo ,,Hans,Nee,(leeg),,Marielle,,Emiel,,,,Harmen,,Tim ,,,, Januari Januari,,,,,,MD,Overnachten MD,Toetsen 1,Overnachten Toetsen 1,Toetsen 2,Overnachten Toetsen 2,Toetsen 3,Overnachten Toetsen 3,Reed 1,Overnachten Reed 1,Reed 2,Overnachten Reed 2,Drums,Overnachten Drums,Gitaar,Overnachten Gitaar,Bass,Overnachten Bass,,OPMERKINGEN,BIJZITTERS,BIJZITTERS Za,2,14:30,REG,Breda,,,,Tom,,,,,,Coen,,,,,,,,Marijn,,,,, Maart Maart,,,,,,MD,Overnachten MD,Toetsen 1,Overnachten Toetsen 1,Toetsen 2,Overnachten Toetsen 2,Toetsen 3,Overnachten Toetsen 3,Reed 1,Overnachten Reed 1,Reed 2,Overnachten Reed 2,Drums,Overnachten Drums,Gitaar,Overnachten Gitaar,Bass,Overnachten Bass,,OPMERKINGEN,BIJZITTERS,BIJZITTERS Woe ,31,20:00,REG,Amterdam DLM,,,,Hans,,,,,,Marielle,,Michiel ,,,,Harmen,,Tim ,,,,, Feb Mamma Mia\! the Party,,,,,,,,,,, FEBRUARI,,,,MD/Keys,Guitar 1,Guitar 2,Bass,Drums,,ABSENT,OPMERKINGEN Sun,1,11:30,,,Max,,,,,, Mon,2,,,,,,,,,,
```

- [ ] **Stap 2: Schrijf de falende tests**

Maak `tests/test_orkest.py`:

```python
import unittest
from datetime import date
from pathlib import Path

from catscheck.model import ParseFout
from catscheck.orkest import parse_orkest

FIXTURE = (Path(__file__).parent / "fixtures" / "orkest.txt").read_text(encoding="utf-8")


class TestParseOrkest(unittest.TestCase):
    def setUp(self):
        self.vs = parse_orkest(FIXTURE)

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

    def test_rommel_uit_de_opmerkingenkolom_lekt_niet_naar_de_volgende_rij(self):
        # Rij 1 eindigt op ",,,hans" en rij 2 begint met "Woe,7".
        tweede = self.vs[1]
        self.assertEqual(tweede.datum, date(2026, 10, 7))
        self.assertEqual(tweede.reed2, "emiel")

    def test_twee_voorstellingen_op_een_dag_blijven_allebei_staan(self):
        op_23 = [v for v in self.vs if v.datum == date(2026, 10, 23)]
        self.assertEqual([v.tijd for v in op_23], ["15:00", "20:00"])

    def test_jaartal_loopt_door_over_de_jaargrens(self):
        datums = [v.datum for v in self.vs]
        self.assertIn(date(2026, 12, 13), datums)   # december blijft 2026
        self.assertIn(date(2027, 1, 2), datums)     # januari wordt 2027
        self.assertIn(date(2027, 3, 31), datums)    # maart blijft 2027

    def test_naam_in_de_reed1_kolom_wordt_niet_voor_reed2_aangezien(self):
        # Januari heeft twee extra BIJZITTERS-kolommen achteraan, en Coen staat
        # er in de Reed 1-kolom terwijl Reed 2 leeg is. Coen bespeelt beide
        # stoelen, dus een parser die op een vaste kolompositie werkt in plaats
        # van op de kopnaam pikt hem hier ten onrechte op als Reed 2.
        za2 = [v for v in self.vs if v.datum == date(2027, 1, 2)][0]
        self.assertEqual(za2.tijd, "14:30")
        self.assertEqual(za2.plaats, "BREDA")
        self.assertIsNone(za2.reed2)

    def test_leeg_tussen_haakjes_in_een_andere_kolom_verstoort_niets(self):
        zo13 = [v for v in self.vs if v.datum == date(2026, 12, 13)][0]
        self.assertEqual(zo13.reed2, "emiel")

    def test_delamar_typefout_wordt_genormaliseerd(self):
        wo31 = [v for v in self.vs if v.datum == date(2027, 3, 31)][0]
        self.assertEqual(wo31.plaats, "AMSTERDAM DELAMAR")
        self.assertEqual(wo31.reed2, "michiel")

    def test_mamma_mia_blokken_worden_overgeslagen(self):
        # Die staart heeft geen Reed 2-kolom en hoort bij een andere productie.
        self.assertTrue(all(v.datum.year in (2026, 2027) for v in self.vs))
        self.assertTrue(all(v.plaats is not None for v in self.vs))
        self.assertEqual(len(self.vs), 7)


class TestValidatie(unittest.TestCase):
    def test_verkeerde_weekdag_geeft_een_parsefout(self):
        # 6 oktober 2026 is een dinsdag; "Wo" hoort een fout te geven, want dat
        # betekent dat de jaartal-afleiding is misgelopen.
        kapot = FIXTURE.replace(" Di,6,20:15,", " Wo,6,20:15,", 1)
        with self.assertRaises(ParseFout) as ctx:
            parse_orkest(kapot)
        self.assertIn("weekdag", str(ctx.exception).lower())

    def test_ontbrekende_reed2_kolom_geeft_een_parsefout(self):
        kapot = FIXTURE.replace("Reed 2,Overnachten Reed 2", "Riet 2,Overnachten Riet 2")
        with self.assertRaises(ParseFout) as ctx:
            parse_orkest(kapot)
        self.assertIn("Reed 2", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Stap 3: Draai de tests en stel vast dat ze falen**

Draai: `python3 -m unittest tests.test_orkest -v`
Verwacht: FAIL met `ModuleNotFoundError: No module named 'catscheck.orkest'`

- [ ] **Stap 4: Schrijf `catscheck/orkest.py`**

```python
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
```

- [ ] **Stap 5: Draai de tests en stel vast dat ze slagen**

Draai: `python3 -m unittest tests.test_orkest -v`
Verwacht: PASS, 11 tests.

- [ ] **Stap 6: Toets tegen de echte lijst**

Deze stap vangt af wat een fixture niet kan: onbekende weekdagafkortingen,
rare types, jaartalfouten verderop in het seizoen.

Vraag Claude de echte orkestlijst op te halen naar `cache/orkest.txt`
(`read_file_content` op `1qXIFu7Wq9SBKrBxjPqoTOqCccH65fpcg`, alleen lezen) en
draai dan:

```bash
python3 -c "
from catscheck.orkest import parse_orkest
vs = parse_orkest(open('cache/orkest.txt', encoding='utf-8').read())
print(len(vs), 'voorstellingen')
print('eerste:', vs[0].datum, vs[0].tijd, vs[0].plaats, vs[0].reed2)
print('laatste:', vs[-1].datum, vs[-1].tijd, vs[-1].plaats, vs[-1].reed2)
import collections
print('types:', collections.Counter(v.type for v in vs))
print('reed2-namen:', collections.Counter(v.reed2 for v in vs))
"
```

Verwacht: geen `ParseFout`; eerste voorstelling 2026-10-06 om 20:15 in ALMERE
met emiel; laatste 2027-06-06; bij `reed2-namen` uitsluitend `emiel`,
`christof`, `coen`, `michiel` en `None`. Staat er een andere naam tussen, dan is
dat een echte vondst en geen parserfout — noteer hem, want dat is precies een
melding die het rapport straks moet geven.

- [ ] **Stap 7: Commit**

```bash
git add catscheck/orkest.py tests/test_orkest.py tests/fixtures/orkest.txt
git commit -m "feat: parser voor de orkestlijst"
```

---

### Taak 3: Parser voor de reed 2-sheet

**Bestanden:**
- Aanmaken: `catscheck/reed2.py`
- Aanmaken: `tests/test_reed2.py`
- Aanmaken: `tests/fixtures/reed2.csv`

**Interfaces:**
- Gebruikt: `Voorstelling`, `ParseFout`, `WEEKDAGEN`, `WEEKDAG_NAMEN` en de
  normalisatiefuncties uit `catscheck.model`
- Levert: `parse_reed2(csv_tekst: str) -> list[Voorstelling]` met `bron="reed2"`

- [ ] **Stap 1: Leg de fixture vast**

Maak `tests/fixtures/reed2.csv`. Let op de titelregel bovenaan en de lege
kolommen — die moeten in de CSV-export bewaard blijven:

```
CATS REED 1,,,,,,,,
Speeldatum,Type,Aanvang,Theater,Plaats,Wie ?,Opmerking Emiel,Opmerking Christof,Opmerking Michiel
do 24-09-2026,BOUW,,Kunstlinie,ALMERE,,,,
vr 25-09-2026,MON,,Kunstlinie,ALMERE,Emiel,,,
ma 28-09-2026,VRIJ,,,,,,,
zo 11-10-2026,TO,14:30,Kunstlinie,ALMERE,Emiel,,,
vr 23-10-2026,S-OPT,15:00,Koninklijk Theater Carré,AMSTERDAM,Emiel,niet,,
vr 23-10-2026,REG,20:00,Koninklijk Theater Carré,AMSTERDAM,Emiel,niet,,
za 24-10-2026,REG,14:30,Koninklijk Theater Carré,AMSTERDAM,Michiel,,,
zo 04-10-2026,BESL,,Kunstlinie,ALMERE,Emiel,,,
```

- [ ] **Stap 2: Schrijf de falende tests**

Maak `tests/test_reed2.py`:

```python
import unittest
from datetime import date
from pathlib import Path

from catscheck.model import ParseFout
from catscheck.reed2 import parse_reed2

FIXTURE = (Path(__file__).parent / "fixtures" / "reed2.csv").read_text(encoding="utf-8")


class TestParseReed2(unittest.TestCase):
    def setUp(self):
        self.vs = parse_reed2(FIXTURE)

    def test_titelregel_boven_de_kop_wordt_overgeslagen(self):
        self.assertEqual(self.vs[0].datum, date(2026, 9, 24))

    def test_leest_datum_type_tijd_theater_plaats_en_naam(self):
        v = [x for x in self.vs if x.datum == date(2026, 10, 11)][0]
        self.assertEqual(v.tijd, "14:30")
        self.assertEqual(v.type, "TO")
        self.assertEqual(v.theater, "Kunstlinie")
        self.assertEqual(v.plaats, "ALMERE")
        self.assertEqual(v.reed2, "emiel")
        self.assertEqual(v.bron, "reed2")

    def test_dagen_zonder_aanvangstijd_krijgen_tijd_none(self):
        mon = [x for x in self.vs if x.datum == date(2026, 9, 25)][0]
        self.assertEqual(mon.type, "MON")
        self.assertIsNone(mon.tijd)
        self.assertEqual(mon.reed2, "emiel")

    def test_vrije_dagen_blijven_staan_met_lege_naam(self):
        vrij = [x for x in self.vs if x.datum == date(2026, 9, 28)][0]
        self.assertEqual(vrij.type, "VRIJ")
        self.assertIsNone(vrij.reed2)

    def test_twee_voorstellingen_op_een_dag(self):
        op23 = [x for x in self.vs if x.datum == date(2026, 10, 23)]
        self.assertEqual([x.tijd for x in op23], ["15:00", "20:00"])
        self.assertEqual([x.type for x in op23], ["S-OPT", "REG"])


class TestValidatie(unittest.TestCase):
    def test_verkeerde_weekdag_geeft_een_parsefout(self):
        kapot = FIXTURE.replace("zo 11-10-2026", "ma 11-10-2026")
        with self.assertRaises(ParseFout) as ctx:
            parse_reed2(kapot)
        self.assertIn("weekdag", str(ctx.exception).lower())

    def test_ontbrekende_kopregel_geeft_een_parsefout(self):
        with self.assertRaises(ParseFout):
            parse_reed2("alleen maar rommel,zonder,kop\n1,2,3\n")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Stap 3: Draai de tests en stel vast dat ze falen**

Draai: `python3 -m unittest tests.test_reed2 -v`
Verwacht: FAIL met `ModuleNotFoundError: No module named 'catscheck.reed2'`

- [ ] **Stap 4: Schrijf `catscheck/reed2.py`**

```python
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
```

- [ ] **Stap 5: Draai de tests en stel vast dat ze slagen**

Draai: `python3 -m unittest tests.test_reed2 -v`
Verwacht: PASS, 7 tests.

- [ ] **Stap 6: Toets tegen de echte sheet**

De CSV-export levert alleen het eerste tabblad. Laat Claude
`download_file_content` draaien op `1jOjspqJjxHZdwBPgiBsyDMsyw_gy0caEHucaV5eP1rI`
met `exportMimeType: "text/csv"`, base64-decodeer dat naar `cache/reed2.csv` en
draai:

```bash
python3 -c "
from catscheck.reed2 import parse_reed2
vs = parse_reed2(open('cache/reed2.csv', encoding='utf-8').read())
print(len(vs), 'regels')
print('eerste:', vs[0].datum, vs[0].type)
print('laatste:', vs[-1].datum, vs[-1].type)
import collections
print('types:', collections.Counter(v.type for v in vs))
print('namen:', collections.Counter(v.reed2 for v in vs))
"
```

Verwacht: geen `ParseFout`, eerste regel 2026-09-24 (BOUW), laatste regel in
juni 2027, en bij `namen` alleen de vier bekende namen plus `None`. Loopt de
lijst niet door tot juni 2027, dan staat de rest op een tweede tabblad en moet
de ophaalstap in taak 8 dat tabblad apart exporteren.

- [ ] **Stap 7: Commit**

```bash
git add catscheck/reed2.py tests/test_reed2.py tests/fixtures/reed2.csv
git commit -m "feat: parser voor de reed 2-planning"
```

---

### Taak 4: Parser voor musicalcats.nl

De eenvoudigste van de vier. De pagina bevat één tabel met vaste klassen op de
cellen: `<td class="date"><strong>DD-MM-YYYY</strong><br/>HH:MM</td>`,
`<td class="location">`, `<td class="city">`.

**Bestanden:**
- Aanmaken: `catscheck/website.py`
- Aanmaken: `tests/test_website.py`
- Aanmaken: `tests/fixtures/website.html`

**Interfaces:**
- Gebruikt: `Voorstelling`, `ParseFout`, `normaliseer_plaats`, `normaliseer_tijd`
- Levert: `parse_website(html: str) -> tuple[list[Voorstelling], bool]` — de
  voorstellingen (met `bron="website"`, `type=None` en `reed2=None`; de site
  zegt niets over bezetting) plus een vlag die zegt of de pagina *volledig*
  gelezen kon worden

- [ ] **Stap 1: Leg de fixture vast**

Maak `tests/fixtures/website.html`:

```html
<table>
<tr><th data-sort="date">Datum</th><th>Locatie</th><th>Stad</th><th></th></tr>
<tr data-salesperc="27"><td class="date" data-label="Datum"><strong>06-10-2026</strong><br/>20:15</td><td class="location" data-label="Locatie">Kunstlinie</td><td class="city" data-label="Stad">ALMERE</td><td class="buttons" data-label="Boekings">
<a href="https://kunstlinie.nl/programma/cats/" target="_blank">Boek via theater</a></td></tr>
<tr data-salesperc="3"><td class="date" data-label="Datum"><strong>17-01-2027</strong><br/>14:30</td><td class="location" data-label="Locatie">Nieuwe Luxor Theater</td><td class="city" data-label="Stad">ROTTERDAM</td><td class="buttons" data-label="Boekings">
<a href="https://luxortheater.nl/agenda/cats-55258" target="_blank">Boek via theater</a></td></tr>
<tr data-salesperc="9"><td class="date" data-label="Datum"><strong>26-11-2026</strong><br/>20:00</td><td class="location" data-label="Locatie">PLT, Theater Heerlen</td><td class="city" data-label="Stad">HEERLEN</td><td class="buttons" data-label="Boekings">
<a href="https://plt.nl/cats" target="_blank">Boek via theater</a></td></tr>
</table>
```

- [ ] **Stap 2: Schrijf de falende tests**

Maak `tests/test_website.py`:

```python
import unittest
from datetime import date
from pathlib import Path

from catscheck.model import ParseFout
from catscheck.website import parse_website

FIXTURE = (Path(__file__).parent / "fixtures" / "website.html").read_text(encoding="utf-8")


class TestParseWebsite(unittest.TestCase):
    def setUp(self):
        self.vs, self.volledig = parse_website(FIXTURE)

    def test_leest_alle_voorstellingen(self):
        self.assertEqual(len(self.vs), 3)

    def test_een_volledig_gelezen_pagina_meldt_zich_als_volledig(self):
        self.assertTrue(self.volledig)

    def test_leest_datum_tijd_theater_en_plaats(self):
        v = self.vs[0]
        self.assertEqual(v.datum, date(2026, 10, 6))
        self.assertEqual(v.tijd, "20:15")
        self.assertEqual(v.theater, "Kunstlinie")
        self.assertEqual(v.plaats, "ALMERE")
        self.assertEqual(v.bron, "website")

    def test_zegt_niets_over_type_of_bezetting(self):
        self.assertTrue(all(v.type is None for v in self.vs))
        self.assertTrue(all(v.reed2 is None for v in self.vs))

    def test_theaternaam_met_komma_blijft_heel(self):
        heerlen = [v for v in self.vs if v.plaats == "HEERLEN"][0]
        self.assertEqual(heerlen.theater, "PLT, Theater Heerlen")

    def test_jaargrens_levert_gewoon_2027_op(self):
        self.assertIn(date(2027, 1, 17), [v.datum for v in self.vs])


class TestValidatie(unittest.TestCase):
    def test_gewijzigde_opmaak_geeft_een_parsefout(self):
        # Als de site verbouwd wordt moet dat opvallen, niet stil doorlopen.
        with self.assertRaises(ParseFout):
            parse_website("<html><body><p>Binnenkort meer</p></body></html>")

    def test_een_onleesbare_rij_maakt_de_pagina_onvolledig(self):
        # Eén rij met de attributen in een andere volgorde matcht niet. De
        # overige rijen komen gewoon door, maar de vlag zegt dat er iets mist —
        # anders zou die rij later als "ontbreekt op de site" gemeld worden.
        kreupel = FIXTURE.replace(
            '<td class="date" data-label="Datum"><strong>17-01-2027</strong>',
            '<td data-label="Datum" class="date"><strong>17-01-2027</strong>',
        )
        vs, volledig = parse_website(kreupel)
        self.assertEqual(len(vs), 2)
        self.assertFalse(volledig)

    def test_een_datumcel_in_een_script_telt_niet_mee(self):
        # De echte pagina heeft een JavaScript-sjabloon dat op een datumcel
        # lijkt. Dat mag de pagina niet onvolledig maken.
        met_script = FIXTURE.replace(
            "</table>",
            '</table><script>var rij = \'<td class="date">${datum}</td>\';</script>',
        )
        vs, volledig = parse_website(met_script)
        self.assertEqual(len(vs), 3)
        self.assertTrue(volledig)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Stap 3: Draai de tests en stel vast dat ze falen**

Draai: `python3 -m unittest tests.test_website -v`
Verwacht: FAIL met `ModuleNotFoundError: No module named 'catscheck.website'`

- [ ] **Stap 4: Schrijf `catscheck/website.py`**

```python
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

# De pagina bevat een <script> met een sjabloon dat op een datumcel lijkt. Dat
# is geen voorstelling, dus scripts gaan er eerst uit.
_SCRIPT = re.compile(r"<script\b.*?</script>", re.S | re.I)

# Hoeveel datumcellen er in de tabel staan. Wijkt dat af van het aantal
# gelezen rijen, dan is de pagina maar half begrepen. Bewust soepeler dan
# _RIJ hierboven: die eist class="date" als eerste attribuut, deze niet. Zou
# de teller even streng zijn als de noemer, dan telt een onleesbare rij aan
# beide kanten weg en meldt de vlag altijd "volledig".
_DATUMCEL = re.compile(r'<td[^>]*?class="date"', re.I)


def parse_website(html):
    """Geef (voorstellingen, volledig) terug.

    `volledig` is False als er datumcellen op de pagina staan die de parser
    niet heeft kunnen lezen. De aanroeper laat de website-vergelijking dan
    achterwege in plaats van tientallen verzonnen verschillen te melden.
    """
    kaal = _SCRIPT.sub("", html)
    treffers = _RIJ.findall(kaal)
    if not treffers:
        raise ParseFout(
            "geen voorstellingen gevonden op de pagina; de opmaak van "
            "musicalcats.nl is waarschijnlijk gewijzigd"
        )
    volledig = len(treffers) == len(_DATUMCEL.findall(kaal))
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
    return voorstellingen, volledig


def _tekst(fragment):
    """Haal tags en entiteiten weg, houd de leestekens heel."""
    kaal = re.sub(r"<[^>]+>", "", fragment)
    return " ".join(htmlmod.unescape(kaal).split())
```

- [ ] **Stap 5: Draai de tests en stel vast dat ze slagen**

Draai: `python3 -m unittest tests.test_website -v`
Verwacht: PASS, 9 tests.

- [ ] **Stap 6: Toets tegen de echte pagina**

```bash
mkdir -p cache
curl -sL --max-time 30 "https://musicalcats.nl/waar-wanneer/" -o cache/website.html
python3 -c "
from catscheck.website import parse_website
vs, volledig = parse_website(open('cache/website.html', encoding='utf-8').read())
print(len(vs), 'voorstellingen; volledig gelezen:', volledig)
import collections
for (p, t), n in collections.Counter((v.plaats, v.theater) for v in vs).items():
    print(f'{n:4d}  {p:20s} {t}')
"
```

Verwacht: 165 voorstellingen verdeeld over 18 speelplaatsen, van ALMERE tot
UTRECHT, en `volledig gelezen: True`. Komt daar False uit, dan staan er
datumcellen op de pagina die de parser niet begrijpt en moet de regex mee —
dat is geen reden om de vlag weg te halen.

- [ ] **Stap 7: Commit**

```bash
git add catscheck/website.py tests/test_website.py tests/fixtures/website.html
git commit -m "feat: parser voor musicalcats.nl"
```

---

### Taak 5: Parser voor de agenda-export

**Bestanden:**
- Aanmaken: `catscheck/agenda.py`
- Aanmaken: `tests/test_agenda.py`
- Aanmaken: `tests/fixtures/agenda.ics`

**Interfaces:**
- Gebruikt: `AgendaItem`, `ParseFout` uit `catscheck.model`
- Levert: `parse_agenda(ics: str) -> tuple[list[AgendaItem], int, int]` — de
  afspraken, het aantal overgeslagen herhalende afspraken, en het aantal
  afspraken zonder begintijd die niet gelezen konden worden — plus
  `AGENDA_TIJDZONE = ZoneInfo("Europe/Amsterdam")`

Beperking, bewust: afspraken met een `RRULE` (herhalende afspraken) worden
overgeslagen. Voorstellingen herhalen niet, en het uitrekenen van herhalingen
zonder externe bibliotheek is meer risico dan het waard is. Het aantal
overgeslagen afspraken wordt geteld en onderaan het rapport gemeld.

- [ ] **Stap 1: Leg de fixture vast**

Maak `tests/fixtures/agenda.ics`. Let op de gevouwen regel bij de derde
afspraak — iCal breekt lange regels af met een spatie aan het begin:

```
BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Google Inc//Google Calendar 70.9054//EN
BEGIN:VEVENT
UID:aaa@google.com
DTSTART;TZID=Europe/Amsterdam:20261006T171500
DTEND;TZID=Europe/Amsterdam:20261006T230000
SUMMARY:Cats Almere
END:VEVENT
BEGIN:VEVENT
UID:bbb@google.com
DTSTART:20261015T160000Z
DTEND:20261015T210000Z
SUMMARY:CATS Carre
END:VEVENT
BEGIN:VEVENT
UID:ccc@google.com
DTSTART;VALUE=DATE:20261011
DTEND;VALUE=DATE:20261012
SUMMARY:Cats Almere matinee en verder nog een hele lange titel die over 
 twee regels loopt
END:VEVENT
BEGIN:VEVENT
UID:ddd@google.com
RRULE:FREQ=WEEKLY;BYDAY=MO
DTSTART;TZID=Europe/Amsterdam:20261005T100000
SUMMARY:Wekelijkse les
END:VEVENT
BEGIN:VEVENT
UID:eee@google.com
DTSTART;TZID=Europe/Amsterdam:20261020T200000
SUMMARY:Verjaardag Joost
END:VEVENT
END:VCALENDAR
```

- [ ] **Stap 2: Schrijf de falende tests**

Maak `tests/test_agenda.py`:

```python
import unittest
from datetime import date, time
from pathlib import Path

from catscheck.agenda import parse_agenda

FIXTURE = (Path(__file__).parent / "fixtures" / "agenda.ics").read_text(encoding="utf-8")


class TestParseAgenda(unittest.TestCase):
    def setUp(self):
        self.items, self.overgeslagen, self.onleesbaar = parse_agenda(FIXTURE)

    def test_leest_een_afspraak_met_tijdzone(self):
        item = [i for i in self.items if i.titel == "Cats Almere"][0]
        self.assertEqual(item.datum, date(2026, 10, 6))
        self.assertEqual(item.start, time(17, 15))

    def test_utc_wordt_omgerekend_naar_nederlandse_tijd(self):
        # 16:00 UTC in oktober is 18:00 in Amsterdam (zomertijd).
        item = [i for i in self.items if i.titel == "CATS Carre"][0]
        self.assertEqual(item.datum, date(2026, 10, 15))
        self.assertEqual(item.start, time(18, 0))

    def test_afspraak_van_een_hele_dag_heeft_geen_starttijd(self):
        item = [i for i in self.items if i.datum == date(2026, 10, 11)][0]
        self.assertIsNone(item.start)

    def test_gevouwen_regels_worden_weer_aan_elkaar_geplakt(self):
        item = [i for i in self.items if i.datum == date(2026, 10, 11)][0]
        self.assertEqual(
            item.titel,
            "Cats Almere matinee en verder nog een hele lange titel die over twee regels loopt",
        )

    def test_herhalende_afspraken_worden_overgeslagen_en_geteld(self):
        self.assertNotIn("Wekelijkse les", [i.titel for i in self.items])
        self.assertEqual(self.overgeslagen, 1)

    def test_niet_cats_afspraken_blijven_gewoon_staan(self):
        # Filteren op trefwoord gebeurt later, in vergelijk.py.
        self.assertIn("Verjaardag Joost", [i.titel for i in self.items])
        self.assertEqual(self.onleesbaar, 0)

    def test_afspraak_zonder_begintijd_wordt_geteld_niet_stil_weggegooid(self):
        # Een VEVENT zonder DTSTART valt niet te plaatsen. Hij mag niet
        # geruisloos verdwijnen: het rapport moet kunnen melden dat de
        # controle niet over alles ging.
        kapot = FIXTURE.replace(
            "DTSTART;TZID=Europe/Amsterdam:20261020T200000\n", ""
        )
        items, herhalend, onleesbaar = parse_agenda(kapot)
        self.assertEqual(onleesbaar, 1)
        self.assertNotIn("Verjaardag Joost", [i.titel for i in items])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Stap 3: Draai de tests en stel vast dat ze falen**

Draai: `python3 -m unittest tests.test_agenda -v`
Verwacht: FAIL met `ModuleNotFoundError: No module named 'catscheck.agenda'`

- [ ] **Stap 4: Schrijf `catscheck/agenda.py`**

```python
"""Parser voor de iCal-export van Emiels Google Agenda.

Alleen lezen: een iCal-URL kan per definitie niets wijzigen.
"""

import re
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

from catscheck.model import AgendaItem, ParseFout

AGENDA_TIJDZONE = ZoneInfo("Europe/Amsterdam")

_DATUMTIJD = re.compile(r"^(\d{8})T(\d{6})(Z?)$")
_DATUM = re.compile(r"^(\d{8})$")


def parse_agenda(ics):
    """Geef (afspraken, herhalend_overgeslagen, onleesbaar) terug.

    Herhalende afspraken worden overgeslagen. Een VEVENT zonder DTSTART kan
    niet geplaatst worden en wordt evenmin gelezen. Beide aantallen komen mee
    terug, zodat het rapport kan melden dat de controle niet volledig was in
    plaats van er stilzwijgend overheen te stappen.
    """
    regels = _ontvouw(ics)
    if not any(r.startswith("BEGIN:VCALENDAR") for r in regels):
        raise ParseFout("dit lijkt geen iCal-bestand; is de agenda-URL nog geldig?")

    items = []
    overgeslagen = 0
    onleesbaar = 0
    huidig = None
    for regel in regels:
        if regel == "BEGIN:VEVENT":
            huidig = {}
            continue
        if regel == "END:VEVENT":
            if huidig is None:
                continue
            if "RRULE" in huidig:
                overgeslagen += 1
            elif "DTSTART" in huidig:
                items.append(_maak_item(huidig))
            else:
                # Zonder begintijd valt niet te zeggen wanneer dit is. Niet
                # stil weggooien: tellen, zodat het rapport het kan melden.
                onleesbaar += 1
            huidig = None
            continue
        if huidig is None:
            continue
        sleutel, _, waarde = regel.partition(":")
        naam = sleutel.split(";")[0].upper()
        if naam in ("DTSTART", "SUMMARY", "UID", "RRULE"):
            huidig[naam] = waarde
            if naam == "DTSTART":
                huidig["DTSTART_PARAMS"] = sleutel
    return items, overgeslagen, onleesbaar


def _ontvouw(ics):
    """Plak gevouwen iCal-regels weer aan elkaar.

    Een regel die met een spatie of tab begint hoort bij de vorige regel.
    """
    regels = []
    for ruw in ics.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if ruw[:1] in (" ", "\t") and regels:
            regels[-1] += ruw[1:]
        else:
            regels.append(ruw)
    return [r for r in regels if r]


def _maak_item(velden):
    ruw = velden["DTSTART"].strip()
    params = velden.get("DTSTART_PARAMS", "")

    m = _DATUMTIJD.match(ruw)
    if m:
        jjjjmmdd, hhmmss, is_utc = m.groups()
        naief = datetime.strptime(jjjjmmdd + hhmmss, "%Y%m%d%H%M%S")
        if is_utc:
            lokaal = naief.replace(tzinfo=timezone.utc).astimezone(AGENDA_TIJDZONE)
        else:
            tzid = _tzid(params)
            lokaal = naief.replace(tzinfo=tzid).astimezone(AGENDA_TIJDZONE)
        return AgendaItem(
            datum=lokaal.date(),
            start=time(lokaal.hour, lokaal.minute),
            titel=_titel(velden),
            herkomst=velden.get("UID", ""),
        )

    m = _DATUM.match(ruw)
    if m:
        d = datetime.strptime(m.group(1), "%Y%m%d").date()
        return AgendaItem(datum=d, start=None, titel=_titel(velden), herkomst=velden.get("UID", ""))

    raise ParseFout(f"onbegrijpelijke DTSTART in de agenda: {ruw!r}")


def _tzid(params):
    m = re.search(r"TZID=([^;:]+)", params)
    if not m:
        return AGENDA_TIJDZONE
    try:
        return ZoneInfo(m.group(1))
    except Exception:
        return AGENDA_TIJDZONE


def _titel(velden):
    ruw = velden.get("SUMMARY", "")
    # iCal ontsnapt komma's, puntkomma's en regeleindes met een backslash.
    ontsnapt = ruw.replace("\\,", ",").replace("\\;", ";").replace("\\n", " ")
    return " ".join(ontsnapt.split())
```

- [ ] **Stap 5: Draai de tests en stel vast dat ze slagen**

Draai: `python3 -m unittest tests.test_agenda -v`
Verwacht: PASS, 7 tests.

- [ ] **Stap 6: Commit**

```bash
git add catscheck/agenda.py tests/test_agenda.py tests/fixtures/agenda.ics
git commit -m "feat: parser voor de agenda-export"
```

---

### Taak 6: De vergelijking

Het hart van het programma. Alle regels uit het spec komen hier samen.

**Bestanden:**
- Aanmaken: `catscheck/vergelijk.py`
- Aanmaken: `tests/test_vergelijk.py`
- Aanmaken: `config/trefwoorden.json`

**Interfaces:**
- Gebruikt: `Voorstelling`, `AgendaItem`, `Melding`, `Ernst`, `REED2_NAMEN`,
  `SPEEL_TYPES`, `WERK_TYPES`, `NEGEER_TYPES`
- Levert:
  - `Instellingen(marge_voor_minuten=240, marge_na_minuten=30, trefwoorden=("cats",), mijn_naam="emiel")`
  - `vergelijk(orkest, reed2, website, agenda, instellingen, vanaf) -> list[Melding]`

- [ ] **Stap 1: Maak `config/trefwoorden.json`**

```json
{
  "mijn_naam": "emiel",
  "marge_voor_minuten": 240,
  "marge_na_minuten": 30,
  "trefwoorden": ["cats"]
}
```

- [ ] **Stap 2: Schrijf de falende tests**

Maak `tests/test_vergelijk.py`:

```python
import unittest
from datetime import date, time

from catscheck.model import AgendaItem, Ernst, Voorstelling
from catscheck.vergelijk import Instellingen, vergelijk

VANAF = date(2026, 1, 1)
INST = Instellingen()


def v(bron, dag, tijd, reed2=None, plaats="ALMERE", soort="REG", theater=None):
    return Voorstelling(
        datum=dag, tijd=tijd, type=soort, plaats=plaats, theater=theater,
        reed2=reed2, bron=bron, herkomst="test",
    )


def leeg():
    return []


class TestBezetting(unittest.TestCase):
    def test_naamverschil_met_emiel_is_kritiek(self):
        m = vergelijk(
            [v("orkest", date(2026, 10, 22), "20:00", "christof")],
            [v("reed2", date(2026, 10, 22), "20:00", "emiel")],
            leeg(), leeg(), INST, VANAF,
        )
        kritiek = [x for x in m if x.ernst is Ernst.KRITIEK]
        self.assertEqual(len(kritiek), 1)
        self.assertIn("christof", kritiek[0].tekst)
        self.assertIn("emiel", kritiek[0].tekst)

    def test_naamverschil_tussen_collegas_is_een_verschil_geen_kritiek(self):
        m = vergelijk(
            [v("orkest", date(2026, 10, 22), "20:00", "christof")],
            [v("reed2", date(2026, 10, 22), "20:00", "michiel")],
            leeg(), leeg(), INST, VANAF,
        )
        self.assertEqual([x.ernst for x in m], [Ernst.VERSCHIL])

    def test_onbekende_naam_bij_reed2_is_altijd_kritiek(self):
        m = vergelijk(
            [v("orkest", date(2026, 10, 22), "20:00", "marielle")],
            [v("reed2", date(2026, 10, 22), "20:00", "michiel")],
            leeg(), leeg(), INST, VANAF,
        )
        kritiek = [x for x in m if x.ernst is Ernst.KRITIEK]
        self.assertEqual(len(kritiek), 1)
        self.assertIn("marielle", kritiek[0].tekst)

    def test_lege_cel_in_de_orkestlijst_is_open(self):
        m = vergelijk(
            [v("orkest", date(2026, 10, 22), "20:00", None)],
            [v("reed2", date(2026, 10, 22), "20:00", "michiel")],
            leeg(), leeg(), INST, VANAF,
        )
        self.assertEqual([x.ernst for x in m], [Ernst.OPEN])

    def test_gelijke_bezetting_levert_niets_op(self):
        m = vergelijk(
            [v("orkest", date(2026, 10, 22), "20:00", "emiel")],
            [v("reed2", date(2026, 10, 22), "20:00", "emiel")],
            leeg(),
            [AgendaItem(date(2026, 10, 22), time(17, 0), "Cats Almere", "x")],
            INST, VANAF,
        )
        self.assertEqual(m, [])


class TestVoorstellingen(unittest.TestCase):
    def test_verschillende_aanvangstijd_wordt_gemeld_als_tijdsverschil(self):
        m = vergelijk(
            [v("orkest", date(2026, 10, 11), "15:00", "emiel")],
            [v("reed2", date(2026, 10, 11), "14:30", "emiel")],
            leeg(),
            [AgendaItem(date(2026, 10, 11), time(12, 30), "Cats", "x")],
            INST, VANAF,
        )
        tijden = [x for x in m if "15:00" in x.tekst and "14:30" in x.tekst]
        self.assertEqual(len(tijden), 1)
        self.assertIs(tijden[0].ernst, Ernst.VERSCHIL)

    def test_verschillende_plaats_wordt_gemeld(self):
        m = vergelijk(
            [v("orkest", date(2027, 5, 20), "19:45", "emiel", plaats="DEN BOSCH")],
            [v("reed2", date(2027, 5, 20), "19:45", "emiel", plaats="DEN HAAG")],
            leeg(),
            [AgendaItem(date(2027, 5, 20), time(17, 0), "Cats", "x")],
            INST, VANAF,
        )
        self.assertTrue(any("DEN BOSCH" in x.tekst and "DEN HAAG" in x.tekst for x in m))

    def test_dag_met_twee_shows_tegenover_een_dag_met_een_show(self):
        m = vergelijk(
            [v("orkest", date(2026, 10, 24), "15:00", "michiel"),
             v("orkest", date(2026, 10, 24), "20:00", "michiel")],
            [v("reed2", date(2026, 10, 24), "20:00", "michiel")],
            leeg(), leeg(), INST, VANAF,
        )
        self.assertTrue(any("aantal voorstellingen" in x.tekst.lower() for x in m))

    def test_website_verschil_is_alleen_informatief(self):
        m = vergelijk(
            [v("orkest", date(2027, 5, 20), "19:45", "michiel", plaats="DEN BOSCH")],
            [v("reed2", date(2027, 5, 20), "19:45", "michiel", plaats="DEN BOSCH")],
            [v("website", date(2027, 5, 20), "19:45", None, plaats="DEN HAAG")],
            leeg(), INST, VANAF,
        )
        self.assertEqual([x.ernst for x in m], [Ernst.WEBSITE])


class TestOnbekendType(unittest.TestCase):
    def test_onbekend_type_wordt_gemeld_in_plaats_van_stil_overgeslagen(self):
        # "OVERSTA DAG" staat echt in de orkestlijst. Zo'n regel valt buiten
        # elke vergelijking; dat mag hij, maar niet zonder het te zeggen.
        m = vergelijk(
            [v("orkest", date(2027, 2, 7), None, None, soort="OVERSTA DAG")],
            leeg(), leeg(), leeg(), INST, VANAF,
        )
        self.assertEqual(len(m), 1)
        self.assertIn("OVERSTA DAG", m[0].tekst)
        self.assertIs(m[0].ernst, Ernst.VERSCHIL)

    def test_onbekend_type_op_jouw_naam_is_kritiek(self):
        # Een typefout in de typekolom zou anders een voorstelling van Emiel
        # geruisloos uit de controle laten verdwijnen.
        m = vergelijk(
            [v("orkest", date(2027, 2, 7), "20:00", "emiel", soort="REGG")],
            leeg(), leeg(), leeg(), INST, VANAF,
        )
        self.assertEqual([x.ernst for x in m], [Ernst.KRITIEK])
        self.assertIn("REGG", m[0].tekst)


class TestAgenda(unittest.TestCase):
    def test_speelbeurt_zonder_agenda_item_is_kritiek(self):
        m = vergelijk(
            [v("orkest", date(2026, 10, 6), "20:15", "emiel")],
            [v("reed2", date(2026, 10, 6), "20:15", "emiel")],
            leeg(), leeg(), INST, VANAF,
        )
        self.assertEqual([x.ernst for x in m], [Ernst.KRITIEK])
        self.assertIn("agenda", m[0].tekst.lower())

    def test_agenda_item_vier_uur_voor_aanvang_telt_als_gevonden(self):
        m = vergelijk(
            [v("orkest", date(2026, 10, 6), "20:15", "emiel")],
            [v("reed2", date(2026, 10, 6), "20:15", "emiel")],
            leeg(),
            [AgendaItem(date(2026, 10, 6), time(16, 15), "Cats Almere", "x")],
            INST, VANAF,
        )
        self.assertEqual(m, [])

    def test_agenda_item_ruim_te_vroeg_valt_buiten_het_venster(self):
        m = vergelijk(
            [v("orkest", date(2026, 10, 6), "20:15", "emiel")],
            [v("reed2", date(2026, 10, 6), "20:15", "emiel")],
            leeg(),
            [AgendaItem(date(2026, 10, 6), time(9, 0), "Cats Almere", "x")],
            INST, VANAF,
        )
        self.assertEqual([x.ernst for x in m], [Ernst.KRITIEK])

    def test_verkeerde_tijd_meldt_de_tijd_en_niet_dat_het_ontbreekt(self):
        # Staat het item op dezelfde dag maar ver buiten het venster, dan is de
        # tijd verkeerd genoteerd. Eén melding daarover — niet twee meldingen
        # die allebei het tegendeel beweren.
        m = vergelijk(
            [v("orkest", date(2026, 10, 6), "20:15", "emiel")],
            [v("reed2", date(2026, 10, 6), "20:15", "emiel")],
            leeg(),
            [AgendaItem(date(2026, 10, 6), time(9, 0), "Cats Almere", "x")],
            INST, VANAF,
        )
        self.assertEqual(len(m), 1)
        self.assertIn("09:00", m[0].tekst)
        self.assertIn("20:15", m[0].tekst)
        self.assertNotIn("niets in je agenda", m[0].tekst)

    def test_agenda_item_na_aanvang_valt_buiten_het_venster(self):
        m = vergelijk(
            [v("orkest", date(2026, 10, 6), "20:15", "emiel")],
            [v("reed2", date(2026, 10, 6), "20:15", "emiel")],
            leeg(),
            [AgendaItem(date(2026, 10, 6), time(21, 30), "Cats Almere", "x")],
            INST, VANAF,
        )
        self.assertEqual([x.ernst for x in m], [Ernst.KRITIEK])

    def test_hele_dag_item_telt_als_aanwezig_maar_meldt_dat_de_tijd_niet_toetsbaar_is(self):
        m = vergelijk(
            [v("orkest", date(2026, 10, 6), "20:15", "emiel")],
            [v("reed2", date(2026, 10, 6), "20:15", "emiel")],
            leeg(),
            [AgendaItem(date(2026, 10, 6), None, "Cats Almere", "x")],
            INST, VANAF,
        )
        self.assertEqual(len(m), 1)
        self.assertIn("hele dag", m[0].tekst.lower())

    def test_cats_agenda_item_zonder_speelbeurt_is_kritiek(self):
        m = vergelijk(
            leeg(), leeg(), leeg(),
            [AgendaItem(date(2026, 10, 7), time(17, 0), "Cats Almere", "x")],
            INST, VANAF,
        )
        self.assertEqual([x.ernst for x in m], [Ernst.KRITIEK])
        self.assertIn("geen speelbeurt", m[0].tekst.lower())

    def test_twee_shows_op_een_dag_pikken_elkaars_agenda_item_niet_in(self):
        # Bij 14:00 en 18:00 overlappen de vensters van vier uur. Wie per beurt
        # het dichtstbijzijnde item pakt, laat de matinee het item van de avond
        # inpikken en meldt daarna twee dingen die allebei onwaar zijn.
        m = vergelijk(
            [v("orkest", date(2026, 11, 7), "14:00", "emiel"),
             v("orkest", date(2026, 11, 7), "18:00", "emiel")],
            [v("reed2", date(2026, 11, 7), "14:00", "emiel"),
             v("reed2", date(2026, 11, 7), "18:00", "emiel")],
            leeg(),
            [AgendaItem(date(2026, 11, 7), time(10, 5), "Cats matinee", "a"),
             AgendaItem(date(2026, 11, 7), time(14, 15), "Cats avond", "b")],
            INST, VANAF,
        )
        self.assertEqual(m, [])

    def test_ontbrekend_item_wijst_de_juiste_voorstelling_aan(self):
        # Alleen een afspraak voor de avondvoorstelling. Dan moet de matinee
        # als ontbrekend gemeld worden, niet de avond.
        m = vergelijk(
            [v("orkest", date(2027, 5, 21), "15:00", "emiel"),
             v("orkest", date(2027, 5, 21), "19:45", "emiel")],
            [v("reed2", date(2027, 5, 21), "15:00", "emiel"),
             v("reed2", date(2027, 5, 21), "19:45", "emiel")],
            leeg(),
            [AgendaItem(date(2027, 5, 21), time(16, 0), "Cats avond", "b")],
            INST, VANAF,
        )
        self.assertEqual(len(m), 1)
        self.assertIn("15:00", m[0].tekst)
        self.assertIn("niets in je agenda", m[0].tekst)

    def test_agenda_item_zonder_trefwoord_wordt_genegeerd(self):
        m = vergelijk(
            leeg(), leeg(), leeg(),
            [AgendaItem(date(2026, 10, 7), time(17, 0), "Verjaardag Joost", "x")],
            INST, VANAF,
        )
        self.assertEqual(m, [])

    def test_repetitiedag_uit_de_reed2_sheet_telt_mee_voor_de_agenda(self):
        m = vergelijk(
            leeg(),
            [v("reed2", date(2026, 9, 25), None, "emiel", soort="MON")],
            leeg(), leeg(), INST, VANAF,
        )
        self.assertEqual([x.ernst for x in m], [Ernst.KRITIEK])

    def test_vrije_dagen_leveren_niets_op(self):
        m = vergelijk(
            leeg(),
            [v("reed2", date(2026, 9, 28), None, None, soort="VRIJ", plaats=None)],
            leeg(), leeg(), INST, VANAF,
        )
        self.assertEqual(m, [])


class TestVanaf(unittest.TestCase):
    def test_voorstellingen_voor_de_peildatum_worden_overgeslagen(self):
        m = vergelijk(
            [v("orkest", date(2026, 10, 6), "20:15", "christof")],
            [v("reed2", date(2026, 10, 6), "20:15", "emiel")],
            leeg(), leeg(), INST, date(2026, 11, 1),
        )
        self.assertEqual(m, [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Stap 3: Draai de tests en stel vast dat ze falen**

Draai: `python3 -m unittest tests.test_vergelijk -v`
Verwacht: FAIL met `ModuleNotFoundError: No module named 'catscheck.vergelijk'`

- [ ] **Stap 4: Schrijf `catscheck/vergelijk.py`**

```python
"""Vergelijk de vier bronnen en lever bevindingen op.

Voorstellingen worden gekoppeld op datum, niet op datum plus tijd. Anders leest
een verschil van 14:30 tegenover 15:00 als twee ontbrekende voorstellingen in
plaats van als één tijdsverschil.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from catscheck.model import (
    Ernst,
    Melding,
    NEGEER_TYPES,
    REED2_NAMEN,
    SPEEL_TYPES,
    WERK_TYPES,
)


@dataclass(frozen=True)
class Instellingen:
    mijn_naam: str = "emiel"
    # Vier uur vooraf, een half uur erna. Emiel zet een matinee-afspraak
    # standaard op 12:00; bij een voorstelling om 15:00 zou drie uur precies
    # de grens zijn, dus daar zit geen speling in.
    marge_voor_minuten: int = 240
    marge_na_minuten: int = 30
    trefwoorden: tuple = ("cats",)


def vergelijk(orkest, reed2, website, agenda, instellingen, vanaf):
    """Geef alle bevindingen terug, ongesorteerd."""
    meldingen = []
    meldingen += _onbekende_types(orkest, reed2, instellingen, vanaf)
    meldingen += _vergelijk_bronnen(orkest, reed2, instellingen, vanaf)
    meldingen += _vergelijk_website(orkest, website, vanaf)
    meldingen += _vergelijk_agenda(orkest, reed2, agenda, instellingen, vanaf)
    return meldingen


# --- regels die we niet begrijpen ------------------------------------------

BRONNAAM = {
    "orkest": "de orkestlijst",
    "reed2": "jullie reed 2-sheet",
    "website": "musicalcats.nl",
}


def _onbekende_types(orkest, reed2, inst, vanaf):
    """Meld regels met een type dat in geen enkele verzameling voorkomt.

    Zo'n regel valt buiten elke vergelijking. Zonder deze melding laat een
    typefout in de typekolom een hele voorstelling verdwijnen — inclusief een
    naamverschil dat Emiel raakt. Liever een regel die je kunt negeren dan een
    voorstelling die je nooit ziet.
    """
    bekend = SPEEL_TYPES | WERK_TYPES | NEGEER_TYPES
    meldingen = []
    for v in list(orkest) + list(reed2):
        if v.datum < vanaf or v.type is None or v.type in bekend:
            continue
        meldingen.append(Melding(
            Ernst.KRITIEK if v.reed2 == inst.mijn_naam else Ernst.VERSCHIL,
            v.datum,
            f"onbekend type {v.type!r} in {BRONNAAM.get(v.bron, v.bron)} — "
            f"deze voorstelling is niet gecontroleerd",
            (f"{v.bron}: {v.herkomst}",),
        ))
    return meldingen


# --- orkestlijst tegenover de reed 2-sheet ---------------------------------

def _vergelijk_bronnen(orkest, reed2, inst, vanaf):
    meldingen = []
    per_dag_o = _per_dag(orkest, vanaf)
    per_dag_r = _per_dag(reed2, vanaf, alleen_met_publiek=True)

    for dag in sorted(set(per_dag_o) | set(per_dag_r)):
        o, r = per_dag_o.get(dag, []), per_dag_r.get(dag, [])
        if o and r and len(o) != len(r):
            meldingen.append(Melding(
                Ernst.VERSCHIL, dag,
                f"aantal voorstellingen verschilt: orkestlijst {len(o)}, reed 2-sheet {len(r)}",
                tuple(_omschrijf(x) for x in o + r),
            ))
            continue
        for a, b in zip(o, r):
            meldingen += _vergelijk_paar(dag, a, b, inst)
    return meldingen


def _vergelijk_paar(dag, o, r, inst):
    meldingen = []
    if o.reed2 and o.reed2 not in REED2_NAMEN:
        meldingen.append(Melding(
            Ernst.KRITIEK, dag,
            f"onbekende naam bij Reed 2 in de orkestlijst: {o.reed2!r} — "
            f"dit hoort Emiel, Christof, Coen of Michiel te zijn",
            (f"orkestlijst: {o.herkomst}",),
        ))
    elif o.reed2 is None and r.reed2 is not None:
        meldingen.append(Melding(
            Ernst.OPEN, dag,
            f"orkestlijst nog leeg bij Reed 2; jullie sheet zegt {r.reed2}",
        ))
    elif o.reed2 != r.reed2 and r.reed2 is not None:
        raakt_mij = inst.mijn_naam in (o.reed2, r.reed2)
        meldingen.append(Melding(
            Ernst.KRITIEK if raakt_mij else Ernst.VERSCHIL, dag,
            f"Reed 2 verschilt: orkestlijst {o.reed2}, jullie sheet {r.reed2}",
            (f"{_omschrijf(o)} / {_omschrijf(r)}",),
        ))

    if o.tijd and r.tijd and o.tijd != r.tijd:
        meldingen.append(Melding(
            Ernst.VERSCHIL, dag,
            f"aanvangstijd verschilt: orkestlijst {o.tijd}, jullie sheet {r.tijd}",
        ))
    if o.type and r.type and o.type != r.type:
        meldingen.append(Melding(
            Ernst.VERSCHIL, dag,
            f"type verschilt: orkestlijst {o.type}, jullie sheet {r.type}",
        ))
    if o.plaats and r.plaats and o.plaats != r.plaats:
        meldingen.append(Melding(
            Ernst.VERSCHIL, dag,
            f"plaats verschilt: orkestlijst {o.plaats}, jullie sheet {r.plaats}",
        ))
    return meldingen


# --- orkestlijst tegenover de website --------------------------------------

def _vergelijk_website(orkest, website, vanaf):
    # Is een van beide lijsten leeg, dan is er niets te vergelijken. Zonder deze
    # afslag zou een mislukte ophaalactie elke voorstelling als verschil melden.
    if not orkest or not website:
        return []
    meldingen = []
    per_dag_o = _per_dag(orkest, vanaf)
    per_dag_w = _per_dag(website, vanaf)

    for dag in sorted(set(per_dag_o) | set(per_dag_w)):
        o, w = per_dag_o.get(dag, []), per_dag_w.get(dag, [])
        if not o:
            meldingen.append(Melding(
                Ernst.WEBSITE, dag,
                f"staat wel op musicalcats.nl ({len(w)}x) maar niet in de orkestlijst",
                tuple(_omschrijf(x) for x in w),
            ))
            continue
        if not w:
            meldingen.append(Melding(
                Ernst.WEBSITE, dag,
                f"staat wel in de orkestlijst ({len(o)}x) maar niet op musicalcats.nl",
                tuple(_omschrijf(x) for x in o),
            ))
            continue
        if len(o) != len(w):
            meldingen.append(Melding(
                Ernst.WEBSITE, dag,
                f"aantal voorstellingen verschilt van musicalcats.nl: "
                f"orkestlijst {len(o)}, site {len(w)}",
            ))
            continue
        for a, b in zip(o, w):
            if a.tijd and b.tijd and a.tijd != b.tijd:
                meldingen.append(Melding(
                    Ernst.WEBSITE, dag,
                    f"aanvangstijd wijkt af van de site: orkestlijst {a.tijd}, site {b.tijd}",
                ))
            if a.plaats and b.plaats and a.plaats != b.plaats:
                meldingen.append(Melding(
                    Ernst.WEBSITE, dag,
                    f"plaats wijkt af van de site: orkestlijst {a.plaats}, "
                    f"site {b.plaats} ({b.theater})",
                ))
    return meldingen


# --- speelbeurten tegenover de agenda --------------------------------------

def _vergelijk_agenda(orkest, reed2, agenda, inst, vanaf):
    meldingen = []
    beurten_per_dag = defaultdict(list)
    for beurt in _mijn_speelbeurten(orkest, reed2, inst, vanaf):
        beurten_per_dag[beurt.datum].append(beurt)

    items_per_dag = defaultdict(list)
    for item in agenda:
        if item.datum >= vanaf and any(
            t in item.titel.lower() for t in inst.trefwoorden
        ):
            items_per_dag[item.datum].append(item)
    for dag in items_per_dag:
        # Items zonder tijd achteraan: die zijn nergens op te sorteren.
        items_per_dag[dag].sort(
            key=lambda i: (i.start is None, i.start or time(0, 0))
        )

    for dag in sorted(set(beurten_per_dag) | set(items_per_dag)):
        beurten = beurten_per_dag.get(dag, [])
        items = items_per_dag.get(dag, [])
        koppeling = _beste_koppeling(beurten, items, inst)
        gekoppelde_beurten = {b for b, _ in koppeling}
        vrij = [j for j in range(len(items)) if j not in {i for _, i in koppeling}]

        for b, j in koppeling:
            if items[j].start is None:
                meldingen.append(Melding(
                    Ernst.KRITIEK, dag,
                    f"agenda-item duurt de hele dag, de tijd is dus niet te "
                    f"controleren — {_omschrijf(beurten[b])}",
                    (f"agenda: {items[j].titel}",),
                ))

        for b, beurt in enumerate(beurten):
            if b in gekoppelde_beurten:
                continue
            if vrij:
                # Er staat wel iets die dag, maar op een tijd die niet kan
                # kloppen. Dat is één melding over een verkeerde tijd — niet
                # een ontbrekende plus een overtollige afspraak, want die
                # zouden allebei het tegendeel beweren van wat er aan de hand is.
                j = min(vrij, key=lambda k: _afstand(items[k], beurt))
                vrij.remove(j)
                klok = (items[j].start.strftime("%H:%M")
                        if items[j].start else "de hele dag")
                meldingen.append(Melding(
                    Ernst.KRITIEK, dag,
                    f"agenda-item staat op {klok} maar de voorstelling begint "
                    f"om {beurt.tijd} — {_omschrijf(beurt)}",
                    (f"agenda: {items[j].titel}",),
                ))
            else:
                meldingen.append(Melding(
                    Ernst.KRITIEK, dag,
                    f"jij staat ingeroosterd maar er staat niets in je agenda — "
                    f"{_omschrijf(beurt)}",
                ))

        for j in vrij:
            meldingen.append(Melding(
                Ernst.KRITIEK, dag,
                f"agenda-item {items[j].titel!r} hoort bij geen speelbeurt van jou",
                (f"start {items[j].start.strftime('%H:%M') if items[j].start else 'hele dag'}",),
            ))
    return meldingen


def _beste_koppeling(beurten, items, inst):
    """Koppel de agenda-items van één dag aan de speelbeurten van die dag.

    Geeft een lijst (index_beurt, index_item) terug. Gezocht wordt naar de
    toewijzing die de meeste beurten binnen hun venster koppelt, en bij
    gelijke stand naar die met de kleinste totale afwijking.

    Per beurt greedy het dichtstbijzijnde item pakken gaat mis zodra twee
    vensters elkaar overlappen: de vroegste beurt pikt dan het item in dat bij
    de latere hoort, waarna er twee meldingen ontstaan die allebei onjuist
    zijn. Een speeldag telt hooguit een handvol voorstellingen, dus alle
    varianten aflopen kost niets.
    """
    mogelijk = [
        [j for j in range(len(items)) if _past_in_venster(items[j], beurt, inst)]
        for beurt in beurten
    ]
    beste = []
    beste_score = None

    def zoek(b, gekozen, bezet, afstand):
        nonlocal beste, beste_score
        if b == len(beurten):
            score = (-len(gekozen), afstand)
            if beste_score is None or score < beste_score:
                beste_score, beste = score, list(gekozen)
            return
        for j in mogelijk[b]:
            if j in bezet:
                continue
            gekozen.append((b, j))
            zoek(b + 1, gekozen, bezet | {j},
                 afstand + _afstand(items[j], beurten[b]))
            gekozen.pop()
        # Deze beurt zonder item laten is ook een mogelijkheid.
        zoek(b + 1, gekozen, bezet, afstand)

    zoek(0, [], frozenset(), timedelta())
    return beste


def _mijn_speelbeurten(orkest, reed2, inst, vanaf):
    """Alle dagen waarop Emiel moet spelen of repeteren.

    De orkestlijst is leidend. MON- en BESL-dagen staan daar niet in, dus die
    komen uit de reed 2-sheet.
    """
    beurten = [
        v for v in orkest
        if v.datum >= vanaf and v.reed2 == inst.mijn_naam
        and (v.type in SPEEL_TYPES or v.type in WERK_TYPES)
    ]
    bezet = {(v.datum, v.tijd) for v in beurten}
    for v in reed2:
        if (v.datum >= vanaf and v.reed2 == inst.mijn_naam
                and v.type in WERK_TYPES and (v.datum, v.tijd) not in bezet):
            beurten.append(v)
    return sorted(beurten, key=lambda v: (v.datum, v.tijd or ""))


def _past_in_venster(item, beurt, inst):
    if item.start is None:
        return True
    if beurt.tijd is None:
        return True
    aanvang = _samen(beurt.datum, beurt.tijd)
    start = datetime.combine(item.datum, item.start)
    return (aanvang - timedelta(minutes=inst.marge_voor_minuten)
            <= start
            <= aanvang + timedelta(minutes=inst.marge_na_minuten))


def _afstand(item, beurt):
    if item.start is None or beurt.tijd is None:
        return timedelta(days=1)
    return abs(datetime.combine(item.datum, item.start) - _samen(beurt.datum, beurt.tijd))


def _samen(dag, tijdtekst):
    uur, minuut = (int(x) for x in tijdtekst.split(":"))
    return datetime.combine(dag, time(uur, minuut))


# --- hulpjes ---------------------------------------------------------------

def _per_dag(voorstellingen, vanaf, alleen_met_publiek=False):
    """Groepeer per datum en sorteer binnen een dag op aanvangstijd."""
    per_dag = defaultdict(list)
    for v in voorstellingen:
        if v.datum < vanaf:
            continue
        if v.type in NEGEER_TYPES:
            continue
        if alleen_met_publiek and v.type not in SPEEL_TYPES:
            continue
        if not alleen_met_publiek and v.type is not None and v.type not in SPEEL_TYPES:
            continue
        per_dag[v.datum].append(v)
    for dag in per_dag:
        per_dag[dag].sort(key=lambda v: v.tijd or "")
    return dict(per_dag)


def _omschrijf(v):
    onderdelen = [v.datum.strftime("%d-%m-%Y")]
    if v.tijd:
        onderdelen.append(v.tijd)
    if v.type:
        onderdelen.append(v.type)
    if v.plaats:
        onderdelen.append(v.plaats)
    return " ".join(onderdelen)
```

- [ ] **Stap 5: Draai de tests en stel vast dat ze slagen**

Draai: `python3 -m unittest tests.test_vergelijk -v`
Verwacht: PASS, 24 tests.

- [ ] **Stap 6: Commit**

```bash
git add catscheck/vergelijk.py tests/test_vergelijk.py config/trefwoorden.json
git commit -m "feat: vergelijking van de vier bronnen"
```

---

### Taak 7: Rapport en commandoregel

Vanaf 17 december is de Reed 2-kolom in de orkestlijst grotendeels leeg,
terwijl de reed 2-sheet tot en met juni gevuld is. Dat zijn ruim honderd
`OPEN`-meldingen. Het rapport vat die samen tot één regel; anders verdrinkt de
rest.

**Bestanden:**
- Aanmaken: `catscheck/rapport.py`
- Aanmaken: `catscheck/__main__.py`
- Aanmaken: `tests/test_rapport.py`

**Interfaces:**
- Levert: `maak_rapport(meldingen, vanaf, overgeslagen_herhalend=0, samenvatten_vanaf=SAMENVATTEN_VANAF, website_onbetrouwbaar=False, onleesbare_afspraken=0) -> str`
  en de constante `SAMENVATTEN_VANAF = 15`
- `python3 -m catscheck [--vanaf JJJJ-MM-DD] [--cache MAP] [--config BESTAND]`

- [ ] **Stap 1: Schrijf de falende tests**

Maak `tests/test_rapport.py`:

```python
import unittest
from datetime import date

from catscheck.model import Ernst, Melding
from catscheck.rapport import SAMENVATTEN_VANAF, maak_rapport

VANAF = date(2026, 9, 5)


class TestRapport(unittest.TestCase):
    def test_zonder_meldingen_zegt_het_dat_alles_klopt(self):
        tekst = maak_rapport([], VANAF)
        self.assertIn("geen verschillen", tekst.lower())

    def test_kritiek_staat_boven_de_rest(self):
        tekst = maak_rapport([
            Melding(Ernst.WEBSITE, date(2026, 10, 1), "site wijkt af"),
            Melding(Ernst.KRITIEK, date(2026, 12, 1), "niet in je agenda"),
        ], VANAF)
        self.assertLess(tekst.index("niet in je agenda"), tekst.index("site wijkt af"))

    def test_meldingen_binnen_een_groep_staan_op_datum(self):
        tekst = maak_rapport([
            Melding(Ernst.KRITIEK, date(2026, 12, 1), "later"),
            Melding(Ernst.KRITIEK, date(2026, 10, 1), "eerder"),
        ], VANAF)
        self.assertLess(tekst.index("eerder"), tekst.index("later"))

    def test_details_staan_ingesprongen_onder_de_melding(self):
        tekst = maak_rapport([
            Melding(Ernst.KRITIEK, date(2026, 10, 1), "kop", ("detailregel",)),
        ], VANAF)
        self.assertIn("    detailregel", tekst)

    def test_veel_open_punten_worden_samengevat(self):
        veel = [
            Melding(Ernst.OPEN, date(2026, 12, 17), f"orkestlijst nog leeg bij Reed 2; jullie sheet zegt emiel")
            for _ in range(40)
        ]
        tekst = maak_rapport(veel, VANAF)
        self.assertIn("40", tekst)
        self.assertLess(tekst.count("orkestlijst nog leeg"), 40)

    def test_weinig_open_punten_worden_gewoon_opgesomd(self):
        weinig = [
            Melding(Ernst.OPEN, date(2026, 12, 17), "orkestlijst nog leeg bij Reed 2; jullie sheet zegt emiel"),
            Melding(Ernst.OPEN, date(2026, 12, 18), "orkestlijst nog leeg bij Reed 2; jullie sheet zegt coen"),
        ]
        tekst = maak_rapport(weinig, VANAF)
        self.assertIn("17-12-2026", tekst)
        self.assertIn("18-12-2026", tekst)

    def test_overgeslagen_herhalende_afspraken_worden_vermeld(self):
        tekst = maak_rapport([], VANAF, overgeslagen_herhalend=3)
        self.assertIn("3", tekst)
        self.assertIn("herhalende", tekst.lower())

    def test_de_peildatum_staat_in_de_kop(self):
        self.assertIn("05-09-2026", maak_rapport([], VANAF))

    def test_afspraken_zonder_begintijd_worden_vermeld(self):
        tekst = maak_rapport([], VANAF, onleesbare_afspraken=2)
        self.assertIn("2", tekst)
        self.assertIn("begintijd", tekst.lower())

    def test_onbetrouwbare_website_wordt_bovenaan_gemeld(self):
        tekst = maak_rapport([], VANAF, website_onbetrouwbaar=True)
        self.assertIn("musicalcats.nl", tekst)
        self.assertIn("gedeeltelijk", tekst.lower())
        # De waarschuwing moet boven de bevindingen staan, niet eronder.
        self.assertLess(tekst.index("LET OP"), tekst.index("Geen verschillen"))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Stap 2: Draai de tests en stel vast dat ze falen**

Draai: `python3 -m unittest tests.test_rapport -v`
Verwacht: FAIL met `ModuleNotFoundError: No module named 'catscheck.rapport'`

- [ ] **Stap 3: Schrijf `catscheck/rapport.py`**

```python
"""Maak Nederlandse terminaltekst van de bevindingen."""

from collections import Counter

from catscheck.model import Ernst

KOPPEN = {
    Ernst.KRITIEK: "KRITIEK — dit raakt jou direct",
    Ernst.VERSCHIL: "VERSCHIL — orkestlijst tegenover jullie reed 2-sheet",
    Ernst.WEBSITE: "WEBSITE — musicalcats.nl wijkt af (niet de bron)",
    Ernst.OPEN: "NOG IN TE VULLEN",
}

# Boven dit aantal wordt een groep samengevat in plaats van opgesomd.
SAMENVATTEN_VANAF = 15


def maak_rapport(meldingen, vanaf, overgeslagen_herhalend=0,
                 samenvatten_vanaf=SAMENVATTEN_VANAF,
                 website_onbetrouwbaar=False, onleesbare_afspraken=0):
    regels = [
        "Cats speellijst-checker",
        f"Peildatum: {vanaf.strftime('%d-%m-%Y')} (alles daarvoor is overgeslagen)",
        "",
    ]
    if website_onbetrouwbaar:
        # Bovenaan, want het verandert hoe je de rest van het rapport leest.
        regels += [
            "LET OP: musicalcats.nl kon maar gedeeltelijk gelezen worden.",
            "De opmaak van de pagina is waarschijnlijk gewijzigd. De website is",
            "daarom helemaal buiten de vergelijking gelaten; de rest klopt wel.",
            "",
        ]
    if not meldingen:
        regels.append("Geen verschillen gevonden. Alle vier de bronnen zijn het eens.")
    else:
        for ernst in sorted(KOPPEN):
            groep = sorted(
                (m for m in meldingen if m.ernst is ernst),
                key=lambda m: (m.datum, m.tekst),
            )
            if not groep:
                continue
            regels.append(f"{KOPPEN[ernst]}  ({len(groep)})")
            regels.append("-" * len(KOPPEN[ernst]))
            regels += _toon_groep(groep, samenvatten_vanaf)
            regels.append("")

    if overgeslagen_herhalend:
        regels.append(
            f"Let op: {overgeslagen_herhalend} herhalende agenda-afspraken zijn "
            f"niet meegenomen; die worden niet uitgerekend."
        )
    if onleesbare_afspraken:
        regels.append(
            f"Let op: {onleesbare_afspraken} agenda-afspraken misten een "
            f"begintijd en konden niet gecontroleerd worden."
        )
    return "\n".join(regels).rstrip() + "\n"


def _toon_groep(groep, samenvatten_vanaf):
    if len(groep) > samenvatten_vanaf:
        return _vat_samen(groep)
    regels = []
    for m in groep:
        regels.append(f"  {m.datum.strftime('%d-%m-%Y')}  {m.tekst}")
        for detail in m.details:
            regels.append(f"    {detail}")
    return regels


def _vat_samen(groep):
    """Vat een lange groep samen op de gemeenschappelijke tekst.

    Zonder dit verdwijnt één belangrijke melding tussen honderd gelijksoortige.
    """
    regels = [
        f"  {len(groep)} meldingen, van {groep[0].datum.strftime('%d-%m-%Y')} "
        f"tot en met {groep[-1].datum.strftime('%d-%m-%Y')}:"
    ]
    for tekst, aantal in Counter(m.tekst for m in groep).most_common():
        regels.append(f"    {aantal:4d}x  {tekst}")
    regels.append("  (draai met --alles om ze allemaal te zien)")
    return regels
```

- [ ] **Stap 4: Draai de tests en stel vast dat ze slagen**

Draai: `python3 -m unittest tests.test_rapport -v`
Verwacht: PASS, 10 tests.

- [ ] **Stap 5: Schrijf `catscheck/__main__.py`**

```python
"""Commandoregel voor de Cats speellijst-checker.

Leest uitsluitend lokale bestanden uit de cachemap. Doet zelf geen enkel
netwerkverzoek: het ophalen van de bronnen gebeurt door Claude, met alleen-
lees-tools.
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from catscheck.agenda import parse_agenda
from catscheck.model import ParseFout
from catscheck.orkest import parse_orkest
from catscheck.rapport import maak_rapport
from catscheck.reed2 import parse_reed2
from catscheck.vergelijk import Instellingen, vergelijk
from catscheck.website import parse_website


def main(argv=None):
    p = argparse.ArgumentParser(description="Controleer de Cats-speellijsten op verschillen.")
    p.add_argument("--cache", default="cache", type=Path, help="map met de opgehaalde bronnen")
    p.add_argument("--config", default="config/trefwoorden.json", type=Path)
    p.add_argument("--vanaf", default=None, help="peildatum JJJJ-MM-DD, standaard vandaag")
    p.add_argument("--alles", action="store_true", help="vat lange groepen niet samen")
    args = p.parse_args(argv)

    vanaf = date.fromisoformat(args.vanaf) if args.vanaf else date.today()
    inst = _lees_instellingen(args.config)

    try:
        orkest = parse_orkest(_lees(args.cache / "orkest.txt"))
        reed2 = parse_reed2(_lees(args.cache / "reed2.csv"))
        website, website_volledig = parse_website(_lees(args.cache / "website.html"))
        agenda, overgeslagen, onleesbaar = parse_agenda(_lees(args.cache / "agenda.ics"))
    except ParseFout as fout:
        print(f"De controle kon niet worden uitgevoerd: {fout}", file=sys.stderr)
        return 2
    except FileNotFoundError as fout:
        print(
            f"Bronbestand ontbreekt: {fout.filename}\n"
            f"Vraag Claude de bronnen op te halen (/cats-check).",
            file=sys.stderr,
        )
        return 2

    # Is de pagina maar half gelezen, dan levert vergelijken met de website
    # alleen verzonnen verschillen op. De rest van de controle gaat wel door.
    meldingen = vergelijk(
        orkest, reed2, website if website_volledig else [], agenda, inst, vanaf
    )
    print(maak_rapport(
        meldingen, vanaf, overgeslagen,
        samenvatten_vanaf=10 ** 9 if args.alles else SAMENVATTEN_VANAF,
        website_onbetrouwbaar=not website_volledig,
        onleesbare_afspraken=onleesbaar,
    ))
    return 1 if meldingen else 0


def _lees(pad):
    return Path(pad).read_text(encoding="utf-8")


def _lees_instellingen(pad):
    if not Path(pad).exists():
        return Instellingen()
    rauw = json.loads(Path(pad).read_text(encoding="utf-8"))
    return Instellingen(
        mijn_naam=rauw.get("mijn_naam", "emiel"),
        marge_voor_minuten=rauw.get("marge_voor_minuten", 240),
        marge_na_minuten=rauw.get("marge_na_minuten", 30),
        trefwoorden=tuple(t.lower() for t in rauw.get("trefwoorden", ["cats"])),
    )


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Stap 6: Draai alle tests**

Draai: `python3 -m unittest discover -s tests -v`
Verwacht: PASS, 78 tests, geen fouten.

- [ ] **Stap 7: Draai op de echte bronnen**

Alle vier de cachebestanden staan er al, inclusief een echte
`cache/agenda.ics`. **Overschrijf die niet** — het is een opgehaalde kopie van
een privéagenda en er staat geen tweede exemplaar van.

```bash
python3 -m catscheck --vanaf 2026-09-01
```

Verwacht, op grond van wat er eerder handmatig in de bronnen is nagekeken:

- onder VERSCHIL de tijdsverschillen tussen orkestlijst en reed 2-sheet op
  11, 18, 24 en 25 oktober 2026;
- onder WEBSITE het plaatsverschil rond 20 tot en met 23 mei 2027 (orkestlijst
  Den Bosch, site Den Haag) en de DeLaMar-reeks die niet op de site staat;
- onder KRITIEK drie speeldagen zonder Cats-afspraak in de agenda
  (21-10-2026, 20-11-2026, 13-12-2026) en drie dagen met twee voorstellingen
  waar één afspraak "Cats 2x" staat (7 en 14 november, 5 december);
- onder NOG IN TE VULLEN ruim honderd lege Reed 2-cellen vanaf half december,
  samengevat tot één regel in plaats van uitgeschreven.

Wijkt het rapport hier sterk van af, meld dat dan — het betekent dat een van de
onderdelen anders werkt dan bedoeld, niet dat de verwachting bijgesteld moet
worden.

- [ ] **Stap 8: Commit**

```bash
git add catscheck/rapport.py catscheck/__main__.py tests/test_rapport.py
git commit -m "feat: rapport en commandoregel"
```

---

### Taak 8: Ophaalscript en de skill

**Bestanden:**
- Aanmaken: `scripts/ophalen.sh`
- Aanmaken: `.claude/skills/cats-check/SKILL.md`
- Aanmaken: `README.md`

- [ ] **Stap 1: Schrijf `scripts/ophalen.sh`**

Dit script haalt de twee bronnen op die zonder Google-inloggegevens bereikbaar
zijn. De twee Drive-bestanden haalt Claude op met alleen-lees-tools.

```bash
#!/usr/bin/env bash
# Haalt de website en de agenda op naar cache/. Alleen lezen.
set -euo pipefail

cd "$(dirname "$0")/.."
mkdir -p cache

echo "musicalcats.nl ophalen..."
curl -sSL --max-time 30 "https://musicalcats.nl/waar-wanneer/" -o cache/website.html

if [[ -f config/ical_url.txt ]]; then
  echo "agenda ophalen..."
  # De URL zelf verschijnt nooit in de uitvoer; hij is een geheim.
  url="$(tr -d '[:space:]' < config/ical_url.txt)"
  if ! curl -sSL --max-time 30 "$url" -o cache/agenda.ics; then
    echo "agenda ophalen mislukt; controleer de URL in config/ical_url.txt" >&2
    exit 1
  fi
  if ! head -1 cache/agenda.ics | grep -q "BEGIN:VCALENDAR"; then
    echo "de agenda-URL gaf geen iCal-bestand terug; is hij nog geldig?" >&2
    exit 1
  fi
else
  echo "config/ical_url.txt ontbreekt; de agendacontrole wordt overgeslagen." >&2
fi

echo "klaar."
```

Maak hem uitvoerbaar: `chmod +x scripts/ophalen.sh`

- [ ] **Stap 2: Toets het script**

```bash
./scripts/ophalen.sh && ls -la cache/
```

Verwacht: `cache/website.html` van ruim 400 kB. Zonder `config/ical_url.txt`
een waarschuwing op stderr en afsluitcode 0.

- [ ] **Stap 3: Schrijf de skill**

Maak `.claude/skills/cats-check/SKILL.md`:

```markdown
---
name: cats-check
description: Use when Emiel wants to check the Cats musical playlists for inconsistencies - compares the orchestra list, the reed 2 planning sheet, musicalcats.nl and his personal calendar, read-only
---

# Cats speellijst-checker

Controleert vier bronnen op verschillen en meldt wat er niet klopt.

## Absolute regel: alleen lezen

De orkestlijst is van iemand anders en wordt door alle musici gebruikt. De
reed 2-sheet is een gedeelde planning van drie mensen. **Er wordt nooit,
onder geen enkele omstandigheid, naar een van beide geschreven.**

Toegestaan zijn uitsluitend `read_file_content`, `download_file_content` en
`get_file_metadata`. De schrijvende Drive-tools zijn geblokkeerd in
`.claude/settings.json`; probeer die blokkade nooit te omzeilen. Vraagt iemand
om iets in te vullen, aan te passen of over te nemen in een sheet, weiger dan
en verwijs naar deze regel.

## Werkwijze

**Stap 1 — is er iets veranderd?**

Draai `get_file_metadata` op beide Drive-bestanden en vergelijk `modifiedTime`
met `cache/stempels.json`. Is er niets gewijzigd én bestaan de cachebestanden
al, sla stap 2 dan over.

- orkestlijst: `1qXIFu7Wq9SBKrBxjPqoTOqCccH65fpcg`
- reed 2-sheet: `1jOjspqJjxHZdwBPgiBsyDMsyw_gy0caEHucaV5eP1rI`

**Stap 2 — bronnen verversen**

- Orkestlijst: `read_file_content` op het orkest-bestand, schrijf de volledige
  tekst naar `cache/orkest.txt`.
- Reed 2-sheet: `download_file_content` met `exportMimeType: "text/csv"`,
  base64-decodeer naar `cache/reed2.csv`.
- Website en agenda: draai `./scripts/ophalen.sh`.
- Werk `cache/stempels.json` bij met de nieuwe `modifiedTime`-waarden.

**Stap 3 — controleren**

```bash
python3 -m catscheck
```

Afsluitcode 0 betekent geen verschillen, 1 betekent meldingen, 2 betekent dat
een bron niet gelezen kon worden.

**Stap 4 — toelichten**

Druk het rapport af en licht de KRITIEK-meldingen toe. Zeg er per melding bij
wat Emiel eraan kan doen: zelf zijn agenda bijwerken, het met Christof en
Michiel opnemen, of het bij Ryanne melden omdat de orkestlijst aangepast moet
worden. Dat laatste doet Emiel zelf — jij past niets aan.

## Bij een ParseFout

Een parser die zijn structuur niet herkent stopt met een `ParseFout`. Dat
betekent bijna altijd dat een bron van vorm is veranderd: een kolom
tussengevoegd, de site verbouwd, een tabblad erbij. Repareer de parser en voeg
een test met de nieuwe vorm toe. Vul nooit met de hand aan wat de parser mist.

## Later, nog niet gebouwd

Ontbrekende speelbeurten in de agenda zetten. Dat vraagt de Google
Calendar-connector; een iCal-URL kan alleen lezen. Pas bouwen als Emiel er
uitdrukkelijk om vraagt.
```

- [ ] **Stap 4: Schrijf `README.md`**

```markdown
# Cats speellijst-checker

Controleert vier bronnen op verschillen: de orkestlijst, de reed 2-planning,
musicalcats.nl en Emiels agenda. **Alles alleen-lezen.**

## Eenmalig instellen

Zet de geheime iCal-URL van je agenda in `config/ical_url.txt`:

1. Google Agenda → instellingen van je agenda → Agenda integreren
2. Kopieer "Privé-adres in iCal-indeling"
3. `mkdir -p config && printf '%s' 'PLAK_HIER' > config/ical_url.txt`
4. `chmod 600 config/ical_url.txt`

Wie deze URL heeft kan je agenda lezen. Het bestand staat in `.gitignore` en
verschijnt nooit in de uitvoer.

## Gebruiken

In Claude Code: `/cats-check`

Handmatig, met een gevulde `cache/`:

```bash
./scripts/ophalen.sh          # website en agenda
python3 -m catscheck          # controleren
python3 -m catscheck --vanaf 2026-10-01 --alles
```

## Tests

```bash
python3 -m unittest discover -s tests
```
```

- [ ] **Stap 5: Draai alles nog één keer**

```bash
python3 -m unittest discover -s tests
./scripts/ophalen.sh
python3 -m catscheck --vanaf 2026-09-01 | head -40
```

Verwacht: alle tests slagen, het script haalt de website op, en het rapport
verschijnt.

- [ ] **Stap 6: Commit**

```bash
git add scripts/ .claude/skills/ README.md
git commit -m "feat: ophaalscript, skill en documentatie"
```

---

## Wat er níét in zit

- **Overnachtingen.** De kolom `Overnachten Reed 2` wordt niet gelezen.
- **Schrijven naar een sheet of naar de agenda.** Bewust geblokkeerd.
- **Een deelbaar rapport.** Alleen terminaluitvoer. Het rapport wordt uit losse
  `Melding`-objecten opgebouwd, dus een bestand of pagina kan er later zonder
  herbouw uit rollen.
- **Herhalende agenda-afspraken.** Worden overgeslagen en geteld.
