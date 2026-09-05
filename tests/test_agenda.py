import unittest
from datetime import date, time
from pathlib import Path

from catscheck.agenda import parse_agenda

FIXTURE = (Path(__file__).parent / "fixtures" / "agenda.ics").read_text(encoding="utf-8")


class TestParseAgenda(unittest.TestCase):
    def setUp(self):
        self.items, self.overgeslagen, self.onleesbaar = parse_agenda(FIXTURE)

    def test_leest_een_afspraak_met_tijdzone(self):
        item = [i for i in self.items if i.titel == "Cats Almere"][0]
        self.assertEqual(item.datum, date(2026, 10, 6))
        self.assertEqual(item.start, time(17, 15))

    def test_utc_wordt_omgerekend_naar_nederlandse_tijd(self):
        # 16:00 UTC in oktober is 18:00 in Amsterdam (zomertijd).
        item = [i for i in self.items if i.titel == "CATS Carre"][0]
        self.assertEqual(item.datum, date(2026, 10, 15))
        self.assertEqual(item.start, time(18, 0))

    def test_afspraak_van_een_hele_dag_heeft_geen_starttijd(self):
        item = [i for i in self.items if i.datum == date(2026, 10, 11)][0]
        self.assertIsNone(item.start)

    def test_gevouwen_regels_worden_weer_aan_elkaar_geplakt(self):
        item = [i for i in self.items if i.datum == date(2026, 10, 11)][0]
        self.assertEqual(
            item.titel,
            "Cats Almere matinee en verder nog een hele lange titel die over twee regels loopt",
        )

    def test_herhalende_afspraken_worden_overgeslagen_en_geteld(self):
        self.assertNotIn("Wekelijkse les", [i.titel for i in self.items])
        self.assertEqual(self.overgeslagen, 1)

    def test_niet_cats_afspraken_blijven_gewoon_staan(self):
        # Filteren op trefwoord gebeurt later, in vergelijk.py.
        self.assertIn("Verjaardag Joost", [i.titel for i in self.items])
        self.assertEqual(self.onleesbaar, 0)

    def test_afspraak_zonder_begintijd_wordt_geteld_niet_stil_weggegooid(self):
        # Een VEVENT zonder DTSTART valt niet te plaatsen. Hij mag niet
        # geruisloos verdwijnen: het rapport moet kunnen melden dat de
        # controle niet over alles ging.
        kapot = FIXTURE.replace(
            "DTSTART;TZID=Europe/Amsterdam:20261020T200000\n", ""
        )
        items, herhalend, onleesbaar = parse_agenda(kapot)
        self.assertEqual(onleesbaar, 1)
        self.assertNotIn("Verjaardag Joost", [i.titel for i in items])


if __name__ == "__main__":
    unittest.main()
