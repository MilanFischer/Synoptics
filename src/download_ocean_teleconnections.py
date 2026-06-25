from __future__ import annotations

import argparse
import json
import math
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import xarray as xr

from utils import DATA_DIR, REPORTS_DIR, resolve_run_time

# =============================================================================
# Ocean and teleconnection background for Synoptics
# =============================================================================
# Production version:
# - OISST is downloaded primarily as daily NetCDF files from the NCEI archive.
# - Newer days may legitimately return 404 because OISST is delayed; the script
#   silently steps back until a valid file is found. Use --debug to see attempts.
# - THREDDS/OPeNDAP is retained only as a fallback.
# - ERDDAP is intentionally not used here because it proved brittle for this use.
# =============================================================================

OISST_DIRECT_URL_TEMPLATES = [
    "https://www.ncei.noaa.gov/data/sea-surface-temperature-optimum-interpolation/v2.1/access/avhrr/{yyyymm}/oisst-avhrr-v02r01.{yyyymmdd}.nc",
    "https://www.ncei.noaa.gov/data/sea-surface-temperature-optimum-interpolation/v2.1/access/avhrr-only/{yyyymm}/oisst-avhrr-v02r01.{yyyymmdd}.nc",
    "https://www.ncei.noaa.gov/data/sea-surface-temperature-optimum-interpolation/v2/access/avhrr/{yyyymm}/oisst-avhrr-v02r01.{yyyymmdd}.nc",
]

OISST_THREDDS_BEST_URL = (
    "https://www.ncei.noaa.gov/thredds/dodsC/ncFC/"
    "fc-oisst-daily-avhrr-only-dly/"
    "OISST_Daily_AVHRR-only_Feature_Collection_best.ncd"
)
OISST_DATASET_LABEL = "NOAA OISST v2.1 AVHRR daily"

NAO_DAILY_URLS = [
    "https://ftp.cpc.ncep.noaa.gov/cwlinks/norm.daily.nao.index.b500101.current.ascii",
    "https://www.cpc.ncep.noaa.gov/products/precip/CWlink/pna/norm.daily.nao.index.b500101.current.ascii",
]
NAO_MONTHLY_URLS = [
    "https://www.cpc.ncep.noaa.gov/products/precip/CWlink/pna/norm.nao.monthly.b5001.current.ascii",
    "https://www.cpc.ncep.noaa.gov/products/precip/CWlink/pna/norm.nao.monthly.b5001.current.ascii.table",
]
EA_MONTHLY_URLS = [
    "https://ftp.cpc.ncep.noaa.gov/wd52dg/data/indices/ea_index.tim",
    "https://www.cpc.ncep.noaa.gov/data/indices/ea_index.tim",
    "https://ftp.cpc.ncep.noaa.gov/cwlinks/norm.ea.monthly.b5001.current.ascii",
    "https://www.cpc.ncep.noaa.gov/products/precip/CWlink/pna/norm.ea.monthly.b5001.current.ascii",
]

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
        help="Model run in UTC, e.g. '2026-06-24 12:00'. If omitted, a recent GFS cycle is used.",
    )
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=30,
        help="Maximum number of days to step back from the model run for OISST.",
    )
    parser.add_argument("--timeout", type=int, default=45, help="HTTP timeout in seconds.")
    parser.add_argument("--debug", action="store_true", help="Print OISST diagnostic information.")
    return parser.parse_args()


def run_id(run_time: str) -> str:
    dt = datetime.strptime(run_time, "%Y-%m-%d %H:%M")
    return f"gfs_{dt:%Y-%m-%d_%H}"


def http_get_bytes(url: str, timeout: int = 45) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "Synoptics/1.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
    if not raw:
        raise RuntimeError(f"Downloaded response is empty: {url}")
    return raw


def http_get_text(url: str, timeout: int = 45) -> str:
    return http_get_bytes(url, timeout=timeout).decode("utf-8", errors="replace")


def _coord_name(obj: xr.Dataset | xr.DataArray, candidates: tuple[str, ...]) -> str:
    for name in candidates:
        if name in obj.coords or name in obj.dims:
            return name
    raise KeyError(f"None of coordinates/dimensions found: {candidates}")


def _var_name(ds: xr.Dataset, candidates: tuple[str, ...]) -> str:
    for name in candidates:
        if name in ds.data_vars:
            return name
    raise KeyError(f"None of variables found: {candidates}. Available: {list(ds.data_vars)}")


def _normalize_longitudes(field: xr.DataArray) -> xr.DataArray:
    lon_name = _coord_name(field, ("lon", "longitude"))
    lon = field[lon_name]
    if float(lon.max()) > 180.0:
        field = field.assign_coords({lon_name: ((lon + 180.0) % 360.0) - 180.0}).sortby(lon_name)
    return field


def _subset_region(field: xr.DataArray, region: dict[str, float]) -> xr.DataArray:
    field = _normalize_longitudes(field)
    lat_name = _coord_name(field, ("lat", "latitude"))
    lon_name = _coord_name(field, ("lon", "longitude"))

    lat_values = field[lat_name].values
    if float(lat_values[0]) <= float(lat_values[-1]):
        lat_slice = slice(region["lat_min"], region["lat_max"])
    else:
        lat_slice = slice(region["lat_max"], region["lat_min"])

    return field.sel({lat_name: lat_slice, lon_name: slice(region["lon_min"], region["lon_max"])})


def _area_weighted_mean(field: xr.DataArray) -> float | None:
    field = field.squeeze(drop=True)
    if field.size == 0:
        return None
    lat_name = _coord_name(field, ("lat", "latitude"))
    weights = np.cos(np.deg2rad(field[lat_name]))
    try:
        value = field.weighted(weights).mean(skipna=True).compute().item()
    except Exception:
        value = field.weighted(weights).mean(skipna=True).item()
    if value is None or not math.isfinite(float(value)):
        return None
    return round(float(value), 2)


def _valid_count(field: xr.DataArray) -> int:
    try:
        return int(field.count().compute().item())
    except Exception:
        return int(field.count().item())


def _prepare_sst_anom(ds: xr.Dataset, selected_time: Any | None = None) -> tuple[xr.DataArray, xr.DataArray, str | None]:
    sst_name = _var_name(ds, ("sst", "analysed_sst", "sea_surface_temperature"))
    anom_name = _var_name(ds, ("anom", "sst_anomaly", "sst_anom"))
    time_name = "time" if "time" in ds.coords or "time" in ds.dims else None

    sst = ds[sst_name]
    anom = ds[anom_name]
    valid_date = None

    if selected_time is not None and time_name and time_name in sst.dims:
        sst = sst.sel({time_name: selected_time})
        anom = anom.sel({time_name: selected_time})
        valid_date = np.datetime_as_string(np.datetime64(selected_time), unit="D")
    elif time_name and time_name in sst.dims:
        sst = sst.isel({time_name: 0})
        anom = anom.isel({time_name: 0})
        try:
            valid_date = np.datetime_as_string(ds[time_name].values[0], unit="D")
        except Exception:
            valid_date = None

    for depth_name in ("depth", "zlev", "lev"):
        if depth_name in sst.dims:
            sst = sst.isel({depth_name: 0})
        if depth_name in anom.dims:
            anom = anom.isel({depth_name: 0})

    return sst, anom, valid_date


def _summarize_regions(sst: xr.DataArray, anom: xr.DataArray, *, debug: bool = False) -> tuple[dict[str, Any], int]:
    regions: dict[str, Any] = {}
    total_valid = 0

    for key, region in REGIONS.items():
        sst_region = _subset_region(sst, region)
        anom_region = _subset_region(anom, region)
        valid = _valid_count(sst_region)
        total_valid += valid

        item: dict[str, Any] = {
            "label": region["label"],
            "sst_c_mean": _area_weighted_mean(sst_region),
            "sst_anomaly_c_mean": _area_weighted_mean(anom_region),
            "bounds": {k: region[k] for k in ["lat_min", "lat_max", "lon_min", "lon_max"]},
            "grid_points_used": valid,
        }

        if valid > 0:
            lat_name = _coord_name(sst_region, ("lat", "latitude"))
            lon_name = _coord_name(sst_region, ("lon", "longitude"))
            item.update(
                {
                    "lat_min_selected": round(float(sst_region[lat_name].min()), 3),
                    "lat_max_selected": round(float(sst_region[lat_name].max()), 3),
                    "lon_min_selected": round(float(sst_region[lon_name].min()), 3),
                    "lon_max_selected": round(float(sst_region[lon_name].max()), 3),
                }
            )

        regions[key] = item

        if debug:
            print(f"\nREGION DEBUG: {key}")
            print("grid points:", valid)
            print("sst mean:", item["sst_c_mean"])
            print("anom mean:", item["sst_anomaly_c_mean"])
            if valid > 0:
                print("lat selected:", item["lat_min_selected"], item["lat_max_selected"])
                print("lon selected:", item["lon_min_selected"], item["lon_max_selected"])

    return regions, total_valid


def _debug_dataset(ds: xr.Dataset, source: str) -> None:
    print("\n=== DATASET DEBUG ===")
    print("source:", source)
    print("coords:", list(ds.coords))
    print("dims:", dict(ds.sizes))
    print("data variables:", list(ds.data_vars))
    for coord in ("time", "lat", "latitude", "lon", "longitude", "depth", "zlev"):
        if coord in ds.coords:
            values = ds[coord].values
            try:
                print(f"{coord} first/last:", values[0], values[-1])
            except Exception:
                print(f"{coord}:", values)


def _candidate_days(run_time: str, lookback_days: int):
    target_dt = datetime.strptime(run_time, "%Y-%m-%d %H:%M")
    for offset in range(int(lookback_days) + 1):
        yield offset, target_dt - timedelta(days=offset)


def load_oisst_direct(run_time: str, lookback_days: int, timeout: int, *, debug: bool = False) -> dict[str, Any]:
    errors: list[str] = []

    for offset, day_dt in _candidate_days(run_time, lookback_days):
        yyyymm = day_dt.strftime("%Y%m")
        yyyymmdd = day_dt.strftime("%Y%m%d")

        for template in OISST_DIRECT_URL_TEMPLATES:
            url = template.format(yyyymm=yyyymm, yyyymmdd=yyyymmdd)
            local = DATA_DIR / "oisst" / f"oisst-avhrr-v02r01.{yyyymmdd}.nc"

            try:
                if not local.exists() or local.stat().st_size == 0:
                    if debug:
                        print("Trying direct OISST URL:", url)
                    local.parent.mkdir(parents=True, exist_ok=True)
                    local.write_bytes(http_get_bytes(url, timeout=timeout))

                ds = xr.open_dataset(local, decode_times=True)
                if debug:
                    _debug_dataset(ds, str(local))

                sst, anom, valid_date = _prepare_sst_anom(ds)
                regions, total_valid = _summarize_regions(sst, anom, debug=debug)

                if total_valid > 0:
                    return {
                        "status": "ok",
                        "dataset": f"{OISST_DATASET_LABEL} via direct NetCDF file",
                        "valid_date": valid_date or day_dt.strftime("%Y-%m-%d"),
                        "requested_run_time": run_time,
                        "lookback_days_used": offset,
                        "source_url": url,
                        "regions": regions,
                    }

                raise RuntimeError("NetCDF opened, but target regions contain no valid SST grid points.")

            except Exception as exc:
                msg = f"{day_dt:%Y-%m-%d} {url}: {exc}"
                errors.append(msg)
                if debug:
                    print("Direct OISST candidate failed:", msg)
                continue

    raise RuntimeError(" | ".join(errors[-12:]))


def load_oisst_thredds(run_time: str, lookback_days: int, *, debug: bool = False) -> dict[str, Any]:
    ds = xr.open_dataset(OISST_THREDDS_BEST_URL, decode_times=True)
    if debug:
        _debug_dataset(ds, OISST_THREDDS_BEST_URL)

    time_name = _coord_name(ds, ("time",))
    target = np.datetime64(datetime.strptime(run_time, "%Y-%m-%d %H:%M"))
    earliest = target - np.timedelta64(int(lookback_days), "D")
    times = ds[time_name].values
    valid_times = times[(times <= target) & (times >= earliest)]
    target_day = np.datetime64(datetime.strptime(run_time, "%Y-%m-%d %H:%M").date())
    errors: list[str] = []

    for selected_time in valid_times[::-1]:
        selected_day = np.datetime_as_string(selected_time, unit="D")
        lookback_used = int((target_day - np.datetime64(selected_day)) / np.timedelta64(1, "D"))
        try:
            sst, anom, _ = _prepare_sst_anom(ds, selected_time=selected_time)
            regions, total_valid = _summarize_regions(sst, anom, debug=debug)
            if total_valid > 0:
                return {
                    "status": "ok",
                    "dataset": f"{OISST_DATASET_LABEL} via NCEI THREDDS/OPeNDAP",
                    "valid_date": selected_day,
                    "requested_run_time": run_time,
                    "lookback_days_used": lookback_used,
                    "source_url": OISST_THREDDS_BEST_URL,
                    "regions": regions,
                }
            errors.append(f"{selected_day}: no valid SST grid points")
        except Exception as exc:
            errors.append(f"{selected_day}: {exc}")

    raise RuntimeError(" | ".join(errors[-12:]) if errors else "No THREDDS time candidates inside lookback window.")


def load_latest_oisst(run_time: str, lookback_days: int, timeout: int, *, debug: bool = False) -> dict[str, Any]:
    errors: list[str] = []

    try:
        return load_oisst_direct(run_time, lookback_days, timeout, debug=debug)
    except Exception as exc:
        errors.append(f"direct: {exc}")
        if debug:
            print("OISST direct method failed:", exc)

    try:
        return load_oisst_thredds(run_time, lookback_days, debug=debug)
    except Exception as exc:
        errors.append(f"thredds: {exc}")
        if debug:
            print("OISST THREDDS method failed:", exc)

    return {
        "status": "unavailable",
        "dataset": OISST_DATASET_LABEL,
        "requested_run_time": run_time,
        "error": " || ".join(errors),
        "regions": {},
    }


def parse_cpc_daily_index(text: str, target_date: datetime) -> dict[str, Any] | None:
    rows: list[tuple[datetime, float]] = []
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
        if date <= target_date and math.isfinite(value):
            rows.append((date, value))
    if not rows:
        return None
    date, value = rows[-1]
    return {"value": round(value, 2), "valid_date": date.strftime("%Y-%m-%d")}


def parse_monthly_index_table(text: str, run_time: str) -> dict[str, Any] | None:
    target = datetime.strptime(run_time, "%Y-%m-%d %H:%M")
    candidates: list[tuple[datetime, float]] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.replace(",", " ").split()

        if len(parts) >= 13:
            try:
                year = int(float(parts[0]))
                values = [float(v) for v in parts[1:13]]
            except ValueError:
                pass
            else:
                for month, value in enumerate(values, start=1):
                    date = datetime(year, month, 1)
                    if date <= target and math.isfinite(value):
                        candidates.append((date, value))
                continue

        if len(parts) >= 3:
            try:
                year = int(float(parts[0]))
                month = int(float(parts[1]))
                value = float(parts[2])
                date = datetime(year, month, 1)
            except ValueError:
                pass
            else:
                if date <= target and math.isfinite(value):
                    candidates.append((date, value))
                continue

        if len(parts) >= 2 and "-" in parts[0]:
            try:
                date = datetime.strptime(parts[0][:7], "%Y-%m")
                value = float(parts[1])
            except ValueError:
                continue
            if date <= target and math.isfinite(value):
                candidates.append((date, value))

    if not candidates:
        return None
    date, value = sorted(candidates, key=lambda item: item[0])[-1]
    return {"value": round(value, 2), "valid_month": date.strftime("%Y-%m")}


def fetch_first_parsed(urls: list[str], parser, timeout: int, *parser_args) -> tuple[dict[str, Any], str]:
    errors = []
    for url in urls:
        try:
            text = http_get_text(url, timeout=timeout)
            parsed = parser(text, *parser_args)
            if parsed is None:
                raise RuntimeError("No valid rows found.")
            return parsed, url
        except Exception as exc:
            errors.append(f"{url}: {exc}")
    raise RuntimeError(" | ".join(errors))


def fetch_nao(run_time: str, timeout: int) -> dict[str, Any]:
    target_date = datetime.strptime(run_time, "%Y-%m-%d %H:%M")
    try:
        parsed, url = fetch_first_parsed(NAO_DAILY_URLS, parse_cpc_daily_index, timeout, target_date)
        return {"status": "ok", "name": "NAO", "frequency": "daily", "source_url": url, **parsed}
    except Exception as daily_exc:
        try:
            parsed, url = fetch_first_parsed(NAO_MONTHLY_URLS, parse_monthly_index_table, timeout, run_time)
            return {
                "status": "ok",
                "name": "NAO",
                "frequency": "monthly_fallback",
                "source_url": url,
                "note": "Daily NAO unavailable; monthly NAO fallback used.",
                **parsed,
            }
        except Exception as monthly_exc:
            return {
                "status": "unavailable",
                "name": "NAO",
                "source_urls_tried": NAO_DAILY_URLS + NAO_MONTHLY_URLS,
                "error": f"daily: {daily_exc}; monthly fallback: {monthly_exc}",
            }


def fetch_ea(run_time: str, timeout: int) -> dict[str, Any]:
    try:
        parsed, url = fetch_first_parsed(EA_MONTHLY_URLS, parse_monthly_index_table, timeout, run_time)
        return {"status": "ok", "name": "EA", "frequency": "monthly", "source_url": url, **parsed}
    except Exception as exc:
        return {"status": "unavailable", "name": "EA", "source_urls_tried": EA_MONTHLY_URLS, "error": str(exc)}


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
    lines: list[str] = []
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
            suffix = " Monthly fallback value used." if nao.get("frequency") == "monthly_fallback" else ""
            lines.append(f"NAO is {value:+.2f} ({phase}), useful as background guidance for Atlantic-European flow regime.{suffix}")

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

    ocean = load_latest_oisst(run_time, args.lookback_days, args.timeout, debug=args.debug)
    teleconnections = {
        "nao": fetch_nao(run_time, args.timeout),
        "ea": fetch_ea(run_time, args.timeout),
    }

    output = {
        "model_run_time": run_time,
        "created_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ocean": ocean,
        "teleconnections": teleconnections,
    }
    output["interpretation_hints_en"] = build_interpretation(ocean, teleconnections)

    out = REPORTS_DIR / f"climate_background_{run_id(run_time)}.json"
    out.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved: {out}")


if __name__ == "__main__":
    main()
