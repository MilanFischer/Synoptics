from pathlib import Path
import argparse
import json

from utils import add_model_run_args, resolve_run_time, REPORTS_DIR


REPORTS_DIR = REPORTS_DIR


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


def point_text(point, unit):
    return f"{point['value']:.1f} {unit} ({point['lat']:.1f}°N, {point['lon']:.1f}°E)"


def first_or_none(items):
    return items[0] if items else None


def assess_pressure(pressure):
    lines = []

    low = first_or_none(pressure["lows_mslp_hpa"])
    high = first_or_none(pressure["highs_mslp_hpa"])

    if low:
        if low["value"] <= 995:
            lines.append(
                f"Je detekována hlubší tlaková níže s minimem {point_text(low, 'hPa')}."
            )
        elif low["value"] <= 1005:
            lines.append(
                f"Je detekována tlaková níže s minimem {point_text(low, 'hPa')}."
            )
        else:
            lines.append(
                f"V poli MSLP je detekováno slabší minimum {point_text(low, 'hPa')}."
            )

    if high:
        if high["value"] >= 1030:
            lines.append(
                f"Je detekována výrazná tlaková výše s maximem {point_text(high, 'hPa')}."
            )
        elif high["value"] >= 1020:
            lines.append(
                f"Je detekována tlaková výše s maximem {point_text(high, 'hPa')}."
            )
        else:
            lines.append(
                f"V poli MSLP je detekováno slabší maximum {point_text(high, 'hPa')}."
            )

    if not lines:
        lines.append("Pole MSLP nevykazuje v evropské doméně výrazné uzavřené tlakové centrum.")

    return lines


def assess_upper_air(upper):
    lines = []

    zmax = first_or_none(upper["z500_maxima_dam"])
    zmin = first_or_none(upper["z500_minima_dam"])

    if zmax:
        if zmax["value"] >= 588:
            lines.append(
                f"V hladině 500 hPa je přítomna oblast velmi vysokého geopotenciálu s maximem {point_text(zmax, 'dam')}."
            )
        elif zmax["value"] >= 576:
            lines.append(
                f"V hladině 500 hPa je patrná oblast vyššího geopotenciálu s maximem {point_text(zmax, 'dam')}."
            )

    if zmin:
        if zmin["value"] <= 540:
            lines.append(
                f"V hladině 500 hPa je detekována výrazná oblast nižšího geopotenciálu s minimem {point_text(zmin, 'dam')}."
            )
        elif zmin["value"] <= 552:
            lines.append(
                f"V hladině 500 hPa je patrná oblast nižšího geopotenciálu s minimem {point_text(zmin, 'dam')}."
            )

    if not lines:
        lines.append("Výškové pole Z500 bez výraznějších extrémů v rámci nastavených prahů.")

    return lines


def assess_air_mass(air_mass):
    lines = []

    area15 = air_mass["area_t850_ge_15c_percent"]
    area20 = air_mass["area_t850_ge_20c_percent"]
    tmax = first_or_none(air_mass["t850_maxima_c"])

    if area20 >= 20:
        lines.append(
            f"Velmi teplá vzduchová hmota v 850 hPa je rozsáhlá; T850 ≥ 20 °C pokrývá {area20:.1f} % domény."
        )
    elif area20 >= 5:
        lines.append(
            f"Velmi teplá vzduchová hmota v 850 hPa je přítomna regionálně; T850 ≥ 20 °C pokrývá {area20:.1f} % domény."
        )
    elif area15 >= 20:
        lines.append(
            f"Teplá vzduchová hmota v 850 hPa zasahuje významnou část Evropy; T850 ≥ 15 °C pokrývá {area15:.1f} % domény."
        )
    else:
        lines.append(
            "Teplá vzduchová hmota v 850 hPa je v evropské doméně plošně omezená."
        )

    if tmax:
        lines.append(f"Nejvyšší detekovaná T850 dosahuje {point_text(tmax, '°C')}.")

    return lines


def assess_precipitation(precipitation):
    lines = []

    area1 = precipitation["area_precip_ge_1mm_percent"]
    area10 = precipitation["area_precip_ge_10mm_percent"]
    pmax = first_or_none(precipitation["precip_maxima_mm"])

    if area10 >= 5:
        lines.append(
            f"Významnější srážky jsou plošněji zastoupené; srážky ≥ 10 mm pokrývají {area10:.1f} % domény."
        )
    elif area1 >= 20:
        lines.append(
            f"Srážky jsou plošnější, ale většinou slabší; srážky ≥ 1 mm pokrývají {area1:.1f} % domény."
        )
    elif area1 >= 5:
        lines.append(
            f"Srážky jsou spíše regionální; srážky ≥ 1 mm pokrývají {area1:.1f} % domény."
        )
    else:
        lines.append(
            "Srážky jsou v rámci evropské domény plošně omezené."
        )

    if pmax:
        if pmax["value"] >= 20:
            lines.append(
                f"Lokálně je detekováno výraznější srážkové maximum {point_text(pmax, 'mm')}."
            )
        elif pmax["value"] >= 10:
            lines.append(
                f"Lokálně je detekováno srážkové maximum {point_text(pmax, 'mm')}."
            )
        else:
            lines.append(
                f"Nejvyšší detekované srážky dosahují {point_text(pmax, 'mm')}."
            )

    return lines



def assess_convection(convection):
    lines = []

    if not convection:
        return ["Konvektivní parametry CAPE/CIN nejsou dostupné."]

    cape500 = convection.get("area_cape_ge_500jkg_percent", 0.0)
    cape1000 = convection.get("area_cape_ge_1000jkg_percent", 0.0)
    cin50 = convection.get("area_cin_ge_50jkg_percent", 0.0)
    capemax = first_or_none(convection.get("cape_maxima_jkg", []))
    cinmax = first_or_none(convection.get("cin_maxima_jkg", []))

    if cape1000 >= 5:
        lines.append(f"Výraznější instabilita je přítomna v části domény; CAPE ≥ 1000 J/kg pokrývá {cape1000:.1f} % domény.")
    elif cape500 >= 10:
        lines.append(f"Zvýšený konvektivní potenciál je regionální; CAPE ≥ 500 J/kg pokrývá {cape500:.1f} % domény.")
    elif cape500 > 0:
        lines.append(f"CAPE ≥ 500 J/kg je pouze lokální; pokrývá {cape500:.1f} % domény.")
    else:
        lines.append("Konvektivní energie CAPE je v evropské doméně převážně nízká.")

    if capemax:
        lines.append(f"Nejvyšší detekovaná CAPE dosahuje {point_text(capemax, 'J/kg')}.")

    if cin50 >= 10:
        lines.append(f"Konvektivní inhibice je plošněji významná; CIN ≥ 50 J/kg pokrývá {cin50:.1f} % domény a může omezovat iniciaci konvekce.")
    elif cin50 > 0:
        lines.append(f"CIN ≥ 50 J/kg je regionální; inhibice může lokálně potlačovat bouřkovou iniciaci.")
    else:
        lines.append("Výraznější CIN nad 50 J/kg není v doméně plošně zastoupena.")

    if cinmax:
        lines.append(f"Nejvyšší detekovaná CIN dosahuje {point_text(cinmax, 'J/kg')}.")

    return lines


def main():
    args = parse_args()
    run_filter = resolve_run_time(args.run) if args.run else None
    fxx_filter = args.fxx if args.run else None

    feature_file, features = load_json("features", run_filter, fxx_filter)
    synoptic_file, synoptic = load_json("synoptic_features", run_filter, fxx_filter)

    valid_time = features["valid_time_utc"]
    run_time = features["run_time"]
    fxx = features["forecast_hour"]

    syn = synoptic["features"]

    sections = {
        "tlakové_pole": assess_pressure(syn["pressure_systems"]),
        "výškové_pole": assess_upper_air(syn["upper_air"]),
        "vzduchová_hmota": assess_air_mass(syn["air_mass"]),
        "srážky": assess_precipitation(syn["precipitation"]),
        "konvekce": assess_convection(syn.get("convection", {})),
    }

    assessment = {
        "model": features["model"],
        "run_time": run_time,
        "forecast_hour": fxx,
        "valid_time_utc": valid_time,
        "source_files": {
            "features": feature_file.as_posix(),
            "synoptic_features": synoptic_file.as_posix(),
        },
        "assessment": sections,
        "notes": [
            "Toto je pravidlová interpretace z objektivních polí, nikoli AI výstup.",
            "Formulace jsou založené na předem daných prahových hodnotách.",
            "Výstup má sloužit jako základ pro finální synoptický briefing.",
        ],
    }

    outfile = REPORTS_DIR / f"synoptic_assessment_{valid_time.replace(':', '-')}.json"

    with open(outfile, "w", encoding="utf-8") as f:
        json.dump(assessment, f, indent=2, ensure_ascii=False)

    print(f"Saved: {outfile}")


if __name__ == "__main__":
    main()