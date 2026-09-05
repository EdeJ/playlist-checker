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
