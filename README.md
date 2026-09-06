# Cats speellijst-checker

Controleert vier bronnen op verschillen: de orkestlijst, de reed 2-planning,
musicalcats.nl en Emiels agenda. **Alles alleen-lezen.**

## Eenmalig instellen

Zet de geheime iCal-URL van je agenda in `config/ical_url.txt`:

1. Google Agenda → instellingen van je agenda → Agenda integreren
2. Kopieer "Privé-adres in iCal-indeling"
3. `mkdir -p config && printf '%s' 'PLAK_HIER' > config/ical_url.txt`
4. `chmod 600 config/ical_url.txt`

Wie deze URL heeft kan je agenda lezen. Het bestand staat in `.gitignore` en
verschijnt nooit in de uitvoer.

## Gebruiken

In Claude Code: `/cats-check`

Handmatig, met een gevulde `cache/`:

```bash
./scripts/ophalen.sh          # alle vier de bronnen
python3 -m catscheck          # controleren
python3 -m catscheck --vanaf 2026-10-01 --alles
```

## Welk model

De controle zelf is een gewoon Python-script zonder AI; het model start het
ophalen en licht het rapport toe. Een middelzwaar model volstaat dus
ruimschoots — op dit moment Sonnet. Wisselen kan met `/model`.

Geen van de vier bronnen passeert het model. `scripts/ophalen.sh` zet ze
allemaal met `curl` rechtstreeks in `cache/`; alleen het rapport komt in het
gesprek terecht.

## Tests

```bash
python3 -m unittest discover -s tests
```
