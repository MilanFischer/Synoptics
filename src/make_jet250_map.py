import argparse

import numpy as np
import matplotlib.pyplot as plt
import cartopy.crs as ccrs

from styles import (
    FIGSIZE,
    DPI,
    MAP_AXES,
    COLORBAR_AXES,
    JET250_CMAP,
    JET250_FILL_LEVELS_MS,
    JET250_CONTOUR_LEVELS_MS,
    JET250_CORE_LEVELS_MS,
    JET250_CONTOUR_LINEWIDTH,
    JET250_CORE_LINEWIDTHS,
    JET250_VECTOR_SKIP,
    JET250_SHOW_BARBS,
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

    u250_file = download_field(H, ":UGRD:250 mb")
    v250_file = download_field(H, ":VGRD:250 mb")

    ds_u250 = open_grib_dataset(
        u250_file,
        {"typeOfLevel": "isobaricInhPa", "level": 250},
    )
    ds_v250 = open_grib_dataset(
        v250_file,
        {"typeOfLevel": "isobaricInhPa", "level": 250},
    )

    u250 = subset_europe(ds_u250["u"])
    v250 = subset_europe(ds_v250["v"])
    speed_ms = (u250 ** 2 + v250 ** 2) ** 0.5
    speed_ms.name = "jet250_speed_ms"

    valid_time = np.datetime_as_string(ds_u250.valid_time.values, unit="m")

    fig = plt.figure(figsize=FIGSIZE)
    ax = fig.add_axes(MAP_AXES, projection=ccrs.PlateCarree())
    cax = fig.add_axes(COLORBAR_AXES)

    setup_europe_map(ax)

    cf = ax.contourf(
        speed_ms.longitude,
        speed_ms.latitude,
        speed_ms,
        levels=JET250_FILL_LEVELS_MS,
        cmap=JET250_CMAP,
        extend="max",
        transform=ccrs.PlateCarree(),
    )

    cs = ax.contour(
        speed_ms.longitude,
        speed_ms.latitude,
        speed_ms,
        levels=JET250_CONTOUR_LEVELS_MS,
        colors="black",
        linewidths=JET250_CONTOUR_LINEWIDTH,
        transform=ccrs.PlateCarree(),
    )
    ax.clabel(cs, inline=True, fontsize=CONTOUR_LABEL_FONTSIZE, fmt="%d")

    core = ax.contour(
        speed_ms.longitude,
        speed_ms.latitude,
        speed_ms,
        levels=JET250_CORE_LEVELS_MS,
        colors="black",
        linewidths=JET250_CORE_LINEWIDTHS,
        transform=ccrs.PlateCarree(),
    )
    ax.clabel(core, inline=True, fontsize=CONTOUR_LABEL_FONTSIZE, fmt="%d")

    if JET250_SHOW_BARBS:
        skip = JET250_VECTOR_SKIP
        ax.barbs(
            u250.longitude.values[::skip],
            u250.latitude.values[::skip],
            u250.values[::skip, ::skip],
            v250.values[::skip, ::skip],
            length=4.2,
            linewidth=0.3,
            transform=ccrs.PlateCarree(),
        )

    cbar = fig.colorbar(cf, cax=cax, orientation="vertical")
    cbar.set_label("250 hPa wind speed [m/s]", fontsize=COLORBAR_LABEL_FONTSIZE)

    fig.suptitle(
        (
            "GFS Forecast | 250 hPa Jet Stream | Europe\n"
            f"Valid: {valid_time} UTC | Forecast hour: +{fxx} h"
        ),
        fontsize=TITLE_FONTSIZE_LONG,
        fontweight="bold",
        y=0.95,
    )

    outfile = MAP_DIR / f"jet250_europe_{valid_time.replace(':', '-')}.png"
    fig.savefig(outfile, dpi=DPI, facecolor="white")
    plt.close(fig)

    print(f"Saved: {outfile}")


if __name__ == "__main__":
    main()
