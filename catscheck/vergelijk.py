"""Vergelijk de vier bronnen en lever bevindingen op.

Voorstellingen worden gekoppeld op datum, niet op datum plus tijd. Anders leest
een verschil van 14:30 tegenover 15:00 als twee ontbrekende voorstellingen in
plaats van als één tijdsverschil.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from catscheck.model import (
    Ernst,
    Melding,
    NEGEER_TYPES,
    REED2_NAMEN,
    SPEEL_TYPES,
    WERK_TYPES,
)


@dataclass(frozen=True)
class Instellingen:
    mijn_naam: str = "emiel"
    # Vier uur vooraf, een half uur erna. Emiel zet een matinee-afspraak
    # standaard op 12:00; bij een voorstelling om 15:00 zou drie uur precies
    # de grens zijn, dus daar zit geen speling in.
    marge_voor_minuten: int = 240
    marge_na_minuten: int = 30
    trefwoorden: tuple = ("cats",)


def vergelijk(orkest, reed2, website, agenda, instellingen, vanaf):
    """Geef alle bevindingen terug, ongesorteerd."""
    meldingen = []
    meldingen += _vergelijk_bronnen(orkest, reed2, instellingen, vanaf)
    meldingen += _vergelijk_website(orkest, website, vanaf)
    meldingen += _vergelijk_agenda(orkest, reed2, agenda, instellingen, vanaf)
    return meldingen


# --- orkestlijst tegenover de reed 2-sheet ---------------------------------

def _vergelijk_bronnen(orkest, reed2, inst, vanaf):
    meldingen = []
    per_dag_o = _per_dag(orkest, vanaf)
    per_dag_r = _per_dag(reed2, vanaf, alleen_met_publiek=True)

    for dag in sorted(set(per_dag_o) | set(per_dag_r)):
        o, r = per_dag_o.get(dag, []), per_dag_r.get(dag, [])
        if o and r and len(o) != len(r):
            meldingen.append(Melding(
                Ernst.VERSCHIL, dag,
                f"aantal voorstellingen verschilt: orkestlijst {len(o)}, reed 2-sheet {len(r)}",
                tuple(_omschrijf(x) for x in o + r),
            ))
            continue
        for a, b in zip(o, r):
            meldingen += _vergelijk_paar(dag, a, b, inst)
    return meldingen


def _vergelijk_paar(dag, o, r, inst):
    meldingen = []
    if o.reed2 and o.reed2 not in REED2_NAMEN:
        meldingen.append(Melding(
            Ernst.KRITIEK, dag,
            f"onbekende naam bij Reed 2 in de orkestlijst: {o.reed2!r} — "
            f"dit hoort Emiel, Christof, Coen of Michiel te zijn",
            (f"orkestlijst: {o.herkomst}",),
        ))
    elif o.reed2 is None and r.reed2 is not None:
        meldingen.append(Melding(
            Ernst.OPEN, dag,
            f"orkestlijst nog leeg bij Reed 2; jullie sheet zegt {r.reed2}",
        ))
    elif o.reed2 != r.reed2 and r.reed2 is not None:
        raakt_mij = inst.mijn_naam in (o.reed2, r.reed2)
        meldingen.append(Melding(
            Ernst.KRITIEK if raakt_mij else Ernst.VERSCHIL, dag,
            f"Reed 2 verschilt: orkestlijst {o.reed2}, jullie sheet {r.reed2}",
            (f"{_omschrijf(o)} / {_omschrijf(r)}",),
        ))

    if o.tijd and r.tijd and o.tijd != r.tijd:
        meldingen.append(Melding(
            Ernst.VERSCHIL, dag,
            f"aanvangstijd verschilt: orkestlijst {o.tijd}, jullie sheet {r.tijd}",
        ))
    if o.type and r.type and o.type != r.type:
        meldingen.append(Melding(
            Ernst.VERSCHIL, dag,
            f"type verschilt: orkestlijst {o.type}, jullie sheet {r.type}",
        ))
    if o.plaats and r.plaats and o.plaats != r.plaats:
        meldingen.append(Melding(
            Ernst.VERSCHIL, dag,
            f"plaats verschilt: orkestlijst {o.plaats}, jullie sheet {r.plaats}",
        ))
    return meldingen


# --- orkestlijst tegenover de website --------------------------------------

def _vergelijk_website(orkest, website, vanaf):
    # Is een van beide lijsten leeg, dan is er niets te vergelijken. Zonder deze
    # afslag zou een mislukte ophaalactie elke voorstelling als verschil melden.
    if not orkest or not website:
        return []
    meldingen = []
    per_dag_o = _per_dag(orkest, vanaf)
    per_dag_w = _per_dag(website, vanaf)

    for dag in sorted(set(per_dag_o) | set(per_dag_w)):
        o, w = per_dag_o.get(dag, []), per_dag_w.get(dag, [])
        if not o:
            meldingen.append(Melding(
                Ernst.WEBSITE, dag,
                f"staat wel op musicalcats.nl ({len(w)}x) maar niet in de orkestlijst",
                tuple(_omschrijf(x) for x in w),
            ))
            continue
        if not w:
            meldingen.append(Melding(
                Ernst.WEBSITE, dag,
                f"staat wel in de orkestlijst ({len(o)}x) maar niet op musicalcats.nl",
                tuple(_omschrijf(x) for x in o),
            ))
            continue
        if len(o) != len(w):
            meldingen.append(Melding(
                Ernst.WEBSITE, dag,
                f"aantal voorstellingen verschilt van musicalcats.nl: "
                f"orkestlijst {len(o)}, site {len(w)}",
            ))
            continue
        for a, b in zip(o, w):
            if a.tijd and b.tijd and a.tijd != b.tijd:
                meldingen.append(Melding(
                    Ernst.WEBSITE, dag,
                    f"aanvangstijd wijkt af van de site: orkestlijst {a.tijd}, site {b.tijd}",
                ))
            if a.plaats and b.plaats and a.plaats != b.plaats:
                meldingen.append(Melding(
                    Ernst.WEBSITE, dag,
                    f"plaats wijkt af van de site: orkestlijst {a.plaats}, "
                    f"site {b.plaats} ({b.theater})",
                ))
    return meldingen


# --- speelbeurten tegenover de agenda --------------------------------------

def _vergelijk_agenda(orkest, reed2, agenda, inst, vanaf):
    meldingen = []
    mijn = _mijn_speelbeurten(orkest, reed2, inst, vanaf)
    cats_items = [
        i for i in agenda
        if i.datum >= vanaf
        and any(t in i.titel.lower() for t in inst.trefwoorden)
    ]
    gebruikt = set()

    for beurt in mijn:
        # Op de positie zoeken, niet op waarde: twee identieke agenda-items
        # zouden anders naar dezelfde plek in de lijst wijzen.
        zelfde_dag = [
            (n, i) for n, i in enumerate(cats_items)
            if n not in gebruikt and i.datum == beurt.datum
        ]
        kandidaten = [
            (n, i) for n, i in zelfde_dag if _past_in_venster(i, beurt, inst)
        ]
        if kandidaten:
            nummer, beste = min(kandidaten, key=lambda paar: _afstand(paar[1], beurt))
            gebruikt.add(nummer)
            if beste.start is None:
                meldingen.append(Melding(
                    Ernst.KRITIEK, beurt.datum,
                    f"agenda-item duurt de hele dag, de tijd is dus niet te "
                    f"controleren — {_omschrijf(beurt)}",
                    (f"agenda: {beste.titel}",),
                ))
        elif zelfde_dag:
            # Er staat wel iets, maar op een tijd die niet kan kloppen. Dat is
            # één melding over een verkeerde tijd. Zou het item hier blijven
            # liggen, dan meldde de checker het twee keer: eerst als
            # ontbrekende afspraak, daarna als afspraak zonder speelbeurt —
            # allebei onwaar, want het item hoort juist bij deze voorstelling.
            nummer, dichtstbij = min(
                zelfde_dag, key=lambda paar: _afstand(paar[1], beurt)
            )
            gebruikt.add(nummer)
            klok = (dichtstbij.start.strftime("%H:%M")
                    if dichtstbij.start else "de hele dag")
            meldingen.append(Melding(
                Ernst.KRITIEK, beurt.datum,
                f"agenda-item staat op {klok} maar de voorstelling begint om "
                f"{beurt.tijd} — {_omschrijf(beurt)}",
                (f"agenda: {dichtstbij.titel}",),
            ))
        else:
            meldingen.append(Melding(
                Ernst.KRITIEK, beurt.datum,
                f"jij staat ingeroosterd maar er staat niets in je agenda — "
                f"{_omschrijf(beurt)}",
            ))

    for n, item in enumerate(cats_items):
        if n not in gebruikt:
            meldingen.append(Melding(
                Ernst.KRITIEK, item.datum,
                f"agenda-item {item.titel!r} hoort bij geen speelbeurt van jou",
                (f"start {item.start.strftime('%H:%M') if item.start else 'hele dag'}",),
            ))
    return meldingen


def _mijn_speelbeurten(orkest, reed2, inst, vanaf):
    """Alle dagen waarop Emiel moet spelen of repeteren.

    De orkestlijst is leidend. MON- en BESL-dagen staan daar niet in, dus die
    komen uit de reed 2-sheet.
    """
    beurten = [
        v for v in orkest
        if v.datum >= vanaf and v.reed2 == inst.mijn_naam
        and (v.type in SPEEL_TYPES or v.type in WERK_TYPES)
    ]
    bezet = {(v.datum, v.tijd) for v in beurten}
    for v in reed2:
        if (v.datum >= vanaf and v.reed2 == inst.mijn_naam
                and v.type in WERK_TYPES and (v.datum, v.tijd) not in bezet):
            beurten.append(v)
    return sorted(beurten, key=lambda v: (v.datum, v.tijd or ""))


def _past_in_venster(item, beurt, inst):
    if item.start is None:
        return True
    if beurt.tijd is None:
        return True
    aanvang = _samen(beurt.datum, beurt.tijd)
    start = datetime.combine(item.datum, item.start)
    return (aanvang - timedelta(minutes=inst.marge_voor_minuten)
            <= start
            <= aanvang + timedelta(minutes=inst.marge_na_minuten))


def _afstand(item, beurt):
    if item.start is None or beurt.tijd is None:
        return timedelta(days=1)
    return abs(datetime.combine(item.datum, item.start) - _samen(beurt.datum, beurt.tijd))


def _samen(dag, tijdtekst):
    uur, minuut = (int(x) for x in tijdtekst.split(":"))
    return datetime.combine(dag, time(uur, minuut))


# --- hulpjes ---------------------------------------------------------------

def _per_dag(voorstellingen, vanaf, alleen_met_publiek=False):
    """Groepeer per datum en sorteer binnen een dag op aanvangstijd."""
    per_dag = defaultdict(list)
    for v in voorstellingen:
        if v.datum < vanaf:
            continue
        if v.type in NEGEER_TYPES:
            continue
        if alleen_met_publiek and v.type not in SPEEL_TYPES:
            continue
        if not alleen_met_publiek and v.type is not None and v.type not in SPEEL_TYPES:
            continue
        per_dag[v.datum].append(v)
    for dag in per_dag:
        per_dag[dag].sort(key=lambda v: v.tijd or "")
    return dict(per_dag)


def _omschrijf(v):
    onderdelen = [v.datum.strftime("%d-%m-%Y")]
    if v.tijd:
        onderdelen.append(v.tijd)
    if v.type:
        onderdelen.append(v.type)
    if v.plaats:
        onderdelen.append(v.plaats)
    return " ".join(onderdelen)
