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
