#!/usr/bin/env bash
# Bouwt de HTML-rapportpagina uit de al opgehaalde bronnen en opent hem.
#
# Draai eerst ./scripts/ophalen.sh; dit script haalt zelf niets op, het leest
# alleen wat er in cache/ staat. De terminaluitvoer van `python3 -m catscheck`
# blijft ongewijzigd — deze pagina komt daar naast, niet in de plaats van.
set -euo pipefail

cd "$(dirname "$0")/.."
mkdir -p cache

# catscheck geeft 1 terug zodra er meldingen zijn. Dat is een geslaagde
# controle, geen fout — alleen 2 (een bron kon niet gelezen worden) is een
# echte mislukking, en dan valt er ook geen zinnig rapport te bouwen.
code=0
python3 -m catscheck --json > cache/rapport.json || code=$?
if [[ $code -ge 2 ]]; then
  echo "catscheck kon de bronnen niet lezen; er is geen pagina gebouwd." >&2
  exit "$code"
fi

# De tijd wordt hier bepaald en meegegeven, zodat de pagina de lokale klok
# toont en niet die van de omgeving waarin het bouwscript toevallig draait.
python3 scripts/bouw_rapport.py \
    cache/rapport.json cache/rapport.html "$(date '+%d-%m-%Y, %H:%M')" > /dev/null

echo "rapportpagina: file://$(pwd)/cache/rapport.html"

# Op een kale machine of in een SSH-sessie zonder desktop bestaat xdg-open
# niet; het pad hierboven is dan genoeg om zelf te openen.
if command -v xdg-open > /dev/null 2>&1; then
  xdg-open cache/rapport.html > /dev/null 2>&1 &
fi
