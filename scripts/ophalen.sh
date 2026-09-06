#!/usr/bin/env bash
# Haalt de website en de agenda op naar cache/. Alleen lezen.
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

echo "musicalcats.nl ophalen..."
if curl -sSL --fail --max-time 30 "https://musicalcats.nl/waar-wanneer/" \
        -o "$werkmap/website.html" \
   && grep -q 'class="date"' "$werkmap/website.html"; then
  mv "$werkmap/website.html" cache/website.html
else
  echo "website ophalen mislukt; cache/website.html blijft ongewijzigd" >&2
fi

if [[ -f config/ical_url.txt ]]; then
  echo "agenda ophalen..."
  # De URL zelf verschijnt nooit in de uitvoer; hij is een geheim.
  url="$(tr -d '[:space:]' < config/ical_url.txt)"
  # De URL wordt via stdin aan curl gevoerd (-K -) in plaats van als
  # argument: een argument staat in de procestabel (ps, /proc/*/cmdline) en
  # is daarmee tijdens het ophalen voor iedereen op deze machine leesbaar.
  if printf 'url = "%s"\n' "$url" | curl -sSL --max-time 60 -K - -o "$werkmap/agenda.ics" \
     && head -1 "$werkmap/agenda.ics" | grep -q "BEGIN:VCALENDAR" \
     && tail -5 "$werkmap/agenda.ics" | grep -q "END:VCALENDAR"; then
    mv "$werkmap/agenda.ics" cache/agenda.ics
  else
    echo "agenda ophalen mislukt of onvolledig; cache/agenda.ics blijft" \
         "ongewijzigd. Controleer de URL in config/ical_url.txt." >&2
    exit 1
  fi
else
  echo "config/ical_url.txt ontbreekt; de agendacontrole wordt overgeslagen." >&2
fi

echo "klaar."
