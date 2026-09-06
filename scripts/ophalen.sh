#!/usr/bin/env bash
# Haalt de website en de agenda op naar cache/. Alleen lezen.
set -euo pipefail

cd "$(dirname "$0")/.."
mkdir -p cache

echo "musicalcats.nl ophalen..."
curl -sSL --max-time 30 "https://musicalcats.nl/waar-wanneer/" -o cache/website.html

if [[ -f config/ical_url.txt ]]; then
  echo "agenda ophalen..."
  # De URL zelf verschijnt nooit in de uitvoer; hij is een geheim.
  url="$(tr -d '[:space:]' < config/ical_url.txt)"
  if ! curl -sSL --max-time 30 "$url" -o cache/agenda.ics; then
    echo "agenda ophalen mislukt; controleer de URL in config/ical_url.txt" >&2
    exit 1
  fi
  if ! head -1 cache/agenda.ics | grep -q "BEGIN:VCALENDAR"; then
    echo "de agenda-URL gaf geen iCal-bestand terug; is hij nog geldig?" >&2
    exit 1
  fi
else
  echo "config/ical_url.txt ontbreekt; de agendacontrole wordt overgeslagen." >&2
fi

echo "klaar."
