"""Maak Nederlandse terminaltekst van de bevindingen."""

from collections import Counter

from catscheck.model import Ernst

KOPPEN = {
    Ernst.KRITIEK: "KRITIEK — dit raakt jou direct",
    Ernst.VERSCHIL: "VERSCHIL — orkestlijst tegenover jullie reed 2-sheet",
    Ernst.WEBSITE: "WEBSITE — musicalcats.nl wijkt af (niet de bron)",
    Ernst.OPEN: "NOG IN TE VULLEN",
}

# Boven dit aantal wordt een groep samengevat in plaats van opgesomd.
SAMENVATTEN_VANAF = 15


def maak_rapport(meldingen, vanaf, overgeslagen_herhalend=0,
                 samenvatten_vanaf=SAMENVATTEN_VANAF,
                 website_onbetrouwbaar=False, onleesbare_afspraken=0):
    regels = [
        "Cats speellijst-checker",
        f"Peildatum: {vanaf.strftime('%d-%m-%Y')} (alles daarvoor is overgeslagen)",
        "",
    ]
    if website_onbetrouwbaar:
        # Bovenaan, want het verandert hoe je de rest van het rapport leest.
        regels += [
            "LET OP: musicalcats.nl kon maar gedeeltelijk gelezen worden.",
            "De opmaak van de pagina is waarschijnlijk gewijzigd. De website is",
            "daarom helemaal buiten de vergelijking gelaten; de rest klopt wel.",
            "",
        ]
    if not meldingen:
        regels.append("Geen verschillen gevonden. Alle vier de bronnen zijn het eens.")
    else:
        for ernst in sorted(KOPPEN):
            groep = sorted(
                (m for m in meldingen if m.ernst is ernst),
                key=lambda m: (m.datum, m.tekst),
            )
            if not groep:
                continue
            regels.append(f"{KOPPEN[ernst]}  ({len(groep)})")
            regels.append("-" * len(KOPPEN[ernst]))
            # KRITIEK wordt nooit samengevat: dat is juist de groep die je van
            # boven naar beneden wilt aflopen.
            regels += _toon_groep(
                groep, samenvatten_vanaf, mag_samenvatten=ernst is not Ernst.KRITIEK
            )
            regels.append("")

    if overgeslagen_herhalend:
        regels.append(
            f"Let op: {overgeslagen_herhalend} herhalende agenda-afspraken zijn "
            f"niet meegenomen; die worden niet uitgerekend."
        )
    if onleesbare_afspraken:
        regels.append(
            f"Let op: {onleesbare_afspraken} agenda-afspraken misten een "
            f"begintijd en konden niet gecontroleerd worden."
        )
    return "\n".join(regels).rstrip() + "\n"


def _toon_groep(groep, samenvatten_vanaf, mag_samenvatten=True):
    if mag_samenvatten and len(groep) > samenvatten_vanaf and _herhaalt_zich(groep):
        return _vat_samen(groep)
    regels = []
    for m in groep:
        regels.append(f"  {m.datum.strftime('%d-%m-%Y')}  {m.tekst}")
        for detail in m.details:
            regels.append(f"    {detail}")
    return regels


def _herhaalt_zich(groep):
    """Zeg of samenvatten iets oplevert.

    Bij louter unieke teksten geeft samenvatten evenveel regels, maar dan op
    frequentie gesorteerd in plaats van op datum — slechter dan opsommen.
    """
    return len({m.tekst for m in groep}) * 2 <= len(groep)


def _vat_samen(groep):
    """Vat een lange groep samen op de gemeenschappelijke tekst.

    Zonder dit verdwijnt één belangrijke melding tussen honderd gelijksoortige.
    """
    regels = [
        f"  {len(groep)} meldingen, van {groep[0].datum.strftime('%d-%m-%Y')} "
        f"tot en met {groep[-1].datum.strftime('%d-%m-%Y')}:"
    ]
    for tekst, aantal in Counter(m.tekst for m in groep).most_common():
        regels.append(f"    {aantal:4d}x  {tekst}")
    regels.append("  (draai met --alles om ze allemaal te zien)")
    return regels
