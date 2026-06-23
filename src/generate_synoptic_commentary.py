from pathlib import Path
import argparse
import json
from datetime import datetime

from utils import add_model_run_args, resolve_run_time, REPORTS_DIR


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


def find_previous_json(prefix, run_time, current_fxx):
    files = sorted(REPORTS_DIR.glob(f"{prefix}_*.json"))
    candidates = []

    for file in files:
        with open(file, "r", encoding="utf-8") as f:
            data = json.load(f)

        if data.get("run_time") != run_time:
            continue

        fxx = data.get("forecast_hour")
        if fxx is None or int(fxx) >= int(current_fxx):
            continue

        candidates.append((int(fxx), file, data))

    if not candidates:
        return None, None

    _, file, data = sorted(candidates, key=lambda item: item[0])[-1]
    return file, data


def parse_args():
    parser = argparse.ArgumentParser()
    add_model_run_args(parser)
    return parser.parse_args()


def first(items):
    return items[0] if items else None


def point_text(point, unit):
    if not point:
        return "není dostupné"
    return f"{point['value']:.1f} {unit} ({point['lat']:.1f}°N, {point['lon']:.1f}°E)"


def value_trend(current, previous, unit="", decimals=1):
    if current is None or previous is None:
        return None

    delta = current - previous
    sign = "+" if delta > 0 else ""
    return f"{current:.{decimals}f} {unit} ({sign}{delta:.{decimals}f} {unit} oproti předchozímu termínu)"



def czechia_stats(features):
    return features.get("regions", {}).get("czechia", {})


def stat_text(stats, key, unit):
    item = stats.get(key, {}) if stats else {}
    if not item or item.get("mean") is None:
        return "není dostupné"
    return f"min {item['min']:.1f} {unit}, průměr {item['mean']:.1f} {unit}, max {item['max']:.1f} {unit}"


def build_czechia_summary(features, synoptic):
    cz = czechia_stats(features)
    if not cz:
        return ["Regionální statistika pro Českou republiku není v tomto výstupu dostupná."]

    t850 = cz.get("t850_c", {})
    mslp = cz.get("mslp_hpa", {})
    precip = cz.get("precip_mm", {})
    pwat = cz.get("pwat_mm", {})
    cape = cz.get("cape_jkg", {})
    cin = cz.get("cin_jkg", {})
    z500 = cz.get("z500_dam", {})
    jet250 = cz.get("jet250_speed_ms", {})

    lines = [
        f"Česká republika: T850 {stat_text(cz, 't850_c', '°C')}.",
        f"Česká republika: MSLP {stat_text(cz, 'mslp_hpa', 'hPa')}, Z500 {stat_text(cz, 'z500_dam', 'dam')}.",
        f"Česká republika: akumulované srážky {stat_text(cz, 'precip_mm', 'mm')}.",
        f"Česká republika: PWAT / srážková voda ve sloupci {stat_text(cz, 'pwat_mm', 'mm')}.",
        f"Česká republika: CAPE {stat_text(cz, 'cape_jkg', 'J/kg')}, CIN {stat_text(cz, 'cin_jkg', 'J/kg')}.",
        f"Česká republika: rychlost větru v hladině 250 hPa {stat_text(cz, 'jet250_speed_ms', 'm/s')}.",
    ]

    area20 = t850.get("area_fraction_percent", {}).get("ge_20c")
    area15 = t850.get("area_fraction_percent", {}).get("ge_15c")
    precip10 = precip.get("area_fraction_percent", {}).get("ge_10mm")
    precip1 = precip.get("area_fraction_percent", {}).get("ge_1mm")
    pwat40 = pwat.get("area_fraction_percent", {}).get("ge_40mm")
    pwat30 = pwat.get("area_fraction_percent", {}).get("ge_30mm")
    cape500 = cape.get("area_fraction_percent", {}).get("ge_500jkg")
    cape1000 = cape.get("area_fraction_percent", {}).get("ge_1000jkg")
    cin50 = cin.get("area_fraction_percent", {}).get("ge_50jkg")

    if area20 is not None:
        if area20 >= 50:
            lines.append(f"V ČR zasahuje velmi teplá vzduchová hmota plošně; T850 ≥ 20 °C pokrývá {area20:.1f} % regionu.")
        elif area20 >= 10:
            lines.append(f"V ČR se velmi teplá vzduchová hmota uplatňuje regionálně; T850 ≥ 20 °C pokrývá {area20:.1f} % regionu.")
        elif area15 is not None and area15 >= 50:
            lines.append(f"V ČR je patrná teplá vzduchová hmota; T850 ≥ 15 °C pokrývá {area15:.1f} % regionu.")
        else:
            lines.append("V ČR není podle T850 pole plošně výrazná velmi teplá vzduchová hmota.")

    if pwat40 is not None:
        if pwat40 >= 20:
            lines.append(f"Atmosférický sloupec nad ČR je výrazně vlhký; PWAT ≥ 40 mm pokrývá {pwat40:.1f} % regionu, což zvyšuje potenciál intenzivních srážek při vhodném výstupném mechanismu.")
        elif pwat30 is not None and pwat30 >= 20:
            lines.append(f"Nad ČR je k dispozici zvýšená vlhkost atmosférického sloupce; PWAT ≥ 30 mm pokrývá {pwat30:.1f} % regionu.")

    if cape500 is not None:
        if cape1000 is not None and cape1000 >= 20:
            lines.append(f"V ČR je výraznější konvektivní energie; CAPE ≥ 1000 J/kg pokrývá {cape1000:.1f} % regionu.")
        elif cape500 >= 20:
            lines.append(f"V ČR je zvýšený konvektivní potenciál; CAPE ≥ 500 J/kg pokrývá {cape500:.1f} % regionu.")

    if cin50 is not None and cin50 >= 20:
        lines.append(f"Zároveň je patrná konvektivní inhibice; CIN ≥ 50 J/kg pokrývá {cin50:.1f} % regionu, což může omezovat spuštění bouřek bez dostatečného výstupného mechanismu.")

    if precip10 is not None:
        if precip10 >= 20:
            lines.append(f"Srážkový signál pro ČR je výraznější; srážky ≥ 10 mm pokrývají {precip10:.1f} % regionu.")
        elif precip1 is not None and precip1 >= 20:
            lines.append(f"Srážky v ČR jsou spíše plošnější, většinou však bez rozsáhlých vyšších úhrnů; ≥ 1 mm pokrývá {precip1:.1f} % regionu.")
        else:
            lines.append("Srážkový signál pro ČR je podle akumulace plošně omezený.")

    return lines


def classify_synoptic_type(features, synoptic):
    fields = features["fields"]
    derived = features["derived"]
    syn = synoptic["features"]

    z500_max = fields["z500_dam"]["max"]["value"]
    z500_min = fields["z500_dam"]["min"]["value"]
    mslp_max = fields["mslp_hpa"]["max"]["value"]
    mslp_min = fields["mslp_hpa"]["min"]["value"]
    area20 = syn["air_mass"]["area_t850_ge_20c_percent"]
    area15 = syn["air_mass"]["area_t850_ge_15c_percent"]
    jetmax = first(syn.get("upper_air", {}).get("jet250_maxima_ms", []))
    capemax = first(syn.get("convection", {}).get("cape_maxima_jkg", []))

    if z500_max >= 594 and mslp_max >= 1025:
        synoptic_type = "výrazný anticyklonální hřeben / blokující výše"
    elif z500_max >= 588 and mslp_max >= 1020:
        synoptic_type = "anticyklonální hřeben nad částí Evropy"
    elif z500_min <= 540 and mslp_min <= 995:
        synoptic_type = "cyklonální situace se severní až severozápadní níží"
    else:
        synoptic_type = "smíšené pole bez jednoznačné dominantní klasifikace"

    if area20 >= 20:
        weather_regime = "rozsáhlá velmi teplá epizoda"
    elif area20 >= 8:
        weather_regime = "regionálně velmi teplý režim"
    elif area15 >= 25:
        weather_regime = "teplý režim v jižní a střední části domény"
    else:
        weather_regime = "teplotně méně výrazný režim"

    if derived["mslp_range_hpa"] >= 35:
        flow_type = "zesílený tlakový gradient mezi severem a středem/jihovýchodem Evropy"
    elif z500_max - z500_min >= 55:
        flow_type = "výrazně meridionální výškové proudění"
    else:
        flow_type = "slabší až střední synoptický gradient"

    return {
        "synoptic_type": synoptic_type,
        "weather_regime": weather_regime,
        "flow_type": flow_type,
        "signals": {
            "z500_max_dam": round(z500_max, 1),
            "z500_min_dam": round(z500_min, 1),
            "mslp_max_hpa": round(mslp_max, 1),
            "mslp_min_hpa": round(mslp_min, 1),
            "t850_ge_20c_percent": round(area20, 1),
        },
    }


def detect_hazards(features, synoptic):
    syn = synoptic["features"]
    hazards = []

    area20 = syn["air_mass"]["area_t850_ge_20c_percent"]
    t850_max = first(syn["air_mass"]["t850_maxima_c"])
    precip_max = first(syn["precipitation"]["precip_maxima_mm"])
    area_p10 = syn["precipitation"]["area_precip_ge_10mm_percent"]
    moisture = syn.get("moisture", {})
    convection = syn.get("convection", {})
    pwat_max = first(moisture.get("pwat_maxima_mm", []))
    cape_max = first(convection.get("cape_maxima_jkg", []))
    cin_max = first(convection.get("cin_maxima_jkg", []))
    area_pwat40 = moisture.get("area_pwat_ge_40mm_percent", 0.0)
    area_cape500 = convection.get("area_cape_ge_500jkg_percent", 0.0)
    area_cape1000 = convection.get("area_cape_ge_1000jkg_percent", 0.0)
    mslp_range = features["derived"]["mslp_range_hpa"]

    if t850_max and t850_max["value"] >= 28:
        hazards.append("horká vzduchová hmota v jižní až jihozápadní části domény")
    elif area20 >= 10:
        hazards.append("regionálně velmi teplá vzduchová hmota")

    if pwat_max and pwat_max["value"] >= 50:
        hazards.append("extrémně vlhký atmosférický sloupec s vysokým potenciálem přívalových srážek při iniciaci konvekce")
    elif pwat_max and pwat_max["value"] >= 40 or area_pwat40 >= 5:
        hazards.append("výrazně vlhký atmosférický sloupec podporující vyšší srážkovou účinnost")

    if cape_max and cape_max["value"] >= 1500 and pwat_max and pwat_max["value"] >= 35:
        hazards.append("kombinace výrazného CAPE a vlhkého sloupce podporuje silnější konvekci při překonání inhibice")
    elif area_cape1000 >= 5 or area_cape500 >= 10:
        hazards.append("zvýšený konvektivní potenciál v části domény")

    if cin_max and cin_max["value"] >= 100:
        hazards.append("výraznější CIN může lokálně potlačovat iniciaci konvekce")

    if precip_max and precip_max["value"] >= 30:
        hazards.append("lokálně vydatné srážky / potenciálně konvektivní maxima")
    elif precip_max and precip_max["value"] >= 15:
        hazards.append("lokálně významnější srážky")

    if area_p10 >= 1:
        hazards.append("plošněji zastoupené srážky nad 10 mm v části domény")

    if mslp_range >= 35:
        hazards.append("zesílený tlakový gradient hlavně v severní části Evropy")

    if not hazards:
        hazards.append("bez výrazného plošného rizika v dostupných polích")

    return hazards


def build_trends(features, synoptic, previous_features, previous_synoptic):
    if previous_features is None or previous_synoptic is None:
        return ["Pro tento běh není k dispozici předchozí termín pro trendové srovnání."]

    current_syn = synoptic["features"]
    previous_syn = previous_synoptic["features"]

    trends = []

    current_area20 = current_syn["air_mass"]["area_t850_ge_20c_percent"]
    previous_area20 = previous_syn["air_mass"]["area_t850_ge_20c_percent"]
    trends.append(
        "Podíl domény s T850 ≥ 20 °C: "
        + value_trend(current_area20, previous_area20, "%", 1)
        + "."
    )

    current_mslp_max = features["fields"]["mslp_hpa"]["max"]["value"]
    previous_mslp_max = previous_features["fields"]["mslp_hpa"]["max"]["value"]
    trends.append(
        "Maximum MSLP: "
        + value_trend(current_mslp_max, previous_mslp_max, "hPa", 1)
        + "."
    )

    current_z500_max = features["fields"]["z500_dam"]["max"]["value"]
    previous_z500_max = previous_features["fields"]["z500_dam"]["max"]["value"]
    trends.append(
        "Maximum Z500: "
        + value_trend(current_z500_max, previous_z500_max, "dam", 1)
        + "."
    )

    current_cape_max = features.get("fields", {}).get("cape_jkg", {}).get("max", {}).get("value")
    previous_cape_max = previous_features.get("fields", {}).get("cape_jkg", {}).get("max", {}).get("value")
    if current_cape_max is not None and previous_cape_max is not None:
        trends.append(
            "Maximum CAPE: "
            + value_trend(current_cape_max, previous_cape_max, "J/kg", 0)
            + "."
        )

    current_precip_max = features["fields"]["precip_mm"]["max"]["value"]
    previous_precip_max = previous_features["fields"]["precip_mm"]["max"]["value"]
    trends.append(
        "Maximum akumulovaných srážek: "
        + value_trend(current_precip_max, previous_precip_max, "mm", 1)
        + "."
    )

    return trends


def build_regional_summary(synoptic):
    syn = synoptic["features"]
    tmax = first(syn["air_mass"]["t850_maxima_c"])
    pmax = first(syn["precipitation"]["precip_maxima_mm"])
    jetmax = first(syn.get("upper_air", {}).get("jet250_maxima_ms", []))
    capemax = first(syn.get("convection", {}).get("cape_maxima_jkg", []))
    low = first(syn["pressure_systems"]["lows_mslp_hpa"])
    high = first(syn["pressure_systems"]["highs_mslp_hpa"])

    lines = []

    if high:
        lines.append(
            f"Anticyklonální centrum / hřeben je nejvýraznější v okolí {point_text(high, 'hPa')}."
        )

    if low:
        lines.append(
            f"Cyklonální aktivita je nejvýraznější u minima {point_text(low, 'hPa')}."
        )

    if tmax:
        if tmax["lat"] < 40:
            region = "jižní Evropě a severní Africe"
        elif tmax["lon"] < 5:
            region = "jihozápadní až západní Evropě"
        else:
            region = "jižní až jihovýchodní Evropě"
        lines.append(f"Nejteplejší vzduchová hmota leží převážně v {region}; maximum T850 je {point_text(tmax, '°C')}.")

    if jetmax:
        lines.append(f"Nejsilnější proudění v hladině 250 hPa dosahuje {point_text(jetmax, 'm/s')}; tato oblast je klíčová pro polohu tryskového proudění a dynamickou podporu vývoje." )

    if capemax:
        lines.append(f"Nejvyšší konvektivní energie CAPE je {point_text(capemax, 'J/kg')}; pro reálnou iniciaci je nutné hodnotit současně CIN, PWAT a výstupné mechanismy.")

    if pmax:
        lines.append(f"Nejvýraznější srážkové maximum je {point_text(pmax, 'mm')}; interpretovat jako lokální maximum modelu.")
    else:
        lines.append("Srážková maxima nejsou v dostupném poli významná.")

    return lines


def build_main_summary(classification, features, synoptic, hazards):
    syn = synoptic["features"]
    low = first(syn["pressure_systems"]["lows_mslp_hpa"])
    high = first(syn["pressure_systems"]["highs_mslp_hpa"])
    zmax = first(syn["upper_air"]["z500_maxima_dam"])
    zmin = first(syn["upper_air"]["z500_minima_dam"])
    area20 = syn["air_mass"]["area_t850_ge_20c_percent"]
    area15 = syn["air_mass"]["area_t850_ge_15c_percent"]
    jetmax = first(syn.get("upper_air", {}).get("jet250_maxima_ms", []))
    capemax = first(syn.get("convection", {}).get("cape_maxima_jkg", []))

    paragraph_1 = (
        f"Situace odpovídá typu: {classification['synoptic_type']}. "
        f"V poli MSLP je hlavní tlaková výše {point_text(high, 'hPa')} a hlavní tlaková níže {point_text(low, 'hPa')}. "
        f"Tlakový rozsah v evropské doméně dosahuje {features['derived']['mslp_range_hpa']:.1f} hPa."
    )

    paragraph_2 = (
        f"Ve výškovém poli je maximum Z500 {point_text(zmax, 'dam')} a minimum Z500 {point_text(zmin, 'dam')}. "
        f"Jet stream 250 hPa má nejsilnější analyzované jádro {point_text(jetmax, 'm/s')}. "
        f"To podporuje charakter proudění: {classification['flow_type']}."
    )

    paragraph_3 = (
        f"Vzduchová hmota má charakter: {classification['weather_regime']}. "
        f"T850 ≥ 15 °C pokrývá {area15:.1f} % domény a T850 ≥ 20 °C {area20:.1f} % domény. "
        f"Hlavní upozornění: {', '.join(hazards)}."
    )

    return [paragraph_1, paragraph_2, paragraph_3]


def confidence_level(features, synoptic, previous_features):
    score = 0

    if previous_features is not None:
        score += 1
    if features["derived"]["mslp_range_hpa"] >= 25:
        score += 1
    if synoptic["features"]["upper_air"]["z500_maxima_dam"]:
        score += 1
    if synoptic["features"]["pressure_systems"]["highs_mslp_hpa"] or synoptic["features"]["pressure_systems"]["lows_mslp_hpa"]:
        score += 1

    if score >= 4:
        return "vyšší"
    if score >= 2:
        return "střední"
    return "nižší"


def main():
    args = parse_args()
    run_filter = resolve_run_time(args.run) if args.run else None
    fxx_filter = args.fxx if args.run else None

    feature_file, features = load_json("features", run_filter, fxx_filter)
    synoptic_file, synoptic = load_json("synoptic_features", run_filter, fxx_filter)
    assessment_file, assessment = load_json("synoptic_assessment", run_filter, fxx_filter)

    previous_feature_file, previous_features = find_previous_json(
        "features",
        features["run_time"],
        features["forecast_hour"],
    )
    previous_synoptic_file, previous_synoptic = find_previous_json(
        "synoptic_features",
        features["run_time"],
        features["forecast_hour"],
    )

    classification = classify_synoptic_type(features, synoptic)
    hazards = detect_hazards(features, synoptic)
    trends = build_trends(features, synoptic, previous_features, previous_synoptic)
    regional_summary = build_regional_summary(synoptic)
    czechia_summary = build_czechia_summary(features, synoptic)
    main_summary = build_main_summary(classification, features, synoptic, hazards)
    confidence = confidence_level(features, synoptic, previous_features)

    commentary = {
        "model": features["model"],
        "run_time": features["run_time"],
        "forecast_hour": features["forecast_hour"],
        "valid_time_utc": features["valid_time_utc"],
        "source_files": {
            "features": feature_file.as_posix(),
            "synoptic_features": synoptic_file.as_posix(),
            "synoptic_assessment": assessment_file.as_posix(),
            "previous_features": previous_feature_file.as_posix() if previous_feature_file else None,
            "previous_synoptic_features": previous_synoptic_file.as_posix() if previous_synoptic_file else None,
        },
        "classification": classification,
        "summary": main_summary,
        "trends": trends,
        "regional_summary": regional_summary,
        "czechia_summary": czechia_summary,
        "hazards": hazards,
        "confidence": confidence,
        "notes": [
            "Komentář je pravidlový a vychází z objektivních polí GFS.",
            "Trendové srovnání používá předchozí dostupný forecast hour stejného běhu modelu.",
            "Frontální systémy nejsou explicitně detekovány; možné frontální rozhraní je pouze nepřímá interpretace z polí.",
        ],
    }

    valid_time = features["valid_time_utc"]
    outfile = REPORTS_DIR / f"synoptic_commentary_{valid_time.replace(':', '-')}.json"

    with open(outfile, "w", encoding="utf-8") as f:
        json.dump(commentary, f, indent=2, ensure_ascii=False)

    print(f"Saved: {outfile}")


if __name__ == "__main__":
    main()
