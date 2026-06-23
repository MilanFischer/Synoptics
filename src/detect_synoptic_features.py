from pathlib import Path

import argparse
import json
from math import radians, sin, cos, sqrt, atan2

import numpy as np
import xarray as xr
from scipy.ndimage import minimum_filter, maximum_filter

from utils import normalize_longitude, subset_europe, subset_czechia, simple_field_stats, REPORTS_DIR, add_model_run_args, resolve_run_time, parse_priority, create_herbie, open_grib_dataset, download_field, download_first_available, cin_magnitude, zero_precip_from_template


OUT_DIR = REPORTS_DIR
OUT_DIR.mkdir(parents=True, exist_ok=True)


CAPE_SEARCHES = [
    ":CAPE:surface",
    ":CAPE:180-0 mb above ground",
    ":CAPE:90-0 mb above ground",
    ":CAPE:255-0 mb above ground",
]

CIN_SEARCHES = [
    ":CIN:surface",
    ":CIN:180-0 mb above ground",
    ":CIN:90-0 mb above ground",
    ":CIN:255-0 mb above ground",
]


def get_first_available_var(ds, candidates):
    for name in candidates:
        if name in ds.data_vars:
            return ds[name]

    raise KeyError(
        f"None of these variables found: {candidates}. "
        f"Available variables: {list(ds.data_vars)}"
    )


def open_field(file, filter_by_keys=None):
    return open_grib_dataset(file, filter_by_keys)


def haversine_km(lat1, lon1, lat2, lon2):
    radius_km = 6371.0

    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)

    a = (
        sin(dlat / 2) ** 2
        + cos(radians(lat1))
        * cos(radians(lat2))
        * sin(dlon / 2) ** 2
    )

    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return radius_km * c


def merge_nearby_points(points, min_distance_km=400):
    merged = []

    for point in points:
        too_close = False

        for existing in merged:
            distance = haversine_km(
                point["lat"],
                point["lon"],
                existing["lat"],
                existing["lon"],
            )

            if distance < min_distance_km:
                too_close = True
                break

        if not too_close:
            merged.append(point)

    return merged


def local_extrema(
    field,
    mode,
    threshold=None,
    size=25,
    max_count=5,
    min_distance_km=400,
):
    values = field.values

    if mode == "min":
        filtered = minimum_filter(
            values,
            size=size,
            mode="nearest",
        )
        mask = values == filtered

        if threshold is not None:
            mask &= values <= threshold

        sort_reverse = False

    elif mode == "max":
        filtered = maximum_filter(
            values,
            size=size,
            mode="nearest",
        )
        mask = values == filtered

        if threshold is not None:
            mask &= values >= threshold

        sort_reverse = True

    else:
        raise ValueError("mode must be 'min' or 'max'")

    points = []

    for i, j in np.argwhere(mask):
        value = float(values[i, j])

        if not np.isfinite(value):
            continue

        points.append(
            {
                "value": round(value, 1),
                "lat": round(float(field.latitude.values[i]), 2),
                "lon": round(float(field.longitude.values[j]), 2),
            }
        )

    points = sorted(
        points,
        key=lambda x: x["value"],
        reverse=sort_reverse,
    )

    points = merge_nearby_points(
        points,
        min_distance_km=min_distance_km,
    )

    return points[:max_count]


def area_fraction(field, threshold):
    values = field.values
    valid = np.isfinite(values)

    if valid.sum() == 0:
        return 0.0

    return round(
        float((values[valid] >= threshold).sum() / valid.sum() * 100),
        1,
    )


def parse_args():
    parser = argparse.ArgumentParser()
    add_model_run_args(parser)
    return parser.parse_args()


def main():
    args = parse_args()
    run_time = resolve_run_time(args.run)
    fxx = args.fxx
    priority = parse_priority(args.priority)

    H = create_herbie(run_time, fxx=fxx, priority=priority)

    t850_file = download_field(H, ":TMP:850 mb")
    z500_file = download_field(H, ":HGT:500 mb")
    mslp_file = download_field(H, ":MSLET:")
    precip_file = None if int(fxx) == 0 else download_field(H, ":APCP:")
    u250_file = download_field(H, ":UGRD:250 mb")
    v250_file = download_field(H, ":VGRD:250 mb")
    pwat_file = download_field(H, ":PWAT:")
    cape_file = download_first_available(H, CAPE_SEARCHES)
    cin_file = download_first_available(H, CIN_SEARCHES)

    ds_t850 = open_field(
        t850_file,
        {
            "typeOfLevel": "isobaricInhPa",
            "level": 850,
        },
    )

    ds_z500 = open_field(
        z500_file,
        {
            "typeOfLevel": "isobaricInhPa",
            "level": 500,
        },
    )

    ds_mslp = open_field(mslp_file)

    ds_u250 = open_field(
        u250_file,
        {
            "typeOfLevel": "isobaricInhPa",
            "level": 250,
        },
    )

    ds_v250 = open_field(
        v250_file,
        {
            "typeOfLevel": "isobaricInhPa",
            "level": 250,
        },
    )

    ds_pwat = open_field(pwat_file)
    ds_cape = open_field(cape_file)
    ds_cin = open_field(cin_file)

    t850 = subset_europe(ds_t850["t"] - 273.15)
    t850.name = "t850_c"

    z500 = subset_europe(ds_z500["gh"] / 10.0)
    z500.name = "z500_dam"

    mslp = subset_europe(
        get_first_available_var(ds_mslp, ["mslet", "msl", "prmsl"])
        / 100.0
    )
    mslp.name = "mslp_hpa"

    u250 = subset_europe(ds_u250["u"])
    v250 = subset_europe(ds_v250["v"])
    jet250 = (u250 ** 2 + v250 ** 2) ** 0.5
    jet250.name = "jet250_speed_ms"

    pwat = subset_europe(get_first_available_var(ds_pwat, ["pwat", "unknown"]))
    pwat.name = "pwat_mm"

    cape = subset_europe(get_first_available_var(ds_cape, ["cape", "unknown"]))
    cape.name = "cape_jkg"

    cin = subset_europe(cin_magnitude(get_first_available_var(ds_cin, ["cin", "unknown"])))

    if precip_file is None:
        precip = subset_europe(zero_precip_from_template(ds_t850["t"]))
    else:
        ds_precip = open_field(precip_file)
        precip = subset_europe(
            get_first_available_var(ds_precip, ["tp", "apcp", "unknown"])
        )
    precip.name = "precip_mm"

    valid_time = np.datetime_as_string(
        ds_t850.valid_time.values,
        unit="m",
    )

    features = {
        "model": "GFS",
        "run_time": run_time,
        "forecast_hour": fxx,
        "valid_time_utc": valid_time,
        "domain": "Europe",
        "regions": {
            "czechia": {
                "t850_c": simple_field_stats(
                    subset_czechia(t850),
                    thresholds={"ge_15c": 15, "ge_20c": 20},
                ),
                "mslp_hpa": simple_field_stats(subset_czechia(mslp)),
                "precip_mm": simple_field_stats(
                    subset_czechia(precip),
                    thresholds={"ge_1mm": 1, "ge_10mm": 10},
                ),
                "jet250_speed_ms": simple_field_stats(
                    subset_czechia(jet250),
                    thresholds={"ge_35ms": 35, "ge_50ms": 50, "ge_60ms": 60},
                ),
                "pwat_mm": simple_field_stats(
                    subset_czechia(pwat),
                    thresholds={"ge_30mm": 30, "ge_40mm": 40, "ge_50mm": 50},
                ),
                "cape_jkg": simple_field_stats(
                    subset_czechia(cape),
                    thresholds={"ge_250jkg": 250, "ge_500jkg": 500, "ge_1000jkg": 1000},
                ),
                "cin_jkg": simple_field_stats(
                    subset_czechia(cin),
                    thresholds={"ge_25jkg": 25, "ge_50jkg": 50, "ge_100jkg": 100},
                ),
            },
        },
        "features": {
            "pressure_systems": {
                "lows_mslp_hpa": local_extrema(
                    mslp,
                    mode="min",
                    threshold=1010,
                    size=35,
                    max_count=5,
                    min_distance_km=500,
                ),
                "highs_mslp_hpa": local_extrema(
                    mslp,
                    mode="max",
                    threshold=1018,
                    size=35,
                    max_count=5,
                    min_distance_km=500,
                ),
            },
            "upper_air": {
                "z500_minima_dam": local_extrema(
                    z500,
                    mode="min",
                    size=35,
                    max_count=5,
                    min_distance_km=500,
                ),
                "z500_maxima_dam": local_extrema(
                    z500,
                    mode="max",
                    size=35,
                    max_count=5,
                    min_distance_km=500,
                ),
                "jet250_maxima_ms": local_extrema(
                    jet250,
                    mode="max",
                    threshold=35,
                    size=25,
                    max_count=8,
                    min_distance_km=400,
                ),
                "area_jet250_ge_35ms_percent": area_fraction(jet250, 35),
                "area_jet250_ge_50ms_percent": area_fraction(jet250, 50),
                "area_jet250_ge_60ms_percent": area_fraction(jet250, 60),
                "jet250_strength": (
                    "strong" if float(np.nanmax(jet250.values)) >= 50
                    else "moderate" if float(np.nanmax(jet250.values)) >= 35
                    else "weak"
                ),
            },
            "moisture": {
                "pwat_maxima_mm": local_extrema(
                    pwat,
                    mode="max",
                    threshold=30,
                    size=25,
                    max_count=10,
                    min_distance_km=350,
                ),
                "area_pwat_ge_30mm_percent": area_fraction(pwat, 30),
                "area_pwat_ge_40mm_percent": area_fraction(pwat, 40),
                "area_pwat_ge_50mm_percent": area_fraction(pwat, 50),
                "pwat_moisture_class": (
                    "extremely_moist" if float(np.nanmax(pwat.values)) >= 50
                    else "very_moist" if float(np.nanmax(pwat.values)) >= 40
                    else "moist" if float(np.nanmax(pwat.values)) >= 30
                    else "normal_or_dry"
                ),
            },

            "convection": {
                "cape_maxima_jkg": local_extrema(
                    cape,
                    mode="max",
                    threshold=250,
                    size=25,
                    max_count=10,
                    min_distance_km=350,
                ),
                "cin_maxima_jkg": local_extrema(
                    cin,
                    mode="max",
                    threshold=25,
                    size=25,
                    max_count=10,
                    min_distance_km=350,
                ),
                "area_cape_ge_250jkg_percent": area_fraction(cape, 250),
                "area_cape_ge_500jkg_percent": area_fraction(cape, 500),
                "area_cape_ge_1000jkg_percent": area_fraction(cape, 1000),
                "area_cin_ge_25jkg_percent": area_fraction(cin, 25),
                "area_cin_ge_50jkg_percent": area_fraction(cin, 50),
                "area_cin_ge_100jkg_percent": area_fraction(cin, 100),
                "cape_instability_class": (
                    "extreme" if float(np.nanmax(cape.values)) >= 3000
                    else "strong" if float(np.nanmax(cape.values)) >= 1500
                    else "moderate" if float(np.nanmax(cape.values)) >= 500
                    else "weak" if float(np.nanmax(cape.values)) >= 100
                    else "minimal"
                ),
                "cin_inhibition_class": (
                    "strong" if float(np.nanmax(cin.values)) >= 100
                    else "moderate" if float(np.nanmax(cin.values)) >= 50
                    else "weak" if float(np.nanmax(cin.values)) >= 25
                    else "minimal"
                ),
            },
            "air_mass": {
                "t850_maxima_c": local_extrema(
                    t850,
                    mode="max",
                    threshold=15,
                    size=25,
                    max_count=5,
                    min_distance_km=500,
                ),
                "area_t850_ge_15c_percent": area_fraction(t850, 15),
                "area_t850_ge_20c_percent": area_fraction(t850, 20),
            },
            "precipitation": {
                "precip_maxima_mm": local_extrema(
                    precip,
                    mode="max",
                    threshold=5,
                    size=25,
                    max_count=10,
                    min_distance_km=300,
                ),
                "area_precip_ge_1mm_percent": area_fraction(precip, 1),
                "area_precip_ge_10mm_percent": area_fraction(precip, 10),
            },
        },
        "notes": [
            "Detected features are algorithmic candidates, not manually analysed fronts.",
            "Nearby gridpoint extrema are merged using a minimum-distance filter.",
            "Local extrema depend on grid resolution, smoothing and filter size.",
            "Use these features as structured guidance for the report, not as absolute truth.",
        ],
    }

    outfile = OUT_DIR / f"synoptic_features_{valid_time.replace(':', '-')}.json"

    with open(outfile, "w", encoding="utf-8") as f:
        json.dump(
            features,
            f,
            indent=2,
            ensure_ascii=False,
        )

    print(f"Saved: {outfile}")


if __name__ == "__main__":
    main()