from __future__ import annotations

import argparse
import json
import math
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import xarray as xr

from utils import REPORTS_DIR, DATA_DIR, resolve_run_time

OISST_BASE_URL = (
    "https://www.ncei.noaa.gov/data/sea-surface-temperature-optimum-interpolation/"
    "v2.1/access/avhrr"
)
NAO_DAILY_URL = "https://www.cpc.ncep.noaa.gov/products/precip/CWlink/pna/norm.daily.nao.index.b500101.current.ascii"
# CPC monthly teleconnection table. Kept optional: if unavailable, the workflow continues.
EA_MONTHLY_URL = "https://www.cpc.ncep.noaa.gov/data/teledoc/ea.data"

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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--run",
        type=str,
        default=None,
        help="Model run in UTC, e.g. '2026-06-24 00:00'. If omitted, a recent GFS cycle is used.",
    )
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=14,
        help="Maximum number of days to step back when the latest OISST file is not available.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=45,
        help="HTTP timeout in seconds.",
    )
    return parser.parse_args()


def run_id(run_time: str) -> str:
    dt = datetime.strptime(run_time, "%Y-%m-%d %H:%M")
    return f"gfs_{dt:%Y-%m-%d_%H}"


def oisst_url(day: datetime) -> str:
    return f"{OISST_BASE_URL}/{day:%Y%m}/oisst-avhrr-v02r01.{day:%Y%m%d}.nc"


def download_url(url: str, dst: Path, timeout: int = 45) -> Path:
    dst.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "Synoptics/1.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = response.read()
    if not data:
        raise RuntimeError(f"Downloaded file is empty: {url}")
    dst.write_bytes(data)
    return dst


def normalize_lon_dataset(ds: xr.Dataset) -> xr.Dataset:
    lon_name = "lon" if "lon" in ds.coords else "longitude"
    ds = ds.assign_coords({lon_name: ((ds[lon_name] + 180) % 360) - 180}).sortby(lon_name)
    return ds


def area_weighted_mean(field: xr.DataArray) -> float | None:
    field = field.squeeze(drop=True)
    lat_name = "lat" if "lat" in field.coords else "latitude"
    weights = np.cos(np.deg2rad(field[lat_name]))
    value = field.weighted(weights).mean(skipna=True).item()
    if value is None or not math.isfinite(float(value)):
        return None
    return round(float(value), 2)


def subset_region(field: xr.DataArray, region: dict[str, float]) -> xr.DataArray:
    lat_name = "lat" if "lat" in field.coords else "latitude"
    lon_name = "lon" if "lon" in field.coords else "longitude"
    return field.sel(
        {lat_name: slice(region["lat_max"], region["lat_min"]), lon_name: slice(region["lon_min"], region["lon_max"])}
    )


def compute_oisst_summary(path: Path, source_url: str) -> dict[str, Any]:
    ds = normalize_lon_dataset(xr.open_dataset(path))
    sst_name = "sst" if "sst" in ds.data_vars else None
    anom_name = "anom" if "anom" in ds.data_vars else None
    if sst_name is None or anom_name is None:
        raise KeyError(f"Required OISST variables not found. Available: {list(ds.data_vars)}")

    sst = ds[sst_name]
    anom = ds[anom_name]
    if "zlev" in sst.dims:
        sst = sst.isel(zlev=0)
    if "zlev" in anom.dims:
        anom = anom.isel(zlev=0)

    regions: dict[str, Any] = {}
    for key, region in REGIONS.items():
        regions[key] = {
            "label": region["label"],
            "sst_c_mean": area_weighted_mean(subset_region(sst, region)),
            "sst_anomaly_c_mean": area_weighted_mean(subset_region(anom, region)),
            "bounds": {k: region[k] for k in ["lat_min", "lat_max", "lon_min", "lon_max"]},
        }

    valid_date = None
    if "time" in ds.coords:
        try:
            valid_date = np.datetime_as_string(ds["time"].values[0], unit="D")
        except Exception:
            valid_date = None

    return {
        "status": "ok",
        "dataset": "NOAA OISST v2.1 AVHRR daily",
        "valid_date": valid_date,
        "source_url": source_url,
        "regions": regions,
    }


def load_latest_oisst(run_time: str, lookback_days: int, timeout: int) -> dict[str, Any]:
    run_dt = datetime.strptime(run_time, "%Y-%m-%d %H:%M")
    start_day = run_dt.date()
    last_error = None
    for offset in range(int(lookback_days) + 1):
        day = datetime.combine(start_day - timedelta(days=offset), datetime.min.time())
        url = oisst_url(day)
        dst = DATA_DIR / "oisst" / f"oisst-avhrr-v02r01.{day:%Y%m%d}.nc"
        try:
            if not dst.exists() or dst.stat().st_size == 0:
                download_url(url, dst, timeout=timeout)
            summary = compute_oisst_summary(dst, url)
            summary["requested_run_time"] = run_time
            summary["lookback_days_used"] = offset
            return summary
        except Exception as exc:
            last_error = str(exc)
            continue

    return {
        "status": "unavailable",
        "dataset": "NOAA OISST v2.1 AVHRR daily",
        "requested_run_time": run_time,
        "error": last_error,
        "regions": {},
    }


def parse_cpc_daily_index(text: str, target_date: datetime) -> dict[str, Any] | None:
    rows = []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue
        try:
            year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
            value = float(parts[3])
        except ValueError:
            continue
        date = datetime(year, month, day)
        if date <= target_date:
            rows.append((date, value))
    if not rows:
        return None
    date, value = rows[-1]
    return {"value": round(value, 2), "valid_date": date.strftime("%Y-%m-%d")}


def fetch_nao(run_time: str, timeout: int) -> dict[str, Any]:
    try:
        request = urllib.request.Request(NAO_DAILY_URL, headers={"User-Agent": "Synoptics/1.0"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            text = response.read().decode("utf-8", errors="replace")
        target_date = datetime.strptime(run_time, "%Y-%m-%d %H:%M")
        parsed = parse_cpc_daily_index(text, target_date)
        if parsed is None:
            raise RuntimeError("No valid NAO row found.")
        return {"status": "ok", "name": "NAO", "source_url": NAO_DAILY_URL, **parsed}
    except Exception as exc:
        return {"status": "unavailable", "name": "NAO", "source_url": NAO_DAILY_URL, "error": str(exc)}


def parse_cpc_monthly_table(text: str, run_time: str) -> dict[str, Any] | None:
    target = datetime.strptime(run_time, "%Y-%m-%d %H:%M")
    candidates = []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 13:
            continue
        try:
            year = int(parts[0])
            values = [float(v) for v in parts[1:13]]
        except ValueError:
            continue
        for month, value in enumerate(values, start=1):
            date = datetime(year, month, 1)
            if date <= target:
                candidates.append((date, value))
    if not candidates:
        return None
    date, value = candidates[-1]
    return {"value": round(value, 2), "valid_month": date.strftime("%Y-%m")}


def fetch_ea(run_time: str, timeout: int) -> dict[str, Any]:
    try:
        request = urllib.request.Request(EA_MONTHLY_URL, headers={"User-Agent": "Synoptics/1.0"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            text = response.read().decode("utf-8", errors="replace")
        parsed = parse_cpc_monthly_table(text, run_time)
        if parsed is None:
            raise RuntimeError("No valid EA row found.")
        return {"status": "ok", "name": "EA", "source_url": EA_MONTHLY_URL, **parsed}
    except Exception as exc:
        return {"status": "unavailable", "name": "EA", "source_url": EA_MONTHLY_URL, "error": str(exc)}


def interpret_sst_anomaly(value: float | None) -> str | None:
    if value is None:
        return None
    if value >= 2.0:
        return "strongly above normal"
    if value >= 1.0:
        return "above normal"
    if value <= -2.0:
        return "strongly below normal"
    if value <= -1.0:
        return "below normal"
    return "near normal"


def build_interpretation(ocean: dict[str, Any], teleconnections: dict[str, Any]) -> list[str]:
    lines = []
    regions = ocean.get("regions", {}) if ocean.get("status") == "ok" else {}
    med = regions.get("mediterranean", {})
    atl = regions.get("north_atlantic", {})
    med_anom = med.get("sst_anomaly_c_mean")
    atl_anom = atl.get("sst_anomaly_c_mean")
    if med_anom is not None:
        lines.append(
            f"Mediterranean SST anomaly is {med_anom:+.2f} °C ({interpret_sst_anomaly(med_anom)}); this is relevant for moisture supply and high-PWAT air masses."
        )
    if atl_anom is not None:
        lines.append(
            f"North Atlantic SST anomaly is {atl_anom:+.2f} °C ({interpret_sst_anomaly(atl_anom)}); this is a background factor for the storm track and jet-stream wave pattern."
        )
    nao = teleconnections.get("nao", {})
    if nao.get("status") == "ok":
        value = nao.get("value")
        if value is not None:
            if value <= -0.5:
                phase = "negative"
            elif value >= 0.5:
                phase = "positive"
            else:
                phase = "near-neutral"
            lines.append(f"NAO is {value:+.2f} ({phase}), useful as background guidance for Atlantic-European flow regime.")
    ea = teleconnections.get("ea", {})
    if ea.get("status") == "ok":
        value = ea.get("value")
        if value is not None:
            lines.append(f"EA monthly index is {value:+.2f}; use as low-frequency background, not as a deterministic daily trigger.")
    return lines


def main() -> None:
    args = parse_args()
    run_time = resolve_run_time(args.run)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    ocean = load_latest_oisst(run_time, args.lookback_days, args.timeout)
    teleconnections = {
        "nao": fetch_nao(run_time, args.timeout),
        "ea": fetch_ea(run_time, args.timeout),
    }
    output = {
        "model_run_time": run_time,
        "created_utc": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ocean": ocean,
        "teleconnections": teleconnections,
    }
    output["interpretation_hints_en"] = build_interpretation(ocean, teleconnections)

    out = REPORTS_DIR / f"climate_background_{run_id(run_time)}.json"
    out.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved: {out}")


if __name__ == "__main__":
    main()
