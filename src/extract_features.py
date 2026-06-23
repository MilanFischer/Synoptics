from pathlib import Path

import argparse
import json

import numpy as np
import xarray as xr

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


def extrema(field):
    values = field.values

    min_idx = np.unravel_index(np.nanargmin(values), values.shape)
    max_idx = np.unravel_index(np.nanargmax(values), values.shape)

    lat_min = float(field.latitude.values[min_idx[0]])
    lon_min = float(field.longitude.values[min_idx[1]])
    lat_max = float(field.latitude.values[max_idx[0]])
    lon_max = float(field.longitude.values[max_idx[1]])

    return {
        "min": {
            "value": float(np.nanmin(values)),
            "lat": lat_min,
            "lon": lon_min,
        },
        "max": {
            "value": float(np.nanmax(values)),
            "lat": lat_max,
            "lon": lon_max,
        },
    }


def open_field(file, filter_by_keys=None):
    return open_grib_dataset(file, filter_by_keys)


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
        get_first_available_var(ds_mslp, ["mslet", "msl", "prmsl"]) / 100.0
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

    czechia = {
        "t850_c": simple_field_stats(
            subset_czechia(t850),
            thresholds={"ge_15c": 15, "ge_20c": 20},
        ),
        "z500_dam": simple_field_stats(subset_czechia(z500)),
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
    }

    summary = {
        "model": "GFS",
        "run_time": run_time,
        "forecast_hour": fxx,
        "valid_time_utc": valid_time,
        "domain": "Europe",
        "regions": {
            "czechia": czechia,
        },
        "fields": {
            "t850_c": extrema(t850),
            "z500_dam": extrema(z500),
            "mslp_hpa": extrema(mslp),
            "precip_mm": extrema(precip),
            "jet250_speed_ms": extrema(jet250),
            "pwat_mm": extrema(pwat),
            "cape_jkg": extrema(cape),
            "cin_jkg": extrema(cin),
        },
        "derived": {
            "t850_range_c": round(
                float(t850.max() - t850.min()),
                1,
            ),
            "mslp_range_hpa": round(
                float(mslp.max() - mslp.min()),
                1,
            ),
            "precip_area_gt_1mm_percent": round(
                float((precip > 1).sum() / precip.size * 100),
                1,
            ),
            "precip_area_gt_10mm_percent": round(
                float((precip > 10).sum() / precip.size * 100),
                1,
            ),
            "jet250_area_gt_35ms_percent": round(
                float((jet250 > 35).sum() / jet250.size * 100),
                1,
            ),
            "jet250_area_gt_50ms_percent": round(
                float((jet250 > 50).sum() / jet250.size * 100),
                1,
            ),
            "jet250_area_gt_60ms_percent": round(
                float((jet250 > 60).sum() / jet250.size * 100),
                1,
            ),
            "pwat_area_gt_30mm_percent": round(
                float((pwat > 30).sum() / pwat.size * 100),
                1,
            ),
            "pwat_area_gt_40mm_percent": round(
                float((pwat > 40).sum() / pwat.size * 100),
                1,
            ),
            "pwat_area_gt_50mm_percent": round(
                float((pwat > 50).sum() / pwat.size * 100),
                1,
            ),
            "cape_area_gt_250jkg_percent": round(
                float((cape > 250).sum() / cape.size * 100),
                1,
            ),
            "cape_area_gt_500jkg_percent": round(
                float((cape > 500).sum() / cape.size * 100),
                1,
            ),
            "cape_area_gt_1000jkg_percent": round(
                float((cape > 1000).sum() / cape.size * 100),
                1,
            ),
            "cin_area_gt_25jkg_percent": round(
                float((cin > 25).sum() / cin.size * 100),
                1,
            ),
            "cin_area_gt_50jkg_percent": round(
                float((cin > 50).sum() / cin.size * 100),
                1,
            ),
            "cin_area_gt_100jkg_percent": round(
                float((cin > 100).sum() / cin.size * 100),
                1,
            ),
        },
    }

    outfile = OUT_DIR / f"features_{valid_time.replace(':', '-')}.json"

    with open(outfile, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print(f"Saved: {outfile}")


if __name__ == "__main__":
    main()