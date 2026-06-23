from pathlib import Path
import argparse
import json

from utils import add_model_run_args, resolve_run_time, REPORTS_DIR, MAPS_DIR, PROJECT_ROOT


# Output directories are defined relative to the project root in utils.py


def load_json(prefix, run_time=None, fxx=None):
    files = sorted(REPORTS_DIR.glob(f"{prefix}_*.json"))

    if not files:
        raise FileNotFoundError(f"No {prefix}_*.json file found in reports/.")

    matches = []
    for file in files:
        with open(file, "r", encoding="utf-8") as f:
            data = json.load(f)

        if run_time is not None and data.get("run_time") != run_time:
            continue
        if fxx is not None and data.get("forecast_hour") != fxx:
            continue

        matches.append((file, data))

    if not matches:
        raise FileNotFoundError(
            f"No {prefix}_*.json matching run={run_time!r}, fxx={fxx!r}."
        )

    return matches[-1]


def parse_args():
    parser = argparse.ArgumentParser()
    add_model_run_args(parser)
    return parser.parse_args()


def find_map(prefix, valid_time=None):
    if valid_time is not None:
        target = MAPS_DIR / f"{prefix}_{valid_time.replace(':', '-')}.png"
        if target.exists():
            return target

    files = sorted(MAPS_DIR.glob(f"{prefix}_*.png"))
    return files[-1] if files else None


def relpath(path):
    if not path:
        return "nenalezena"

    path = Path(path)
    try:
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def fmt_point(item, unit):
    return (
        f"{item['value']:.1f} {unit} "
        f"({item['lat']:.1f}°N, {item['lon']:.1f}°E)"
    )


def fmt_points(items, unit):
    if not items:
        return "- Nenalezeno"

    return "\n".join(f"- {fmt_point(item, unit)}" for item in items)


def fmt_assessment_section(title, lines):
    if not lines:
        body = "- Bez dostupného hodnocení"
    else:
        body = "\n".join(f"- {line}" for line in lines)

    return f"### {title}\n\n{body}"


def fmt_lines(lines):
    if not lines:
        return "- Bez dostupných položek"
    return "\n".join(f"- {line}" for line in lines)


def fmt_commentary(commentary):
    if not commentary:
        return "Komentář není dostupný."

    classification = commentary.get("classification", {})
    summary = commentary.get("summary", [])
    trends = commentary.get("trends", [])
    regional_summary = commentary.get("regional_summary", [])
    czechia_summary = commentary.get("czechia_summary", [])
    hazards = commentary.get("hazards", [])
    confidence = commentary.get("confidence", "neuvedena")

    return f"""### Celkové zhodnocení

{chr(10).join(summary) if summary else "Bez dostupného shrnutí."}

### Klasifikace režimu

- Synoptický typ: {classification.get("synoptic_type", "neuveden")}
- Charakter proudění: {classification.get("flow_type", "neuveden")}
- Teplotní režim: {classification.get("weather_regime", "neuveden")}
- Spolehlivost pravidlové interpretace: {confidence}

### Trend oproti předchozímu termínu

{fmt_lines(trends)}

### Regionální poznámky

{fmt_lines(regional_summary)}

### Zaměření na Českou republiku

{fmt_lines(czechia_summary)}

### Hlavní signály / rizika

{fmt_lines(hazards)}
"""


def fmt_stat(stats, key, unit):
    region = stats.get(key, {}) if stats else {}
    if not region or region.get("mean") is None:
        return "není dostupné"
    return f"min {region['min']:.1f} {unit}, průměr {region['mean']:.1f} {unit}, max {region['max']:.1f} {unit}"


def fmt_czechia_values(data):
    cz = data.get("regions", {}).get("czechia")
    if not cz:
        return "- Regionální statistika pro ČR není dostupná."

    t850 = cz.get("t850_c", {})
    precip = cz.get("precip_mm", {})
    pwat = cz.get("pwat_mm", {})
    cape = cz.get("cape_jkg", {})
    cin = cz.get("cin_jkg", {})
    jet250 = cz.get("jet250_speed_ms", {})
    t850_area = t850.get("area_fraction_percent", {})
    precip_area = precip.get("area_fraction_percent", {})
    pwat_area = pwat.get("area_fraction_percent", {})
    cape_area = cape.get("area_fraction_percent", {})
    cin_area = cin.get("area_fraction_percent", {})

    return (
        f"- T850: {fmt_stat(cz, 't850_c', '°C')}\n"
        f"- MSLP: {fmt_stat(cz, 'mslp_hpa', 'hPa')}\n"
        f"- Z500: {fmt_stat(cz, 'z500_dam', 'dam')}\n"
        f"- Srážky: {fmt_stat(cz, 'precip_mm', 'mm')}\n"
        f"- PWAT: {fmt_stat(cz, 'pwat_mm', 'mm')}\n"
        f"- CAPE: {fmt_stat(cz, 'cape_jkg', 'J/kg')}\n"
        f"- CIN: {fmt_stat(cz, 'cin_jkg', 'J/kg')}\n"
        f"- Jet 250 hPa: {fmt_stat(cz, 'jet250_speed_ms', 'm/s')}\n"
        f"- Podíl ČR s T850 ≥ 15 °C: {t850_area.get('ge_15c', 0.0):.1f} %\n"
        f"- Podíl ČR s T850 ≥ 20 °C: {t850_area.get('ge_20c', 0.0):.1f} %\n"
        f"- Podíl ČR se srážkami ≥ 1 mm: {precip_area.get('ge_1mm', 0.0):.1f} %\n"
        f"- Podíl ČR se srážkami ≥ 10 mm: {precip_area.get('ge_10mm', 0.0):.1f} %\n"
        f"- Podíl ČR s PWAT ≥ 30 mm: {pwat_area.get('ge_30mm', 0.0):.1f} %\n"
        f"- Podíl ČR s PWAT ≥ 40 mm: {pwat_area.get('ge_40mm', 0.0):.1f} %\n"
        f"- Podíl ČR s CAPE ≥ 500 J/kg: {cape_area.get('ge_500jkg', 0.0):.1f} %\n"
        f"- Podíl ČR s CAPE ≥ 1000 J/kg: {cape_area.get('ge_1000jkg', 0.0):.1f} %\n"
        f"- Podíl ČR s CIN ≥ 50 J/kg: {cin_area.get('ge_50jkg', 0.0):.1f} %"
    )


def main():
    args = parse_args()
    run_filter = resolve_run_time(args.run) if args.run else None
    fxx_filter = args.fxx if args.run else None

    feature_file, data = load_json("features", run_filter, fxx_filter)
    synoptic_file, syn = load_json("synoptic_features", run_filter, fxx_filter)
    assessment_file, assessment = load_json("synoptic_assessment", run_filter, fxx_filter)

    try:
        commentary_file, commentary = load_json("synoptic_commentary", run_filter, fxx_filter)
    except FileNotFoundError:
        commentary_file, commentary = None, None

    valid_time = data["valid_time_utc"]
    run_time = data["run_time"]
    fxx = data["forecast_hour"]

    fields = data["fields"]
    derived = data["derived"]

    t850 = fields["t850_c"]
    z500 = fields["z500_dam"]
    mslp = fields["mslp_hpa"]
    precip = fields["precip_mm"]
    pwat = fields.get("pwat_mm")
    cape = fields.get("cape_jkg")
    cin = fields.get("cin_jkg")
    jet250 = fields.get("jet250_speed_ms")

    syn_features = syn["features"]
    pressure = syn_features["pressure_systems"]
    upper = syn_features["upper_air"]
    air_mass = syn_features["air_mass"]
    precipitation = syn_features["precipitation"]
    moisture = syn_features.get("moisture", {})
    convection = syn_features.get("convection", {})

    assessment_sections = assessment["assessment"]

    t850_map = find_map("t850_europe", valid_time)
    z500_t850_map = find_map("z500_t850_europe", valid_time)
    mslp_wind_map = find_map("mslp_wind_europe", valid_time)
    precip_map = find_map("precip_europe", valid_time)
    pwat_map = find_map("pwat_europe", valid_time)
    cape_cin_map = find_map("cape_cin_europe", valid_time)
    jet250_map = find_map("jet250_europe", valid_time)

    report = f"""# Ranní synoptický briefing – Evropa

**Model:** {data["model"]}  
**Běh modelu:** {run_time} UTC  
**Předpovědní krok:** +{fxx} h  
**Validita:** {valid_time} UTC  

**Zdroj objektivních charakteristik:** `{feature_file.as_posix()}`  
**Zdroj detekovaných synoptických prvků:** `{synoptic_file.as_posix()}`  
**Zdroj pravidlového synoptického hodnocení:** `{assessment_file.as_posix()}`  
**Zdroj synoptického komentáře:** `{commentary_file.as_posix() if commentary_file else "nenalezen"}`

---

## 1. Synoptický komentář

{fmt_commentary(commentary)}

---

## 2. Pravidlové synoptické hodnocení

{fmt_assessment_section("Tlakové pole", assessment_sections.get("tlakové_pole", []))}

{fmt_assessment_section("Výškové pole", assessment_sections.get("výškové_pole", []))}

{fmt_assessment_section("Vzduchová hmota", assessment_sections.get("vzduchová_hmota", []))}

{fmt_assessment_section("Srážky", assessment_sections.get("srážky", []))}

{fmt_assessment_section("Konvekce", assessment_sections.get("konvekce", []))}

---

## 3. Objektivní přehled polí

### Teplota v hladině 850 hPa

- Minimum T850: {fmt_point(t850["min"], "°C")}
- Maximum T850: {fmt_point(t850["max"], "°C")}
- Rozsah T850 nad Evropou: {derived["t850_range_c"]:.1f} °C

### Geopotenciální výška v hladině 500 hPa

- Minimum Z500: {fmt_point(z500["min"], "dam")}
- Maximum Z500: {fmt_point(z500["max"], "dam")}

### Tlak redukovaný na hladinu moře

- Minimum MSLP: {fmt_point(mslp["min"], "hPa")}
- Maximum MSLP: {fmt_point(mslp["max"], "hPa")}
- Tlakový rozsah nad Evropou: {derived["mslp_range_hpa"]:.1f} hPa

### Srážky

- Maximum akumulovaných srážek: {fmt_point(precip["max"], "mm")}
- Plocha se srážkami nad 1 mm: {derived["precip_area_gt_1mm_percent"]:.1f} %
- Plocha se srážkami nad 10 mm: {derived["precip_area_gt_10mm_percent"]:.1f} %


### PWAT – srážková voda ve sloupci

- Maximum PWAT: {fmt_point(pwat["max"], "mm") if pwat else "není dostupné"}
- Plocha domény s PWAT nad 30 mm: {derived.get("pwat_area_gt_30mm_percent", 0.0):.1f} %
- Plocha domény s PWAT nad 40 mm: {derived.get("pwat_area_gt_40mm_percent", 0.0):.1f} %
- Plocha domény s PWAT nad 50 mm: {derived.get("pwat_area_gt_50mm_percent", 0.0):.1f} %

### CAPE a CIN – konvektivní potenciál

- Maximum CAPE: {fmt_point(cape["max"], "J/kg") if cape else "není dostupné"}
- Maximum CIN: {fmt_point(cin["max"], "J/kg") if cin else "není dostupné"}
- Plocha domény s CAPE nad 500 J/kg: {derived.get("cape_area_gt_500jkg_percent", 0.0):.1f} %
- Plocha domény s CAPE nad 1000 J/kg: {derived.get("cape_area_gt_1000jkg_percent", 0.0):.1f} %
- Plocha domény s CIN nad 50 J/kg: {derived.get("cin_area_gt_50jkg_percent", 0.0):.1f} %

### Jet stream 250 hPa

- Maximum rychlosti větru v hladině 250 hPa: {fmt_point(jet250["max"], "m/s") if jet250 else "není dostupné"}
- Plocha domény s větrem nad 35 m/s: {derived.get("jet250_area_gt_35ms_percent", 0.0):.1f} %
- Plocha domény s větrem nad 50 m/s: {derived.get("jet250_area_gt_50ms_percent", 0.0):.1f} %
- Plocha domény s větrem nad 60 m/s: {derived.get("jet250_area_gt_60ms_percent", 0.0):.1f} %

---

## 4. Detekované synoptické prvky

### Kandidáti tlakových níží

{fmt_points(pressure["lows_mslp_hpa"], "hPa")}

### Kandidáti tlakových výší

{fmt_points(pressure["highs_mslp_hpa"], "hPa")}

### Minimum Z500

{fmt_points(upper["z500_minima_dam"], "dam")}

### Maximum Z500

{fmt_points(upper["z500_maxima_dam"], "dam")}

### Teplá vzduchová hmota v 850 hPa

- Podíl domény s T850 ≥ 15 °C: {air_mass["area_t850_ge_15c_percent"]:.1f} %
- Podíl domény s T850 ≥ 20 °C: {air_mass["area_t850_ge_20c_percent"]:.1f} %

Kandidáti maxim T850:

{fmt_points(air_mass["t850_maxima_c"], "°C")}

### Srážková maxima

- Podíl domény se srážkami ≥ 1 mm: {precipitation["area_precip_ge_1mm_percent"]:.1f} %
- Podíl domény se srážkami ≥ 10 mm: {precipitation["area_precip_ge_10mm_percent"]:.1f} %

Kandidáti srážkových maxim:

{fmt_points(precipitation["precip_maxima_mm"], "mm")}

### Vlhkost atmosférického sloupce / PWAT

- Podíl domény s PWAT ≥ 30 mm: {moisture.get("area_pwat_ge_30mm_percent", 0.0):.1f} %
- Podíl domény s PWAT ≥ 40 mm: {moisture.get("area_pwat_ge_40mm_percent", 0.0):.1f} %
- Podíl domény s PWAT ≥ 50 mm: {moisture.get("area_pwat_ge_50mm_percent", 0.0):.1f} %
- Třída vlhkosti sloupce: {moisture.get("pwat_moisture_class", "neuvedena")}

Kandidáti maxim PWAT:

{fmt_points(moisture.get("pwat_maxima_mm", []), "mm")}

### Konvektivní potenciál / CAPE a CIN

- Podíl domény s CAPE ≥ 250 J/kg: {convection.get("area_cape_ge_250jkg_percent", 0.0):.1f} %
- Podíl domény s CAPE ≥ 500 J/kg: {convection.get("area_cape_ge_500jkg_percent", 0.0):.1f} %
- Podíl domény s CAPE ≥ 1000 J/kg: {convection.get("area_cape_ge_1000jkg_percent", 0.0):.1f} %
- Podíl domény s CIN ≥ 50 J/kg: {convection.get("area_cin_ge_50jkg_percent", 0.0):.1f} %
- Třída instability CAPE: {convection.get("cape_instability_class", "neuvedena")}
- Třída inhibice CIN: {convection.get("cin_inhibition_class", "neuvedena")}

Kandidáti maxim CAPE:

{fmt_points(convection.get("cape_maxima_jkg", []), "J/kg")}

Kandidáti maxim CIN:

{fmt_points(convection.get("cin_maxima_jkg", []), "J/kg")}

---

## 5. Zaměření na Českou republiku – objektivní hodnoty

{fmt_czechia_values(data)}

---

## 6. Mapové přílohy

### Z500 + T850

![Z500 + T850]({relpath(z500_t850_map)})

### T850

![T850]({relpath(t850_map)})

### Jet stream 250 hPa

![Jet 250 hPa]({relpath(jet250_map)})

### PWAT – srážková voda ve sloupci

![PWAT]({relpath(pwat_map)})

### CAPE a CIN

![CAPE + CIN]({relpath(cape_cin_map)})

### MSLP + 10 m wind speed

![MSLP + Wind]({relpath(mslp_wind_map)})

### Accumulated precipitation

![Precipitation]({relpath(precip_map)})

---

## 7. Omezení

- Report vychází pouze z jednoho deterministického běhu modelu GFS.
- Synoptické hodnocení i komentář jsou pravidlové, nikoli ruční analýza.
- Detekované útvary jsou algoritmické kandidáty.
- Neobsahuje srovnání s ensemblem.
- Frontální systémy nejsou explicitně analyzovány.
- Extrémy jsou počítány pouze v definované evropské doméně.
"""

    out_name = f"briefing_static_{valid_time.replace(':', '-')}.md"
    outfile = REPORTS_DIR / out_name

    with open(outfile, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"Saved: {outfile}")


if __name__ == "__main__":
    main()