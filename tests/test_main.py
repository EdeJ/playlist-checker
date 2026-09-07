import io
import json
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from catscheck.__main__ import _lees_instellingen, main
from tests.orkestblad import orkest_xlsx

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


def draai(argv):
    """Draai de commandoregel en geef (afsluitcode, uitvoer, fouten) terug."""
    uit, fout = io.StringIO(), io.StringIO()
    with redirect_stdout(uit), redirect_stderr(fout):
        code = main(argv)
    return code, uit.getvalue(), fout.getvalue()


class TestAfsluitcodes(unittest.TestCase):
    def test_rapport_op_de_fixtures(self):
        code, uit, _ = draai(["--cache", FIXTURES, "--vanaf", "2026-09-01"])
        self.assertIn("Cats speellijst-checker", uit)
        self.assertIn(code, (0, 1))

    def test_zonder_agenda_werkt_ook_zonder_agenda_ics(self):
        # De cloud-routine heeft het geheime iCal-adres niet, en dus ook
        # geen cache/agenda.ics. --zonder-agenda mag dan niet als
        # ontbrekend bronbestand (code 2) worden gemeld, en de agenda mag
        # geen valse KRITIEK-meldingen opleveren.
        with tempfile.TemporaryDirectory() as zonder_agenda:
            for naam in ("reed2.csv", "website.html"):
                shutil.copy(Path(FIXTURES) / naam, Path(zonder_agenda) / naam)
            shutil.copy(
                Path(FIXTURES) / "orkest.xlsx", Path(zonder_agenda) / "orkest.xlsx"
            )
            code, uit, fout = draai([
                "--cache", zonder_agenda, "--vanaf", "2026-09-01", "--zonder-agenda",
            ])
        self.assertIn(code, (0, 1))
        self.assertNotIn("agenda", uit.lower())
        self.assertEqual(fout, "")

    def test_json_geeft_geldige_json_op_stdout(self):
        code, uit, _ = draai(["--cache", FIXTURES, "--vanaf", "2026-09-01", "--json"])
        self.assertIn(code, (0, 1))
        data = json.loads(uit)
        self.assertIn("meldingen", data)
        self.assertIn("peildatum", data)
        self.assertIs(data["agenda_gecontroleerd"], True)

    def test_json_zonder_agenda_meldt_dat_in_de_json(self):
        with tempfile.TemporaryDirectory() as zonder_agenda:
            for naam in ("reed2.csv", "website.html"):
                shutil.copy(Path(FIXTURES) / naam, Path(zonder_agenda) / naam)
            shutil.copy(
                Path(FIXTURES) / "orkest.xlsx", Path(zonder_agenda) / "orkest.xlsx"
            )
            code, uit, _ = draai([
                "--cache", zonder_agenda, "--vanaf", "2026-09-01",
                "--zonder-agenda", "--json",
            ])
        self.assertIn(code, (0, 1))
        data = json.loads(uit)
        self.assertIs(data["agenda_gecontroleerd"], False)

    def test_ontbrekende_cachemap_geeft_code_2(self):
        with tempfile.TemporaryDirectory() as leeg:
            code, _, fout = draai(["--cache", leeg])
        self.assertEqual(code, 2)
        self.assertIn("ontbreekt", fout)

    def test_ongeldige_peildatum_geeft_code_2_en_geen_traceback(self):
        # Code 1 zou "er zijn verschillen gevonden" betekenen; een crash mag
        # daar niet mee samenvallen.
        code, _, fout = draai(["--cache", FIXTURES, "--vanaf", "geen-datum"])
        self.assertEqual(code, 2)
        self.assertIn("peildatum", fout.lower())
        self.assertNotIn("Traceback", fout)

    def test_kapotte_configuratie_geeft_code_2_en_geen_traceback(self):
        with tempfile.TemporaryDirectory() as map_:
            kapot = Path(map_) / "trefwoorden.json"
            kapot.write_text("{dit is geen json", encoding="utf-8")
            code, _, fout = draai(
                ["--cache", FIXTURES, "--config", str(kapot), "--vanaf", "2026-09-01"]
            )
        self.assertEqual(code, 2)
        self.assertIn("niet lezen", fout)
        self.assertNotIn("Traceback", fout)

    def test_configuratie_die_geen_object_is_geeft_code_2_en_geen_traceback(self):
        # Een lijst of losse tekst in plaats van een JSON-object gaf voorheen
        # een Engelse AttributeError-traceback met afsluitcode 1 — dezelfde
        # code als "er zijn meldingen gevonden".
        with tempfile.TemporaryDirectory() as map_:
            kapot = Path(map_) / "trefwoorden.json"
            kapot.write_text(json.dumps(["cats"]), encoding="utf-8")
            code, _, fout = draai(
                ["--cache", FIXTURES, "--config", str(kapot), "--vanaf", "2026-09-01"]
            )
        self.assertEqual(code, 2)
        self.assertIn("niet lezen", fout)
        self.assertNotIn("Traceback", fout)

    def test_trefwoorden_als_losse_tekst_geeft_code_2_in_plaats_van_stille_misparse(self):
        # {"trefwoorden": "cats"} werd zonder foutmelding een tuple losse
        # letters ('c', 'a', 't', 's'), waardoor bijna elke afspraak als
        # Cats-gerelateerd telt — fout, en zonder enig signaal.
        with tempfile.TemporaryDirectory() as map_:
            kapot = Path(map_) / "trefwoorden.json"
            kapot.write_text(json.dumps({"trefwoorden": "cats"}), encoding="utf-8")
            code, _, fout = draai(
                ["--cache", FIXTURES, "--config", str(kapot), "--vanaf", "2026-09-01"]
            )
        self.assertEqual(code, 2)
        self.assertIn("niet lezen", fout)
        self.assertNotIn("Traceback", fout)

    def test_niet_numerieke_marge_geeft_code_2_en_geen_traceback(self):
        with tempfile.TemporaryDirectory() as map_:
            kapot = Path(map_) / "trefwoorden.json"
            kapot.write_text(
                json.dumps({"marge_voor_minuten": "vier uur"}), encoding="utf-8"
            )
            code, _, fout = draai(
                ["--cache", FIXTURES, "--config", str(kapot), "--vanaf", "2026-09-01"]
            )
        self.assertEqual(code, 2)
        self.assertIn("niet lezen", fout)
        self.assertNotIn("Traceback", fout)

    def test_niet_tekst_mijn_naam_geeft_code_2_en_geen_traceback(self):
        # {"mijn_naam": null} (of elk ander niet-tekst-type) laat elke
        # naamvergelijking mislukken, want overal wordt met een
        # genormaliseerde (lowercase) tekenreeks vergeleken.
        with tempfile.TemporaryDirectory() as map_:
            kapot = Path(map_) / "trefwoorden.json"
            kapot.write_text(json.dumps({"mijn_naam": None}), encoding="utf-8")
            code, _, fout = draai(
                ["--cache", FIXTURES, "--config", str(kapot), "--vanaf", "2026-09-01"]
            )
        self.assertEqual(code, 2)
        self.assertIn("niet lezen", fout)
        self.assertNotIn("Traceback", fout)

    def test_mijn_naam_wordt_genormaliseerd_naar_kleine_letters(self):
        # "Emiel" met hoofdletter matcht anders nergens meer, want elke
        # naamvergelijking elders gebeurt met de genormaliseerde (lowercase)
        # tekst uit normaliseer_naam().
        with tempfile.TemporaryDirectory() as map_:
            pad = Path(map_) / "trefwoorden.json"
            pad.write_text(json.dumps({"mijn_naam": "Emiel"}), encoding="utf-8")
            inst = _lees_instellingen(pad)
        self.assertEqual(inst.mijn_naam, "emiel")

    def test_lege_trefwoordenlijst_geeft_code_2_in_plaats_van_stille_uitschakeling(self):
        # Een lege lijst matcht geen enkele afspraak meer, waardoor de hele
        # agendacontrole zonder signaal uitgeschakeld raakt.
        with tempfile.TemporaryDirectory() as map_:
            kapot = Path(map_) / "trefwoorden.json"
            kapot.write_text(json.dumps({"trefwoorden": []}), encoding="utf-8")
            code, _, fout = draai(
                ["--cache", FIXTURES, "--config", str(kapot), "--vanaf", "2026-09-01"]
            )
        self.assertEqual(code, 2)
        self.assertIn("niet lezen", fout)
        self.assertNotIn("Traceback", fout)


if __name__ == "__main__":
    unittest.main()
