import unittest
from datetime import date
from pathlib import Path

from catscheck.model import ParseFout
from catscheck.website import parse_website

FIXTURE = (Path(__file__).parent / "fixtures" / "website.html").read_text(encoding="utf-8")


class TestParseWebsite(unittest.TestCase):
    def setUp(self):
        self.vs, self.volledig = parse_website(FIXTURE)

    def test_leest_alle_voorstellingen(self):
        self.assertEqual(len(self.vs), 3)

    def test_een_volledig_gelezen_pagina_meldt_zich_als_volledig(self):
        self.assertTrue(self.volledig)

    def test_leest_datum_tijd_theater_en_plaats(self):
        v = self.vs[0]
        self.assertEqual(v.datum, date(2026, 10, 6))
        self.assertEqual(v.tijd, "20:15")
        self.assertEqual(v.theater, "Kunstlinie")
        self.assertEqual(v.plaats, "ALMERE")
        self.assertEqual(v.bron, "website")

    def test_zegt_niets_over_type_of_bezetting(self):
        self.assertTrue(all(v.type is None for v in self.vs))
        self.assertTrue(all(v.reed2 is None for v in self.vs))

    def test_theaternaam_met_komma_blijft_heel(self):
        heerlen = [v for v in self.vs if v.plaats == "HEERLEN"][0]
        self.assertEqual(heerlen.theater, "PLT, Theater Heerlen")

    def test_jaargrens_levert_gewoon_2027_op(self):
        self.assertIn(date(2027, 1, 17), [v.datum for v in self.vs])


class TestValidatie(unittest.TestCase):
    def test_gewijzigde_opmaak_geeft_een_parsefout(self):
        # Als de site verbouwd wordt moet dat opvallen, niet stil doorlopen.
        with self.assertRaises(ParseFout):
            parse_website("<html><body><p>Binnenkort meer</p></body></html>")

    def test_een_onleesbare_rij_maakt_de_pagina_onvolledig(self):
        # Eén rij met de attributen in een andere volgorde matcht niet. De
        # overige rijen komen gewoon door, maar de vlag zegt dat er iets mist —
        # anders zou die rij later als "ontbreekt op de site" gemeld worden.
        kreupel = FIXTURE.replace(
            '<td class="date" data-label="Datum"><strong>17-01-2027</strong>',
            '<td data-label="Datum" class="date"><strong>17-01-2027</strong>',
        )
        vs, volledig = parse_website(kreupel)
        self.assertEqual(len(vs), 2)
        self.assertFalse(volledig)

    def test_een_datumcel_in_een_script_telt_niet_mee(self):
        # De echte pagina heeft een JavaScript-sjabloon dat op een datumcel
        # lijkt. Dat mag de pagina niet onvolledig maken.
        met_script = FIXTURE.replace(
            "</table>",
            '</table><script>var rij = \'<td class="date">${datum}</td>\';</script>',
        )
        vs, volledig = parse_website(met_script)
        self.assertEqual(len(vs), 3)
        self.assertTrue(volledig)


if __name__ == "__main__":
    unittest.main()
