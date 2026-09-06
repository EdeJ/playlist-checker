"""Parser voor de iCal-export van Emiels Google Agenda.

Alleen lezen: een iCal-URL kan per definitie niets wijzigen.
"""

import re
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

from catscheck.model import AgendaItem, ParseFout

AGENDA_TIJDZONE = ZoneInfo("Europe/Amsterdam")

_DATUMTIJD = re.compile(r"^(\d{8})T(\d{6})(Z?)$")
_DATUM = re.compile(r"^(\d{8})$")


def parse_agenda(ics):
    """Geef (afspraken, herhalend_overgeslagen, onleesbaar) terug.

    Herhalende afspraken worden overgeslagen. Een VEVENT zonder DTSTART kan
    niet geplaatst worden en wordt evenmin gelezen. Beide aantallen komen mee
    terug, zodat het rapport kan melden dat de controle niet volledig was in
    plaats van er stilzwijgend overheen te stappen.
    """
    regels = _ontvouw(ics)
    if not any(r.startswith("BEGIN:VCALENDAR") for r in regels):
        raise ParseFout("dit lijkt geen iCal-bestand; is de agenda-URL nog geldig?")

    items = []
    overgeslagen = 0
    onleesbaar = 0
    huidig = None
    for regel in regels:
        if regel == "BEGIN:VEVENT":
            huidig = {}
            continue
        if regel == "END:VEVENT":
            if huidig is None:
                continue
            if "RRULE" in huidig:
                overgeslagen += 1
            elif "DTSTART" in huidig:
                items.append(_maak_item(huidig))
            else:
                # Zonder begintijd valt niet te zeggen wanneer dit is. Niet
                # stil weggooien: tellen, zodat het rapport het kan melden.
                onleesbaar += 1
            huidig = None
            continue
        if huidig is None:
            continue
        sleutel, _, waarde = regel.partition(":")
        naam = sleutel.split(";")[0].upper()
        if naam in ("DTSTART", "SUMMARY", "UID", "RRULE"):
            huidig[naam] = waarde
            if naam == "DTSTART":
                huidig["DTSTART_PARAMS"] = sleutel
    return items, overgeslagen, onleesbaar


def _ontvouw(ics):
    """Plak gevouwen iCal-regels weer aan elkaar.

    Een regel die met een spatie of tab begint hoort bij de vorige regel.
    """
    regels = []
    for ruw in ics.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if ruw[:1] in (" ", "\t") and regels:
            regels[-1] += ruw[1:]
        else:
            regels.append(ruw)
    return [r for r in regels if r]


def _maak_item(velden):
    ruw = velden["DTSTART"].strip()
    params = velden.get("DTSTART_PARAMS", "")

    m = _DATUMTIJD.match(ruw)
    if m:
        jjjjmmdd, hhmmss, is_utc = m.groups()
        naief = datetime.strptime(jjjjmmdd + hhmmss, "%Y%m%d%H%M%S")
        if is_utc:
            lokaal = naief.replace(tzinfo=timezone.utc).astimezone(AGENDA_TIJDZONE)
        else:
            tzid = _tzid(params)
            lokaal = naief.replace(tzinfo=tzid).astimezone(AGENDA_TIJDZONE)
        return AgendaItem(
            datum=lokaal.date(),
            start=time(lokaal.hour, lokaal.minute),
            titel=_titel(velden),
            herkomst=velden.get("UID", ""),
        )

    m = _DATUM.match(ruw)
    if m:
        d = datetime.strptime(m.group(1), "%Y%m%d").date()
        return AgendaItem(datum=d, start=None, titel=_titel(velden), herkomst=velden.get("UID", ""))

    raise ParseFout(f"onbegrijpelijke DTSTART in de agenda: {ruw!r}")


def _tzid(params):
    m = re.search(r"TZID=([^;:]+)", params)
    if not m:
        return AGENDA_TIJDZONE
    try:
        return ZoneInfo(m.group(1))
    except Exception:
        return AGENDA_TIJDZONE


def _titel(velden):
    ruw = velden.get("SUMMARY", "")
    # iCal ontsnapt komma's, puntkomma's en regeleindes met een backslash.
    ontsnapt = ruw.replace("\\,", ",").replace("\\;", ";").replace("\\n", " ")
    return " ".join(ontsnapt.split())
