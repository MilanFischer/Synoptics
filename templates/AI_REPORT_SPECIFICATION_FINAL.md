# AI REPORT SPECIFICATION FINAL

## Filozofie reportu

Tento dokument není souborem komentářů k mapám.
Tento dokument je synoptickou prognostickou diskusí.
Mapy představují důkazy podporující interpretaci.

## Povinná struktura

1. Stručné shrnutí
2. Hlavní synoptický příběh
3. Meteorologické mechanismy
4. Vývoj situace v čase
5. Nejvýznamnější jevy období
6. Dopady na Evropu
7. Dopady na Českou republiku
8. Prognostická důvěra
9. Interpretace map

## Práce s mapami

Mapy musí být vloženy průběžně.
Mapová galerie na konci dokumentu je zakázána.
Pouhé vložení map bez interpretace je nepřípustné.

## Kritéria kvality

Report je neplatný pokud:
- obsahuje mapy bez interpretace,
- pouze popisuje pole,
- neobsahuje mechanismy,
- neobsahuje vývoj v čase,
- neobsahuje evropský kontext,
- opakuje stejné odstavce,
- nevyužívá všechny prognostické termíny.

## Závěrečný test

Pokud odstraním všechny mapy, musí report stále fungovat jako plnohodnotná synoptická analýza.


## Povinná integrace nových proměnných

Report musí využít nové diagnostické vrstvy v meteorologickém kontextu, ne jako samostatný seznam map.

### Jet 250 hPa

Použij pro vysvětlení výškové dynamiky, Rossbyho vln, hřebenů, brázd, blokací, cyklogeneze a postupu frontálních systémů.

### PWAT

Použij pro vysvětlení vlhkosti atmosférického sloupce a potenciálu intenzivních srážek. Vždy rozlišuj mezi dostupnou vlhkostí a skutečnou realizací srážek.

### CAPE/CIN

Použij pro hodnocení konvekčního prostředí. CAPE nikdy neinterpretuj izolovaně. Vždy uveď, zda CIN konvekci podporuje, omezuje nebo blokuje a zda existuje spouštěcí mechanismus.

## Povinné syntetické propojení

V části o mechanismech musí být propojena alespoň tato pole:

- tlakové pole a proudění,
- Z500 a T850,
- Jet 250 hPa,
- PWAT,
- CAPE a CIN.

Cílem je vysvětlit, proč se dané počasí vyvíjí, nikoli jen vyjmenovat hodnoty.


## Kumulované srážky

Při hodnocení srážek vždy rozlišuj srážky za aktuální prognostický interval a kumulované srážky od začátku výhledu. Pokud jsou k dispozici mapy `precip_compare`, používej je pro prostorové srovnání intervalových a kumulovaných úhrnů.

## Oceánské a telekonekční pozadí

Pokud je v `briefing_context.json` přítomen objekt `climate_background`, report musí stručně interpretovat:

- SST anomálii severního Atlantiku,
- SST anomálii Středozemního moře,
- index NAO,
- index EA, pokud je dostupný.

Tyto hodnoty používej jako širší synoptické pozadí. Nevydávej je za deterministickou příčinu konkrétního počasí, ale vysvětli jejich možnou souvislost s polohou jet streamu, blokací, vlhkostí vzduchové hmoty a hodnotami PWAT.

V této části musí být vždy explicitně uvedena také metadata oceánského podkladu, pokud jsou dostupná:

- Zdroj SST: hodnota `climate_background.ocean.dataset`, zkráceně nejméně jako `NOAA OISST v2.1`.
- Datum datasetu: hodnota `climate_background.ocean.valid_date`.
- Zpoždění vůči běhu modelu: hodnota `climate_background.ocean.lookback_days_used` ve dnech.

Doporučený tvar v reportu:

```text
Zdroj SST: NOAA OISST v2.1
Datum datasetu: YYYY-MM-DD
Zpoždění vůči běhu modelu: N dní
```


Pokud je v `briefing_context.json` přítomen objekt `ocean_climatology_analysis`, musí být ve stejné kapitole využit také historický kontext SST anomálií:

- sezonní percentil aktuální SST anomálie pro Středozemní moře a severní Atlantik,
- pořadí aktuální hodnoty v sezonním okně,
- all-days percentil pouze jako doplňkový kontext,
- historické maximum a datum maxima, pokud jsou dostupné.

Tyto statistiky interpretuj jako informaci o výjimečnosti aktuálního oceánského pozadí vůči lokální databázi NOAA OISST od roku 2000. Nevydávej je za přímou deterministickou příčinu počasí, ale propoj je s potenciálem vlhkosti, latentního tepla, PWAT a synoptickým režimem.

