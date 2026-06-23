import argparse

import numpy as np
import matplotlib.pyplot as plt
import cartopy.crs as ccrs

from styles import (
    FIGSIZE,
    DPI,
    MAP_AXES,
    COLORBAR_AXES,
    PWAT_CMAP,
    PWAT_FILL_LEVELS_MM,
    PWAT_CONTOUR_LEVELS_MM,
    PWAT_HIGH_LEVELS_MM,
    PWAT_CONTOUR_LINEWIDTH,
    PWAT_HIGH_LINEWIDTHS,
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

    pwat_file = download_field(H, ":PWAT:")
    ds_pwat = open_grib_dataset(pwat_file)

    pwat = get_first_available_var(ds_pwat, ["pwat", "unknown"])
    # GFS PWAT is typically kg m-2, which is numerically equivalent to mm of water.
    pwat_mm = subset_europe(pwat)
    pwat_mm.name = "pwat_mm"

    valid_time = np.datetime_as_string(ds_pwat.valid_time.values, unit="m")

    fig = plt.figure(figsize=FIGSIZE)
    ax = fig.add_axes(MAP_AXES, projection=ccrs.PlateCarree())
    cax = fig.add_axes(COLORBAR_AXES)

    setup_europe_map(ax)

    cf = ax.contourf(
        pwat_mm.longitude,
        pwat_mm.latitude,
        pwat_mm,
        levels=PWAT_FILL_LEVELS_MM,
        cmap=PWAT_CMAP,
        extend="max",
        transform=ccrs.PlateCarree(),
    )

    cs = ax.contour(
        pwat_mm.longitude,
        pwat_mm.latitude,
        pwat_mm,
        levels=PWAT_CONTOUR_LEVELS_MM,
        colors="black",
        linewidths=PWAT_CONTOUR_LINEWIDTH,
        transform=ccrs.PlateCarree(),
    )
    ax.clabel(cs, inline=True, fontsize=CONTOUR_LABEL_FONTSIZE, fmt="%d")

    high = ax.contour(
        pwat_mm.longitude,
        pwat_mm.latitude,
        pwat_mm,
        levels=PWAT_HIGH_LEVELS_MM,
        colors="black",
        linewidths=PWAT_HIGH_LINEWIDTHS,
        transform=ccrs.PlateCarree(),
    )
    ax.clabel(high, inline=True, fontsize=CONTOUR_LABEL_FONTSIZE, fmt="%d")

    cbar = fig.colorbar(cf, cax=cax, orientation="vertical")
    cbar.set_label("Precipitable water [mm]", fontsize=COLORBAR_LABEL_FONTSIZE)

    fig.suptitle(
        (
            "GFS Forecast | Precipitable Water | Europe\n"
            f"Valid: {valid_time} UTC | Forecast hour: +{fxx} h"
        ),
        fontsize=TITLE_FONTSIZE_LONG,
        fontweight="bold",
        y=0.95,
    )

    outfile = MAP_DIR / f"pwat_europe_{valid_time.replace(':', '-')}.png"
    fig.savefig(outfile, dpi=DPI, facecolor="white")
    plt.close(fig)

    print(f"Saved: {outfile}")


if __name__ == "__main__":
    main()
