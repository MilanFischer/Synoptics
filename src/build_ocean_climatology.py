from __future__ import annotations

import argparse
import json
import math
import time
import urllib.request
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import xarray as xr

try:
    from utils import DATA_DIR, REPORTS_DIR
except Exception:
    ROOT = Path(__file__).resolve().parents[1]
    DATA_DIR = ROOT / "outputs" / "_manual" / "data"
    REPORTS_DIR = ROOT / "outputs" / "_manual" / "reports"


REGIONS = {
    "north_atlantic": {
        "label": "North Atlantic",
        "lat_min": 30.0,
        "lat_max": 65.0,
        "lon_min": -80.0,
        "lon_max": 0.0,
    },
    "mediterranean": {
        "label": "Mediterranean Sea",
        "lat_min": 30.0,
        "lat_max": 46.0,
        "lon_min": -6.0,
        "lon_max": 36.0,
    },
}


OISST_URL_TEMPLATES = [
    (
        "https://www.ncei.noaa.gov/data/"
        "sea-surface-temperature-optimum-interpolation/"
        "v2.1/access/avhrr/{yyyymm}/oisst-avhrr-v02r01.{yyyymmdd}.nc"
    ),
    (
        "https://www.ncei.noaa.gov/data/"
        "sea-surface-temperature-optimum-interpolation/"
        "v2.1/access/avhrr-only/{yyyymm}/oisst-avhrr-v02r01.{yyyymmdd}.nc"
    ),
    (
        "https://www.ncei.noaa.gov/data/"
        "sea-surface-temperature-optimum-interpolation/"
        "v2/access/avhrr/{yyyymm}/oisst-avhrr-v02r01.{yyyymmdd}.nc"
    ),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a long-term regional NOAA OISST time series for Synoptics. "
            "The script downloads daily OISST NetCDF files, computes area-weighted "
            "regional means, and stores a compact CSV table for percentile/rank analysis."
        )
    )
    parser.add_argument("--start", default="2000-01-01", help="Start date, YYYY-MM-DD.")
    parser.add_argument("--end", default=None, help="End date, YYYY-MM-DD. Defaults to today UTC.")
    parser.add_argument(
        "--output",
        default=None,
        help="Output CSV path. Default: outputs/_manual/data/ocean_climatology/oisst_region_timeseries.csv",
    )
    parser.add_argument(
        "--summary-output",
        default=None,
        help="Summary JSON path. Default: outputs/_manual/reports/ocean_climatology_summary.json",
    )
    parser.add_argument(
        "--current-json",
        default=None,
        help=(
            "Optional climate_background_*.json from download_ocean_teleconnections.py. "
            "If provided, the script computes percentiles and ranks for the current SST anomalies."
        ),
    )
    parser.add_argument(
        "--season-window-days",
        type=int,
        default=15,
        help="Calendar-day window for seasonal percentile comparison, e.g. +/-15 days.",
    )
    parser.add_argument(
        "--cache-dir",
        default=None,
        help="Temporary NetCDF cache directory.",
    )
    parser.add_argument("--keep-netcdf", action="store_true", help="Keep downloaded daily NetCDF files.")
    parser.add_argument("--force", action="store_true", help="Recompute dates already present in the output CSV.")
    parser.add_argument("--sleep", type=float, default=0.15, help="Pause between HTTP downloads in seconds.")
    parser.add_argument("--timeout", type=int, default=60, help="HTTP timeout in seconds.")
    parser.add_argument("--max-days", type=int, default=None, help="Optional limit for testing.")
    parser.add_argument(
        "--save-every",
        type=int,
        default=1,
        help="Save progress every N successfully processed days. Default: 1.",
    )
    parser.add_argument("--debug", action="store_true", help="Print detailed progress information.")
    return parser.parse_args()


def daterange(start: date, end: date) -> list[date]:
    if end < start:
        raise ValueError(f"End date {end} is before start date {start}.")
    days: list[date] = []
    current = start
    while current <= end:
        days.append(current)
        current += timedelta(days=1)
    return days


def oisst_url_candidates(day: date) -> list[str]:
    yyyymm = f"{day:%Y%m}"
    yyyymmdd = f"{day:%Y%m%d}"
    return [tmpl.format(yyyymm=yyyymm, yyyymmdd=yyyymmdd) for tmpl in OISST_URL_TEMPLATES]


def download_url(url: str, dst: Path, timeout: int) -> Path:
    dst.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "Synoptics/1.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = response.read()
    if not data:
        raise RuntimeError(f"Downloaded file is empty: {url}")
    dst.write_bytes(data)
    return dst


def get_oisst_file(day: date, cache_dir: Path, timeout: int, debug: bool) -> tuple[Path, str]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    dst = cache_dir / f"oisst-avhrr-v02r01.{day:%Y%m%d}.nc"
    if dst.exists() and dst.stat().st_size > 0:
        return dst, "local-cache"

    errors: list[str] = []
    for url in oisst_url_candidates(day):
        try:
            if debug:
                print(f"Downloading OISST {day}: {url}")
            download_url(url, dst, timeout=timeout)
            return dst, url
        except Exception as exc:
            errors.append(f"{url}: {exc}")
            if dst.exists() and dst.stat().st_size == 0:
                dst.unlink(missing_ok=True)

    raise RuntimeError(" | ".join(errors))


def coord_name(obj: xr.Dataset | xr.DataArray, candidates: tuple[str, ...]) -> str:
    for name in candidates:
        if name in obj.coords or name in obj.dims:
            return name
    raise KeyError(f"None of coordinates/dimensions found: {candidates}")


def normalize_longitudes(field: xr.DataArray) -> xr.DataArray:
    lon_name = coord_name(field, ("lon", "longitude"))
    lon = field[lon_name]
    if float(lon.max()) > 180.0:
        field = field.assign_coords({lon_name: ((lon + 180.0) % 360.0) - 180.0}).sortby(lon_name)
    return field


def subset_region(field: xr.DataArray, region: dict[str, float]) -> xr.DataArray:
    field = normalize_longitudes(field)
    lat_name = coord_name(field, ("lat", "latitude"))
    lon_name = coord_name(field, ("lon", "longitude"))

    lat_values = field[lat_name].values
    if float(lat_values[0]) <= float(lat_values[-1]):
        lat_slice = slice(region["lat_min"], region["lat_max"])
    else:
        lat_slice = slice(region["lat_max"], region["lat_min"])

    return field.sel({lat_name: lat_slice, lon_name: slice(region["lon_min"], region["lon_max"])})


def area_weighted_mean(field: xr.DataArray) -> float | None:
    field = field.squeeze(drop=True)
    if field.size == 0:
        return None
    lat_name = coord_name(field, ("lat", "latitude"))
    weights = np.cos(np.deg2rad(field[lat_name]))
    value = field.weighted(weights).mean(skipna=True).item()
    if value is None or not math.isfinite(float(value)):
        return None
    return round(float(value), 4)


def valid_count(field: xr.DataArray) -> int:
    return int(field.count().item())


def compute_day(path: Path, day: date, source_url: str) -> list[dict[str, Any]]:
    with xr.open_dataset(path) as ds:
        if "sst" not in ds.data_vars or "anom" not in ds.data_vars:
            raise KeyError(f"Required variables sst/anom not found. Available: {list(ds.data_vars)}")

        sst = ds["sst"]
        anom = ds["anom"]

        for dim_name in ("time", "zlev", "depth"):
            if dim_name in sst.dims:
                sst = sst.isel({dim_name: 0})
            if dim_name in anom.dims:
                anom = anom.isel({dim_name: 0})

        rows: list[dict[str, Any]] = []
        for key, region in REGIONS.items():
            sst_region = subset_region(sst, region)
            anom_region = subset_region(anom, region)
            rows.append(
                {
                    "date": day.isoformat(),
                    "year": day.year,
                    "month": day.month,
                    "day": day.day,
                    "day_of_year": day.timetuple().tm_yday,
                    "region": key,
                    "label": region["label"],
                    "sst_c_mean": area_weighted_mean(sst_region),
                    "sst_anomaly_c_mean": area_weighted_mean(anom_region),
                    "grid_points_used": valid_count(sst_region),
                    "source_url": source_url,
                }
            )
        return rows


def load_existing(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def save_timeseries(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not df.empty:
        df = df.sort_values(["date", "region"]).reset_index(drop=True)
    df.to_csv(path, index=False)


def circular_day_distance(a: int, b: int) -> int:
    diff = abs(a - b)
    return min(diff, 366 - diff)


def percentile_rank(values: np.ndarray, current: float) -> float | None:
    values = values[np.isfinite(values)]
    if len(values) == 0 or not math.isfinite(current):
        return None
    return round(float((values <= current).sum() / len(values) * 100.0), 2)


def descending_rank(values: np.ndarray, current: float) -> int | None:
    values = values[np.isfinite(values)]
    if len(values) == 0 or not math.isfinite(current):
        return None
    return int((values > current).sum() + 1)


def build_current_summary(
    timeseries: pd.DataFrame,
    current_json_path: Path | None,
    season_window_days: int,
) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "created_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "timeseries_rows": int(len(timeseries)),
        "date_min": None if timeseries.empty else str(timeseries["date"].min()),
        "date_max": None if timeseries.empty else str(timeseries["date"].max()),
        "season_window_days": season_window_days,
        "regions": {},
    }

    if not timeseries.empty:
        for region in sorted(timeseries["region"].dropna().unique()):
            sub = timeseries[timeseries["region"] == region].copy()
            anom = sub["sst_anomaly_c_mean"].astype(float).to_numpy()
            summary["regions"][region] = {
                "count": int(np.isfinite(anom).sum()),
                "anomaly_mean_c": round(float(np.nanmean(anom)), 3) if np.isfinite(anom).any() else None,
                "anomaly_max_c": round(float(np.nanmax(anom)), 3) if np.isfinite(anom).any() else None,
                "anomaly_min_c": round(float(np.nanmin(anom)), 3) if np.isfinite(anom).any() else None,
            }

    if current_json_path is None:
        return summary

    current = json.loads(current_json_path.read_text(encoding="utf-8"))
    ocean = current.get("ocean", {})
    valid_date = ocean.get("valid_date")
    if not valid_date:
        summary["current_json"] = {"path": str(current_json_path), "status": "no ocean valid_date found"}
        return summary

    current_day = datetime.strptime(valid_date, "%Y-%m-%d").date()
    current_doy = current_day.timetuple().tm_yday
    summary["current_json"] = {
        "path": str(current_json_path),
        "ocean_valid_date": valid_date,
        "dataset": ocean.get("dataset"),
        "lookback_days_used": ocean.get("lookback_days_used"),
        "regions": {},
    }

    for region_key, region_data in ocean.get("regions", {}).items():
        current_value = region_data.get("sst_anomaly_c_mean")
        if current_value is None:
            continue

        region_ts = timeseries[timeseries["region"] == region_key].copy()
        if region_ts.empty:
            continue

        region_ts["doy_distance"] = region_ts["day_of_year"].apply(
            lambda x: circular_day_distance(int(x), current_doy)
        )
        seasonal = region_ts[region_ts["doy_distance"] <= season_window_days]

        all_values = region_ts["sst_anomaly_c_mean"].astype(float).to_numpy()
        seasonal_values = seasonal["sst_anomaly_c_mean"].astype(float).to_numpy()

        summary["current_json"]["regions"][region_key] = {
            "current_sst_anomaly_c_mean": round(float(current_value), 3),
            "all_days_percentile": percentile_rank(all_values, float(current_value)),
            "all_days_rank_highest": descending_rank(all_values, float(current_value)),
            "all_days_count": int(np.isfinite(all_values).sum()),
            "seasonal_percentile": percentile_rank(seasonal_values, float(current_value)),
            "seasonal_rank_highest": descending_rank(seasonal_values, float(current_value)),
            "seasonal_count": int(np.isfinite(seasonal_values).sum()),
            "season_window_days": season_window_days,
        }

    return summary


def main() -> None:
    args = parse_args()

    start_date = datetime.strptime(args.start, "%Y-%m-%d").date()
    end_date = datetime.strptime(args.end, "%Y-%m-%d").date() if args.end else datetime.now(UTC).date()

    output = (
        Path(args.output)
        if args.output
        else DATA_DIR / "ocean_climatology" / "oisst_region_timeseries.csv"
    )
    summary_output = (
        Path(args.summary_output)
        if args.summary_output
        else REPORTS_DIR / "ocean_climatology_summary.json"
    )
    cache_dir = (
        Path(args.cache_dir)
        if args.cache_dir
        else DATA_DIR / "ocean_climatology" / "netcdf_cache"
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    summary_output.parent.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)

    existing = load_existing(output)
    already_done: set[tuple[str, str]] = set()
    if not existing.empty and not args.force:
        already_done = set(zip(existing["date"].astype(str), existing["region"].astype(str)))

    days = daterange(start_date, end_date)
    if args.max_days is not None:
        days = days[: int(args.max_days)]

    combined = existing.copy()
    buffer_rows: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    successful_days_since_save = 0

    def flush_progress() -> None:
        nonlocal combined, buffer_rows, successful_days_since_save
        if not buffer_rows:
            if combined.empty and not output.exists():
                save_timeseries(combined, output)
            return

        new_df = pd.DataFrame(buffer_rows)
        combined = pd.concat([combined, new_df], ignore_index=True) if not combined.empty else new_df
        combined = combined.drop_duplicates(subset=["date", "region"], keep="last")
        save_timeseries(combined, output)

        buffer_rows = []
        successful_days_since_save = 0
        if args.debug:
            print(f"  progress saved: {output} ({len(combined)} rows)")

    try:
        for index, day in enumerate(days, start=1):
            if not args.force and all((day.isoformat(), region_key) in already_done for region_key in REGIONS):
                if args.debug:
                    print(f"[{index}/{len(days)}] skip existing {day}")
                continue

            if args.debug:
                print(f"[{index}/{len(days)}] processing {day}")

            nc_path: Path | None = None
            source_url = ""
            try:
                nc_path, source_url = get_oisst_file(day, cache_dir, args.timeout, args.debug)
                rows = compute_day(nc_path, day, source_url)
                buffer_rows.extend(rows)
                successful_days_since_save += 1

                if args.debug:
                    for row in rows:
                        print(
                            f"  {row['region']}: "
                            f"SST={row['sst_c_mean']} °C, "
                            f"anom={row['sst_anomaly_c_mean']} °C, "
                            f"n={row['grid_points_used']}"
                        )

                if successful_days_since_save >= max(1, int(args.save_every)):
                    flush_progress()

            except Exception as exc:
                failures.append({"date": day.isoformat(), "error": str(exc)})
                if args.debug:
                    print(f"  FAILED {day}: {exc}")
            finally:
                if nc_path is not None and not args.keep_netcdf:
                    try:
                        nc_path.unlink(missing_ok=True)
                    except Exception:
                        pass

            if args.sleep > 0:
                time.sleep(float(args.sleep))
    finally:
        # Always save finished work even if the run is interrupted with Ctrl+C.
        flush_progress()

    if combined.empty and not output.exists():
        save_timeseries(combined, output)

    current_json = Path(args.current_json) if args.current_json else None
    summary = build_current_summary(combined, current_json, args.season_window_days)
    summary["output_csv"] = str(output)
    summary["failed_days_count"] = len(failures)
    summary["failed_days_sample"] = failures[:20]

    summary_output.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Saved timeseries: {output}")
    print(f"Saved summary: {summary_output}")
    print(f"Rows: {len(combined)}")
    if failures:
        print(f"Failed days: {len(failures)}. See summary JSON for sample errors.")


if __name__ == "__main__":
    main()
