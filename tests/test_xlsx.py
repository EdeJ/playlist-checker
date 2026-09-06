import io
import unittest
import zipfile

from catscheck.model import ParseFout
from catscheck.xlsx import lees_tabbladen
from tests.xlsxhulp import kolomnaam, maak_xlsx


def _herbouw_met_wijziging(data, naam, nieuwe_inhoud):
    """Geef `data` terug met het zip-lid `naam` vervangen door nieuwe_inhoud."""
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        leden = {n: z.read(n) for n in z.namelist()}
    leden[naam] = nieuwe_inhoud
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        for n, inhoud in leden.items():
            z.writestr(n, inhoud)
    return buffer.getvalue()


class TestKolomnaam(unittest.TestCase):
    def test_eerste_kolommen(self):
        self.assertEqual(kolomnaam(0), "A")
        self.assertEqual(kolomnaam(16), "Q")
        self.assertEqual(kolomnaam(25), "Z")

    def test_voorbij_z(self):
        self.assertEqual(kolomnaam(26), "AA")


class TestLeesTabbladen(unittest.TestCase):
    def test_geeft_tabbladen_in_bladvolgorde(self):
        data = maak_xlsx({"INPUT": [["a"]], "Oktober": [["b"]]})
        self.assertEqual([naam for naam, _ in lees_tabbladen(data)], ["INPUT", "Oktober"])

    def test_verborgen_tabbladen_komen_er_niet_in(self):
        # De Mamma Mia-tabbladen staan op hidden en horen bij een andere
        # productie; die mogen nooit als Cats-voorstellingen meetellen.
        data = maak_xlsx({"Oktober": [["b"]], "Feb": [["x"]]}, verborgen=("Feb",))
        self.assertEqual([naam for naam, _ in lees_tabbladen(data)], ["Oktober"])

    def test_lege_cellen_houden_hun_kolompositie(self):
        # Excel laat lege cellen weg. Wie de rij dan gewoon achter elkaar
        # plakt, schuift elke naam een kolom op en leest de verkeerde stoel.
        data = maak_xlsx({"Oktober": [["Di", "", "", "TO"]]})
        (_, rijen), = lees_tabbladen(data)
        self.assertEqual(rijen[0], ["Di", "", "", "TO"])

    def test_rij_zonder_cellen_blijft_een_lege_rij(self):
        data = maak_xlsx({"Oktober": [[], ["Di"]]})
        (_, rijen), = lees_tabbladen(data)
        self.assertEqual(rijen, [[], ["Di"]])

    def test_kolommen_voorbij_z_komen_op_de_juiste_plek(self):
        rij = ["x"] * 27
        rij[26] = "BIJZITTERS"
        data = maak_xlsx({"Oktober": [rij]})
        (_, rijen), = lees_tabbladen(data)
        self.assertEqual(rijen[0][26], "BIJZITTERS")

    def test_getalcellen_zonder_t_attribuut_worden_gelezen(self):
        # Het echte bestand bewaart dagnummer en tijd als kale <v>, zonder
        # t-attribuut. Die tak mag niet verward worden met tekst.
        data = maak_xlsx({"Oktober": [["6.0", "0.84375"]]})
        (_, rijen), = lees_tabbladen(data)
        self.assertEqual(rijen[0], ["6.0", "0.84375"])

    def test_inline_string_cel_wordt_ook_gelezen(self):
        # Het echte bestand gebruikt dit nooit (zie maak_xlsx), maar de tak
        # bestaat nog in xlsx.py en moet dus gedekt blijven.
        data = maak_xlsx({"Oktober": [["Emiel"]]}, inline=True)
        (_, rijen), = lees_tabbladen(data)
        self.assertEqual(rijen[0], ["Emiel"])


class TestOnleesbaar(unittest.TestCase):
    def test_geen_zip_geeft_een_parsefout(self):
        # Wordt de linkdeling ingetrokken, dan levert curl een inlogpagina op
        # in plaats van het bestand. Dat moet stoppen, niet stil doorgaan.
        with self.assertRaises(ParseFout) as ctx:
            lees_tabbladen(b"<html>Sign in to continue</html>")
        self.assertIn("xlsx", str(ctx.exception))

    def test_zip_zonder_werkmap_geeft_een_parsefout(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as z:
            z.writestr("iets.txt", "geen xlsx")
        with self.assertRaises(ParseFout):
            lees_tabbladen(buffer.getvalue())

    def test_kapotte_gedeelde_tekst_verwijzing_geeft_een_parsefout(self):
        # Elke tekstcel in het echte bestand is een gedeelde tekst. Raakt
        # sharedStrings.xml gedeeltelijk stuk of verschuift een index, dan
        # verwijst een cel naar een tekst die er niet is — dat is geen lege
        # cel maar een onbegrepen bestand, en mag niet als "" doorglijden.
        data = maak_xlsx({"Oktober": [["Emiel"]]})
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            sheet = z.read("xl/worksheets/sheet1.xml").decode("utf-8")
        kapot = sheet.replace("<v>0</v>", "<v>99</v>")
        self.assertNotEqual(kapot, sheet)
        data = _herbouw_met_wijziging(data, "xl/worksheets/sheet1.xml", kapot.encode("utf-8"))
        with self.assertRaises(ParseFout):
            lees_tabbladen(data)

    def test_kapotte_sharedstrings_xml_geeft_een_parsefout(self):
        # Een geldige zip met een halve sharedStrings.xml erin gaf voorheen
        # een xml.etree.ElementTree.ParseError, geen ParseFout: een Engelse
        # traceback en afsluitcode 1 in plaats van 2.
        data = maak_xlsx({"Oktober": [["Emiel"]]})
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            kapot = z.read("xl/sharedStrings.xml")[:20]
        data = _herbouw_met_wijziging(data, "xl/sharedStrings.xml", kapot)
        with self.assertRaises(ParseFout):
            lees_tabbladen(data)

    def test_kapot_tabblad_geeft_een_parsefout(self):
        data = maak_xlsx({"Oktober": [["Emiel"]]})
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            kapot = z.read("xl/worksheets/sheet1.xml")[:30]
        data = _herbouw_met_wijziging(data, "xl/worksheets/sheet1.xml", kapot)
        with self.assertRaises(ParseFout):
            lees_tabbladen(data)


if __name__ == "__main__":
    unittest.main()
