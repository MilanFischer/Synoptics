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
    T850_CONTOUR_LINEWIDTH,
    TITLE_FONTSIZE,
    COLORBAR_LABEL_FONTSIZE,
    CONTOUR_LABEL_FONTSIZE,
)
from utils import (
    normalize_longitude,
    subset_europe,
    dynamic_t850_levels,
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

    grib_file = download_field(H, ":TMP:850 mb")

    ds = open_grib_dataset(
        grib_file,
        {
            "typeOfLevel": "isobaricInhPa",
            "level": 850,
        },
    )

    ds = normalize_longitude(ds)

    t850 = ds["t"] - 273.15
    t850.name = "t850_c"

    t850_eu = subset_europe(t850)

    _, _, fill_levels, contour_levels = dynamic_t850_levels(t850_eu)

    valid_time = np.datetime_as_string(
        ds.valid_time.values,
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
        levels=fill_levels,
        cmap=T850_CMAP,
        extend="both",
        transform=ccrs.PlateCarree(),
    )

    cs = ax.contour(
        t850_eu.longitude,
        t850_eu.latitude,
        t850_eu,
        levels=contour_levels,
        colors="black",
        linewidths=T850_CONTOUR_LINEWIDTH,
        transform=ccrs.PlateCarree(),
    )

    ax.clabel(
        cs,
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
            "GFS Forecast | 850 hPa Temperature | Europe\n"
            f"Valid: {valid_time} UTC | Forecast hour: +{fxx} h"
        ),
        fontsize=TITLE_FONTSIZE,
        fontweight="bold",
        y=0.95,
    )

    outfile = MAP_DIR / f"t850_europe_{valid_time.replace(':', '-')}.png"

    fig.savefig(
        outfile,
        dpi=DPI,
        facecolor="white",
    )

    plt.close(fig)

    print(f"Saved: {outfile}")


if __name__ == "__main__":
    main()