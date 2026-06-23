from pathlib import Path
import argparse
import json
import shutil
import zipfile
from datetime import datetime

from utils import PROJECT_ROOT, REPORTS_DIR, MAPS_DIR, AI_INPUTS_DIR, parse_priority


MAP_PREFIXES = {
    "z500_t850": "z500_t850_europe",
    "jet250": "jet250_europe",
    "pwat": "pwat_europe",
    "cape_cin": "cape_cin_europe",
    "mslp_wind": "mslp_wind_europe",
    "t850": "t850_europe",
    "precip": "precip_europe",
    "precip_accum": "precip_accum_europe",
}

# Order and human-facing labels for one AI-friendly overview image per forecast hour.
# Labels are intentionally English because map products in this project use English.
COMBINED_MAP_LAYOUT = [
    ("mslp_wind", "MSLP + 10 m wind"),
    ("z500_t850", "Z500 + T850"),
    ("t850", "T850"),
    ("pwat", "PWAT"),
    ("cape_cin", "CAPE + CIN"),
    ("jet250", "Jet 250 hPa"),
    ("precip", "Period precipitation"),
    ("precip_accum", "Cumulative precipitation from +0 h"),
]

COMBINED_FIGURE_DIRNAME = "combined_figures"
COMBINED_TILE_SIZE = (1400, 900)
COMBINED_MARGIN = 36
COMBINED_GAP = 24
COMBINED_HEADER_HEIGHT = 92
COMBINED_LABEL_HEIGHT = 42


TEMPLATES_DIR = PROJECT_ROOT / "templates"

TEMPLATE_FILES = [
    "START_HERE.md",
    "README.md",
    "AI_REPORT_SPECIFICATION_FINAL.md",
    "REPORT_INSTRUCTIONS.md",
    "style_guide.md",
    "briefing_template.md",
    "prompt.md",
    "metadata.json",
]

TEXT_TEMPLATE_SUFFIXES = {".md", ".txt", ".json"}


STYLE_GUIDE = """# Pokyny pro tvorbu synoptického briefingu

Piš česky. Nepoužívej anglické názvy kapitol.

Cílem je odborný operativní synoptický briefing pro Evropu se zvláštním zaměřením na Českou republiku.

Používej zejména tyto pojmy: tlaková výše, tlaková níže, výškový hřeben, výšková brázda, advekce, cyklonální činnost, anticyklonální vliv, frontální rozhraní, srážky, konvekce, srážková voda v atmosférickém sloupci, teplá vzduchová hmota.

Zpráva má obsahovat:

1. Stručné shrnutí
2. Synoptická situace nad Evropou
3. Vývoj v čase
4. Zaměření na Českou republiku
5. Teplotní poměry
6. Tlakové pole a proudění
7. Vlhkost atmosférického sloupce, CAPE/CIN, srážky a konvekce
8. Hlavní meteorologická rizika
9. Prognostická důvěra

Mapy používej jako hlavní zdroj prostorové interpretace. JSON používej pro čísla a trendy.
"""


PROMPT = """Jsi zkušený synoptický meteorolog. Z přiloženého balíčku vytvoř profesionální synoptický briefing v češtině.

Použij briefing_context.json, maps_manifest.json a přiložené mapy. Dodrž style_guide.md. Zvláštní pozornost věnuj České republice: popiš její polohu vůči hlavním tlakovým útvarům, proudění, teplotní advekci, srážkám a případným rizikům.

Výstup připrav jako souvislou odbornou zprávu. Pokud máš vytvořit dokument, vlož vhodné mapy s českými popisky.
"""


REPORT_INSTRUCTIONS = """# Pokyny pro generování synoptického reportu

Pokud je tento soubor přítomen v AI balíčku, vytvoř nový dokument MS Word ve formátu DOCX.

## Povinný výstup

Výstupem musí být profesionálně formátovaný český synoptický report s mapami.

Report musí být určen meteorologům a pokročilým uživatelům. Nepiš popularizační text a nepoužívej anglické názvy kapitol.

## Zásadní pravidlo

Report nesmí hodnotit pouze první forecast hour. Musí analyzovat všechny dostupné prognostické termíny obsažené v `briefing_context.json` a `maps_manifest.json`.

## Povinný rozsah interpretace

Report musí hodnotit:

- celou Evropu,
- Českou republiku,
- vývoj synoptické situace v čase,
- mechanismy počasí,
- extrémy a anomálie,
- hlavní meteorologická rizika,
- prognostickou důvěru.

## Práce s mapami

Použij mapy jako hlavní zdroj prostorové synoptické interpretace. Do dokumentu vlož vybrané mapy, zejména:

- Z500 + T850,
- jet stream 250 hPa v jednotkách m/s,
- PWAT / srážkovou vodu v atmosférickém sloupci v mm,
- CAPE + CIN pro konvektivní potenciál,
- MSLP + vítr,
- srážky, včetně rozlišení intervalových a kumulovaných úhrnů od začátku výhledu.

Ke každé vložené mapě přidej odborný český komentář.
"""


AI_REPORT_SPECIFICATION = """# Specifikace synoptického reportu

## Účel

Po nahrání AI balíčku ZIP vytvoř profesionální synoptický report v českém jazyce ve formátu DOCX.

Report nesmí být pouze popisem jednotlivých map. Cílem je odborná synoptická analýza, interpretace mechanismů a hodnocení očekávaného vývoje počasí.

## Vstupy

AI balíček může obsahovat:

- `briefing_context.json`,
- `maps_manifest.json`,
- `REPORT_INSTRUCTIONS.md`,
- `AI_REPORT_SPECIFICATION_FINAL.md`,
- `style_guide.md`,
- `briefing_template.md`,
- mapy T850,
- mapy Z500 + T850,
- mapy MSLP + vítr,
- mapy srážek,
- mapy jet streamu 250 hPa v jednotkách m/s,
- mapy CAPE a CIN v jednotkách J/kg,
- další JSON soubory s charakteristikami a hodnocením.

Použij všechny dostupné podklady.

## Povinný výstup

Vytvoř:

- DOCX report,
- český jazyk,
- odborný styl,
- vložené mapy,
- tabulky a strukturované kapitoly.

Cílový rozsah: 5–10 stran včetně map a komentářů.

## Hlavní zaměření

### Evropa

Analyzuj:

- tlakové výše a níže,
- výškové hřebeny a brázdy,
- blokující situace,
- cyklonální činnost,
- frontální rozhraní,
- teplotní advekci,
- proudění,
- vývoj tlakových systémů.

Diskutuj:

- horké vlny,
- studené vpády,
- extrémní srážky,
- silný vítr,
- teplotní anomálie,
- významné regionální rozdíly.

Uveď konkrétní oblasti Evropy, například Pyrenejský poloostrov, Francii, Britské ostrovy, Skandinávii, Alpy, Balkán, střední Evropu a oblast České republiky.

### Česká republika

V samostatné kapitole vyhodnoť:

- synoptické postavení ČR,
- očekávaný vývoj počasí,
- teplotní poměry,
- srážkové poměry,
- konvekci,
- hlavní rizika.

## Vývoj v čase

Report nesmí hodnotit pouze forecast +0 h. Musí analyzovat všechny dostupné termíny.

Vyhodnoť časové bloky podle dostupných dat, typicky:

- +0 až +12 h,
- +12 až +24 h,
- +24 až +48 h,
- +48 až +72 h.

Popiš:

- zesilování a slábnutí útvarů,
- přesuny tlakových systémů,
- změny teplotního pole,
- změny srážkové činnosti,
- změny větrného pole.

## Mechanismy

Nevytvářej pouze popis map. Vysvětluj:

- proč dochází k oteplování či ochlazování,
- proč vznikají srážky,
- proč se prohlubují níže,
- proč zesilují výše,
- jak souvisí Z500, T850, MSLP, vítr a srážky.

Zaměř se na příčiny a souvislosti.


### Dynamika vyšší troposféry / jet stream 250 hPa

Povinně interpretuj pole 250 hPa jet streamu. Zaměř se na:

- polohu hlavních větví tryskového proudění,
- jádra jet streamu, zejména rychlosti nad 50 m/s,
- vztah jet streamu k výškovým hřebenům a brázdám,
- dynamickou podporu cyklogeneze, frontogeneze a blokace,
- důsledky pro střední Evropu a Českou republiku.

### Konvektivní potenciál / CAPE a CIN

Povinně interpretuj CAPE a CIN společně s PWAT a srážkami. Zaměř se na:

- oblasti se zvýšeným CAPE nad 500 a 1000 J/kg,
- oblasti se zvýšenou inhibicí CIN nad 50 a 100 J/kg,
- rozdíl mezi dostupnou energií a reálnou pravděpodobností spuštění konvekce,
- vztah PWAT k potenciálu přívalových srážek,
- důsledky pro střední Evropu a Českou republiku.

## Povinná struktura reportu

1. Stručné shrnutí
2. Synoptická situace nad Evropou
3. Vývoj synoptické situace
4. Významné anomálie a extrémy
5. Situace nad Českou republikou
6. Teplotní poměry
7. Tlakové pole a proudění
8. Srážky a konvekce
9. Hlavní meteorologická rizika
10. Prognostická důvěra
11. Závěrečné hodnocení

## Styl

Používej odbornou terminologii synoptické meteorologie. Nepoužívej anglické názvy kapitol. Preferuj vysvětlení mechanismů před prostým popisem polí. Mapy používej jako hlavní zdroj interpretace.
"""


BRIEFING_TEMPLATE = """# Stručné shrnutí

# Synoptická situace nad Evropou

# Vývoj synoptické situace

## +0 až +12 h

## +12 až +24 h

## +24 až +48 h

## +48 až +72 h

# Významné anomálie a extrémy

# Situace nad Českou republikou

# Teplotní poměry

# Tlakové pole a proudění

# Srážky a konvekce

# Hlavní meteorologická rizika

# Prognostická důvěra

# Závěrečné hodnocení
"""


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True, help='Example: "2026-06-19 00:00"')
    parser.add_argument("--priority", default="aws,nomads,google,azure")
    return parser.parse_args()


def safe_time_id(value):
    return value.replace(":", "-")


def run_id(run_time):
    dt = datetime.strptime(run_time, "%Y-%m-%d %H:%M")
    return f"gfs_{dt:%Y-%m-%d_%H}"


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def find_json(prefix, valid_time):
    path = REPORTS_DIR / f"{prefix}_{safe_time_id(valid_time)}.json"
    return path if path.exists() else None


def find_map(prefix, valid_time):
    path = MAPS_DIR / f"{prefix}_{safe_time_id(valid_time)}.png"
    return path if path.exists() else None


def collect_timesteps(run_time):
    timesteps = []

    for feature_file in sorted(REPORTS_DIR.glob("features_*.json")):
        features = load_json(feature_file)
        if features.get("run_time") != run_time:
            continue

        valid_time = features["valid_time_utc"]
        fxx = features["forecast_hour"]

        synoptic_file = find_json("synoptic_features", valid_time)
        assessment_file = find_json("synoptic_assessment", valid_time)
        commentary_file = find_json("synoptic_commentary", valid_time)
        precip_accum_file = find_json("precip_accum", valid_time)
        briefing_md_file = REPORTS_DIR / f"briefing_static_{safe_time_id(valid_time)}.md"
        briefing_pdf_file = REPORTS_DIR / f"briefing_static_{safe_time_id(valid_time)}.pdf"

        item = {
            "forecast_hour": fxx,
            "valid_time": valid_time,
            "source_files": {
                "features": feature_file.name,
                "synoptic_features": synoptic_file.name if synoptic_file else None,
                "assessment": assessment_file.name if assessment_file else None,
                "commentary": commentary_file.name if commentary_file else None,
                "precip_accum": precip_accum_file.name if precip_accum_file else None,
                "briefing_md": briefing_md_file.name if briefing_md_file.exists() else None,
                "briefing_pdf": briefing_pdf_file.name if briefing_pdf_file.exists() else None,
            },
            "features": features,
            "synoptic_features": load_json(synoptic_file) if synoptic_file else None,
            "assessment": load_json(assessment_file) if assessment_file else None,
            "commentary": load_json(commentary_file) if commentary_file else None,
            "precip_accum": load_json(precip_accum_file) if precip_accum_file else None,
            "maps": {},
        }

        # Enrich the main features object with cumulative precipitation diagnostics
        # so the AI report can use one consistent JSON path.
        if item["precip_accum"]:
            accum_cz = (
                item["precip_accum"]
                .get("regions", {})
                .get("czechia", {})
                .get("precip_accum_total_mm")
            )
            if accum_cz:
                features.setdefault("regions", {}).setdefault("czechia", {})["precip_accum_total_mm"] = accum_cz

            accum_domain = (
                item["precip_accum"]
                .get("domain", {})
                .get("precip_accum_total_mm")
            )
            if accum_domain:
                features.setdefault("features", {}).setdefault("precipitation", {})["precip_accum_total_mm"] = accum_domain

        for key, prefix in MAP_PREFIXES.items():
            map_file = find_map(prefix, valid_time)
            if map_file:
                item["maps"][key] = map_file

        timesteps.append(item)

    return sorted(timesteps, key=lambda x: x["forecast_hour"])


def copy_maps(timesteps, output_maps_dir):
    output_maps_dir.mkdir(parents=True, exist_ok=True)
    manifest = []

    for item in timesteps:
        copied_maps = {}
        for key, src in item["maps"].items():
            dst = output_maps_dir / src.name
            shutil.copy2(src, dst)
            rel = Path("maps") / dst.name
            copied_maps[key] = rel.as_posix()
            manifest.append({
                "forecast_hour": item["forecast_hour"],
                "valid_time": item["valid_time"],
                "type": key,
                "file": rel.as_posix(),
            })
        item["maps"] = copied_maps

    return manifest



def _get_nested(mapping, path, default=None):
    value = mapping
    for key in path:
        if not isinstance(value, dict) or key not in value:
            return default
        value = value[key]
    return value


def _fmt_metric(value, unit="", decimals=1):
    if value is None:
        return "n/a"
    try:
        value = float(value)
    except (TypeError, ValueError):
        return "n/a"
    if decimals == 0:
        text = f"{value:.0f}"
    else:
        text = f"{value:.{decimals}f}"
    return f"{text} {unit}".strip()


def _cz_diagnostics_lines(item):
    """Return compact Czechia diagnostics for the text tile in the combined figure."""
    cz = _get_nested(item, ["features", "regions", "czechia"], {}) or {}
    return [
        "Czechia diagnostics",
        f"T850 mean/max: {_fmt_metric(_get_nested(cz, ['t850_c', 'mean']), '°C')} / {_fmt_metric(_get_nested(cz, ['t850_c', 'max']), '°C')}",
        f"MSLP mean: {_fmt_metric(_get_nested(cz, ['mslp_hpa', 'mean']), 'hPa')}",
        f"PWAT max: {_fmt_metric(_get_nested(cz, ['pwat_mm', 'max']), 'mm')}",
        f"CAPE max: {_fmt_metric(_get_nested(cz, ['cape_jkg', 'max']), 'J/kg', 0)}",
        f"CIN mean: {_fmt_metric(_get_nested(cz, ['cin_jkg', 'mean']), 'J/kg')}",
        f"Precip max: {_fmt_metric(_get_nested(cz, ['precip_mm', 'max']), 'mm')}",
        f"Cum. precip max: {_fmt_metric(_get_nested(cz, ['precip_accum_total_mm', 'max']), 'mm')}",
        f"Jet250 max: {_fmt_metric(_get_nested(cz, ['jet250_speed_ms', 'max']), 'm/s')}",
    ]


def _load_font(size, bold=False):
    """Load a common system font without bundling fonts into the project."""
    from PIL import ImageFont

    candidates = []
    if bold:
        candidates.extend([
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
        ])
    candidates.extend([
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ])
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size=size)
        except Exception:
            continue
    return ImageFont.load_default()


def _fit_image(src_path, tile_size):
    from PIL import Image

    img = Image.open(src_path).convert("RGB")
    img.thumbnail(tile_size, Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", tile_size, "white")
    x = (tile_size[0] - img.width) // 2
    y = (tile_size[1] - img.height) // 2
    canvas.paste(img, (x, y))
    return canvas


def _make_precip_pair_tile(period_src, accum_src, tile_size):
    """Create one combined precipitation tile from two separate map products.

    Individual maps remain available in maps/. This tile is used only inside
    combined_overview_*.png so the AI sees period precipitation and cumulative
    precipitation side by side for the same forecast hour.
    """
    from PIL import Image, ImageDraw

    tile_w, tile_h = tile_size
    label_h = 44
    gap = 12
    half_w = (tile_w - gap) // 2
    img_h = tile_h - label_h

    canvas = Image.new("RGB", tile_size, "white")
    draw = ImageDraw.Draw(canvas)
    label_font = _load_font(28, bold=True)

    draw.text((8, 6), "Period precipitation", fill=(20, 20, 20), font=label_font)
    draw.text((half_w + gap + 8, 6), "Cumulative from +0 h", fill=(20, 20, 20), font=label_font)

    def paste_fit(src, x0):
        if not src:
            return
        src = Path(src)
        if not src.exists():
            return
        img = Image.open(src).convert("RGB")
        img.thumbnail((half_w, img_h), Image.Resampling.LANCZOS)
        x = x0 + (half_w - img.width) // 2
        y = label_h + (img_h - img.height) // 2
        canvas.paste(img, (x, y))

    paste_fit(period_src, 0)
    paste_fit(accum_src, half_w + gap)

    return canvas


def _make_text_tile(lines, tile_size):
    from PIL import Image, ImageDraw

    tile = Image.new("RGB", tile_size, "white")
    draw = ImageDraw.Draw(tile)
    title_font = _load_font(44, bold=True)
    text_font = _load_font(34)
    small_font = _load_font(28)

    x = 58
    y = 60
    draw.text((x, y), lines[0], fill=(20, 20, 20), font=title_font)
    y += 84
    for line in lines[1:]:
        draw.text((x, y), line, fill=(35, 35, 35), font=text_font)
        y += 56

    note = "Use maps for spatial interpretation; use JSON for exact values."
    draw.text((x, tile_size[1] - 90), note, fill=(80, 80, 80), font=small_font)
    return tile


def create_combined_figures(timesteps, output_dir):
    """Create one AI-friendly overview PNG per forecast hour.

    The original individual maps remain in maps/. These combined figures are
    designed for multimodal AI/API use: one image contains all key layers for a
    single valid time plus compact Czechia diagnostics.
    """
    from PIL import Image, ImageDraw

    combined_dir = output_dir / COMBINED_FIGURE_DIRNAME
    combined_dir.mkdir(parents=True, exist_ok=True)

    tile_w, tile_h = COMBINED_TILE_SIZE
    cols = 2
    rows = 4
    width = COMBINED_MARGIN * 2 + cols * tile_w + (cols - 1) * COMBINED_GAP
    height = (
        COMBINED_MARGIN * 2
        + COMBINED_HEADER_HEIGHT
        + rows * (COMBINED_LABEL_HEIGHT + tile_h)
        + (rows - 1) * COMBINED_GAP
    )

    title_font = _load_font(42, bold=True)
    label_font = _load_font(30, bold=True)
    manifest = []

    for item in timesteps:
        canvas = Image.new("RGB", (width, height), "white")
        draw = ImageDraw.Draw(canvas)
        fxx = item["forecast_hour"]
        valid = item["valid_time"]
        title = f"GFS combined synoptic overview | +{fxx} h | valid {valid} UTC"
        draw.text((COMBINED_MARGIN, COMBINED_MARGIN), title, fill=(15, 15, 15), font=title_font)

        panels = []
        for key, label in COMBINED_MAP_LAYOUT:
            if key == "precip_pair":
                period_rel = item.get("maps", {}).get("precip")
                accum_rel = item.get("maps", {}).get("precip_accum")
                if period_rel or accum_rel:
                    period_src = output_dir / period_rel if period_rel else None
                    accum_src = output_dir / accum_rel if accum_rel else None
                    panels.append((
                        label,
                        _make_precip_pair_tile(period_src, accum_src, COMBINED_TILE_SIZE),
                    ))
                continue

            rel = item.get("maps", {}).get(key)
            if not rel:
                continue
            src = output_dir / rel
            if src.exists():
                panels.append((label, _fit_image(src, COMBINED_TILE_SIZE)))
        panels.append(("Czechia key diagnostics", _make_text_tile(_cz_diagnostics_lines(item), COMBINED_TILE_SIZE)))

        for idx, (label, panel) in enumerate(panels[: cols * rows]):
            row = idx // cols
            col = idx % cols
            x = COMBINED_MARGIN + col * (tile_w + COMBINED_GAP)
            y = COMBINED_MARGIN + COMBINED_HEADER_HEIGHT + row * (COMBINED_LABEL_HEIGHT + tile_h + COMBINED_GAP)
            draw.text((x, y), label, fill=(20, 20, 20), font=label_font)
            canvas.paste(panel, (x, y + COMBINED_LABEL_HEIGHT))

        out_name = f"combined_overview_f{int(fxx):03d}_{safe_time_id(valid)}.png"
        out_path = combined_dir / out_name
        canvas.save(out_path, optimize=True)
        rel = Path(COMBINED_FIGURE_DIRNAME) / out_name
        item["combined_figure"] = rel.as_posix()
        manifest.append({
            "forecast_hour": fxx,
            "valid_time": valid,
            "type": "combined_overview",
            "file": rel.as_posix(),
            "contains": ["mslp_wind", "z500_t850", "t850", "pwat", "cape_cin", "jet250", "precip", "precip_accum", "czechia_diagnostics"],
        })

    return manifest


def strip_paths_for_json(timesteps):
    cleaned = []
    for item in timesteps:
        cleaned.append({
            "forecast_hour": item["forecast_hour"],
            "valid_time": item["valid_time"],
            "source_files": item["source_files"],
            "features": item["features"],
            "synoptic_features": item["synoptic_features"],
            "assessment": item["assessment"],
            "commentary": item["commentary"],
            "precip_accum": item.get("precip_accum"),
            "maps": item["maps"],
            "combined_figure": item.get("combined_figure"),
        })
    return cleaned


def read_template_file(filename, fallback=None):
    path = TEMPLATES_DIR / filename
    if path.exists():
        return path.read_text(encoding="utf-8")
    if fallback is not None:
        return fallback
    return None


def default_start_here():
    return """# START_HERE – hlavní pokyny pro AI

Pokud jsi AI systém a obdržel jsi tento ZIP, tvým úkolem je vytvořit profesionální český synoptický report ve formátu DOCX.

Nečekej na další dlouhé zadání od uživatele. Tento balíček už obsahuje všechna data, mapy a instrukce potřebné pro vytvoření reportu.

## Postup

1. Přečti tento soubor.
2. Přečti `REPORT_INSTRUCTIONS.md`.
3. Přečti `AI_REPORT_SPECIFICATION_FINAL.md`.
4. Přečti `style_guide.md`.
5. Použij `briefing_template.md` jako požadovanou strukturu.
6. Použij `briefing_context.json` pro hodnoty, trendy a objektivní charakteristiky.
7. Použij `combined_figures_manifest.json` a složku `combined_figures/` jako hlavní vizuální přehled pro každý prognostický termín.
8. Použij `maps_manifest.json` a složku `maps/` jako detailní přílohu a zdroj jednotlivých vrstev.
9. Vytvoř výsledný dokument DOCX.

## Povinné zásady

- Report musí hodnotit celou Evropu i Českou republiku.
- Report musí analyzovat všechny dostupné prognostické termíny, nikoliv pouze +0 h.
- Primárně používej kombinované obrázky ze složky `combined_figures/`, protože shrnují všechny klíčové vrstvy pro jeden prognostický termín.
- Jednotlivé mapy ze složky `maps/` používej selektivně tam, kde je potřeba detailní důkazní materiál.
- Ke každému vloženému kombinovanému obrázku přidej odborný komentář, ale komentáře se nesmí šablonovitě opakovat.
- Report musí vysvětlovat meteorologické mechanismy, nikoliv pouze popisovat pole.
- Report musí uvádět významné anomálie, extrémy a rizika nad Evropou i dopady na Českou republiku.
- Nepoužívej anglické názvy kapitol.
- Nezmiňuj AI balíček, JSON soubory, manifesty ani interní strukturu vstupů v samotném reportu.
- Piš jako synoptický meteorolog, ne jako technický systém.

## Výstup

Výstupem má být profesionální report DOCX s mapami a českými nadpisy.
"""


def default_readme(context):
    return f"""# Podklady pro synoptický report

Tento balíček je určen pro vytvoření profesionálního českého synoptického reportu.

Model: {context['model']}  
Běh modelu: {context['run_time']} UTC  
Počet prognostických termínů: {len(context['timesteps'])}  
Doména: Evropa  
Zaměření: Evropa a Česká republika

## Hlavní soubor pro AI

Začni souborem:

`START_HERE.md`

Ten obsahuje jednoznačné pokyny, co má AI udělat.

## Datové zdroje v balíčku

- `briefing_context.json` – strukturované hodnoty, trendy a meteorologické charakteristiky.
- `combined_figures_manifest.json` – seznam kombinovaných přehledových obrázků po prognostických termínech.
- `combined_figures/` – hlavní AI-friendly obrázky; každý obsahuje všechny klíčové vrstvy pro jeden termín.
- `maps_manifest.json` – seznam všech jednotlivých map.
- `maps/` – detailní mapové podklady včetně dynamiky, vlhkosti a konvekce.
- `AI_REPORT_SPECIFICATION_FINAL.md` – detailní specifikace reportu.
- `REPORT_INSTRUCTIONS.md` – provozní pokyny pro vytvoření reportu.
- `style_guide.md` – jazyk a styl.
- `briefing_template.md` – požadovaná struktura dokumentu.
- `metadata.json` – metadata výstupu.

## Důležité

Ve výsledném reportu nezmiňuj tento balíček, JSON soubory, manifesty ani technické instrukční soubory. Tyto soubory slouží pouze jako interní podklady pro tvorbu reportu.
"""


def write_template_files(output_dir, context, priority):
    """Copy every file from PROJECT_ROOT/templates into the AI package.

    This intentionally copies both text templates and binary reference files such
    as sample_report.pdf or sample_report.docx. Updating templates/ therefore
    automatically updates all future AI ZIP packages.

    Built-in fallbacks are written only for the core instruction files when they
    are missing, so the pipeline remains functional.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    fallback_metadata = {
        "report_spec_version": "2.1",
        "language": "cs",
        "output": "docx",
        "audience": "meteorologists",
        "focus": ["Europe", "Czech Republic"],
        "include_maps": True,
        "include_combined_figures": True,
        "include_all_maps": True,
        "analyse_all_forecast_hours": True,
        "explain_mechanisms": True,
        "include_extremes": True,
        "include_anomalies": True,
        "include_impacts": True,
        "mention_ai_package_in_report": False,
        "minimum_quality_reference": "sample_report.pdf",
        "herbie_priority": parse_priority(priority),
    }

    fallbacks = {
        "START_HERE.md": default_start_here(),
        "README.md": default_readme(context),
        "AI_REPORT_SPECIFICATION_FINAL.md": AI_REPORT_SPECIFICATION,
        "REPORT_INSTRUCTIONS.md": REPORT_INSTRUCTIONS,
        "style_guide.md": STYLE_GUIDE,
        "briefing_template.md": BRIEFING_TEMPLATE,
        "prompt.md": PROMPT,
        "metadata.json": json.dumps(fallback_metadata, indent=2, ensure_ascii=False),
    }

    copied = set()

    if TEMPLATES_DIR.exists():
        for src in sorted(TEMPLATES_DIR.rglob("*")):
            if not src.is_file():
                continue

            rel = src.relative_to(TEMPLATES_DIR)
            dst = output_dir / rel
            dst.parent.mkdir(parents=True, exist_ok=True)

            # Text templates can be enriched or normalized.
            if src.suffix.lower() in TEXT_TEMPLATE_SUFFIXES:
                text = src.read_text(encoding="utf-8")

                if rel.as_posix() == "metadata.json":
                    try:
                        metadata = json.loads(text)
                        metadata.setdefault("report_spec_version", "2.1")
                        metadata.setdefault("language", "cs")
                        metadata.setdefault("output", "docx")
                        metadata.setdefault("audience", "meteorologists")
                        metadata.setdefault("focus", ["Europe", "Czech Republic"])
                        metadata.setdefault("include_maps", True)
                        metadata.setdefault("include_combined_figures", True)
                        metadata.setdefault("include_all_maps", True)
                        metadata.setdefault("analyse_all_forecast_hours", True)
                        metadata.setdefault("explain_mechanisms", True)
                        metadata.setdefault("include_extremes", True)
                        metadata.setdefault("include_anomalies", True)
                        metadata.setdefault("include_impacts", True)
                        metadata.setdefault("mention_ai_package_in_report", False)
                        metadata.setdefault("minimum_quality_reference", "sample_report.pdf")
                        metadata["model"] = context["model"]
                        metadata["run_time"] = context["run_time"]
                        metadata["domain"] = context["domain"]
                        metadata["focus_region"] = context["focus_region"]
                        metadata["forecast_hours"] = [
                            item["forecast_hour"] for item in context["timesteps"]
                        ]
                        metadata["herbie_priority"] = parse_priority(priority)
                        text = json.dumps(metadata, indent=2, ensure_ascii=False)
                    except json.JSONDecodeError:
                        pass

                dst.write_text(text, encoding="utf-8")
            else:
                # Binary/reference files, for example sample_report.pdf/docx.
                shutil.copy2(src, dst)

            copied.add(rel.as_posix())

    # Ensure core instruction files exist even if templates/ is incomplete.
    for filename in TEMPLATE_FILES:
        if filename in copied:
            continue
        text = fallbacks.get(filename)
        if text is not None:
            (output_dir / filename).write_text(text, encoding="utf-8")
            copied.add(filename)

    if "sample_report.pdf" not in copied and "sample_report.docx" not in copied:
        print(
            "Warning: no sample_report.pdf or sample_report.docx found in templates/. "
            "The AI package will still work, but without a visual quality reference."
        )

    if not copied:
        raise RuntimeError("No AI report templates were written to the package.")

def zip_directory(output_dir):
    zip_path = output_dir.with_suffix(".zip")
    if zip_path.exists():
        zip_path.unlink()

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(output_dir.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(output_dir.parent))

    return zip_path


def main():
    args = parse_args()
    package_id = run_id(args.run)
    output_dir = AI_INPUTS_DIR / package_id
    output_maps_dir = output_dir / "maps"

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    timesteps = collect_timesteps(args.run)
    if not timesteps:
        raise FileNotFoundError(f"No timesteps found for run {args.run}")

    manifest = copy_maps(timesteps, output_maps_dir)
    combined_manifest = create_combined_figures(timesteps, output_dir)

    context = {
        "model": "GFS",
        "run_time": args.run,
        "domain": "Europe",
        "focus_region": "Česká republika",
        "purpose": "Podklady pro časový synoptický briefing s mapami",
        "timesteps": strip_paths_for_json(timesteps),
    }

    (output_dir / "briefing_context.json").write_text(
        json.dumps(context, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (output_dir / "maps_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (output_dir / "combined_figures_manifest.json").write_text(
        json.dumps(combined_manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    write_template_files(output_dir, context, args.priority)
    zip_path = zip_directory(output_dir)

    print(f"Saved AI briefing input package: {output_dir}")
    print(f"Saved ZIP package: {zip_path}")


if __name__ == "__main__":
    main()
