#!/usr/bin/env python3
"""Bouw de HTML-rapportpagina uit de JSON-uitvoer van catscheck --json.

    python3 -m catscheck --zonder-agenda --json | python3 scripts/bouw_rapport.py - rapport.html

Vult scripts/rapport_sjabloon.html met de bevindingen. Vat, anders dan
catscheck/rapport.py (de terminaltekst), nooit samen: "9x aanvangstijd
verschilt: orkestlijst 15:00, jullie sheet 14:30" is compact maar onbruikbaar
op een pagina waar je juist wilt zien óm welke voorstellingen het gaat. Elke
melding krijgt in plaats daarvan een eigen regel mét een actie-aanwijzing,
zodat de pagina hetzelfde zegt als de toelichting die de checker anders elke
keer opnieuw met de hand zou moeten formuleren.
"""
import html
import json
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

ERNST_VOLGORDE = ["KRITIEK", "VERSCHIL", "WEBSITE", "OPEN"]
ERNST_INFO = {
    "KRITIEK": ("KRITIEK", "dit raakt jou direct", "kritiek"),
    "VERSCHIL": ("VERSCHIL", "orkestlijst tegenover jullie reed 2-sheet", "verschil"),
    "WEBSITE": ("WEBSITE", "musicalcats.nl wijkt af (niet de bron)", "website"),
    "OPEN": ("NOG IN TE VULLEN", "orkestlijst nog niet compleet", "open"),
}

SJABLOON = Path(__file__).parent / "rapport_sjabloon.html"


def _fmt_datum(iso):
    return date.fromisoformat(iso).strftime("%d-%m-%Y")


# Elke actietekst hier komt direct uit .claude/skills/cats-check/SKILL.md
# ("Stap 4 — toelichten"): agenda zelf bijwerken, tijd/plaats/type zelf
# rechtzetten in de orkestlijst (Emiel heeft daar schrijfrechten), en
# verschillen over wíé speelt eerst uitzoeken in plaats van aanpassen. Deze
# functie herkent welke van de drie van toepassing is aan de letterlijke
# formuleringen die catscheck/vergelijk.py produceert.
def _actie(ernst, tekst):
    if ernst == "WEBSITE":
        return "Ter info — musicalcats.nl is niet de bron, geen actie nodig."
    if ernst == "OPEN":
        return "Nog niet ingevuld — geen actie voor jou, gewoon nog open."
    if tekst.startswith("Reed 2 verschilt"):
        return "Eerst uitzoeken met de betrokkenen — niet zomaar aanpassen."
    if "agenda-item" in tekst or tekst.startswith("jij staat ingeroosterd"):
        return "Zelf je agenda bijwerken."
    if tekst.startswith("onbekende naam bij Reed 2"):
        return "Navragen bij wie de orkestlijst invult — dit hoort Emiel, Christof, Coen of Michiel te zijn."
    if tekst.startswith("leeg type") or tekst.startswith("onbekend type"):
        return "Navragen/rechtzetten — deze voorstelling is niet meegenomen in de controle."
    return "Zelf rechtzetten in de orkestlijst — jij hebt daar schrijfrechten."


def _render_groep(ernst, groep):
    items = "".join(
        f'<li class="melding"><span class="datum">{_fmt_datum(m["datum"])}</span>'
        f'<span class="tekst">{html.escape(m["tekst"])}</span>'
        + "".join(f'<div class="detail">{html.escape(d)}</div>' for d in m["details"])
        + f'<div class="actie">&rarr; {html.escape(_actie(ernst, m["tekst"]))}</div>'
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
    if len(argv) not in (3, 4):
        print(f"gebruik: {argv[0]} <json-pad|-> <output-html-pad> [bijgewerkt-tekst]", file=sys.stderr)
        return 2
    json_pad, uit_pad = argv[1], argv[2]
    ruw = sys.stdin.read() if json_pad == "-" else Path(json_pad).read_text(encoding="utf-8")
    data = json.loads(ruw)
    # Zonder expliciete tekst gebruikt de aanroeper zijn eigen lokale klok
    # (datetime.now() zonder tijdzone), wat in een cloud-omgeving UTC kan
    # zijn — geef daarom liever expliciet een al-omgezette lokale tijd mee.
    bijgewerkt = argv[3] if len(argv) == 4 else datetime_now_tekst()
    html_tekst, tellingen = bouw(data, bijgewerkt)
    Path(uit_pad).write_text(html_tekst, encoding="utf-8")
    print(json.dumps(tellingen))
    return 0


def datetime_now_tekst():
    from datetime import datetime
    return datetime.now().strftime("%d-%m-%Y, %H:%M")


if __name__ == "__main__":
    sys.exit(main(sys.argv))
