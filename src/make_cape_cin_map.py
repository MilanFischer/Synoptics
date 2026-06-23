import argparse

import numpy as np
import matplotlib.pyplot as plt
import cartopy.crs as ccrs

from styles import (
    FIGSIZE,
    DPI,
    MAP_AXES,
    COLORBAR_AXES,
    CAPE_CMAP,
    CAPE_FILL_LEVELS_JKG,
    CAPE_CONTOUR_LEVELS_JKG,
    CAPE_CONTOUR_LINEWIDTH,
    CAPE_HIGH_LEVELS_JKG,
    CAPE_HIGH_LINEWIDTHS,
    CIN_HATCH_LEVELS_JKG,
    CIN_HATCHES,
    TITLE_FONTSIZE_LONG,
    COLORBAR_LABEL_FONTSIZE,
    CONTOUR_LABEL_FONTSIZE,
)
from utils import (
    subset_europe,
    setup_europe_map,
    add_model_run_args,
    resolve_run_time,
    parse_priority,
    create_herbie,
    open_grib_dataset,
    download_first_available,
    cin_magnitude,
    MAPS_DIR,
)


MAP_DIR = MAPS_DIR
MAP_DIR.mkdir(parents=True, exist_ok=True)

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

    cape_file = download_first_available(H, CAPE_SEARCHES)
    cin_file = download_first_available(H, CIN_SEARCHES)

    ds_cape = open_grib_dataset(cape_file)
    ds_cin = open_grib_dataset(cin_file)

    cape = subset_europe(get_first_available_var(ds_cape, ["cape", "unknown"]))
    cape.name = "cape_jkg"

    cin = subset_europe(
        cin_magnitude(get_first_available_var(ds_cin, ["cin", "unknown"]))
    )
    cin.name = "cin_jkg"

    valid_time = np.datetime_as_string(ds_cape.valid_time.values, unit="m")

    fig = plt.figure(figsize=FIGSIZE)
    ax = fig.add_axes(MAP_AXES, projection=ccrs.PlateCarree())
    cax = fig.add_axes(COLORBAR_AXES)

    setup_europe_map(ax)

    cf = ax.contourf(
        cape.longitude,
        cape.latitude,
        cape,
        levels=CAPE_FILL_LEVELS_JKG,
        cmap=CAPE_CMAP,
        extend="max",
        transform=ccrs.PlateCarree(),
    )

    cape_cs = ax.contour(
        cape.longitude,
        cape.latitude,
        cape,
        levels=CAPE_CONTOUR_LEVELS_JKG,
        colors="black",
        linewidths=CAPE_CONTOUR_LINEWIDTH,
        transform=ccrs.PlateCarree(),
    )
    ax.clabel(
        cape_cs,
        inline=True,
        fontsize=CONTOUR_LABEL_FONTSIZE,
        fmt="%d",
    )

    cape_high = ax.contour(
        cape.longitude,
        cape.latitude,
        cape,
        levels=CAPE_HIGH_LEVELS_JKG,
        colors="black",
        linewidths=CAPE_HIGH_LINEWIDTHS,
        transform=ccrs.PlateCarree(),
    )
    ax.clabel(
        cape_high,
        inline=True,
        fontsize=CONTOUR_LABEL_FONTSIZE,
        fmt="%d",
    )

    # CIN is converted to positive magnitude by cin_magnitude().
    # Hatching therefore uses positive thresholds: 100 and 250 J/kg.
    ax.contourf(
        cin.longitude,
        cin.latitude,
        cin,
        levels=CIN_HATCH_LEVELS_JKG,
        hatches=CIN_HATCHES,
        colors="none",
        transform=ccrs.PlateCarree(),
    )

    cbar = fig.colorbar(cf, cax=cax, orientation="vertical")
    cbar.set_label(
        "Surface-based CAPE [J/kg]; hatched areas = convective inhibition (CIN)",
        fontsize=COLORBAR_LABEL_FONTSIZE,
    )

    fig.suptitle(
        (
            "GFS Forecast | CAPE and CIN | Europe\n"
            f"Valid: {valid_time} UTC | Forecast hour: +{fxx} h"
        ),
        fontsize=TITLE_FONTSIZE_LONG,
        fontweight="bold",
        y=0.95,
    )

    outfile = MAP_DIR / f"cape_cin_europe_{valid_time.replace(':', '-')}.png"
    fig.savefig(outfile, dpi=DPI, facecolor="white")
    plt.close(fig)

    print(f"Saved: {outfile}")


if __name__ == "__main__":
    main()