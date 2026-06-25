from __future__ import annotations

import argparse
import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

try:
    from utils import DATA_DIR, REPORTS_DIR
except Exception:
    ROOT = Path(__file__).resolve().parents[1]
    DATA_DIR = ROOT / "outputs" / "_manual" / "data"
    REPORTS_DIR = ROOT / "outputs" / "_manual" / "reports"


DEFAULT_TIMESERIES = DATA_DIR / "ocean_climatology" / "oisst_region_timeseries.csv"
DEFAULT_CURRENT_JSON = REPORTS_DIR / "climate_background_gfs_2026-06-24_12.json"
DEFAULT_OUTPUT_JSON = REPORTS_DIR / "ocean_climatology_analysis.json"
DEFAULT_OUTPUT_CSV = DATA_DIR / "ocean_climatology" / "ocean_climatology_current_ranks.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Analyze regional NOAA OISST climatology time series and compare current "
            "SST anomalies against the historical distribution."
        )
    )
    parser.add_argument("--timeseries", default=str(DEFAULT_TIMESERIES))
    parser.add_argument("--current-json", default=str(DEFAULT_CURRENT_JSON))
    parser.add_argument("--output-json", default=str(DEFAULT_OUTPUT_JSON))
    parser.add_argument("--output-csv", default=str(DEFAULT_OUTPUT_CSV))
    parser.add_argument("--season-window-days", type=int, default=15)
    parser.add_argument("--baseline-start", default=None)
    parser.add_argument("--baseline-end", default=None)
    parser.add_argument("--exclude-current-date", action="store_true")
    parser.add_argument("--debug", action="store_true")
    return parser.parse_args()


def load_timeseries(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Timeseries CSV not found: {path}")

    df = pd.read_csv(path)
    required = {"date", "region", "label", "sst_c_mean", "sst_anomaly_c_mean", "grid_points_used"}
    missing = required - set(df.columns)
    if missing:
        raise KeyError(f"Missing columns in {path}: {sorted(missing)}")

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["sst_c_mean"] = pd.to_numeric(df["sst_c_mean"], errors="coerce")
    df["sst_anomaly_c_mean"] = pd.to_numeric(df["sst_anomaly_c_mean"], errors="coerce")
    df["grid_points_used"] = pd.to_numeric(df["grid_points_used"], errors="coerce")

    if "day_of_year" not in df.columns:
        df["day_of_year"] = df["date"].dt.dayofyear
    else:
        df["day_of_year"] = pd.to_numeric(df["day_of_year"], errors="coerce")

    return df.dropna(subset=["date", "region", "sst_anomaly_c_mean"]).sort_values(["date", "region"]).reset_index(drop=True)


def load_current_background(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Current climate background JSON not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def circular_day_distance(day_a: int, day_b: int) -> int:
    diff = abs(int(day_a) - int(day_b))
    return min(diff, 366 - diff)


def percentile_rank(values: pd.Series, current: float) -> float | None:
    arr = pd.to_numeric(values, errors="coerce").dropna().to_numpy(dtype=float)
    if arr.size == 0 or not math.isfinite(current):
        return None
    return round(float((arr <= current).sum() / arr.size * 100.0), 2)


def rank_highest(values: pd.Series, current: float) -> int | None:
    arr = pd.to_numeric(values, errors="coerce").dropna().to_numpy(dtype=float)
    if arr.size == 0 or not math.isfinite(current):
        return None
    return int((arr > current).sum() + 1)


def format_date(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    return pd.Timestamp(value).strftime("%Y-%m-%d")


def summarize_distribution(df: pd.DataFrame, column: str = "sst_anomaly_c_mean") -> dict[str, Any]:
    values = pd.to_numeric(df[column], errors="coerce").dropna()
    if values.empty:
        return {
            "count": 0,
            "mean": None,
            "median": None,
            "min": None,
            "max": None,
            "p90": None,
            "p95": None,
            "p99": None,
        }

    max_idx = values.idxmax()
    min_idx = values.idxmin()
    return {
        "count": int(values.size),
        "mean": round(float(values.mean()), 3),
        "median": round(float(values.median()), 3),
        "min": round(float(values.min()), 3),
        "min_date": format_date(df.loc[min_idx, "date"]),
        "max": round(float(values.max()), 3),
        "max_date": format_date(df.loc[max_idx, "date"]),
        "p90": round(float(values.quantile(0.90)), 3),
        "p95": round(float(values.quantile(0.95)), 3),
        "p99": round(float(values.quantile(0.99)), 3),
    }


def nearest_available_date(df: pd.DataFrame, target: pd.Timestamp) -> str | None:
    if df.empty:
        return None
    dates = pd.to_datetime(df["date"].dropna().unique())
    if len(dates) == 0:
        return None
    deltas = np.abs((dates - target).days)
    return pd.Timestamp(dates[int(np.argmin(deltas))]).strftime("%Y-%m-%d")


def build_interpretation(region_label: str, current_anom: float, seasonal_percentile: float | None, seasonal_rank: int | None, seasonal_count: int, all_percentile: float | None) -> str:
    parts = [f"{region_label} SST anomaly is {current_anom:+.2f} °C."]

    if seasonal_percentile is not None:
        rank_text = f" and ranks {seasonal_rank} out of {seasonal_count} highest values" if seasonal_rank else ""
        parts.append(
            f"Compared with historical values from the same part of the year, "
            f"it is at the {seasonal_percentile:.2f} percentile{rank_text}."
        )

    if all_percentile is not None:
        parts.append(f"Across all available days it is at the {all_percentile:.2f} percentile.")

    if seasonal_percentile is not None:
        if seasonal_percentile >= 99:
            parts.append("This is an exceptional warm-SST signal for this part of the year.")
        elif seasonal_percentile >= 95:
            parts.append("This is a very unusual warm-SST signal for this part of the year.")
        elif seasonal_percentile >= 90:
            parts.append("This is a clearly elevated warm-SST signal for this part of the year.")
        elif seasonal_percentile <= 10:
            parts.append("This is unusually cool for this part of the year.")
        else:
            parts.append("This is not an extreme seasonal SST anomaly.")

    return " ".join(parts)


def analyze_region(
    *,
    region_key: str,
    region_current: dict[str, Any],
    region_ts: pd.DataFrame,
    current_valid_date: pd.Timestamp,
    season_window_days: int,
    exclude_current_date: bool,
) -> dict[str, Any]:
    label = region_current.get("label") or (region_ts["label"].dropna().iloc[0] if not region_ts.empty else region_key)
    current_sst = region_current.get("sst_c_mean")
    current_anom = region_current.get("sst_anomaly_c_mean")
    current_grid_points = region_current.get("grid_points_used")

    if current_anom is None:
        return {"label": label, "status": "unavailable", "reason": "Current SST anomaly is missing."}

    current_anom = float(current_anom)
    current_doy = int(current_valid_date.dayofyear)

    comparison = region_ts.copy()
    if exclude_current_date:
        comparison = comparison[comparison["date"] != current_valid_date]

    if comparison.empty:
        return {"label": label, "status": "unavailable", "reason": "No historical comparison data available."}

    comparison["doy_distance"] = comparison["day_of_year"].apply(lambda x: circular_day_distance(int(x), current_doy))
    seasonal = comparison[comparison["doy_distance"] <= int(season_window_days)].copy()

    all_values = comparison["sst_anomaly_c_mean"]
    seasonal_values = seasonal["sst_anomaly_c_mean"]

    all_percentile = percentile_rank(all_values, current_anom)
    seasonal_percentile = percentile_rank(seasonal_values, current_anom)
    all_rank = rank_highest(all_values, current_anom)
    seasonal_rank = rank_highest(seasonal_values, current_anom)

    above_2c = float((comparison["sst_anomaly_c_mean"] >= 2.0).mean() * 100.0)
    above_current = float((comparison["sst_anomaly_c_mean"] >= current_anom).mean() * 100.0)
    seasonal_above_2c = float((seasonal["sst_anomaly_c_mean"] >= 2.0).mean() * 100.0) if not seasonal.empty else None
    seasonal_above_current = float((seasonal["sst_anomaly_c_mean"] >= current_anom).mean() * 100.0) if not seasonal.empty else None

    seasonal_count = int(pd.to_numeric(seasonal_values, errors="coerce").dropna().size)

    return {
        "label": label,
        "status": "ok",
        "current": {
            "valid_date": current_valid_date.strftime("%Y-%m-%d"),
            "sst_c_mean": round(float(current_sst), 3) if current_sst is not None else None,
            "sst_anomaly_c_mean": round(float(current_anom), 3),
            "grid_points_used": int(current_grid_points) if current_grid_points is not None else None,
        },
        "comparison_period": {
            "date_min": format_date(comparison["date"].min()),
            "date_max": format_date(comparison["date"].max()),
            "count": int(len(comparison)),
            "nearest_available_date_to_current": nearest_available_date(comparison, current_valid_date),
            "exclude_current_date": bool(exclude_current_date),
        },
        "all_days": {
            "percentile": all_percentile,
            "rank_highest": all_rank,
            "count": int(pd.to_numeric(all_values, errors="coerce").dropna().size),
            "share_days_ge_2c_percent": round(above_2c, 3),
            "share_days_ge_current_percent": round(above_current, 3),
            "distribution": summarize_distribution(comparison),
        },
        "seasonal_window": {
            "window_days": int(season_window_days),
            "description": (
                f"Comparison with historical values from the same part of the year "
                f"(±{int(season_window_days)} days around the current calendar day)."
            ),
            "recommended_report_phrase_cs": (
                f"Ve srovnání se stejným obdobím roku (±{int(season_window_days)} dní)"
            ),
            "day_of_year": current_doy,
            "percentile": seasonal_percentile,
            "rank_highest": seasonal_rank,
            "count": seasonal_count,
            "share_days_ge_2c_percent": round(seasonal_above_2c, 3) if seasonal_above_2c is not None else None,
            "share_days_ge_current_percent": round(seasonal_above_current, 3) if seasonal_above_current is not None else None,
            "distribution": summarize_distribution(seasonal),
        },
        "interpretation_hint_en": build_interpretation(
            str(label), current_anom, seasonal_percentile, seasonal_rank, seasonal_count, all_percentile
        ),
    }


def apply_baseline_filter(df: pd.DataFrame, baseline_start: str | None, baseline_end: str | None) -> pd.DataFrame:
    out = df.copy()
    if baseline_start:
        out = out[out["date"] >= pd.Timestamp(baseline_start)]
    if baseline_end:
        out = out[out["date"] <= pd.Timestamp(baseline_end)]
    return out


def main() -> None:
    args = parse_args()

    timeseries_path = Path(args.timeseries)
    current_json_path = Path(args.current_json)
    output_json_path = Path(args.output_json)
    output_csv_path = Path(args.output_csv)

    ts_all = load_timeseries(timeseries_path)
    ts = apply_baseline_filter(ts_all, args.baseline_start, args.baseline_end)
    current = load_current_background(current_json_path)

    ocean = current.get("ocean", {})
    if ocean.get("status") != "ok":
        raise RuntimeError(f"Current ocean diagnostics are not available: {ocean.get('status')}")

    current_valid_date_raw = ocean.get("valid_date")
    if not current_valid_date_raw:
        raise RuntimeError("Current ocean valid_date is missing.")

    current_valid_date = pd.Timestamp(current_valid_date_raw)
    regions_current = ocean.get("regions", {})

    analysis: dict[str, Any] = {
        "created_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "inputs": {
            "timeseries_csv": str(timeseries_path),
            "current_json": str(current_json_path),
            "timeseries_rows_total": int(len(ts_all)),
            "timeseries_rows_used": int(len(ts)),
        },
        "settings": {
            "season_window_days": int(args.season_window_days),
            "baseline_start": args.baseline_start,
            "baseline_end": args.baseline_end,
            "exclude_current_date": bool(args.exclude_current_date),
        },
        "current_ocean": {
            "dataset": ocean.get("dataset"),
            "valid_date": current_valid_date.strftime("%Y-%m-%d"),
            "requested_run_time": ocean.get("requested_run_time"),
            "lookback_days_used": ocean.get("lookback_days_used"),
            "source_url": ocean.get("source_url"),
        },
        "regions": {},
        "interpretation_hints_en": [],
    }

    csv_rows: list[dict[str, Any]] = []

    for region_key, region_current in regions_current.items():
        region_ts = ts[ts["region"] == region_key].copy()
        result = analyze_region(
            region_key=region_key,
            region_current=region_current,
            region_ts=region_ts,
            current_valid_date=current_valid_date,
            season_window_days=args.season_window_days,
            exclude_current_date=args.exclude_current_date,
        )
        analysis["regions"][region_key] = result

        hint = result.get("interpretation_hint_en")
        if hint:
            analysis["interpretation_hints_en"].append(hint)

        if result.get("status") == "ok":
            csv_rows.append(
                {
                    "region": region_key,
                    "label": result["label"],
                    "current_valid_date": result["current"]["valid_date"],
                    "current_sst_anomaly_c_mean": result["current"]["sst_anomaly_c_mean"],
                    "all_days_percentile": result["all_days"]["percentile"],
                    "all_days_rank_highest": result["all_days"]["rank_highest"],
                    "all_days_count": result["all_days"]["count"],
                    "seasonal_percentile": result["seasonal_window"]["percentile"],
                    "seasonal_rank_highest": result["seasonal_window"]["rank_highest"],
                    "seasonal_count": result["seasonal_window"]["count"],
                    "historical_max": result["all_days"]["distribution"]["max"],
                    "historical_max_date": result["all_days"]["distribution"]["max_date"],
                    "seasonal_max": result["seasonal_window"]["distribution"]["max"],
                    "seasonal_max_date": result["seasonal_window"]["distribution"]["max_date"],
                }
            )

    output_json_path.parent.mkdir(parents=True, exist_ok=True)
    output_json_path.write_text(json.dumps(analysis, indent=2, ensure_ascii=False), encoding="utf-8")

    output_csv_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(csv_rows).to_csv(output_csv_path, index=False)

    print(f"Saved analysis JSON: {output_json_path}")
    print(f"Saved compact CSV: {output_csv_path}")

    if args.debug:
        for row in csv_rows:
            print(
                f"{row['region']}: current={row['current_sst_anomaly_c_mean']:+.2f} °C, "
                f"seasonal percentile={row['seasonal_percentile']}, "
                f"seasonal rank={row['seasonal_rank_highest']}/{row['seasonal_count']}, "
                f"all-days percentile={row['all_days_percentile']}"
            )


if __name__ == "__main__":
    main()
