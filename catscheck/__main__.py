"""Commandoregel voor de Cats speellijst-checker.

Leest uitsluitend lokale bestanden uit de cachemap. Doet zelf geen enkel
netwerkverzoek: het ophalen van de bronnen gebeurt door Claude, met alleen-
lees-tools.
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from catscheck.agenda import parse_agenda
from catscheck.model import ParseFout
from catscheck.orkest import parse_orkest
from catscheck.rapport import SAMENVATTEN_VANAF, maak_rapport
from catscheck.reed2 import parse_reed2
from catscheck.vergelijk import Instellingen, vergelijk
from catscheck.website import parse_website


def main(argv=None):
    p = argparse.ArgumentParser(description="Controleer de Cats-speellijsten op verschillen.")
    p.add_argument("--cache", default="cache", type=Path, help="map met de opgehaalde bronnen")
    p.add_argument("--config", default="config/trefwoorden.json", type=Path)
    p.add_argument("--vanaf", default=None, help="peildatum JJJJ-MM-DD, standaard vandaag")
    p.add_argument("--alles", action="store_true", help="vat lange groepen niet samen")
    args = p.parse_args(argv)

    # Ook deze twee lezen invoer van de gebruiker. Zonder vangnet leveren ze
    # een Engelse traceback met afsluitcode 1 op, en dat is precies de code die
    # "er zijn verschillen gevonden" betekent. Een script kan een crash dan
    # niet van een geslaagde controle onderscheiden.
    try:
        vanaf = date.fromisoformat(args.vanaf) if args.vanaf else date.today()
    except ValueError:
        print(
            f"Ongeldige peildatum {args.vanaf!r}; schrijf hem als JJJJ-MM-DD.",
            file=sys.stderr,
        )
        return 2

    try:
        inst = _lees_instellingen(args.config)
    except (json.JSONDecodeError, OSError, ParseFout) as fout:
        print(f"Kan {args.config} niet lezen: {fout}", file=sys.stderr)
        return 2

    try:
        orkest = parse_orkest(_lees(args.cache / "orkest.txt"))
        reed2 = parse_reed2(_lees(args.cache / "reed2.csv"))
        website, website_volledig = parse_website(_lees(args.cache / "website.html"))
        agenda, overgeslagen, onleesbaar = parse_agenda(_lees(args.cache / "agenda.ics"))
    except ParseFout as fout:
        print(f"De controle kon niet worden uitgevoerd: {fout}", file=sys.stderr)
        return 2
    except FileNotFoundError as fout:
        print(
            f"Bronbestand ontbreekt: {fout.filename}\n"
            f"Vraag Claude de bronnen op te halen (/cats-check).",
            file=sys.stderr,
        )
        return 2

    # Is de pagina maar half gelezen, dan levert vergelijken met de website
    # alleen verzonnen verschillen op. De rest van de controle gaat wel door.
    meldingen = vergelijk(
        orkest, reed2, website if website_volledig else [], agenda, inst, vanaf
    )
    print(maak_rapport(
        meldingen, vanaf, overgeslagen,
        samenvatten_vanaf=10 ** 9 if args.alles else SAMENVATTEN_VANAF,
        website_onbetrouwbaar=not website_volledig,
        onleesbare_afspraken=onleesbaar,
    ))
    return 1 if meldingen else 0


def _lees(pad):
    return Path(pad).read_text(encoding="utf-8")


def _lees_instellingen(pad):
    """Lees en valideer config/trefwoorden.json.

    Zonder deze validatie geeft een lijst of losse tekenreeks in plaats van
    een object een Engelse traceback met afsluitcode 1 — dezelfde code als
    "er zijn meldingen"; een tekenreeks bij trefwoorden wordt zonder
    foutmelding stilzwijgend een tuple losse letters, waardoor bijna elke
    afspraak als Cats-gerelateerd telt. Beide zijn erger dan een duidelijke
    Nederlandse foutmelding.
    """
    if not Path(pad).exists():
        return Instellingen()
    rauw = json.loads(Path(pad).read_text(encoding="utf-8"))
    if not isinstance(rauw, dict):
        raise ParseFout(
            f"{pad} moet een JSON-object zijn (met sleutels als 'trefwoorden'), "
            f"geen {type(rauw).__name__}"
        )
    trefwoorden = rauw.get("trefwoorden", ["cats"])
    if not isinstance(trefwoorden, list) or not all(isinstance(t, str) for t in trefwoorden):
        raise ParseFout("'trefwoorden' in {} moet een lijst met tekst zijn".format(pad))
    if not trefwoorden:
        # Een lege lijst schakelt de agendacontrole zonder enig signaal uit:
        # geen enkele afspraak matcht dan nog, dus geen enkele KRITIEK-melding
        # over een missend agenda-item komt nog boven water.
        raise ParseFout(f"'trefwoorden' in {pad} mag niet leeg zijn")
    mijn_naam = rauw.get("mijn_naam", "emiel")
    if not isinstance(mijn_naam, str):
        # Namen worden overal genormaliseerd vergeleken (lowercase); een
        # niet-tekst hier — of een verkeerde hoofdlettering die vergeten
        # wordt genormaliseerd — laat elke naamvergelijking mislukken.
        raise ParseFout(f"'mijn_naam' in {pad} moet tekst zijn")
    try:
        marge_voor = int(rauw.get("marge_voor_minuten", 240))
        marge_na = int(rauw.get("marge_na_minuten", 30))
    except (TypeError, ValueError):
        raise ParseFout(
            f"'marge_voor_minuten' en 'marge_na_minuten' in {pad} moeten getallen zijn"
        ) from None
    return Instellingen(
        mijn_naam=mijn_naam.lower(),
        marge_voor_minuten=marge_voor,
        marge_na_minuten=marge_na,
        trefwoorden=tuple(t.lower() for t in trefwoorden),
    )


if __name__ == "__main__":
    sys.exit(main())
