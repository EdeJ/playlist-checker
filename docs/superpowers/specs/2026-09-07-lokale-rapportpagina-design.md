# Lokale rapportpagina naast de terminaluitvoer

**Datum:** 2026-09-07

## Aanleiding

Emiel vond de uitvoer van de controle "elke keer anders" en wilde het
visueel duidelijker. Uit navraag bleek: niet de terminaluitvoer moest
veranderen (die blijft precies zoals hij is) en ook niet de vrije toelichting
eromheen, maar er miste een weergave met meer visuele hiërarchie dan een
terminal kan geven.

## Ontwerp

Na de controle wordt dezelfde bevindingenset ook als HTML-pagina gebouwd en
automatisch geopend in de browser. De terminaluitvoer, de afsluitcodes en de
toelichting blijven ongewijzigd; de pagina komt ernaast te staan.

### Hergebruik

`scripts/bouw_rapport.py` en `scripts/rapport_sjabloon.html` bestonden al —
gebouwd voor de (inmiddels gepauzeerde) cloud-routine. Ze worden nu ook
lokaal gebruikt. Omdat een lokale run wél bij het geheime iCal-adres kan,
staat `agenda_gecontroleerd` daar op `true` en toont de pagina ook de
agenda-meldingen; het sjabloon regelde dat verschil al.

### Nieuw: scripts/rapport.sh

Eén script dat drie dingen doet: `catscheck --json` wegschrijven, de pagina
bouwen, en `xdg-open` erop loslaten.

Dat dit een script is en geen handmatige reeks stappen is de kern van het
ontwerp: het model bepaalt niets aan de vorm, dus de pagina ziet er elke keer
identiek uit — dezelfde redenering als bij de vergelijking zelf.

**Afsluitcodes:** 0 en 1 gelden als geslaagd (1 betekent "er zijn
meldingen", geen fout). Bij 2 kon een bron niet gelezen worden; dan wordt er
geen pagina gebouwd, want er valt niets zinnigs te tonen.

**Ontbrekende xdg-open** (SSH-sessie zonder desktop) is geen fout: het
script print het pad en stopt daar.

### Locatie van de bestanden

`cache/rapport.html` en `cache/rapport.json`. Die map staat al in
`.gitignore` omdat de opgehaalde bronnen agenda-inhoud bevatten — de
rapportpagina bevat die ook, en hoort dus niet in git.

## Wat er niet verandert

- De terminaluitvoer van `python3 -m catscheck` en de `--alles`-vlag.
- De afsluitcodes.
- De vrije vorm van de toelichting na afloop.
- De leesregel: er wordt nooit naar de orkestlijst of reed 2-sheet
  geschreven.

## Testen

`scripts/bouw_rapport.py` heeft al tests (`tests/test_bouw_rapport.py`).
`scripts/rapport.sh` is een dunne schil zonder eigen logica en wordt, net als
`scripts/ophalen.sh`, niet apart getest.
