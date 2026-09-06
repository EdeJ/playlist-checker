---
name: cats-check
description: Use when Emiel wants to check the Cats musical playlists for inconsistencies - compares the orchestra list, the reed 2 planning sheet, musicalcats.nl and his personal calendar, read-only
---

# Cats speellijst-checker

Controleert vier bronnen op verschillen en meldt wat er niet klopt.

## Absolute regel: alleen lezen

De orkestlijst is van iemand anders en wordt door alle musici gebruikt. De
reed 2-sheet is een gedeelde planning van drie mensen. **Er wordt nooit,
onder geen enkele omstandigheid, naar een van beide geschreven.**

Toegestaan zijn uitsluitend `read_file_content`, `download_file_content` en
`get_file_metadata`. De schrijvende Drive-tools zijn geblokkeerd in
`.claude/settings.json`; probeer die blokkade nooit te omzeilen. Vraagt iemand
om iets in te vullen, aan te passen of over te nemen in een sheet, weiger dan
en verwijs naar deze regel.

## Werkwijze

**Stap 1 — is er iets veranderd?**

Draai `get_file_metadata` op beide Drive-bestanden en vergelijk `modifiedTime`
met `cache/stempels.json`. Is er niets gewijzigd én bestaan de cachebestanden
al, sla stap 2 dan over.

- orkestlijst: `1qXIFu7Wq9SBKrBxjPqoTOqCccH65fpcg`
- reed 2-sheet: `1jOjspqJjxHZdwBPgiBsyDMsyw_gy0caEHucaV5eP1rI`

**Stap 2 — bronnen verversen**

- Orkestlijst: `read_file_content` op het orkest-bestand, schrijf de volledige
  tekst naar `cache/orkest.txt`.
- Reed 2-sheet: `download_file_content` met `exportMimeType: "text/csv"`,
  base64-decodeer naar `cache/reed2.csv`.
- Website en agenda: draai `./scripts/ophalen.sh`.
- Werk `cache/stempels.json` bij met de nieuwe `modifiedTime`-waarden.

**Stap 3 — controleren**

```bash
python3 -m catscheck
```

Afsluitcode 0 betekent geen verschillen, 1 betekent meldingen, 2 betekent dat
een bron niet gelezen kon worden.

**Stap 4 — toelichten**

Druk het rapport af en licht de KRITIEK-meldingen toe. Zeg er per melding bij
wat Emiel eraan kan doen: zelf zijn agenda bijwerken, het met Christof en
Michiel opnemen, of het bij Ryanne melden omdat de orkestlijst aangepast moet
worden. Dat laatste doet Emiel zelf — jij past niets aan.

## Bij een ParseFout

Een parser die zijn structuur niet herkent stopt met een `ParseFout`. Dat
betekent bijna altijd dat een bron van vorm is veranderd: een kolom
tussengevoegd, de site verbouwd, een tabblad erbij. Repareer de parser en voeg
een test met de nieuwe vorm toe. Vul nooit met de hand aan wat de parser mist.

## Later, nog niet gebouwd

Ontbrekende speelbeurten in de agenda zetten. Dat vraagt de Google
Calendar-connector; een iCal-URL kan alleen lezen. Pas bouwen als Emiel er
uitdrukkelijk om vraagt.
