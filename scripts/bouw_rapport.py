#!/usr/bin/env python3
"""Bouw de HTML-rapportpagina uit de JSON-uitvoer van catscheck --json.

    python3 -m catscheck --zonder-agenda --json | python3 scripts/bouw_rapport.py - rapport.html

Vult scripts/rapport_sjabloon.html met de bevindingen. Groepeert lange,
herhalende groepen net als catscheck/rapport.py._herhaalt_zich — dat is
bewust dubbel: dit script bouwt de webpagina, rapport.py de terminaltekst,
en beide moeten onafhankelijk van elkaar leesbaar blijven.
"""
import html
import json
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

SAMENVATTEN_VANAF = 15

ERNST_VOLGORDE = ["KRITIEK", "VERSCHIL", "WEBSITE", "OPEN"]
ERNST_INFO = {
    "KRITIEK": ("KRITIEK", "dit raakt jou direct", "kritiek"),
    "VERSCHIL": ("VERSCHIL", "orkestlijst tegenover jullie reed 2-sheet", "verschil"),
    "WEBSITE": ("WEBSITE", "musicalcats.nl wijkt af (niet de bron)", "website"),
    "OPEN": ("NOG IN TE VULLEN", "orkestlijst nog niet compleet", "open"),
}

SJABLOON = Path(__file__).parent / "rapport_sjabloon.html"


def _herhaalt_zich(groep):
    return len({m["tekst"] for m in groep}) * 2 <= len(groep)


def _fmt_datum(iso):
    return date.fromisoformat(iso).strftime("%d-%m-%Y")


def _render_groep(ernst, groep):
    mag_samenvatten = ernst != "KRITIEK"
    if mag_samenvatten and len(groep) > SAMENVATTEN_VANAF and _herhaalt_zich(groep):
        eerste, laatste = _fmt_datum(groep[0]["datum"]), _fmt_datum(groep[-1]["datum"])
        rijen = "".join(
            f'<li class="sum-row"><span class="sum-n">{aantal}&times;</span>'
            f'<span class="sum-t">{html.escape(tekst)}</span></li>'
            for tekst, aantal in Counter(m["tekst"] for m in groep).most_common()
        )
        return (
            f'<p class="groep-samengevat">{len(groep)} meldingen, van {eerste} '
            f'tot en met {laatste}:</p><ul class="sum-list">{rijen}</ul>'
        )
    items = "".join(
        f'<li class="melding"><span class="datum">{_fmt_datum(m["datum"])}</span>'
        f'<span class="tekst">{html.escape(m["tekst"])}</span>'
        + "".join(f'<div class="detail">{html.escape(d)}</div>' for d in m["details"])
        + "</li>"
        for m in groep
    )
    return f'<ul class="melding-list">{items}</ul>'


def _secties_html(meldingen):
    per_ernst = defaultdict(list)
    for m in meldingen:
        per_ernst[m["ernst"]].append(m)

    tellingen = {e: len(per_ernst.get(e, [])) for e in ERNST_VOLGORDE}

    if not meldingen:
        return tellingen, '<p class="alles-goed">Geen verschillen gevonden. Alle bronnen zijn het eens.</p>'

    secties = []
    for ernst in ERNST_VOLGORDE:
        groep = sorted(per_ernst.get(ernst, []), key=lambda m: (m["datum"], m["tekst"]))
        if not groep:
            continue
        kop, sub, klasse = ERNST_INFO[ernst]
        secties.append(
            f'<section class="sectie sectie-{klasse}" id="{klasse}">'
            f'<div class="sectie-kop"><h2>{kop}</h2>'
            f'<span class="sectie-sub">{sub}</span>'
            f'<span class="sectie-aantal">{len(groep)}</span></div>'
            f'{_render_groep(ernst, groep)}</section>'
        )
    return tellingen, "".join(secties)


def bouw(data, bijgewerkt_tekst):
    tellingen, secties = _secties_html(data["meldingen"])
    if data.get("agenda_gecontroleerd", True):
        agenda_note = "agenda: meegenomen"
    else:
        agenda_note = "agenda: niet meegenomen (alleen bij handmatige run vanaf Emiels laptop)"

    sjabloon = SJABLOON.read_text(encoding="utf-8")
    vervangingen = {
        "{{PEILDATUM}}": _fmt_datum(data["peildatum"]),
        "{{TIJDSTIP}}": bijgewerkt_tekst,
        "{{AGENDA_NOTE}}": agenda_note,
        "{{STRIP_KRITIEK}}": str(tellingen["KRITIEK"]),
        "{{STRIP_VERSCHIL}}": str(tellingen["VERSCHIL"]),
        "{{STRIP_WEBSITE}}": str(tellingen["WEBSITE"]),
        "{{STRIP_OPEN}}": str(tellingen["OPEN"]),
        "{{SECTIES}}": secties,
    }
    for sleutel, waarde in vervangingen.items():
        sjabloon = sjabloon.replace(sleutel, waarde)
    return sjabloon, tellingen


def main(argv):
    if len(argv) != 3:
        print(f"gebruik: {argv[0]} <json-pad|-> <output-html-pad> [bijgewerkt-tekst]", file=sys.stderr)
        return 2
    json_pad, uit_pad = argv[1], argv[2]
    ruw = sys.stdin.read() if json_pad == "-" else Path(json_pad).read_text(encoding="utf-8")
    data = json.loads(ruw)
    bijgewerkt = datetime_now_tekst()
    html_tekst, tellingen = bouw(data, bijgewerkt)
    Path(uit_pad).write_text(html_tekst, encoding="utf-8")
    print(json.dumps(tellingen))
    return 0


def datetime_now_tekst():
    from datetime import datetime
    return datetime.now().strftime("%d-%m-%Y, %H:%M")


if __name__ == "__main__":
    sys.exit(main(sys.argv))
