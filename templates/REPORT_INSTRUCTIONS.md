# REPORT INSTRUCTIONS

## Hlavní filozofie

Nejde o komentář map.
Jde o interpretaci atmosféry.
Mapy slouží jako důkazy.

## Povinné otázky

1. Co se děje?
2. Proč se to děje?
3. Jak se situace změní?
4. Kde budou nejvýznamnější projevy?
5. Jaké budou dopady?

## Povinné oblasti hodnocení

### Evropa
- hlavní synoptická osa dění,
- dominantní tlakové útvary,
- oblasti teplé a studené advekce,
- oblasti zvýšené cyklonální aktivity,
- oblasti stabilního počasí.

### Extrémy
- nejteplejší oblast Evropy,
- nejchladnější oblast Evropy,
- nejsrážkovější oblast,
- oblast nejsilnějšího větru,
- oblast nejvyššího požárního rizika.

### Česká republika
- hlavní mechanismy,
- očekávaný vývoj,
- rizika,
- nejistoty.

## Časový vývoj

Analyzuj všechny prognostické termíny.
Vysvětli co zesiluje, slábne, přesouvá se a stává se dominantním mechanismem.

## Zakázané formulace

Nepoužívej stále stejné věty a opakující se komentáře pod mapami.


## Nové diagnostické vrstvy

### Jet 250 hPa

Jet 250 hPa používej jako hlavní pole pro výškovou dynamiku. Vždy zhodnoť:

- kde leží hlavní osa tryskového proudění,
- kde jsou jet cores,
- zda střední Evropa leží pod hlavním jetem, jižně od něj nebo v oblasti slabého výškového proudění,
- zda konfigurace podporuje hřeben, brázdu, blokaci nebo cyklogenezi.

### PWAT

PWAT používej jako diagnostiku vlhkosti celého atmosférického sloupce. Hodnoty interpretuj orientačně takto:

- méně než 20 mm: suchý sloupec,
- 20–30 mm: běžná vlhkost,
- 30–40 mm: vlhký sloupec,
- více než 40 mm: vysoký potenciál intenzivních srážek,
- více než 50 mm: mimořádně vlhký sloupec.

PWAT není totéž co srážky. Vysvětluje potenciál, nikoli automatický výskyt srážek.

### CAPE a CIN

CAPE a CIN interpretuj společně:

- CAPE ukazuje energii pro konvekci,
- CIN ukazuje blokaci konvekce,
- vysoké CAPE bez spouštěcího mechanismu nemusí vést k bouřkám,
- vysoké CAPE se slabým CIN a dostatkem vlhkosti zvyšuje riziko bouřek,
- vysoké CAPE s výrazným CIN značí potenciál, který může zůstat nevyužitý.

Při hodnocení bouřek vždy kombinuj CAPE, CIN, PWAT, frontální zóny, orografii a výškovou dynamiku.


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

