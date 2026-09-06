"""Vergelijk de vier bronnen en lever bevindingen op.

Voorstellingen worden gekoppeld op datum, niet op datum plus tijd. Anders leest
een verschil van 14:30 tegenover 15:00 als twee ontbrekende voorstellingen in
plaats van als één tijdsverschil.
"""

from collections import defaultdict
from dataclasses import dataclass
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
    meldingen += _onbekende_types(orkest, reed2, instellingen, vanaf)
    meldingen += _vergelijk_bronnen(orkest, reed2, instellingen, vanaf)
    meldingen += _vergelijk_website(orkest, website, vanaf)
    meldingen += _vergelijk_agenda(orkest, reed2, agenda, instellingen, vanaf)
    return meldingen


# --- regels die we niet begrijpen ------------------------------------------

BRONNAAM = {
    "orkest": "de orkestlijst",
    "reed2": "jullie reed 2-sheet",
    "website": "musicalcats.nl",
}


def _onbekende_types(orkest, reed2, inst, vanaf):
    """Meld regels met een type dat in geen enkele verzameling voorkomt.

    Zo'n regel valt buiten elke vergelijking. Zonder deze melding laat een
    typefout in de typekolom een hele voorstelling verdwijnen — inclusief een
    naamverschil dat Emiel raakt. Liever een regel die je kunt negeren dan een
    voorstelling die je nooit ziet.
    """
    bekend = SPEEL_TYPES | WERK_TYPES | NEGEER_TYPES
    meldingen = []
    for v in list(orkest) + list(reed2):
        if v.datum < vanaf or v.type is None or v.type in bekend:
            continue
        meldingen.append(Melding(
            Ernst.KRITIEK if v.reed2 == inst.mijn_naam else Ernst.VERSCHIL,
            v.datum,
            f"onbekend type {v.type!r} in {BRONNAAM.get(v.bron, v.bron)} — "
            f"deze voorstelling is niet gecontroleerd",
            (f"{v.bron}: {v.herkomst}",),
        ))
    return meldingen


# --- orkestlijst tegenover de reed 2-sheet ---------------------------------

def _vergelijk_bronnen(orkest, reed2, inst, vanaf):
    meldingen = []
    per_dag_o = _per_dag(orkest, vanaf)
    per_dag_r = _per_dag(reed2, vanaf, alleen_met_publiek=True)
    overlap = _overlap_bereik(orkest, reed2)

    for dag in sorted(set(per_dag_o) | set(per_dag_r)):
        o, r = per_dag_o.get(dag, []), per_dag_r.get(dag, [])
        if not o or not r:
            # Een dag waarop maar een van de twee bronnen iets zegt, is
            # alleen een echt verschil binnen de periode die beide bronnen
            # bestrijken. Buiten dat overlap is de ene bron domweg nog niet zo
            # ver — dat is geen tegenspraak, alleen een voorsprong.
            if overlap is None or not (overlap[0] <= dag <= overlap[1]):
                continue
            if not o:
                meldingen.append(Melding(
                    Ernst.VERSCHIL, dag,
                    f"staat in jullie reed 2-sheet ({len(r)}x), maar niet in de orkestlijst",
                    tuple(_omschrijf(x) for x in r),
                ))
            else:
                meldingen.append(Melding(
                    Ernst.VERSCHIL, dag,
                    f"staat in de orkestlijst ({len(o)}x), maar niet in jullie reed 2-sheet",
                    tuple(_omschrijf(x) for x in o),
                ))
            continue
        if len(o) != len(r):
            meldingen.append(Melding(
                Ernst.VERSCHIL, dag,
                f"aantal voorstellingen verschilt: orkestlijst {len(o)}, reed 2-sheet {len(r)}",
                tuple(_omschrijf(x) for x in o + r),
            ))
            continue
        for a, b in zip(o, r):
            meldingen += _vergelijk_paar(dag, a, b, inst)
    return meldingen


def _overlap_bereik(orkest, reed2):
    """Geef (eerste, laatste) datum die zowel de orkestlijst als de reed
    2-sheet bestrijken, of None als een van beide leeg is.

    De reed 2-sheet begint doorgaans eerder dan de orkestlijst (concept-
    planning versus definitieve lijst). Buiten dit overlap zegt maar één bron
    iets over een dag; dat is geen tegenspraak en hoort niet gemeld te
    worden.
    """
    if not orkest or not reed2:
        return None
    start = max(min(v.datum for v in orkest), min(v.datum for v in reed2))
    einde = min(max(v.datum for v in orkest), max(v.datum for v in reed2))
    if start > einde:
        return None
    return start, einde


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
    # Tot en met deze dag heeft de orkestlijst iets over Reed 2 te zeggen.
    # Daarna weet de checker niets: een Cats-afspraak daar is geen fout maar
    # een teken dat de orkestlijst nog ingevuld moet worden. Dat als KRITIEK
    # melden leert je juist de rode meldingen negeren.
    ingevuld_tot = max((v.datum for v in orkest if v.reed2), default=None)

    beurten_per_dag = defaultdict(list)
    for beurt in _mijn_speelbeurten(orkest, reed2, inst, vanaf):
        beurten_per_dag[beurt.datum].append(beurt)

    items_per_dag = defaultdict(list)
    for item in agenda:
        if item.datum >= vanaf and any(
            t in item.titel.lower() for t in inst.trefwoorden
        ):
            items_per_dag[item.datum].append(item)
    for dag in items_per_dag:
        # Items zonder tijd achteraan: die zijn nergens op te sorteren.
        items_per_dag[dag].sort(
            key=lambda i: (i.start is None, i.start or time(0, 0))
        )

    for dag in sorted(set(beurten_per_dag) | set(items_per_dag)):
        beurten = beurten_per_dag.get(dag, [])
        items = items_per_dag.get(dag, [])
        koppeling = _beste_koppeling(beurten, items, inst)
        gekoppelde_beurten = {b for b, _ in koppeling}
        vrij = [j for j in range(len(items)) if j not in {i for _, i in koppeling}]

        for b, j in koppeling:
            if items[j].start is None:
                meldingen.append(Melding(
                    Ernst.KRITIEK, dag,
                    f"agenda-item duurt de hele dag, de tijd is dus niet te "
                    f"controleren — {_omschrijf(beurten[b])}",
                    (f"agenda: {items[j].titel}",),
                ))

        for b, beurt in enumerate(beurten):
            if b in gekoppelde_beurten:
                continue
            if vrij:
                # Er staat wel iets die dag, maar op een tijd die niet kan
                # kloppen. Dat is één melding over een verkeerde tijd — niet
                # een ontbrekende plus een overtollige afspraak, want die
                # zouden allebei het tegendeel beweren van wat er aan de hand is.
                j = min(vrij, key=lambda k: _afstand(items[k], beurt))
                vrij.remove(j)
                klok = (items[j].start.strftime("%H:%M")
                        if items[j].start else "de hele dag")
                meldingen.append(Melding(
                    Ernst.KRITIEK, dag,
                    f"agenda-item staat op {klok} maar de voorstelling begint "
                    f"om {beurt.tijd} — {_omschrijf(beurt)}",
                    (f"agenda: {items[j].titel}",),
                ))
            else:
                meldingen.append(Melding(
                    Ernst.KRITIEK, dag,
                    f"jij staat ingeroosterd maar er staat niets in je agenda — "
                    f"{_omschrijf(beurt)}",
                ))

        for j in vrij:
            klok = (items[j].start.strftime("%H:%M")
                    if items[j].start else "hele dag")
            if ingevuld_tot is not None and dag <= ingevuld_tot:
                meldingen.append(Melding(
                    Ernst.KRITIEK, dag,
                    f"agenda-item {items[j].titel!r} hoort bij geen speelbeurt "
                    f"van jou",
                    (f"start {klok}",),
                ))
            else:
                meldingen.append(Melding(
                    Ernst.OPEN, dag,
                    f"agenda-item {items[j].titel!r} staat in je agenda, maar de "
                    f"orkestlijst is voor deze datum nog niet ingevuld",
                    (f"start {klok}",),
                ))
    return meldingen


def _beste_koppeling(beurten, items, inst):
    """Koppel de agenda-items van één dag aan de speelbeurten van die dag.

    Geeft een lijst (index_beurt, index_item) terug. Gezocht wordt naar de
    toewijzing die de meeste beurten binnen hun venster koppelt, en bij
    gelijke stand naar die met de kleinste totale afwijking.

    Per beurt greedy het dichtstbijzijnde item pakken gaat mis zodra twee
    vensters elkaar overlappen: de vroegste beurt pikt dan het item in dat bij
    de latere hoort, waarna er twee meldingen ontstaan die allebei onjuist
    zijn. Een speeldag telt hooguit een handvol voorstellingen, dus alle
    varianten aflopen kost niets.
    """
    mogelijk = [
        [j for j in range(len(items)) if _past_in_venster(items[j], beurt, inst)]
        for beurt in beurten
    ]
    beste = []
    beste_score = None

    def zoek(b, gekozen, bezet, afstand):
        nonlocal beste, beste_score
        if b == len(beurten):
            score = (-len(gekozen), afstand)
            if beste_score is None or score < beste_score:
                beste_score, beste = score, list(gekozen)
            return
        for j in mogelijk[b]:
            if j in bezet:
                continue
            gekozen.append((b, j))
            zoek(b + 1, gekozen, bezet | {j},
                 afstand + _afstand(items[j], beurten[b]))
            gekozen.pop()
        # Deze beurt zonder item laten is ook een mogelijkheid.
        zoek(b + 1, gekozen, bezet, afstand)

    zoek(0, [], frozenset(), timedelta())
    return beste


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
