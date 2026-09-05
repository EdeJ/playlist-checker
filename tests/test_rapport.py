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
