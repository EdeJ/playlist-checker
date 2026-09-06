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
        # Alleen oktober raakt zijn kop kwijt; de andere tabbladen houden hun
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
