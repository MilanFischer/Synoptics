Vytvoř profesionální český synoptický report DOCX podle instrukcí obsažených v tomto balíčku.

Začni souborem START_HERE.md.


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


