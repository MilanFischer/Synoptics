from pathlib import Path

import argparse

import numpy as np
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
from scipy.ndimage import gaussian_filter

import xarray as xr

from styles import (
    FIGSIZE,
    DPI,
    MAP_AXES,
    COLORBAR_AXES,
    TITLE_FONTSIZE_LONG,
    COLORBAR_LABEL_FONTSIZE,
    MSLP_CONTOUR_LINEWIDTH,
)
from utils import (
    normalize_longitude,
    subset_europe,
    setup_europe_map,
    add_model_run_args,
    resolve_run_time,
    parse_priority,
    create_herbie,
    open_grib_dataset,
    download_field,
    MAPS_DIR,
)


MAP_DIR = MAPS_DIR
MAP_DIR.mkdir(parents=True, exist_ok=True)


def get_first_available_var(ds, candidates):
    for name in candidates:
        if name in ds.data_vars:
            return ds[name]

    raise KeyError(
        f"None of these variables found: {candidates}. "
        f"Available variables: {list(ds.data_vars)}"
    )


def dynamic_wind_levels(field):
    values = field.values
    values = values[np.isfinite(values)]

    vmax = np.ceil(np.percentile(values, 98))

    if vmax < 8:
        vmax = 8

    vmax = min(vmax, 30)

    levels = np.arange(0, vmax + 1, 1)

    return levels, vmax


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

    mslp_file = download_field(H, ":MSLET:")
    u10_file = download_field(H, ":UGRD:10 m")
    v10_file = download_field(H, ":VGRD:10 m")

    ds_mslp = open_grib_dataset(mslp_file)

    ds_u10 = open_grib_dataset(
        u10_file,
        {
            "typeOfLevel": "heightAboveGround",
            "level": 10,
        },
    )

    ds_v10 = open_grib_dataset(
        v10_file,
        {
            "typeOfLevel": "heightAboveGround",
            "level": 10,
        },
    )

    ds_mslp = normalize_longitude(ds_mslp)
    ds_u10 = normalize_longitude(ds_u10)
    ds_v10 = normalize_longitude(ds_v10)

    mslp = get_first_available_var(ds_mslp, ["mslet", "msl", "prmsl"]) / 100.0
    mslp.name = "mslp_hpa"

    u10 = get_first_available_var(ds_u10, ["u10", "u"])
    v10 = get_first_available_var(ds_v10, ["v10", "v"])

    mslp_eu = subset_europe(mslp)
    u10_eu = subset_europe(u10)
    v10_eu = subset_europe(v10)

    wind_speed = np.sqrt(u10_eu**2 + v10_eu**2)
    wind_speed.name = "wind_speed_10m"

    wind_speed_smoothed = gaussian_filter(
        wind_speed.values,
        sigma=3.0,
    )

    wind_speed[:] = wind_speed_smoothed

    wind_levels, wind_vmax = dynamic_wind_levels(wind_speed)

    # Fixed 4 hPa isobar spacing for day-to-day comparability
    mslp_levels = np.arange(980, 1045, 4)

    valid_time = np.datetime_as_string(
        ds_mslp.valid_time.values,
        unit="m",
    )

    fig = plt.figure(figsize=FIGSIZE)

    ax = fig.add_axes(
        MAP_AXES,
        projection=ccrs.PlateCarree(),
    )

    cax = fig.add_axes(COLORBAR_AXES)

    setup_europe_map(ax)

    cf = ax.contourf(
        wind_speed.longitude,
        wind_speed.latitude,
        wind_speed,
        levels=wind_levels,
        cmap="Blues",
        extend="max",
        transform=ccrs.PlateCarree(),
    )

    cs = ax.contour(
        mslp_eu.longitude,
        mslp_eu.latitude,
        mslp_eu,
        levels=mslp_levels,
        colors="black",
        linewidths=MSLP_CONTOUR_LINEWIDTH,
        transform=ccrs.PlateCarree(),
    )

    ax.clabel(
        cs,
        inline=True,
        fontsize=8,
        fmt="%d",
    )

    cbar = fig.colorbar(
        cf,
        cax=cax,
        orientation="vertical",
    )

    cbar.set_label(
        "10 m Wind Speed [m/s]",
        fontsize=COLORBAR_LABEL_FONTSIZE,
    )

    fig.suptitle(
        (
            "GFS Forecast | Mean Sea Level Pressure + 10 m Wind Speed | Europe\n"
            f"Valid: {valid_time} UTC | Forecast hour: +{fxx} h"
        ),
        fontsize=TITLE_FONTSIZE_LONG,
        fontweight="bold",
        y=0.95,
    )

    outfile = MAP_DIR / f"mslp_wind_europe_{valid_time.replace(':', '-')}.png"

    fig.savefig(
        outfile,
        dpi=DPI,
        facecolor="white",
    )

    plt.close(fig)

    print(f"Saved: {outfile}")
    print(f"Wind scale: 0–{wind_vmax:.0f} m/s")


if __name__ == "__main__":
    main()