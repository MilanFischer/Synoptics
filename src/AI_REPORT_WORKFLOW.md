# Finální workflow pro denní synoptický report

## 1. Denní spuštění pipeline

Spusť z kořene projektu:

```powershell
python .\src\run_all.py --fxx-list "0,6,12,24,48,72"
```

Pipeline automaticky:

- najde dostupný běh GFS,
- vytvoří denní výstupní složku `outputs/gfs_YYYY-MM-DD_HH/`,
- vygeneruje mapy,
- vygeneruje JSON charakteristiky,
- vygeneruje dílčí Markdown/PDF reporty,
- vytvoří AI balíček ZIP.

## 2. Kde najít ZIP pro AI

Výsledný ZIP je v denní složce:

```text
outputs/gfs_YYYY-MM-DD_HH/ai_inputs/gfs_YYYY-MM-DD_HH.zip
```

Tento ZIP nahraj do ChatGPT nebo jiné AI.

## 3. Co ZIP obsahuje

AI balíček obsahuje:

- `REPORT_INSTRUCTIONS.md`,
- `AI_REPORT_SPECIFICATION_FINAL.md`,
- `style_guide.md`,
- `briefing_template.md`,
- `prompt.md`,
- `metadata.json`,
- `briefing_context.json`,
- `maps_manifest.json`,
- `maps/`.

Tyto soubory jednoznačně určují, že AI má vytvořit profesionální český synoptický report ve formátu MS Word DOCX s mapami.

## 4. Obsah výsledného reportu

Report nesmí být založen pouze na prvním forecast hour.

Report musí analyzovat všechny dostupné prognostické termíny obsažené v:

- `briefing_context.json`,
- `maps_manifest.json`.

Report má hodnotit:

- celou Evropu,
- Českou republiku,
- mechanismy vývoje,
- tlakové pole,
- výškové pole,
- teplotní advekci,
- srážky a konvekci,
- anomálie a extrémy,
- hlavní meteorologická rizika,
- prognostickou důvěru.

## 5. Povinné časové členění

Report musí vyhodnotit vývoj v čase, typicky:

- +0 až +12 h,
- +12 až +24 h,
- +24 až +48 h,
- +48 až +72 h.

Má popsat:

- zesilování nebo slábnutí tlakových útvarů,
- přesuny tlakových systémů,
- změny v teplotním poli,
- změny ve srážkové činnosti,
- změny ve větrném poli,
- významné synoptické mechanismy.

## 6. Evropa a Česká republika

Report musí mít evropské měřítko i samostatnou kapitolu pro Českou republiku.

V evropské části má identifikovat významné extrémy a anomálie, například:

- ohniska horké vlny,
- oblasti výrazných srážek,
- oblasti silného větru,
- studené vpády,
- blokující anticyklony,
- aktivní cyklonální dráhy.

V části pro Českou republiku má popsat:

- synoptické postavení ČR,
- teplotní charakteristiky,
- srážkové a konvektivní riziko,
- vliv hlavních evropských tlakových útvarů na počasí v ČR.

## 7. Doporučená věta pro AI

Po nahrání ZIPu stačí napsat:

```text
Vytvoř z tohoto balíčku český synoptický report DOCX podle přiložených instrukcí.
```
