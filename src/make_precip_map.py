from pathlib import Path
import argparse

import numpy as np
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
from matplotlib.colors import BoundaryNorm

from styles import (
    FIGSIZE,
    DPI,
    MAP_AXES,
    COLORBAR_AXES,
    TITLE_FONTSIZE_LONG,
    COLORBAR_LABEL_FONTSIZE,
    get_precip_levels,
    finite_field_max,
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
    zero_precip_from_template,
    MAPS_DIR,
)

MAP_DIR = MAPS_DIR
MAP_DIR.mkdir(parents=True, exist_ok=True)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Create period precipitation map for one GFS forecast hour."
    )
    add_model_run_args(parser)
    return parser.parse_args()

def get_first_available_var(ds, candidates):
    for name in candidates:
        if name in ds.data_vars:
            return ds[name]

    raise KeyError(
        f"None of these variables found: {candidates}. "
        f"Available variables: {list(ds.data_vars)}"
    )

def main():
    args = parse_args()
    run_time = resolve_run_time(args.run)
    fxx = int(args.fxx)
    priority = parse_priority(args.priority)

    H = create_herbie(run_time, fxx=fxx, priority=priority)

    if fxx == 0:
        # GFS accumulated precipitation at forecast hour 0 is frequently absent
        # or not subsettable. Physically, the period accumulation is 0 mm at F00.
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
        precip.name = "precipitation_mm"
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
    levels = get_precip_levels(precip_eu)

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

    norm = BoundaryNorm(
        boundaries=levels,
        ncolors=plt.get_cmap("YlGnBu").N,
        clip=False,
    )

    cf = ax.contourf(
        precip_eu.longitude,
        precip_eu.latitude,
        precip_eu,
        levels=levels,
        cmap="YlGnBu",
        norm=norm,
        extend="max",
        transform=ccrs.PlateCarree(),
    )

    cbar = fig.colorbar(
        cf,
        cax=cax,
        orientation="vertical",
        ticks=levels,
        spacing="uniform",
    )

    cbar.set_label(
        "Period precipitation [mm]",
        fontsize=COLORBAR_LABEL_FONTSIZE,
    )

    # Keep the title compact. Forecast hour and valid time are already encoded
    # in filenames, manifests, and the combined overview header.
    fig.suptitle(
        "GFS Forecast | Period precipitation | Europe\n"
        f"Valid: {valid_time} UTC | Forecast hour: +{fxx} h",
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
    print(f"Precipitation max over Europe: {finite_field_max(precip_eu):.1f} mm")
    print(f"Precipitation levels used: {levels}")


if __name__ == "__main__":
    main()
