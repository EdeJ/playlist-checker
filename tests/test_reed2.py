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
