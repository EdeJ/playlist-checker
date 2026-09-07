"""Tests voor scripts/bouw_rapport.py.

Het script staat in scripts/, niet in het catscheck-pakket (het is geen
onderdeel van de controle zelf, alleen van de rapportpagina), dus wordt het
via het bestandspad geïmporteerd.
"""
import importlib.util
import re
import sys
import unittest
from pathlib import Path

PAD = Path(__file__).parent.parent / "scripts" / "bouw_rapport.py"
_SPEC = importlib.util.spec_from_file_location("bouw_rapport", PAD)
bouw_rapport = importlib.util.module_from_spec(_SPEC)
sys.modules["bouw_rapport"] = bouw_rapport
_SPEC.loader.exec_module(bouw_rapport)


def m(ernst, datum, tekst, details=()):
    return {"ernst": ernst, "datum": datum, "tekst": tekst, "details": list(details)}


class TestBouwRapport(unittest.TestCase):
    def test_geen_meldingen_toont_alles_goed_en_geen_secties(self):
        html_tekst, tellingen = bouw_rapport.bouw(
            {"peildatum": "2026-09-07", "meldingen": []}, "07-09-2026, 08:00"
        )
        self.assertIn("Geen verschillen gevonden", html_tekst)
        self.assertNotIn('<section', html_tekst)
        self.assertEqual(tellingen, {"KRITIEK": 0, "VERSCHIL": 0, "WEBSITE": 0, "OPEN": 0})

    def test_kritiek_wordt_nooit_samengevat_ook_niet_bij_veel_herhaling(self):
        meldingen = [m("KRITIEK", "2026-09-10", "zelfde tekst") for _ in range(20)]
        html_tekst, tellingen = bouw_rapport.bouw(
            {"peildatum": "2026-09-07", "meldingen": meldingen}, "x"
        )
        self.assertEqual(html_tekst.count('class="melding"'), 20)
        self.assertNotIn('class="groep-samengevat"', html_tekst)
        self.assertEqual(tellingen["KRITIEK"], 20)

    def test_lange_herhalende_groep_wordt_samengevat_met_aantallen(self):
        meldingen = [m("WEBSITE", "2026-09-10", "steeds dezelfde tekst") for _ in range(20)]
        html_tekst, _ = bouw_rapport.bouw({"peildatum": "2026-09-07", "meldingen": meldingen}, "x")
        self.assertIn('class="groep-samengevat"', html_tekst)
        self.assertIn("20&times;", html_tekst)
        self.assertNotIn('class="melding"', html_tekst)

    def test_agenda_niet_gecontroleerd_wordt_vermeld(self):
        html_tekst, _ = bouw_rapport.bouw(
            {"peildatum": "2026-09-07", "agenda_gecontroleerd": False, "meldingen": []}, "x"
        )
        self.assertIn("niet meegenomen", html_tekst)

    def test_agenda_gecontroleerd_wordt_vermeld(self):
        html_tekst, _ = bouw_rapport.bouw(
            {"peildatum": "2026-09-07", "agenda_gecontroleerd": True, "meldingen": []}, "x"
        )
        self.assertIn("agenda: meegenomen", html_tekst)

    def test_tekst_wordt_html_geescaped(self):
        meldingen = [m("OPEN", "2026-09-10", "R&D <script>alert(1)</script>")]
        html_tekst, _ = bouw_rapport.bouw({"peildatum": "2026-09-07", "meldingen": meldingen}, "x")
        self.assertNotIn("<script>alert(1)</script>", html_tekst)
        self.assertIn("&lt;script&gt;", html_tekst)

    def test_alle_placeholders_worden_vervangen(self):
        meldingen = [m("KRITIEK", "2026-09-10", "iets")]
        html_tekst, _ = bouw_rapport.bouw({"peildatum": "2026-09-07", "meldingen": meldingen}, "x")
        self.assertNotRegex(html_tekst, re.compile(r"\{\{[A-Z_]+\}\}"))


if __name__ == "__main__":
    unittest.main()
