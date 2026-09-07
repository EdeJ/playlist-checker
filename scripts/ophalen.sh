#!/usr/bin/env bash
# Haalt de website, de orkestlijst, de reed 2-sheet en de agenda op naar
# cache/. Alleen lezen.
#
# Elke download gaat eerst naar een tijdelijk bestand en wordt pas op zijn
# plek gezet als hij compleet blijkt. `curl -o` kapt het doelbestand namelijk
# af voordat er iets binnenkomt: valt de verbinding halverwege weg, dan blijft
# er een halve agenda achter. Die parseert gewoon, zonder foutmelding, met
# minder afspraken erin — en levert een rapport op vol meldingen dat er
# voorstellingen in de agenda ontbreken die er wel degelijk in staan.
set -euo pipefail

cd "$(dirname "$0")/.."
mkdir -p cache

# In cache/ zelf, zodat het verplaatsen een hernoeming op dezelfde schijf is
# en dus in één ondeelbare stap gebeurt.
werkmap="$(mktemp -d ./cache/.ophalen.XXXXXX)"
trap 'rm -rf "$werkmap"' EXIT

mislukt=0

# Curl's eigen useragent ("curl/8.x") wordt door sommige bot-filters
# geblokkeerd (403), ook al is de opgevraagde pagina gewoon openbaar. Een
# gewone browser-useragent is hier geen misleiding — het is dezelfde
# publieke inhoud die iedereen met een browser ook te zien krijgt — maar
# voorkomt dat dat filter dichtklapt.
useragent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"

echo "musicalcats.nl ophalen..."
if curl -sSL --fail --max-time 30 -A "$useragent" "https://musicalcats.nl/waar-wanneer/" \
        -o "$werkmap/website.html" \
   && grep -q 'class="date"' "$werkmap/website.html"; then
  mv "$werkmap/website.html" cache/website.html
else
  echo "website ophalen mislukt; cache/website.html blijft ongewijzigd" >&2
  mislukt=1
fi

# De twee Drive-bestanden zijn met hun link leesbaar; er is geen inloggen aan
# te pas. Wordt die deling ooit ingetrokken, dan levert curl een inlogpagina
# op met code 200 — daarom wordt niet op de HTTP-code gecontroleerd maar op
# de inhoud.
orkest_id="1qXIFu7Wq9SBKrBxjPqoTOqCccH65fpcg"
reed2_id="1jOjspqJjxHZdwBPgiBsyDMsyw_gy0caEHucaV5eP1rI"

echo "orkestlijst ophalen..."
if curl -sSL --fail --max-time 60 -A "$useragent" \
        "https://drive.google.com/uc?export=download&id=${orkest_id}" \
        -o "$werkmap/orkest.xlsx" \
   && python3 -c 'import sys, zipfile; sys.exit(0 if zipfile.is_zipfile(sys.argv[1]) else 1)' \
        "$werkmap/orkest.xlsx"; then
  mv "$werkmap/orkest.xlsx" cache/orkest.xlsx
else
  echo "orkestlijst ophalen mislukt; cache/orkest.xlsx blijft ongewijzigd." \
       "Is de linkdeling van het bestand gewijzigd?" >&2
  mislukt=1
fi

echo "reed 2-sheet ophalen..."
# Van de vier bronnen is dit de enige waarbij alleen de eerste regel werd
# getoetst. De agenda toetst head -1 én tail -5, de orkestlijst gaat door
# zipfile.is_zipfile (dat de central directory aan het eind nodig heeft), de
# website wordt door de parser op volledigheid getoetst. Een op een
# rijgrens afgekapte CSV kwam hier ongeschonden doorheen — en omdat de
# vergelijking afkapt op de laatste datum die beide bronnen kennen, verkort
# een halve sheet stilzwijgend het venster en verdwijnt elke melding
# daarachter. Daarom ook de laatste regel toetsen: die moet evenveel velden
# hebben als de kopregel.
if curl -sSL --fail --max-time 30 -A "$useragent" \
        "https://docs.google.com/spreadsheets/d/${reed2_id}/export?format=csv" \
        -o "$werkmap/reed2.csv" \
   && head -1 "$werkmap/reed2.csv" | grep -q '^Speeldatum,Type' \
   && python3 -c '
import csv, sys
with open(sys.argv[1], newline="", encoding="utf-8") as f:
    rijen = [r for r in csv.reader(f) if any(veld.strip() for veld in r)]
sys.exit(0 if rijen and len(rijen[-1]) == len(rijen[0]) else 1)
' "$werkmap/reed2.csv"; then
  mv "$werkmap/reed2.csv" cache/reed2.csv
else
  echo "reed 2-sheet ophalen mislukt; cache/reed2.csv blijft ongewijzigd." \
       "Is de linkdeling van het bestand gewijzigd?" >&2
  mislukt=1
fi

if [[ -f config/ical_url.txt ]]; then
  echo "agenda ophalen..."
  # De URL zelf verschijnt nooit in de uitvoer; hij is een geheim.
  url="$(tr -d '[:space:]' < config/ical_url.txt)"
  # De URL wordt via stdin aan curl gevoerd (-K -) in plaats van als
  # argument: een argument staat in de procestabel (ps, /proc/*/cmdline) en
  # is daarmee tijdens het ophalen voor iedereen op deze machine leesbaar.
  if printf 'url = "%s"\n' "$url" | curl -sSL --max-time 60 -A "$useragent" -K - -o "$werkmap/agenda.ics" \
     && head -1 "$werkmap/agenda.ics" | grep -q "BEGIN:VCALENDAR" \
     && tail -5 "$werkmap/agenda.ics" | grep -q "END:VCALENDAR"; then
    mv "$werkmap/agenda.ics" cache/agenda.ics
  else
    echo "agenda ophalen mislukt of onvolledig; cache/agenda.ics blijft" \
         "ongewijzigd. Controleer de URL in config/ical_url.txt." >&2
    mislukt=1
  fi
else
  echo "config/ical_url.txt ontbreekt; de agendacontrole wordt overgeslagen." >&2
fi

if [[ $mislukt -ne 0 ]]; then
  echo "een of meer bronnen zijn niet ververst; de controle draait dan op" \
       "verouderde gegevens." >&2
  exit 1
fi

echo "klaar."
