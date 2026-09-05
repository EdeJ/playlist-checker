# Cats speellijst-checker — ontwerp

Datum: 2026-09-05
Status: ontwerp goedgekeurd, nog niet gebouwd

## Doel

Inconsistenties opsporen tussen vier bronnen die allemaal iets zeggen over de
speellijst van de musical Cats, en specifiek over de Reed 2-stoel die Emiel
deelt met Christof, Coen en Michiel. De controle is **uitsluitend lezend**.
Er wordt nooit iets naar een bron teruggeschreven.

## Bronnen en hun status

| Bron | Type | Eigenaar | Rol |
|---|---|---|---|
| `Orkestoverzicht Cats.xlsx` (`1qXIFu7Wq9SBKrBxjPqoTOqCccH65fpcg`) | xlsx in Drive | Ryanne van der Poel | **De waarheid.** Wat hier staat, geldt. |
| `Cats reed 2` (`1jOjspqJjxHZdwBPgiBsyDMsyw_gy0caEHucaV5eP1rI`) | Google Sheet | Emiel | Concept-planning van de drie reed 2-spelers. Wordt pas na consensus in de orkestlijst overgenomen. |
| `https://musicalcats.nl/waar-wanneer/` | Statische HTML | Productie | Geen bron, wel een extra paar ogen op datum/tijd/theater. |
| Persoonlijke Google Agenda van Emiel | iCal (geheime URL) | Emiel | Moet kloppen met de speelbeurten die in de orkestlijst op Emiels naam staan. |

## Architectuur: ophalen en vergelijken zijn gescheiden

Het vergelijkingsscript draait lokaal en heeft geen Google-inloggegevens. Claude
haalt de bronnen op met alleen-lees-tools en legt ze in `cache/`; het script
leest uitsluitend die lokale bestanden. Het script doet zelf geen enkel verzoek
richting Google Drive. Daarmee is "nooit schrijven" een eigenschap van de
opbouw, niet een belofte in een instructiebestand.

```
bron                          ophalen door Claude           lokale cache
─────────────────────────────────────────────────────────────────────────
Orkestoverzicht Cats.xlsx  →  Drive MCP (read-only)      →  cache/orkest.txt
Cats reed 2 (Sheet)        →  Drive MCP, export CSV      →  cache/reed2.csv
musicalcats.nl             →  curl                       →  cache/website.html
Google Agenda              →  curl op geheime iCal-URL   →  cache/agenda.ics
                                                              ↓
                                                          compare.py → rapport
```

De iCal-URL is alleen-lezen per definitie: een privé-adres in iCal-indeling kan
gelezen worden, maar er kan niets mee gewijzigd worden.

## Read-only wordt afgedwongen, niet gevraagd

In `.claude/settings.json` komt een `permissions.deny`-regel op alle schrijvende
Google Drive-tools:

- `mcp__claude_ai_Google_Drive__update_file`
- `mcp__claude_ai_Google_Drive__create_file`
- `mcp__claude_ai_Google_Drive__trash_file`
- `mcp__claude_ai_Google_Drive__share_file`
- `mcp__claude_ai_Google_Drive__copy_file`

Wat overblijft is `read_file_content`, `download_file_content`,
`get_file_metadata`, `search_files` en `list_recent_files`. De blokkade geldt
voor elke sessie in dit project, ook toekomstige.

## Onderdelen

Vier parsers, één vergelijker. Elke bron heeft zijn eigen eigenaardigheden, dus
elke bron krijgt zijn eigen parser die naar hetzelfde platte formaat vertaalt.

```
scripts/
  fetch_agenda.sh     geheime iCal-URL ophalen naar cache/agenda.ics
  parse_orkest.py     cache/orkest.txt   → genormaliseerde voorstellingen
  parse_reed2.py      cache/reed2.csv    → genormaliseerde voorstellingen
  parse_website.py    cache/website.html → genormaliseerde voorstellingen
  parse_agenda.py     cache/agenda.ics   → agenda-items
  compare.py          vier lijsten       → rapport
```

### Genormaliseerd formaat

```python
Voorstelling(
    datum,        # date, altijd met jaar
    tijd,         # "20:00" of None bij dagen zonder aanvangstijd
    type,         # TO, PREM, REG, VP, S-OPT, MON, BESL, BOUW, VRIJ
    plaats,       # "ALMERE" — genormaliseerd naar hoofdletters
    theater,      # "Kunstlinie" of None (orkestlijst noemt geen theater)
    reed2,        # "Emiel" / "Christof" / "Coen" / "Michiel" / None
    bron,         # "orkest" | "reed2" | "website"
    herkomst,     # rij- of regelnummer, zodat een melding terug te vinden is
)
```

Namen en plaatsnamen worden getrimd en genormaliseerd voor vergelijking
(`"Michiel "` == `"michiel"`), maar in het rapport wordt de originele tekst
getoond.

### Kolommen worden op naam gezocht, niet op letter

De orkestlijst heeft per maandblok een kopregel met onder meer
`Reed 1, Overnachten Reed 1, Reed 2, Overnachten Reed 2, Drums`. De parser zoekt
de kolom `Reed 2` op die kop. Voor Emiel is dit vandaag kolom Q, maar wordt er
ooit een kolom tussengevoegd, dan blijft de controle kloppen. Wordt de kop niet
gevonden, dan is dat zelf een foutmelding — nooit stilzwijgend een andere kolom
lezen.

### Het jaartal wordt afgeleid en geverifieerd

De orkestlijst noemt per rij alleen weekdag en dagnummer; het jaar staat nergens.
De parser leidt het jaar af uit de volgorde van de maandblokken: het eerste blok
is oktober 2026 — gecontroleerd: de weekdagen in dat blok komen overeen met
oktober 2026 — en bij elke overgang van december naar januari gaat het jaartal
omhoog. Als controle wordt de berekende weekdag vergeleken met de weekdag die in
de rij staat (`Di`, `Wo`, `Do`, …). Klopt die niet, dan stopt de parser met een
foutmelding in plaats van door te rekenen met een verschoven jaar.

### Voorstellingen worden op datum gekoppeld, niet op datum plus tijd

Zou er op datum plus tijd gekoppeld worden, dan leest een verschil van 14:30 tegen
15:00 als twee ontbrekende voorstellingen in plaats van als één tijdsverschil.
De regel is daarom:

1. Groepeer per bron alle voorstellingen per datum.
2. Sorteer binnen een dag op tijd.
3. Paar ze op volgorde: eerste met eerste, tweede met tweede.
4. Verschilt het aantal voorstellingen op een dag, dán pas is er sprake van een
   ontbrekende of extra voorstelling.

### Agenda-items koppelen

Een agenda-item hoort bij een speelbeurt als het op dezelfde datum valt en de
starttijd in het venster rond de aanvangstijd valt. Dat venster is bewust
**asymmetrisch**: van drie uur vóór de aanvangstijd tot een half uur erna.
Agenda-items worden namelijk vaak ruim van tevoren gezet (reistijd, inspelen),
maar vrijwel nooit ná aanvang. Beide grenzen staan in `config/trefwoorden.json`.

Een symmetrisch venster van drie uur zou op dagen met een matinee en een
avondvoorstelling overlappen, waardoor één agenda-item bij twee speelbeurten kan
horen. Met het asymmetrische venster overlappen de vensters van 14:30 en 20:00
niet. Vallen er op een dag toch meerdere kandidaten samen, dan wordt elk
agenda-item toegekend aan de speelbeurt waarvan de aanvangstijd het dichtst bij
ligt, en wordt elk item hoogstens één keer gebruikt.

Een agenda-item dat de hele dag beslaat heeft geen bruikbare starttijd. Zo'n item
telt op de juiste datum als aanwezig, maar de tijd wordt niet gecontroleerd; het
rapport vermeldt erbij dat de tijd niet te controleren viel.

Welke agenda-items als Cats-gerelateerd tellen, bepaalt een lijst trefwoorden in
`config/trefwoorden.json` (standaard: `cats`, aangevuld met de theaternamen en
steden uit de speellijst). Die lijst wordt bijgesteld zodra de echte agenda-
inhoud bekend is.

## Wat er gemeld wordt

Het rapport verschijnt in de terminal, gesorteerd op ernst, standaard alleen
vanaf vandaag. Voorbije voorstellingen zijn met een datumoptie op te vragen.

### Kritiek — raakt Emiel direct

- Bij Reed 2 staat een naam die niet Emiel, Christof, Coen of Michiel is. Dit
  wijst op een fout of een verschoven kolom en staat altijd bovenaan.
- De naam bij Reed 2 verschilt tussen orkestlijst en reed 2-sheet, en in een van
  beide staat Emiel.
- Emiel staat in de orkestlijst ingeroosterd, maar er is geen agenda-item.
- Emiel staat ingeroosterd, er is een agenda-item, maar de tijd wijkt meer dan de
  marge af.
- Er is een Cats-agenda-item zonder bijbehorende speelbeurt.

### Verschil tussen orkestlijst en reed 2-sheet

- De naam bij Reed 2 verschilt, maar Emiel komt er niet in voor.
- Aanvangstijd verschilt.
- Type verschilt (bijvoorbeeld REG tegenover S-OPT).
- Plaats verschilt.
- Het aantal voorstellingen op een dag verschilt.

### Website wijkt af — informatief

- musicalcats.nl noemt een andere datum, tijd, theater of stad dan de
  orkestlijst.
- Een voorstelling staat wel op de site en niet in de orkestlijst, of andersom.

### Nog in te vullen

- De reed 2-sheet heeft een naam, de orkestlijst is op die plek nog leeg.

## Reikwijdte

De twee controles hebben een verschillende reikwijdte.

De **vergelijking tussen orkestlijst en reed 2-sheet** kijkt naar alle dagen waar
in een van beide een naam bij Reed 2 staat, ongeacht wie. Verschillen tussen
Christof, Coen en Michiel onderling worden dus wel gemeld, alleen minder zwaar.

De **agendacontrole** kijkt uitsluitend naar dagen waar Emiel staat. Daar horen
ook MON- en BESL-dagen bij (repetitie en besloten voorstelling). Die staan alleen
in de reed 2-sheet en niet in de orkestlijst, dus voor deze dagen is de reed
2-sheet noodgedwongen de bron.

BOUW- en VRIJ-dagen worden overal genegeerd.

## Bewust buiten scope

- **Overnachtingen.** De kolom `Overnachten Reed 2` wordt niet gelezen en er wordt
  niets over gemeld. Overwogen en bewust weggelaten; kan later alsnog.
- **Schrijven naar de agenda.** Ontbrekende speelbeurten in de agenda zetten kan
  een iCal-URL niet; daarvoor moet de Google Calendar-connector geautoriseerd
  worden in de claude.ai-instellingen. Pas aan de orde als de controle
  betrouwbaar draait.
- **Een deelbaar rapport.** Voor nu is de terminal genoeg. Een bestand of pagina
  om naar Christof en Michiel door te sturen kan er later bovenop, want het
  rapport wordt als losse meldingen opgebouwd en niet als kant-en-klare tekst.
- **Schrijven naar welke sheet dan ook.** Geen enkele variant hiervan, ook niet
  later, zonder uitdrukkelijke nieuwe opdracht.

## De skill

`.claude/skills/cats-check/SKILL.md`, aan te roepen als `/cats-check`. De skill
legt vast:

1. Ververs de vier cachebestanden met de alleen-lees-tools.
2. Draai `compare.py`.
3. Presenteer het rapport en licht de meldingen toe.
4. De regel dat er nooit naar een bron geschreven wordt, herhaald op de plek waar
   hij gelezen wordt.

Zonder skill moet die werkwijze elke sessie opnieuw uitgelegd worden. De skill
wordt geschreven met de `writing-skills` skill, zodat hij ook getoetst wordt.

## Testen

- Elke parser wordt getoetst tegen een vastgelegd voorbeeldbestand in
  `tests/fixtures/`, een momentopname van de echte bron.
- `compare.py` wordt getoetst met met de hand gemaakte gevallen: naamverschil,
  tijdverschil, ontbrekende dag, twee voorstellingen op één dag waarvan er één
  mist, onbekende naam bij Reed 2, agenda-item zonder speelbeurt.
- De jaartal-afleiding krijgt een eigen test op de overgang december 2026 naar
  januari 2027.

## Openstaand risico

De orkestlijst is een xlsx van 182 kB. De tekstweergave van Drive kan bij grote
bestanden afkappen. Eerste stap bij het bouwen is nagaan of de volledige lijst
tot en met juni 2027 binnenkomt. Zo niet, dan wordt het bestand als ruwe bytes
opgehaald en met `openpyxl` gelezen. Dat raakt alleen de ophaalstap, niet de rest
van het ontwerp.

## Geheimen

`config/ical_url.txt` bevat de geheime agenda-URL, met rechten 600 en opgenomen
in `.gitignore`. Wie die URL heeft kan de agenda lezen, dus hij wordt nooit
gedeeld, gecommit of in een rapport afgedrukt. `cache/` gaat eveneens in
`.gitignore`: daar staat een kopie van de agenda-inhoud in.
