"""De orkestlijst-fixture als tabel.

Kolom 14 is Reed 1 en kolom 16 is Reed 2; die twee liggen naast elkaar en
worden makkelijk verwisseld, dus ze staan in bijna elke rij ingevuld.
"""

from tests.xlsxhulp import maak_xlsx

KOP = [
    "OKTOBER", "", "", "", "", "",
    "MD", "Overnachten MD",
    "Toetsen 1", "Overnachten Toetsen 1",
    "Toetsen 2", "Overnachten Toetsen 2",
    "Toetsen 3", "Overnachten Toetsen 3",
    "Reed 1", "Overnachten Reed 1",
    "Reed 2", "Overnachten Reed 2",
    "Drums", "Overnachten Drums",
    "Gitaar", "Overnachten Gitaar",
    "Bass", "Overnachten Bass",
    "", "OPMERKINGEN", "BIJZITTERS",
]


def kop(maand, extra=()):
    return [maand] + KOP[1:] + list(extra)


def rij(weekdag, dag, tijd, soort, plaats, reed1="", reed2="", staart=()):
    return ([weekdag, dag, tijd, soort, plaats, "", "", "", "Hajo ", "", "Hans", "",
             "Charles ", "", reed1, "", reed2] + list(staart))


ORKEST_TABBLADEN = {
    "INPUT": [["Namen", "MD/Keys"], ["", "Steven"]],
    "Oktober": [
        [],
        kop("OKTOBER"),
        rij("Di", "6.0", "0.84375", "TO", "Almere", "Marielle", "Emiel",
            staart=["", "", "", "Jurgen", "", "Marijn", "Nee", "", "", "hans"]),
        rij("Woe", "7.0", "0.84375", "TO", "Almere", "Marielle", "Emiel"),
        ["Ma", "12.0"],
        rij("Vr", "23.0", "0.625", "REG", "Amsterdam", "Marielle", "Emiel"),
        rij("Vr", "23.0", "0.833333333333333", "REG", "Amsterdam", "Marielle", "Emiel"),
    ],
    "December": [
        kop("DECEMBER"),
        ["Zo", "13.0", "0.604166666666667", "REG", "Zoetermeer", "", "", "", "Hajo ", "",
         "Hans", "Nee", "(leeg)", "", "Marielle", "", "Emiel"],
    ],
    "Januari ": [
        kop("Januari", extra=["BIJZITTERS"]),
        ["Za", "2.0", "0.604166666666667", "REG", "Breda", "", "", "", "Tom", "", "", "",
         "", "", "Coen"],
    ],
    "Maart ": [
        kop("Maart", extra=["BIJZITTERS"]),
        rij("Woe ", "31.0", "0.833333333333333", "REG", "Amterdam DLM", "Marielle", "Michiel "),
    ],
    "Feb": [["FEBRUARI", "", "", "", "MD/Keys", "Guitar 1"],
            ["Sun", "1.0", "0.479166666666667", "", "", "Max"]],
    "Ma": [["MAART", "", "", "", "MD/Keys", "Guitar 1"]],
}

VERBORGEN = ("Feb", "Ma")


def orkest_xlsx(tabbladen=None):
    return maak_xlsx(tabbladen or ORKEST_TABBLADEN, verborgen=VERBORGEN)
