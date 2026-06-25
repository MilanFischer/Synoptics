from pathlib import Path
import os

# -----------------------------------------------------------------------------
# Project paths
# -----------------------------------------------------------------------------
# Scripts normally live in <project>/src.  These constants keep outputs stable
# regardless of the current working directory used to launch Python.
SRC_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SRC_DIR.parent if SRC_DIR.name.lower() == "src" else SRC_DIR

# Output root can be overridden by run_all.py via SYNOPTICS_OUTPUT_DIR.
# Without that variable, use outputs/_manual so importing utils no longer
# creates project-root data/, maps/ or reports/ directories.
OUTPUT_ROOT = Path(os.environ.get("SYNOPTICS_OUTPUT_DIR", PROJECT_ROOT / "outputs" / "_manual")).resolve()
DATA_DIR = OUTPUT_ROOT / "data"
MAPS_DIR = OUTPUT_ROOT / "maps"
REPORTS_DIR = OUTPUT_ROOT / "reports"
AI_INPUTS_DIR = OUTPUT_ROOT / "ai_inputs"


def ensure_output_dirs():
    """Create standard output directories when a script is actually run.

    This function is intentionally not called at import time. That prevents
    accidental creation of project-root data/, maps/ and reports/ directories
    when run_all.py imports utility functions before it has selected the daily
    output folder.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    MAPS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    AI_INPUTS_DIR.mkdir(parents=True, exist_ok=True)



import numpy as np
from styles import (
    EUROPE_EXTENT,
    LAND_ALPHA,
    OCEAN_ALPHA,
    COASTLINE_RESOLUTION,
    COASTLINE_WIDTH,
    BORDER_WIDTH,
    GRIDLINE_WIDTH,
    GRIDLINE_ALPHA,
    GRIDLINE_STYLE,
)


def normalize_longitude(ds):
    """Convert longitude from 0..360 to -180..180.

    cfgrib/Herbie can occasionally return an empty or incomplete dataset after
    a transient download failure.  In that case the previous implementation
    failed with a generic AttributeError on ``ds.longitude``.  Raise a clear
    RuntimeError instead so the caller can retry the download and the log shows
    what was actually missing.
    """
    if "longitude" not in ds.coords:
        raise RuntimeError(
            "Dataset has no 'longitude' coordinate. "
            f"coords={list(ds.coords)}, variables={list(ds.data_vars)}"
        )

    return (
        ds.assign_coords(
            longitude=((ds["longitude"] + 180) % 360) - 180
        )
        .sortby("longitude")
    )


def subset_europe(field):
    """Subset field to the Europe domain."""
    return field.sel(
        latitude=slice(EUROPE_EXTENT[3], EUROPE_EXTENT[2]),
        longitude=slice(EUROPE_EXTENT[0], EUROPE_EXTENT[1]),
    )


CZECHIA_EXTENT = [12.0, 19.0, 48.0, 51.2]


def subset_czechia(field):
    """Subset field to a Czechia-focused box."""
    return field.sel(
        latitude=slice(CZECHIA_EXTENT[3], CZECHIA_EXTENT[2]),
        longitude=slice(CZECHIA_EXTENT[0], CZECHIA_EXTENT[1]),
    )


def simple_field_stats(field, thresholds=None):
    """Return min/max/mean and optional area fractions for a DataArray."""
    values = field.values
    valid = np.isfinite(values)

    if valid.sum() == 0:
        base = {"min": None, "max": None, "mean": None}
    else:
        base = {
            "min": round(float(np.nanmin(values)), 1),
            "max": round(float(np.nanmax(values)), 1),
            "mean": round(float(np.nanmean(values)), 1),
        }

    if thresholds:
        base["area_fraction_percent"] = {}
        for label, threshold in thresholds.items():
            if valid.sum() == 0:
                fraction = 0.0
            else:
                fraction = float((values[valid] >= threshold).sum() / valid.sum() * 100)
            base["area_fraction_percent"][label] = round(fraction, 1)

    return base


def dynamic_t850_levels(field):
    """Create semi-dynamic T850 levels using 2nd and 98th percentiles."""
    values = field.values
    values = values[np.isfinite(values)]

    vmin = 2 * np.floor(np.percentile(values, 2) / 2)
    vmax = 2 * np.ceil(np.percentile(values, 98) / 2)

    if vmax <= vmin:
        vmax = vmin + 2

    fill_levels = np.arange(vmin, vmax + 1, 1)
    contour_levels = np.arange(vmin, vmax + 1, 2)

    return vmin, vmax, fill_levels, contour_levels


def z500_levels(field, step=4):
    """Create 500 hPa geopotential height contour levels in dam."""
    zmin = step * np.floor(float(field.min()) / step)
    zmax = step * np.ceil(float(field.max()) / step)
    return np.arange(zmin, zmax + step, step)


def setup_europe_map(ax):
    """Apply common Europe map styling."""
    import cartopy.crs as ccrs
    import cartopy.feature as cfeature

    ax.set_extent(EUROPE_EXTENT, crs=ccrs.PlateCarree())

    ax.add_feature(cfeature.LAND, alpha=LAND_ALPHA)
    ax.add_feature(cfeature.OCEAN, alpha=OCEAN_ALPHA)
    ax.coastlines(
        resolution=COASTLINE_RESOLUTION,
        linewidth=COASTLINE_WIDTH,
    )
    ax.add_feature(cfeature.BORDERS, linewidth=BORDER_WIDTH)

    gl = ax.gridlines(
        draw_labels=True,
        linewidth=GRIDLINE_WIDTH,
        alpha=GRIDLINE_ALPHA,
        linestyle=GRIDLINE_STYLE,
    )
    gl.top_labels = False
    gl.right_labels = False

    return gl

# -----------------------------------------------------------------------------
# Model run helpers
# -----------------------------------------------------------------------------

def add_model_run_args(parser):
    """Add common CLI arguments for model run and forecast hour."""
    parser.add_argument(
        "--run",
        type=str,
        default=None,
        help="Model run in UTC, e.g. '2026-06-20 00:00'. If omitted, a recent GFS cycle is used.",
    )
    parser.add_argument(
        "--fxx",
        type=int,
        default=6,
        help="Forecast hour, e.g. 0, 6, 12, 24, 48.",
    )
    parser.add_argument(
        "--priority",
        type=str,
        default="aws,nomads,google,azure",
        help=(
            "Comma-separated Herbie source priority. "
            "Default avoids data.rda.ucar.edu, which may fail SSL validation on some systems."
        ),
    )
    return parser


def parse_priority(value):
    """Return Herbie priority list from comma-separated CLI value."""
    if value is None:
        return ["aws", "nomads", "google", "azure"]

    if isinstance(value, (list, tuple)):
        return list(value)

    items = [item.strip() for item in str(value).split(",") if item.strip()]
    return items or ["aws", "nomads", "google", "azure"]

def latest_gfs_cycle(buffer_hours=6):
    """Return a recent likely-available GFS cycle in UTC.

    A small buffer is used because the newest nominal cycle is not always
    available on remote servers immediately.
    """
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc) - timedelta(hours=buffer_hours)
    cycle_hour = (now.hour // 6) * 6
    cycle = now.replace(hour=cycle_hour, minute=0, second=0, microsecond=0)
    return cycle.strftime("%Y-%m-%d %H:00")


def resolve_run_time(run_time=None):
    """Return user-specified run time or a recent likely-available GFS cycle."""
    return run_time or latest_gfs_cycle()


def valid_time_from_run(run_time, fxx):
    """Compute valid time string matching np.datetime_as_string(..., unit='m')."""
    from datetime import datetime, timedelta

    run = datetime.strptime(run_time, "%Y-%m-%d %H:%M")
    valid = run + timedelta(hours=int(fxx))
    return valid.strftime("%Y-%m-%dT%H:%M")


# -----------------------------------------------------------------------------
# Herbie helpers
# -----------------------------------------------------------------------------

def create_herbie(run_time, fxx, priority=None, product="pgrb2.0p25"):
    """Create a Herbie object and fail with a clear message if the GRIB is unavailable."""
    from herbie import Herbie

    priority_list = parse_priority(priority)

    H = Herbie(
        run_time,
        model="gfs",
        product=product,
        fxx=int(fxx),
        priority=priority_list,
        save_dir=DATA_DIR,
    )

    if getattr(H, "grib", None) is None:
        raise RuntimeError(
            "GFS GRIB was not found for "
            f"run={run_time} UTC, fxx=+{int(fxx)} h, product={product}. "
            "The selected run may not be published yet on the chosen mirrors. "
            "Try omitting --run, using an older cycle such as the previous 6-hour run, "
            "or changing --priority."
        )

    return H


def find_available_gfs_run(start_run_time=None, fxx=0, priority=None, max_back_cycles=8):
    """Find the latest available GFS run by stepping backwards in 6-hour cycles."""
    from datetime import datetime, timedelta

    if start_run_time is None:
        start_run_time = latest_gfs_cycle(buffer_hours=0)

    start = datetime.strptime(start_run_time, "%Y-%m-%d %H:%M")
    start = start.replace(hour=(start.hour // 6) * 6, minute=0, second=0, microsecond=0)

    last_error = None

    for step in range(int(max_back_cycles) + 1):
        candidate = start - timedelta(hours=6 * step)
        candidate_text = candidate.strftime("%Y-%m-%d %H:%M")

        try:
            create_herbie(
                candidate_text,
                fxx=fxx,
                priority=priority,
            )
            return candidate_text
        except Exception as exc:
            last_error = exc

    raise RuntimeError(
        "No available GFS run was found after checking "
        f"{int(max_back_cycles) + 1} cycles back from {start_run_time}. "
        f"Last error: {last_error}"
    )


# -----------------------------------------------------------------------------
# GRIB / cfgrib helpers
# -----------------------------------------------------------------------------

def open_grib_dataset(file, filter_by_keys=None, *, delete_invalid=True):
    """Open a GRIB file with cfgrib without writing persistent .idx files.

    This avoids occasional Windows/cache problems with stale or missing cfgrib
    index files, especially for Herbie subset files.  It also validates that the
    decoded dataset contains real variables and a longitude coordinate.  If a
    transient network failure left a corrupt/non-matching Herbie subset on disk,
    the invalid file is removed so the next run_all retry can download it again.
    """
    from pathlib import Path
    import xarray as xr

    path = Path(file)
    backend_kwargs = {"indexpath": ""}
    if filter_by_keys is not None:
        backend_kwargs["filter_by_keys"] = filter_by_keys

    try:
        ds = xr.open_dataset(
            path,
            engine="cfgrib",
            backend_kwargs=backend_kwargs,
        )

        if len(ds.data_vars) == 0:
            raise RuntimeError(
                "No variables found in GRIB dataset. "
                f"coords={list(ds.coords)}, file={path}"
            )

        return normalize_longitude(ds)

    except Exception as exc:
        if delete_invalid and path.exists() and path.is_file():
            try:
                path.unlink()
            except Exception:
                pass

        raise RuntimeError(
            "Failed to open/validate GRIB dataset. "
            f"file={path}, filter_by_keys={filter_by_keys}, error={exc}"
        ) from exc


def download_field(H, search, attempts=4, delay_seconds=10):
    """Download a Herbie subset robustly and verify that the file exists.

    Remote GFS mirrors occasionally time out during subset downloads.  This
    helper retries transient failures before giving up.  It preserves the
    original behaviour for successful downloads, but makes daily unattended
    runs much less fragile.
    """
    from pathlib import Path
    import time

    last_error = None

    for attempt in range(1, int(attempts) + 1):
        try:
            file = H.download(search)
            path = Path(file)

            if not path.exists():
                raise FileNotFoundError(
                    f"Herbie returned a subset path that does not exist: {path}. "
                    f"Search pattern was: {search!r}."
                )

            if path.stat().st_size == 0:
                raise FileNotFoundError(
                    f"Herbie returned an empty subset file: {path}. "
                    f"Search pattern was: {search!r}."
                )

            return path

        except Exception as exc:
            last_error = exc
            message = str(exc)

            # If Herbie/cfgrib cached a failed index lookup, clear it before retrying.
            if hasattr(H, "index_as_dataframe"):
                try:
                    del H.index_as_dataframe
                except Exception:
                    pass

            if attempt >= int(attempts):
                break

            print(
                f"Download failed for {search!r} "
                f"(attempt {attempt}/{attempts}): {message}"
            )
            print(f"Retrying in {delay_seconds} seconds...")
            time.sleep(delay_seconds)

    raise RuntimeError(
        f"Download failed for {search!r} after {attempts} attempts. "
        f"Last error: {last_error}"
    )


def zero_precip_from_template(template_field):
    """Create a zero precipitation field on the same grid as a template field."""
    precip = template_field * 0.0
    precip.name = "precip_mm"
    precip.attrs["units"] = "mm"
    precip.attrs["long_name"] = "Accumulated precipitation; set to 0 mm for forecast hour 0"
    return precip


def download_first_available(H, searches, attempts=3, delay_seconds=8):
    """Try multiple Herbie regex searches and return the first successfully downloaded subset."""
    last_error = None
    for search in searches:
        try:
            return download_field(
                H,
                search,
                attempts=attempts,
                delay_seconds=delay_seconds,
            )
        except Exception as exc:
            last_error = exc
            print(f"Field search failed for {search!r}: {exc}")
    raise RuntimeError(
        f"None of the candidate field searches succeeded: {searches!r}. "
        f"Last error: {last_error}"
    )


def cin_magnitude(cin_field):
    """Return CIN as positive inhibition magnitude in J/kg.

    Some GRIB decoders expose CIN as positive inhibition, others may preserve
    the meteorological negative sign. For report thresholds we use magnitude.
    """
    import numpy as np

    cin = abs(cin_field)
    cin.name = "cin_jkg"
    cin.attrs["long_name"] = "Convective inhibition magnitude"
    cin.attrs["units"] = "J kg**-1"
    return cin
