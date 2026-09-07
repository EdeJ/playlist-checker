import json
import unittest
from datetime import date, timedelta

from catscheck.model import Ernst, Melding
from catscheck.rapport import maak_json, maak_rapport

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

    def test_kritiek_wordt_nooit_samengevat(self):
        # De belangrijkste groep loop je van boven naar beneden af; die mag
        # nooit tot frequentietellingen worden ingedikt.
        veel = [
            Melding(Ernst.KRITIEK, date(2026, 10, 1) + timedelta(days=i),
                    f"melding {i}")
            for i in range(40)
        ]
        tekst = maak_rapport(veel, VANAF)
        self.assertIn("melding 39", tekst)
        self.assertNotIn("meldingen, van", tekst)

    def test_groep_met_louter_unieke_teksten_wordt_niet_samengevat(self):
        uniek = [
            Melding(Ernst.WEBSITE, date(2026, 10, 1) + timedelta(days=i),
                    f"site wijkt af op dag {i}")
            for i in range(40)
        ]
        tekst = maak_rapport(uniek, VANAF)
        self.assertIn("site wijkt af op dag 39", tekst)

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


class TestJson(unittest.TestCase):
    def test_geeft_geldige_json_met_de_bevindingen(self):
        uit = maak_json([
            Melding(Ernst.KRITIEK, date(2026, 12, 1), "niet in je agenda", ("detail",)),
        ], VANAF)
        data = json.loads(uit)
        self.assertEqual(data["peildatum"], "2026-09-05")
        self.assertEqual(len(data["meldingen"]), 1)
        m = data["meldingen"][0]
        self.assertEqual(m["ernst"], "KRITIEK")
        self.assertEqual(m["datum"], "2026-12-01")
        self.assertEqual(m["tekst"], "niet in je agenda")
        self.assertEqual(m["details"], ["detail"])

    def test_vat_nooit_samen_ook_niet_bij_veel_meldingen(self):
        # maak_rapport vat lange, herhalende groepen samen; maak_json is voor
        # een afnemer die zelf beslist hoe te tonen en moet dus alles geven.
        meldingen = [
            Melding(Ernst.OPEN, date(2026, 9, 5) + timedelta(days=i), "dezelfde tekst")
            for i in range(20)
        ]
        data = json.loads(maak_json(meldingen, VANAF))
        self.assertEqual(len(data["meldingen"]), 20)

    def test_agenda_gecontroleerd_staat_standaard_op_waar(self):
        data = json.loads(maak_json([], VANAF))
        self.assertIs(data["agenda_gecontroleerd"], True)

    def test_agenda_gecontroleerd_kan_op_onwaar_gezet_worden(self):
        data = json.loads(maak_json([], VANAF, agenda_gecontroleerd=False))
        self.assertIs(data["agenda_gecontroleerd"], False)

    def test_ernst_staat_boven_datum_in_de_sortering(self):
        data = json.loads(maak_json([
            Melding(Ernst.WEBSITE, date(2026, 9, 6), "site"),
            Melding(Ernst.KRITIEK, date(2026, 12, 1), "kritiek"),
        ], VANAF))
        self.assertEqual([m["ernst"] for m in data["meldingen"]], ["KRITIEK", "WEBSITE"])


if __name__ == "__main__":
    unittest.main()
