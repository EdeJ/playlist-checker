import unittest
from datetime import date, time

from catscheck.model import AgendaItem, Ernst, Voorstelling
from catscheck.vergelijk import Instellingen, vergelijk

VANAF = date(2026, 1, 1)
INST = Instellingen()


def v(bron, dag, tijd, reed2=None, plaats="ALMERE", soort="REG", theater=None):
    return Voorstelling(
        datum=dag, tijd=tijd, type=soort, plaats=plaats, theater=theater,
        reed2=reed2, bron=bron, herkomst="test",
    )


def leeg():
    return []


class TestBezetting(unittest.TestCase):
    def test_naamverschil_met_emiel_is_kritiek(self):
        m = vergelijk(
            [v("orkest", date(2026, 10, 22), "20:00", "christof")],
            [v("reed2", date(2026, 10, 22), "20:00", "emiel")],
            leeg(), leeg(), INST, VANAF,
        )
        kritiek = [x for x in m if x.ernst is Ernst.KRITIEK]
        self.assertEqual(len(kritiek), 1)
        self.assertIn("christof", kritiek[0].tekst)
        self.assertIn("emiel", kritiek[0].tekst)

    def test_naamverschil_tussen_collegas_is_een_verschil_geen_kritiek(self):
        m = vergelijk(
            [v("orkest", date(2026, 10, 22), "20:00", "christof")],
            [v("reed2", date(2026, 10, 22), "20:00", "michiel")],
            leeg(), leeg(), INST, VANAF,
        )
        self.assertEqual([x.ernst for x in m], [Ernst.VERSCHIL])

    def test_onbekende_naam_bij_reed2_is_altijd_kritiek(self):
        m = vergelijk(
            [v("orkest", date(2026, 10, 22), "20:00", "marielle")],
            [v("reed2", date(2026, 10, 22), "20:00", "michiel")],
            leeg(), leeg(), INST, VANAF,
        )
        kritiek = [x for x in m if x.ernst is Ernst.KRITIEK]
        self.assertEqual(len(kritiek), 1)
        self.assertIn("marielle", kritiek[0].tekst)

    def test_lege_cel_in_de_orkestlijst_is_open(self):
        m = vergelijk(
            [v("orkest", date(2026, 10, 22), "20:00", None)],
            [v("reed2", date(2026, 10, 22), "20:00", "michiel")],
            leeg(), leeg(), INST, VANAF,
        )
        self.assertEqual([x.ernst for x in m], [Ernst.OPEN])

    def test_orkestlijst_zegt_vrij_waar_reed2_sheet_een_voorstelling_heeft(self):
        # Verifieerd geval: de reed 2-sheet noemt een voorstelling op een dag
        # die in de orkestlijst niet als voorstelling voorkomt (VRIJ, dus
        # gefilterd door NEGEER_TYPES) — binnen het overlap van beide bronnen
        # moet dit als verschil gemeld worden, niet stil verdwijnen.
        m = vergelijk(
            [v("orkest", date(2026, 10, 22), None, None, soort="VRIJ", plaats=None)],
            [v("reed2", date(2026, 10, 22), "20:00", "emiel")],
            leeg(), leeg(), INST, VANAF,
        )
        verschillen = [x for x in m if "niet in de orkestlijst" in x.tekst]
        self.assertEqual(len(verschillen), 1)
        self.assertIs(verschillen[0].ernst, Ernst.VERSCHIL)

    def test_reed2_sheet_mist_een_voorstelling_die_de_orkestlijst_wel_heeft(self):
        # Beide bronnen hebben een gedeeld ankerpunt (6 oktober) zodat hun
        # bereik overlapt; 22 oktober staat alleen in de orkestlijst.
        m = vergelijk(
            [v("orkest", date(2026, 10, 6), "20:00", "emiel"),
             v("orkest", date(2026, 10, 22), "20:00", "emiel")],
            [v("reed2", date(2026, 10, 6), "20:00", "emiel"),
             v("reed2", date(2026, 10, 23), "20:00", "emiel")],
            leeg(), leeg(), INST, VANAF,
        )
        verschillen = [x for x in m if "niet in jullie reed 2-sheet" in x.tekst]
        self.assertEqual(len(verschillen), 1)
        self.assertEqual(verschillen[0].datum, date(2026, 10, 22))
        self.assertIs(verschillen[0].ernst, Ernst.VERSCHIL)

    def test_reed2_rij_met_naam_en_datum_maar_leeg_type_telt_mee_als_verschil(self):
        # Verifieerd geval: een reed 2-rij met datum en naam maar een blanco
        # Type-kolom. Zo'n rij valt uit _per_dag (None zit niet in
        # SPEEL_TYPES), dus de orkestlijst-voorstelling die dag lijkt uit de
        # reed 2-sheet te ontbreken. Dat wordt hier apart afgevangen door
        # Important 6 (onbekende_types); hier alleen checken dat het niet
        # stilzwijgend verdwijnt.
        m = vergelijk(
            [v("orkest", date(2026, 10, 22), "20:00", "emiel")],
            [v("reed2", date(2026, 10, 22), "20:00", "emiel", soort=None)],
            leeg(), leeg(), INST, VANAF,
        )
        self.assertTrue(any("niet in jullie reed 2-sheet" in x.tekst for x in m))

    def test_verschil_buiten_het_overlap_van_beide_bronnen_wordt_niet_gemeld(self):
        # De reed 2-sheet begint twee weken eerder dan de orkestlijst. Die
        # twee weken zijn geen tegenspraak, alleen een voorsprong.
        m = vergelijk(
            [v("orkest", date(2026, 10, 6), "20:00", "emiel")],
            [v("reed2", date(2026, 9, 24), "20:00", "emiel"),
             v("reed2", date(2026, 10, 6), "20:00", "emiel")],
            leeg(), leeg(), INST, VANAF,
        )
        self.assertFalse(any("niet in de orkestlijst" in x.tekst for x in m))
        self.assertFalse(any("niet in jullie reed 2-sheet" in x.tekst for x in m))

    def test_gelijke_bezetting_levert_niets_op(self):
        m = vergelijk(
            [v("orkest", date(2026, 10, 22), "20:00", "emiel")],
            [v("reed2", date(2026, 10, 22), "20:00", "emiel")],
            leeg(),
            [AgendaItem(date(2026, 10, 22), time(17, 0), "Cats Almere", "x")],
            INST, VANAF,
        )
        self.assertEqual(m, [])


class TestVoorstellingen(unittest.TestCase):
    def test_verschillende_aanvangstijd_wordt_gemeld_als_tijdsverschil(self):
        m = vergelijk(
            [v("orkest", date(2026, 10, 11), "15:00", "emiel")],
            [v("reed2", date(2026, 10, 11), "14:30", "emiel")],
            leeg(),
            [AgendaItem(date(2026, 10, 11), time(12, 30), "Cats", "x")],
            INST, VANAF,
        )
        tijden = [x for x in m if "15:00" in x.tekst and "14:30" in x.tekst]
        self.assertEqual(len(tijden), 1)
        self.assertIs(tijden[0].ernst, Ernst.VERSCHIL)

    def test_verschillende_plaats_wordt_gemeld(self):
        m = vergelijk(
            [v("orkest", date(2027, 5, 20), "19:45", "emiel", plaats="DEN BOSCH")],
            [v("reed2", date(2027, 5, 20), "19:45", "emiel", plaats="DEN HAAG")],
            leeg(),
            [AgendaItem(date(2027, 5, 20), time(17, 0), "Cats", "x")],
            INST, VANAF,
        )
        self.assertTrue(any("DEN BOSCH" in x.tekst and "DEN HAAG" in x.tekst for x in m))

    def test_dag_met_twee_shows_tegenover_een_dag_met_een_show(self):
        m = vergelijk(
            [v("orkest", date(2026, 10, 24), "15:00", "michiel"),
             v("orkest", date(2026, 10, 24), "20:00", "michiel")],
            [v("reed2", date(2026, 10, 24), "20:00", "michiel")],
            leeg(), leeg(), INST, VANAF,
        )
        self.assertTrue(any("aantal voorstellingen" in x.tekst.lower() for x in m))

    def test_website_verschil_is_alleen_informatief(self):
        m = vergelijk(
            [v("orkest", date(2027, 5, 20), "19:45", "michiel", plaats="DEN BOSCH")],
            [v("reed2", date(2027, 5, 20), "19:45", "michiel", plaats="DEN BOSCH")],
            [v("website", date(2027, 5, 20), "19:45", None, plaats="DEN HAAG")],
            leeg(), INST, VANAF,
        )
        self.assertEqual([x.ernst for x in m], [Ernst.WEBSITE])


class TestOnbekendType(unittest.TestCase):
    def test_onbekend_type_wordt_gemeld_in_plaats_van_stil_overgeslagen(self):
        # "OVERSTA DAG" staat echt in de orkestlijst. Zo'n regel valt buiten
        # elke vergelijking; dat mag hij, maar niet zonder het te zeggen.
        m = vergelijk(
            [v("orkest", date(2027, 2, 7), None, None, soort="OVERSTA DAG")],
            leeg(), leeg(), leeg(), INST, VANAF,
        )
        self.assertEqual(len(m), 1)
        self.assertIn("OVERSTA DAG", m[0].tekst)
        self.assertIs(m[0].ernst, Ernst.VERSCHIL)

    def test_onbekend_type_op_jouw_naam_is_kritiek(self):
        # Een typefout in de typekolom zou anders een voorstelling van Emiel
        # geruisloos uit de controle laten verdwijnen.
        m = vergelijk(
            [v("orkest", date(2027, 2, 7), "20:00", "emiel", soort="REGG")],
            leeg(), leeg(), leeg(), INST, VANAF,
        )
        self.assertEqual([x.ernst for x in m], [Ernst.KRITIEK])
        self.assertIn("REGG", m[0].tekst)


class TestAgenda(unittest.TestCase):
    def test_speelbeurt_zonder_agenda_item_is_kritiek(self):
        m = vergelijk(
            [v("orkest", date(2026, 10, 6), "20:15", "emiel")],
            [v("reed2", date(2026, 10, 6), "20:15", "emiel")],
            leeg(), leeg(), INST, VANAF,
        )
        self.assertEqual([x.ernst for x in m], [Ernst.KRITIEK])
        self.assertIn("agenda", m[0].tekst.lower())

    def test_agenda_item_vier_uur_voor_aanvang_telt_als_gevonden(self):
        m = vergelijk(
            [v("orkest", date(2026, 10, 6), "20:15", "emiel")],
            [v("reed2", date(2026, 10, 6), "20:15", "emiel")],
            leeg(),
            [AgendaItem(date(2026, 10, 6), time(16, 15), "Cats Almere", "x")],
            INST, VANAF,
        )
        self.assertEqual(m, [])

    def test_agenda_item_ruim_te_vroeg_valt_buiten_het_venster(self):
        m = vergelijk(
            [v("orkest", date(2026, 10, 6), "20:15", "emiel")],
            [v("reed2", date(2026, 10, 6), "20:15", "emiel")],
            leeg(),
            [AgendaItem(date(2026, 10, 6), time(9, 0), "Cats Almere", "x")],
            INST, VANAF,
        )
        self.assertEqual([x.ernst for x in m], [Ernst.KRITIEK])

    def test_verkeerde_tijd_meldt_de_tijd_en_niet_dat_het_ontbreekt(self):
        # Staat het item op dezelfde dag maar ver buiten het venster, dan is de
        # tijd verkeerd genoteerd. Eén melding daarover — niet twee meldingen
        # die allebei het tegendeel beweren.
        m = vergelijk(
            [v("orkest", date(2026, 10, 6), "20:15", "emiel")],
            [v("reed2", date(2026, 10, 6), "20:15", "emiel")],
            leeg(),
            [AgendaItem(date(2026, 10, 6), time(9, 0), "Cats Almere", "x")],
            INST, VANAF,
        )
        self.assertEqual(len(m), 1)
        self.assertIn("09:00", m[0].tekst)
        self.assertIn("20:15", m[0].tekst)
        self.assertNotIn("niets in je agenda", m[0].tekst)

    def test_agenda_item_na_aanvang_valt_buiten_het_venster(self):
        m = vergelijk(
            [v("orkest", date(2026, 10, 6), "20:15", "emiel")],
            [v("reed2", date(2026, 10, 6), "20:15", "emiel")],
            leeg(),
            [AgendaItem(date(2026, 10, 6), time(21, 30), "Cats Almere", "x")],
            INST, VANAF,
        )
        self.assertEqual([x.ernst for x in m], [Ernst.KRITIEK])

    def test_hele_dag_item_telt_als_aanwezig_maar_meldt_dat_de_tijd_niet_toetsbaar_is(self):
        m = vergelijk(
            [v("orkest", date(2026, 10, 6), "20:15", "emiel")],
            [v("reed2", date(2026, 10, 6), "20:15", "emiel")],
            leeg(),
            [AgendaItem(date(2026, 10, 6), None, "Cats Almere", "x")],
            INST, VANAF,
        )
        self.assertEqual(len(m), 1)
        self.assertIn("hele dag", m[0].tekst.lower())

    def test_cats_agenda_item_zonder_speelbeurt_is_kritiek(self):
        # De orkestlijst is voor die dag wel ingevuld — iemand anders speelt.
        m = vergelijk(
            [v("orkest", date(2026, 10, 7), "20:00", "michiel")],
            leeg(), leeg(),
            [AgendaItem(date(2026, 10, 7), time(17, 0), "Cats Almere", "x")],
            INST, VANAF,
        )
        self.assertEqual([x.ernst for x in m], [Ernst.KRITIEK])
        self.assertIn("geen speelbeurt", m[0].tekst.lower())

    def test_agenda_item_na_het_ingevulde_deel_is_geen_kritiek(self):
        # De orkestlijst houdt op 06-10-2026 op met Reed 2-namen. Een afspraak
        # in januari zegt dus niets over of Emiel daar speelt.
        m = vergelijk(
            [v("orkest", date(2026, 10, 6), "20:00", "michiel")],
            leeg(), leeg(),
            [AgendaItem(date(2027, 1, 20), time(19, 0), "Cats Breda", "x")],
            INST, VANAF,
        )
        self.assertEqual([x.ernst for x in m], [Ernst.OPEN])
        self.assertIn("nog niet ingevuld", m[0].tekst)

    def test_twee_shows_op_een_dag_pikken_elkaars_agenda_item_niet_in(self):
        # Bij 14:00 en 18:00 overlappen de vensters van vier uur. Wie per beurt
        # het dichtstbijzijnde item pakt, laat de matinee het item van de avond
        # inpikken en meldt daarna twee dingen die allebei onwaar zijn.
        m = vergelijk(
            [v("orkest", date(2026, 11, 7), "14:00", "emiel"),
             v("orkest", date(2026, 11, 7), "18:00", "emiel")],
            [v("reed2", date(2026, 11, 7), "14:00", "emiel"),
             v("reed2", date(2026, 11, 7), "18:00", "emiel")],
            leeg(),
            [AgendaItem(date(2026, 11, 7), time(10, 5), "Cats matinee", "a"),
             AgendaItem(date(2026, 11, 7), time(14, 15), "Cats avond", "b")],
            INST, VANAF,
        )
        self.assertEqual(m, [])

    def test_ontbrekend_item_wijst_de_juiste_voorstelling_aan(self):
        # Alleen een afspraak voor de avondvoorstelling. Dan moet de matinee
        # als ontbrekend gemeld worden, niet de avond.
        m = vergelijk(
            [v("orkest", date(2027, 5, 21), "15:00", "emiel"),
             v("orkest", date(2027, 5, 21), "19:45", "emiel")],
            [v("reed2", date(2027, 5, 21), "15:00", "emiel"),
             v("reed2", date(2027, 5, 21), "19:45", "emiel")],
            leeg(),
            [AgendaItem(date(2027, 5, 21), time(16, 0), "Cats avond", "b")],
            INST, VANAF,
        )
        self.assertEqual(len(m), 1)
        self.assertIn("15:00", m[0].tekst)
        self.assertIn("niets in je agenda", m[0].tekst)

    def test_agenda_item_zonder_trefwoord_wordt_genegeerd(self):
        m = vergelijk(
            leeg(), leeg(), leeg(),
            [AgendaItem(date(2026, 10, 7), time(17, 0), "Verjaardag Joost", "x")],
            INST, VANAF,
        )
        self.assertEqual(m, [])

    def test_repetitiedag_uit_de_reed2_sheet_telt_mee_voor_de_agenda(self):
        m = vergelijk(
            leeg(),
            [v("reed2", date(2026, 9, 25), None, "emiel", soort="MON")],
            leeg(), leeg(), INST, VANAF,
        )
        self.assertEqual([x.ernst for x in m], [Ernst.KRITIEK])

    def test_vrije_dagen_leveren_niets_op(self):
        m = vergelijk(
            leeg(),
            [v("reed2", date(2026, 9, 28), None, None, soort="VRIJ", plaats=None)],
            leeg(), leeg(), INST, VANAF,
        )
        self.assertEqual(m, [])


class TestVanaf(unittest.TestCase):
    def test_voorstellingen_voor_de_peildatum_worden_overgeslagen(self):
        m = vergelijk(
            [v("orkest", date(2026, 10, 6), "20:15", "christof")],
            [v("reed2", date(2026, 10, 6), "20:15", "emiel")],
            leeg(), leeg(), INST, date(2026, 11, 1),
        )
        self.assertEqual(m, [])


if __name__ == "__main__":
    unittest.main()
