from pathlib import Path
import argparse
import json

import numpy as np
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
from matplotlib.colors import BoundaryNorm

from styles import (
    DPI,
    TITLE_FONTSIZE_LONG,
    COLORBAR_LABEL_FONTSIZE,
    get_precip_accum_levels,
    finite_field_max,
)
from utils import (
    subset_europe,
    subset_czechia,
    simple_field_stats,
    setup_europe_map,
    add_model_run_args,
    resolve_run_time,
    parse_priority,
    create_herbie,
    open_grib_dataset,
    download_field,
    zero_precip_from_template,
    MAPS_DIR,
    REPORTS_DIR,
)


MAP_DIR = MAPS_DIR
REPORT_DIR = REPORTS_DIR
MAP_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)


def get_first_available_var(ds, candidates):
    for name in candidates:
        if name in ds.data_vars:
            return ds[name]
    raise KeyError(
        f"None of these variables found: {candidates}. Available variables: {list(ds.data_vars)}"
    )


def parse_fxx_list(value: str):
    return [int(item.strip()) for item in value.split(",") if item.strip()]


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Create cumulative precipitation maps from forecast start and "
            "write cumulative precipitation diagnostics."
        )
    )
    add_model_run_args(parser)
    parser.add_argument(
        "--fxx-list",
        type=parse_fxx_list,
        default=None,
        help="Comma-separated forecast hours, e.g. '0,6,12,24,48'. If omitted, only --fxx is used.",
    )
    return parser.parse_args()


def _safe_time_id(value: str) -> str:
    return value.replace(":", "-")


def _finite_max(field) -> float:
    """Return finite field maximum as float; return 0 for empty/all-NaN fields."""
    values = np.asarray(field.values, dtype=float)
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return 0.0
    return float(np.nanmax(finite))


def adaptive_precip_levels(field) -> list[float]:
    """Create precipitation contour levels with stable thresholds and adaptive top.

    This keeps fixed meteorological thresholds for comparability between maps,
    but automatically extends the colour scale if the forecast exceeds the
    default upper level.
    """
    max_value = _finite_max(field)

    # Always keep at least the base scale for visual consistency.
    if max_value <= PRECIP_BASE_LEVELS[-1]:
        return PRECIP_BASE_LEVELS

    levels = list(PRECIP_BASE_LEVELS)

    for level in PRECIP_EXTRA_LEVELS:
        if level < max_value:
            levels.append(level)
        else:
            levels.append(level)
            return levels

    # Extremely high fallback: round up to a clean 500 mm step.
    upper = float(np.ceil(max_value / 500.0) * 500.0)
    if upper > levels[-1]:
        levels.append(upper)

    return levels


def _precip_step_metadata(field) -> tuple[float | None, float | None]:
    start = field.attrs.get("startStep")
    end = field.attrs.get("endStep")

    if start is None or end is None:
        step_range = field.attrs.get("stepRange")
        if isinstance(step_range, str) and "-" in step_range:
            left, right = step_range.split("-", 1)
            try:
                start = float(left)
                end = float(right)
            except ValueError:
                pass

    try:
        start = float(start) if start is not None else None
    except (TypeError, ValueError):
        start = None

    try:
        end = float(end) if end is not None else None
    except (TypeError, ValueError):
        end = None

    return start, end


def _load_precip_field(run_time: str, fxx: int, priority: list[str]):
    H = create_herbie(run_time, fxx=fxx, priority=priority)

    if int(fxx) == 0:
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
        precip.name = "precip_mm"
        valid_time = np.datetime_as_string(ds.valid_time.values, unit="m")
        return subset_europe(precip), valid_time, (0.0, 0.0)

    precip_file = download_field(H, ":APCP:")
    ds = open_grib_dataset(precip_file)
    precip = get_first_available_var(ds, ["tp", "apcp", "unknown"])
    precip.name = "precip_mm"
    valid_time = np.datetime_as_string(ds.valid_time.values, unit="m")
    return subset_europe(precip), valid_time, _precip_step_metadata(precip)


def _detect_total_from_run(records: list[dict]) -> bool:
    starts = [r["start_step"] for r in records if r["fxx"] > 0 and r["start_step"] is not None]
    if not starts:
        return False
    # If the GRIB accumulation interval starts at 0 for all available positive forecast hours,
    # APCP already represents accumulation from model start to the valid time.
    return all(abs(float(s)) < 1e-6 for s in starts)


def _plot_accum(cumulative, valid_time: str, fxx: int, accumulation_mode: str):
    fig = plt.figure(figsize=(9.5, 8.0))
    ax = fig.add_axes([0.06, 0.12, 0.80, 0.76], projection=ccrs.PlateCarree())
    cax = fig.add_axes([0.89, 0.16, 0.025, 0.68])

    levels = get_precip_accum_levels(cumulative)

    norm = BoundaryNorm(
        boundaries=levels,
        ncolors=plt.get_cmap("YlGnBu").N,
        clip=False,
    )

    setup_europe_map(ax)

    cf = ax.contourf(
        cumulative.longitude,
        cumulative.latitude,
        cumulative,
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
        "Cumulative precipitation [mm]",
        fontsize=COLORBAR_LABEL_FONTSIZE,
    )

    # Keep the title compact. Valid time, forecast hour and accumulation mode
    # are stored in filename/JSON and repeated in the combined overview title.
    fig.suptitle(
        "GFS Forecast | Cumulative precipitation | Europe\n"
        f"Valid: {valid_time} UTC | Forecast hour: +{fxx} h",
        fontsize=TITLE_FONTSIZE_LONG,
        fontweight="bold",
        y=0.97,
    )

    outfile = MAP_DIR / f"precip_accum_europe_{_safe_time_id(valid_time)}.png"
    fig.savefig(outfile, dpi=DPI, facecolor="white")
    plt.close(fig)
    print(f"Saved: {outfile}")
    print(f"Cumulative precipitation max: {finite_field_max(cumulative):.1f} mm | levels: {levels}")
    return outfile


def _write_accum_summary(run_time, fxx, valid_time, cumulative, period, accumulation_mode):
    cz_cumulative = subset_czechia(cumulative)
    cz_period = subset_czechia(period)
    summary = {
        "model": "GFS",
        "run_time": run_time,
        "forecast_hour": int(fxx),
        "valid_time_utc": valid_time,
        "accumulation_mode": accumulation_mode,
        "map_scale": {
            "precip_accum_levels_mm": get_precip_accum_levels(cumulative),
            "precip_accum_max_domain_mm": finite_field_max(cumulative),
        },
        "regions": {
            "czechia": {
                "precip_period_mm": simple_field_stats(
                    cz_period,
                    thresholds={"ge_1mm": 1, "ge_10mm": 10, "ge_30mm": 30},
                ),
                "precip_accum_total_mm": simple_field_stats(
                    cz_cumulative,
                    thresholds={
                        "ge_10mm": 10,
                        "ge_30mm": 30,
                        "ge_50mm": 50,
                        "ge_100mm": 100,
                    },
                ),
            }
        },
        "domain": {
            "precip_accum_total_mm": simple_field_stats(
                cumulative,
                thresholds={
                    "ge_10mm": 10,
                    "ge_30mm": 30,
                    "ge_50mm": 50,
                    "ge_100mm": 100,
                    "ge_150mm": 150,
                    "ge_200mm": 200,
                    "ge_300mm": 300,
                },
            )
        },
        "notes": [
            "period precipitation is the APCP field for this forecast hour as supplied by GFS/Herbie",
            "cumulative precipitation is computed automatically from GRIB accumulation metadata when available",
            "if APCP accumulation starts at 0 h, cumulative precipitation equals the APCP field at the valid time",
            "map legend uses fixed meteorological thresholds and automatically extends above 150 mm when needed",
        ],
    }
    outfile = REPORT_DIR / f"precip_accum_{_safe_time_id(valid_time)}.json"
    outfile.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved: {outfile}")


def main():
    args = parse_args()
    run_time = resolve_run_time(args.run)
    priority = parse_priority(args.priority)
    fxx_values = args.fxx_list if args.fxx_list is not None else [int(args.fxx)]
    fxx_values = sorted(set(int(x) for x in fxx_values))

    records = []
    for fxx in fxx_values:
        print(f"Loading precipitation for +{fxx} h")
        field, valid_time, (start_step, end_step) = _load_precip_field(run_time, fxx, priority)
        records.append({
            "fxx": int(fxx),
            "valid_time": valid_time,
            "field": field,
            "start_step": start_step,
            "end_step": end_step,
        })

    total_from_run = _detect_total_from_run(records)
    accumulation_mode = "apcp_total_from_run" if total_from_run else "sum_of_available_steps"

    cumulative = None
    for record in records:
        period = record["field"]
        if total_from_run:
            cumulative = period
        else:
            cumulative = period if cumulative is None else cumulative + period
            cumulative.name = "precip_accum_total_mm"

        _plot_accum(cumulative, record["valid_time"], record["fxx"], accumulation_mode)
        _write_accum_summary(
            run_time=run_time,
            fxx=record["fxx"],
            valid_time=record["valid_time"],
            cumulative=cumulative,
            period=period,
            accumulation_mode=accumulation_mode,
        )


if __name__ == "__main__":
    main()
