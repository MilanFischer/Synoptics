# Stylová příručka

Piš česky.

Používej odborný, ale srozumitelný jazyk synoptické meteorologie.

Nepoužívej anglické názvy kapitol.

Nepoužívej fráze typu:

- Zpracováno z AI balíčku
- Podle briefing_context.json
- Podle maps_manifest.json
- AI analýza ukazuje

Preferuj formulace vysvětlující příčiny:

- Vývoj je důsledkem...
- Mechanismus spočívá v...
- Rozložení polí naznačuje...
- Tato konfigurace podporuje...
- Dopady lze očekávat zejména...

Vyhýbej se mechanickému opakování stejných vět pod mapami.

Každý odstavec musí přinést novou informaci.


## Terminologie nových polí

Používej české odborné výrazy:

- Jet 250 hPa: tryskové proudění, hlavní větev tryskového proudění, jádro tryskového proudění, výšková dynamika.
- PWAT: srážková voda ve sloupci, vlhkost atmosférického sloupce, potenciál intenzivních srážek.
- CAPE: dostupná konvektivní potenciální energie, labilita, konvekční potenciál.
- CIN: konvektivní inhibice, blokace konvekce, zádržná vrstva.

Nepoužívej formulaci „CAPE způsobí bouřky“. Vhodnější je:

- „CAPE indikuje dostupnou energii pro konvekci.“
- „Realizace bouřek závisí na spouštěcím mechanismu a velikosti CIN.“
- „Vysoký PWAT zvyšuje potenciál intenzivních srážek, pokud dojde ke spuštění srážkové nebo konvekční aktivity.“


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

