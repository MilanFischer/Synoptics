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
    TITLE_FONTSIZE_LONG,
    COLORBAR_LABEL_FONTSIZE,
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
    zero_precip_from_template,
    MAPS_DIR,
)


MAP_DIR = MAPS_DIR
MAP_DIR.mkdir(parents=True, exist_ok=True)


PRECIP_LEVELS = [
    0.0, 0.1, 0.5, 1, 2, 5, 10, 15, 20, 30, 40, 60
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

    if int(fxx) == 0:
        # GFS accumulated precipitation at forecast hour 0 is frequently absent
        # or not subsettable. Physically, the accumulation is 0 mm at F00.
        t850_file = download_field(H, ":TMP:850 mb")
        ds = open_grib_dataset(
            t850_file,
            {
                "typeOfLevel": "isobaricInhPa",
                "level": 850,
            },
        )
        template = ds["t"] - 273.15
        precip = zero_precip_from_template(template)
    else:
        precip_file = download_field(H, ":APCP:")
        ds = open_grib_dataset(precip_file)
        precip = get_first_available_var(
            ds,
            ["tp", "apcp", "unknown"],
        )
        # GFS APCP is usually already in kg m-2 = mm water equivalent.
        precip.name = "precipitation_mm"

    precip_eu = subset_europe(precip)

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
        precip_eu.longitude,
        precip_eu.latitude,
        precip_eu,
        levels=PRECIP_LEVELS,
        cmap="YlGnBu",
        extend="max",
        transform=ccrs.PlateCarree(),
    )

    cbar = fig.colorbar(
        cf,
        cax=cax,
        orientation="vertical",
    )

    cbar.set_label(
        "Accumulated Precipitation [mm]",
        fontsize=COLORBAR_LABEL_FONTSIZE,
    )

    fig.suptitle(
        (
            "GFS Forecast | Accumulated Precipitation | Europe\n"
            f"Valid: {valid_time} UTC | Forecast hour: +{fxx} h"
        ),
        fontsize=TITLE_FONTSIZE_LONG,
        fontweight="bold",
        y=0.95,
    )

    outfile = MAP_DIR / f"precip_europe_{valid_time.replace(':', '-')}.png"

    fig.savefig(
        outfile,
        dpi=DPI,
        facecolor="white",
    )

    plt.close(fig)

    print(f"Saved: {outfile}")


if __name__ == "__main__":
    main()