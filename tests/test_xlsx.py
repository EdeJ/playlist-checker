import unittest

from catscheck.model import ParseFout
from catscheck.xlsx import lees_tabbladen
from tests.xlsxhulp import kolomnaam, maak_xlsx


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
        import io
        import zipfile

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as z:
            z.writestr("iets.txt", "geen xlsx")
        with self.assertRaises(ParseFout):
            lees_tabbladen(buffer.getvalue())


if __name__ == "__main__":
    unittest.main()
