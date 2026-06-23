from pathlib import Path

import argparse

import numpy as np
import matplotlib.pyplot as plt
import cartopy.crs as ccrs

import xarray as xr

from styles import (
    FIGSIZE,
    DPI,
    MAP_AXES,
    COLORBAR_AXES,
    T850_CMAP,
    Z500_CONTOUR_LINEWIDTH,
    TITLE_FONTSIZE_LONG,
    COLORBAR_LABEL_FONTSIZE,
    CONTOUR_LABEL_FONTSIZE,
)
from utils import (
    normalize_longitude,
    subset_europe,
    dynamic_t850_levels,
    z500_levels,
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

    ds_t850 = open_grib_dataset(
        t850_file,
        {
            "typeOfLevel": "isobaricInhPa",
            "level": 850,
        },
    )

    ds_z500 = open_grib_dataset(
        z500_file,
        {
            "typeOfLevel": "isobaricInhPa",
            "level": 500,
        },
    )

    ds_t850 = normalize_longitude(ds_t850)
    ds_z500 = normalize_longitude(ds_z500)

    t850 = ds_t850["t"] - 273.15
    t850.name = "t850_c"

    z500 = ds_z500["gh"] / 10.0
    z500.name = "z500_dam"

    t850_eu = subset_europe(t850)
    z500_eu = subset_europe(z500)

    _, _, t850_fill_levels, _ = dynamic_t850_levels(t850_eu)
    z500_contour_levels = z500_levels(z500_eu, step=4)

    valid_time = np.datetime_as_string(
        ds_t850.valid_time.values,
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
        t850_eu.longitude,
        t850_eu.latitude,
        t850_eu,
        levels=t850_fill_levels,
        cmap=T850_CMAP,
        extend="both",
        transform=ccrs.PlateCarree(),
    )

    zc = ax.contour(
        z500_eu.longitude,
        z500_eu.latitude,
        z500_eu,
        levels=z500_contour_levels,
        colors="black",
        linewidths=Z500_CONTOUR_LINEWIDTH,
        transform=ccrs.PlateCarree(),
    )

    ax.clabel(
        zc,
        inline=True,
        fontsize=CONTOUR_LABEL_FONTSIZE,
        fmt="%d",
    )

    cbar = fig.colorbar(
        cf,
        cax=cax,
        orientation="vertical",
    )

    cbar.set_label(
        "850 hPa Temperature [°C]",
        fontsize=COLORBAR_LABEL_FONTSIZE,
    )

    fig.suptitle(
        (
            "GFS Forecast | 500 hPa Geopotential Height + 850 hPa Temperature | Europe\n"
            f"Valid: {valid_time} UTC | Forecast hour: +{fxx} h"
        ),
        fontsize=TITLE_FONTSIZE_LONG,
        fontweight="bold",
        y=0.95,
    )

    outfile = MAP_DIR / f"z500_t850_europe_{valid_time.replace(':', '-')}.png"

    fig.savefig(
        outfile,
        dpi=DPI,
        facecolor="white",
    )

    plt.close(fig)

    print(f"Saved: {outfile}")


if __name__ == "__main__":
    main()