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

De bronnen worden met `curl` opgehaald; er komt geen Drive-tool meer aan te
pas. De schrijvende Drive-tools zijn daarnaast geblokkeerd in
`.claude/settings.json`; probeer die blokkade nooit te omzeilen. Vraagt iemand
om iets in te vullen, aan te passen of over te nemen in een sheet, weiger dan
en verwijs naar deze regel.

## Werkwijze

**Stap 1 — bronnen ophalen**

```bash
./scripts/ophalen.sh
```

Haalt alle vier de bronnen op naar `cache/`. Eindigt het script met code 1,
dan is er minstens één bron niet ververst; meld dan wat er misging en ga niet
verder. De controle zou dan op verouderde gegevens draaien.

**Stap 2 — controleren**

```bash
python3 -m catscheck
```

Afsluitcode 0 betekent geen verschillen, 1 betekent meldingen, 2 betekent dat
een bron niet gelezen kon worden.

**Stap 3 — toelichten**

Druk het rapport af en licht de KRITIEK-meldingen toe. Zeg er per melding bij
wat Emiel eraan kan doen:

- **Agenda-meldingen** — zelf zijn agenda bijwerken.
- **Tijd- en plaatsverschillen** — zelf rechtzetten in de orkestlijst. Emiel
  heeft daar schrijfrechten; stuur hem hier niet naar Ryanne. Dat de lijst
  van Ryanne is en als waarheid geldt, zegt iets over eigenaarschap, niet
  over toegang.
- **Verschillen over wíé speelt** — eerst uitzoeken, niet aanpassen. Staat er
  in de orkestlijst een andere naam dan in de reed 2-sheet, dan spreken twee
  mensen elkaar tegen; dat gaat Emiel met Christof en Michiel na voordat er
  iets verandert. Eenzijdig overschrijven wist andermans kant van het
  meningsverschil.

Aanpassen doet Emiel altijd zelf — jij past niets aan.

## Welk model hiervoor nodig is

De uitkomst van deze controle hangt niet af van het model. Het ophalen doet
`scripts/ophalen.sh`, het vergelijken doet `python3 -m catscheck` — een gewoon
script zonder AI: dezelfde bronnen leveren altijd hetzelfde rapport op. Er
passeert geen enkel bronbestand het model; het start twee commando's en licht
de uitkomst toe. Het model vindt de verschillen niet — het script doet dat.

Een middelzwaar model is hier daarom ruim voldoende. Het zwaarste model kost
meer en levert niets extra's op. Op het moment van schrijven, september 2026,
is dat middelzware model Sonnet.

Draait deze sessie op een zwaarder model dan dat, meld dan **één keer** — bij
de eerste run in een sessie, niet elke keer — dat het met een lichter model
even goed en goedkoper kan, en dat Emiel dat met `/model` kan wisselen. Draait
de sessie al op een licht of middelzwaar model, zeg er dan niets over.

Verschijnt er later een nieuwe generatie modellen: het gaat om de klasse, niet
om de naam. Kies de middelste van wat er dan beschikbaar is. De reden blijft
dezelfde en veroudert niet — het model is niet wat de verschillen vindt.

## Bij een ParseFout

Een parser die zijn structuur niet herkent stopt met een `ParseFout`. Dat
betekent bijna altijd dat een bron van vorm is veranderd: een kolom
tussengevoegd, de site verbouwd, een tabblad erbij. Repareer de parser en voeg
een test met de nieuwe vorm toe. Vul nooit met de hand aan wat de parser mist.

## Later, nog niet gebouwd

Ontbrekende speelbeurten in de agenda zetten. Dat vraagt de Google
Calendar-connector; een iCal-URL kan alleen lezen. Pas bouwen als Emiel er
uitdrukkelijk om vraagt.
