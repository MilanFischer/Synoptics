# Stručné shrnutí

Krátce shrň hlavní synoptický příběh: dominantní tlakové útvary, teplotní charakter, vlhkostní poměry, dynamiku ve vyšších hladinách a hlavní rizika.

# Synoptická situace nad Evropou

Popiš hlavní rozložení tlakových útvarů, hřebenů, brázd, frontálních zón a advekčních oblastí.

# Výšková dynamika a Jet 250 hPa

Interpretuj tryskové proudění v hladině 250 hPa:

- polohu hlavní větve jet streamu,
- polohu a intenzitu jet core,
- vztah jetu k hřebenům a brázdám,
- podporu nebo absenci podpory cyklogeneze,
- vliv na postup frontálních systémů,
- důsledky pro střední Evropu a Českou republiku.

Nepopisuj pouze rychlost větru. Vysvětli, co poloha jetu znamená pro vývoj synoptické situace.

# Vlhkostní pole a PWAT

Interpretuj precipitable water jako množství vody v celém atmosférickém sloupci:

- oblasti suchého vzduchového sloupce,
- oblasti vlhkého až velmi vlhkého sloupce,
- hodnoty nad 30 mm jako významně vlhké prostředí,
- hodnoty nad 40 mm jako zvýšený potenciál intenzivních srážek,
- hodnoty nad 50 mm jako mimořádně vlhký sloupec.

Vysvětli rozdíl mezi aktuálními srážkami a potenciálem pro intenzivní srážky.

# Konvekční prostředí: CAPE a CIN

Interpretuj CAPE a CIN společně, nikoliv odděleně:

- CAPE jako dostupnou energii pro konvekci,
- CIN jako inhibici bránící spuštění konvekce,
- oblasti, kde je CAPE vysoké a CIN slabé,
- oblasti, kde je CAPE vysoké, ale konvekce může být blokována CIN,
- vliv synoptického zdvihu, front, orografie a vlhkosti na spuštění konvekce.

Nepovažuj vysoké CAPE automaticky za bouřky. Vždy zhodnoť, zda existuje spouštěcí mechanismus a zda CIN konvekci neblokuje.

# Dynamická interpretace a mechanismy vývoje

Propoj tlakové pole, Z500, T850, Jet 250, PWAT, CAPE a CIN do jednoho vysvětlení. Zaměř se na mechanismy, nikoli na izolovaný popis map.

# Vývoj synoptické situace v čase

## +0 až +12 h

## +12 až +24 h

## +24 až +48 h

## +48 až +72 h

## +72 až +96 h

U každého období vysvětli, co zesiluje, slábne, přesouvá se a jak se mění dynamika, vlhkost a konvekční potenciál.

# Významné anomálie a extrémy nad Evropou

Zhodnoť teplotní extrémy, tlakové anomálie, vlhkostní anomálie, srážkový potenciál, silný vítr a konvekční rizika.

# Situace nad Českou republikou

Popiš konkrétně dopady na ČR:

- teplotní charakter,
- vlhkostní charakter,
- vliv jet streamu,
- pravděpodobnost frontálního nebo konvekčního vývoje,
- CAPE/CIN a spouštěcí mechanismy,
- hlavní rizika.

# Dopady na Evropu

# Dopady na Českou republiku

# Teplotní poměry

# Tlakové pole a proudění

# Srážky, vlhkost a konvekce

Propoj srážky s PWAT, CAPE, CIN a synoptickým zdvihem. Nepopisuj pouze srážkové mapy.

# Hlavní meteorologická rizika

Zahrň rizika horka, silného větru, intenzivních srážek, bouřek, sucha a požárního rizika, pokud jsou relevantní.

# Prognostická důvěra

Uveď, které části prognózy jsou dobře podložené a kde je nejistota vyšší. Pokud nejsou dostupná ensemble data, formuluj důvěru opatrně podle konzistence synoptických polí v čase.

# Závěrečné hodnocení

# Mapová příloha

Mapová příloha je povolena pouze jako doplněk. Mapy musí být interpretovány už v hlavním textu.


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

- percentil aktuální SST anomálie pro Středozemní moře a severní Atlantik ve srovnání se stejným obdobím roku,
- pořadí aktuální hodnoty ve srovnání se stejným obdobím roku,
- all-days percentil pouze jako doplňkový kontext,
- historické maximum a datum maxima, pokud jsou dostupné.

Nepoužívej výraz „sezonní okno“ ani „sezonní srovnávací okno“. Místo toho vždy vysvětli metodiku srozumitelně:

```text
Ve srovnání se stejným obdobím roku (±N dní) dosahuje XX.XX percentilu a řadí se na R. místo z N historických případů.
```

Hodnotu `N` převezmi z `ocean_climatology_analysis.regions.<region>.seasonal_window.window_days`, případně použij text `recommended_report_phrase_cs` nebo `description`, pokud je v JSONu dostupný.

Tyto statistiky interpretuj jako informaci o výjimečnosti aktuálního oceánského pozadí vůči lokální databázi NOAA OISST od roku 2000. Nevydávej je za přímou deterministickou příčinu počasí, ale propoj je s potenciálem vlhkosti, latentního tepla, PWAT a synoptickým režimem.

