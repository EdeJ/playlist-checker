import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from catscheck.__main__ import main

FIXTURES = str(Path(__file__).parent / "fixtures")


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


if __name__ == "__main__":
    unittest.main()
