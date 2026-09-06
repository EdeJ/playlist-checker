# Alle bronnen via curl — ontwerp

Datum: 2026-09-06
Status: gebouwd (2026-09-06)
Vervolg op: `2026-09-05-cats-speellijst-checker-design.md`

## Aanleiding

In de eerste opzet halen twee van de vier bronnen hun weg via het model: de
orkestlijst met `read_file_content`, de reed 2-sheet met
`download_file_content`. Dat kost per gewijzigde run grofweg 30.000 tokens,
waarvan de helft uitvoer:

| Bron | Wat er door het model gaat | Kosten |
|---|---|---|
| orkestlijst | 24 kB tekst binnen, daarna diezelfde 24 kB **letterlijk overgetypt** naar `cache/orkest.txt` | ±7k in, ±7k uit |
| reed 2 | 15,5 kB CSV komt als base64 binnen (20,8 kB) en moet er als base64 weer uit om gedecodeerd te worden | ±7k in, ±7k uit |

De uitvoerhelft is de dure helft. Bovendien blijft die 45 kB de rest van het
gesprek in de context staan, en is het overtypen van 24 kB een plek waar het
model stilzwijgend een teken kan verhaspelen.

Beide bestanden blijken met hun link leesbaar zonder authenticatie. Daarmee kan
`curl` ze ophalen, net als de website en de agenda nu al gaan, en passeert geen
enkele bron het model nog.

## Ontwerp

### Ophalen: vier bronnen, één script

`scripts/ophalen.sh` haalt voortaan alle vier de bronnen op, volgens het patroon
dat er al staat: naar een tijdelijk bestand in `cache/`, valideren, en pas dan
met `mv` op zijn plek zetten.

| Bron | URL | Geldig als |
|---|---|---|
| reed 2 | `docs.google.com/spreadsheets/d/<id>/export?format=csv` | eerste regel begint met `Speeldatum,Type` |
| orkestlijst | `drive.google.com/uc?export=download&id=<id>` | bestand begint met `PK` (een zip, dus een echte xlsx) |

De twee bestands-id's staan in het script, naast de musicalcats-URL. Ze zijn
geen geheim; ze stonden al in `SKILL.md` en in git.

`cache/stempels.json` en de hele `modifiedTime`-vergelijking vervallen. `curl`
is gratis, dus er wordt altijd opgehaald.

### Falen is hard falen

Wordt de linkdeling ooit ingetrokken, dan geeft `curl` een inlogpagina terug in
plaats van het bestand. De validatie ziet dat, de cache blijft ongewijzigd, en
het script meldt per bron wat er misging. Het script loopt eerst alle vier de
bronnen langs en sluit daarna af met exitcode 1 als er iets faalde — zo zie je
in één keer wat er stuk is.

Stil doorglippen mag niet: een verouderde cache parseert vrolijk door en levert
een rapport op dat nergens over gaat.

Er komt geen terugvalroute via de Drive-connector. Dat zou betekenen dat de
oude tekstparser naast de nieuwe blijft bestaan, onderhouden voor een situatie
die zich misschien nooit voordoet. Gebeurt het toch, dan is de oude parser met
één `git revert` terug.

### De orkestparser leest de xlsx zelf

`catscheck/orkest.py` wordt herschreven: `parse_orkest(data: bytes)` leest de
xlsx met `zipfile` en `xml.etree` uit de standaardbibliotheek. Geen dependency.

De xlsx heeft de structuur die de tekstweergave was kwijtgeraakt:

| | tekstweergave (nu) | xlsx (straks) |
|---|---|---|
| tabbladen | herkennen aan de maandnaam-dubbel-regex | echte sheetnamen: `Oktober` … `Juni` |
| Mamma Mia buitensluiten | regex die op "Mamma Mia" afkapt | die twee tabbladen zijn `state="hidden"` |
| rijen | knippen op het weekdagpatroon | echte rijen |
| kolommen | tellen na `split(",")` | echte kolommen; `Reed 2` staat overal in Q |

Daarmee vervallen `_BLOK`, `_ANDERE_PRODUCTIE` en `_RIJ`.

Per tabblad:

- tabbladen met `state != "visible"` worden overgeslagen (Mamma Mia), net als
  tabbladen zonder `Reed 2` in de kop (INPUT)
- de kopregel wordt **opgezocht**, niet vastgespijkerd: in Oktober staat hij op
  rij 2, in de overige maanden op rij 1
- de maand komt uit de sheetnaam; `"Januari "` heeft een spatie erachter, dus
  strippen. Het jaar rolt over zoals nu: is de maand kleiner dan de vorige, dan
  jaar erbij
- kolommen A–E zijn in alle negen maandtabbladen gelijk: weekdag, dagnummer,
  tijd, type, plaats. De Reed 2-kolom wordt uit de gevonden kopregel gehaald en
  niet vastgelegd; dat hij vandaag overal Q is, is een waarneming en geen
  aanname

Twee waarden komen anders binnen dan uit de tekstweergave. Het dagnummer is een
float (`6.0`). De tijd is een Excel-dagfractie (`0.84375` = 20:15) waar de
tekstweergave al `"20:15"` maakte; die omrekening gebeurt in de xlsx-laag, zodat
`normaliseer_tijd` blijft wat het is — een pure stringfunctie die alle vier de
bronnen delen. Er wordt op de minuut afgerond, zodat drijvende-kommaruis geen
verschil maakt.

De drie bestaande `ParseFout`-garanties blijven ongewijzigd: datarijen zonder
`Reed 2`-kolom, een weekdag die niet bij de datum past, en nul gevonden
voorstellingen. Er komt er één bij: het bestand is geen leesbare xlsx.

### Aanroep

`catscheck/__main__.py` leest `cache/orkest.xlsx` als bytes in plaats van
`cache/orkest.txt` als tekst, met dezelfde foutafhandeling: een bron die niet
gelezen kan worden geeft exitcode 2.

### Tests

`tests/fixtures/orkest.txt` wordt `tests/fixtures/orkest.xlsx`. Om die fixture
leesbaar te houden komt er een testhelper die uit een dict van sheetnaam naar
rijen een minimale xlsx schrijft. De fixture staat dan als tabel in de test in
plaats van als binair bestand, en kapotte varianten (kop weg, verborgen
tabblad, onmogelijke tijd) zijn gericht te maken.

Alle bestaande gevallen uit `test_orkest.py` gaan mee.

### Skill en documentatie

`SKILL.md`: stap 1 en 2 smelten samen tot `./scripts/ophalen.sh`. De
`modifiedTime`-vergelijking, de bestands-id's en de Drive-toolinstructies
verdwijnen eruit.

De absolute alleen-lezen-regel blijft staan, en het `permissions.deny`-lijstje
in `.claude/settings.json` ook. Die gaan over wat er niet mag gebeuren, niet
over welk gereedschap toevallig in gebruik is.

`README.md`: de alinea over "de twee Drive-bestanden passeren het model, samen
zo'n 10.000 tokens" klopt niet meer en wordt vervangen.

## Wat dit oplevert

Per run passeren nog twee commando's en een rapport het model. Geen bronnen
meer, dus ook geen 24 kB overtypen — dat scheelt tokens en haalt tegelijk de
stilste foutbron uit de keten. De Drive-connector is niet langer nodig en de
checker wordt volledig scriptbaar buiten Claude om.

## Risico

De hele opzet hangt aan de linkdeling van twee bestanden waarvan er één van
iemand anders is. Wordt die deling ingetrokken, dan stopt het ophalen met een
duidelijke melding en is er handwerk nodig. Dat is een bewuste afweging: één
route, hard falen, en de oude route ligt in de geschiedenis.
