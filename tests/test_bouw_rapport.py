"""Tests voor scripts/bouw_rapport.py.

Het script staat in scripts/, niet in het catscheck-pakket (het is geen
onderdeel van de controle zelf, alleen van de rapportpagina), dus wordt het
via het bestandspad geïmporteerd.
"""
import importlib.util
import json
import re
import sys
import tempfile
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

    def test_geen_enkele_groep_wordt_ooit_samengevat(self):
        # Anders dan het terminalrapport vat de pagina lange, herhalende
        # groepen nooit samen ("9x aanvangstijd verschilt: ...") — daar kan
        # Emiel niets mee zonder te weten óm welke voorstelling het gaat.
        for ernst in bouw_rapport.ERNST_VOLGORDE:
            meldingen = [m(ernst, "2026-09-10", "steeds dezelfde tekst") for _ in range(20)]
            html_tekst, tellingen = bouw_rapport.bouw(
                {"peildatum": "2026-09-07", "meldingen": meldingen}, "x"
            )
            self.assertEqual(html_tekst.count('class="melding"'), 20, ernst)
            self.assertNotIn("&times;", html_tekst, ernst)
            self.assertEqual(tellingen[ernst], 20)

    def test_elke_melding_krijgt_een_actieregel(self):
        meldingen = [m("VERSCHIL", "2026-09-10", "aanvangstijd verschilt: orkestlijst 15:00, jullie sheet 14:30")]
        html_tekst, _ = bouw_rapport.bouw({"peildatum": "2026-09-07", "meldingen": meldingen}, "x")
        self.assertIn('class="actie"', html_tekst)

    def test_agenda_meldingen_wijzen_naar_de_eigen_agenda(self):
        for tekst in [
            "agenda-item 'Cats Repetitie' hoort bij geen speelbeurt van jou",
            "jij staat ingeroosterd maar er staat niets in je agenda — 19-12-2026 20:00",
            "agenda-item staat op 19:00 maar de voorstelling begint om 20:00 — iets",
        ]:
            self.assertEqual(bouw_rapport._actie("KRITIEK", tekst), "Zelf je agenda bijwerken.")

    def test_reed2_verschil_wijst_op_eerst_uitzoeken_ongeacht_ernst(self):
        tekst = "Reed 2 verschilt: orkestlijst emiel, jullie sheet christof"
        verwacht = "Eerst uitzoeken met de betrokkenen — niet zomaar aanpassen."
        self.assertEqual(bouw_rapport._actie("KRITIEK", tekst), verwacht)
        self.assertEqual(bouw_rapport._actie("VERSCHIL", tekst), verwacht)

    def test_tijd_type_plaats_verschillen_wijzen_op_zelf_rechtzetten(self):
        for tekst in [
            "aanvangstijd verschilt: orkestlijst 15:00, jullie sheet 14:30",
            "type verschilt: orkestlijst S-OPT, jullie sheet REG",
            "plaats verschilt: orkestlijst ALMERE, jullie sheet BREDA",
            "aantal voorstellingen verschilt: orkestlijst 1, reed 2-sheet 2",
            "staat in de orkestlijst (1x), maar niet in jullie reed 2-sheet",
        ]:
            self.assertEqual(
                bouw_rapport._actie("VERSCHIL", tekst),
                "Zelf rechtzetten in de orkestlijst.",
            )

    def test_onbekende_naam_en_leeg_type_wijzen_op_navragen(self):
        for tekst in [
            "onbekende naam bij Reed 2 in de orkestlijst: 'x' — dit hoort Emiel, Christof, Coen of Michiel te zijn",
            "leeg type bij Reed 2 = emiel in de orkestlijst — deze voorstelling is niet gecontroleerd",
            "onbekend type 'FOO' in de orkestlijst — deze voorstelling is niet gecontroleerd",
        ]:
            actie = bouw_rapport._actie("KRITIEK", tekst)
            self.assertTrue(actie.startswith("Navragen"), actie)

    def test_website_meldingen_zijn_altijd_ter_info(self):
        self.assertEqual(
            bouw_rapport._actie("WEBSITE", "wat dan ook"),
            "Ter info — musicalcats.nl is niet de bron, geen actie nodig.",
        )

    def test_open_meldingen_zijn_altijd_nog_niet_ingevuld(self):
        self.assertEqual(
            bouw_rapport._actie("OPEN", "wat dan ook"),
            "Nog niet ingevuld — geen actie voor jou, gewoon nog open.",
        )

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

    def test_hoofdfunctie_gebruikt_een_meegegeven_bijgewerkt_tekst(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump({"peildatum": "2026-09-07", "meldingen": []}, f)
            json_pad = f.name
        uit_pad = json_pad.replace(".json", ".html")
        try:
            code = bouw_rapport.main(
                ["bouw_rapport.py", json_pad, uit_pad, "07-09-2026, 08:03 (lokale tijd)"]
            )
            self.assertEqual(code, 0)
            self.assertIn("08:03 (lokale tijd)", Path(uit_pad).read_text(encoding="utf-8"))
        finally:
            Path(json_pad).unlink(missing_ok=True)
            Path(uit_pad).unlink(missing_ok=True)

    def test_alle_placeholders_worden_vervangen(self):
        meldingen = [m("KRITIEK", "2026-09-10", "iets")]
        html_tekst, _ = bouw_rapport.bouw({"peildatum": "2026-09-07", "meldingen": meldingen}, "x")
        self.assertNotRegex(html_tekst, re.compile(r"\{\{[A-Z_]+\}\}"))


if __name__ == "__main__":
    unittest.main()
