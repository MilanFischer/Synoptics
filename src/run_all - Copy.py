import argparse
import subprocess
import sys
import os
from pathlib import Path
from datetime import datetime

from utils import resolve_run_time, parse_priority, find_available_gfs_run, PROJECT_ROOT


SCRIPTS = [
    "make_t850_map.py",
    "make_jet250_map.py",
    "make_pwat_map.py",
    "make_cape_cin_map.py",
    "make_z500_t850_map.py",
    "make_mslp_wind_map.py",
    "make_precip_map.py",
    "extract_features.py",
    "detect_synoptic_features.py",
    "generate_synoptic_assessment.py",
    "generate_synoptic_commentary.py",
    "generate_static_report.py",
    "export_pdf.py",
]

DEFAULT_FXX_LIST = [0, 6, 12, 24, 36, 48, 72]


def parse_fxx_list(value: str):
    return [int(item.strip()) for item in value.split(",") if item.strip()]


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--run",
        type=str,
        default=None,
        help="Model run in UTC, e.g. '2026-06-20 00:00'. If omitted, a recent GFS cycle is used.",
    )
    parser.add_argument(
        "--fxx-list",
        type=parse_fxx_list,
        default=DEFAULT_FXX_LIST,
        help="Comma-separated forecast hours, e.g. '0,6,12,24,48'.",
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
    parser.add_argument(
        "--fallback-cycles",
        type=int,
        default=8,
        help=(
            "How many previous 6-hour GFS cycles to try if the requested run is not available. "
            "Use 0 to disable fallback."
        ),
    )
    parser.add_argument(
        "--classic-output",
        action="store_true",
        help="Preserve the old behaviour and write to project-level maps/, reports/ and data/.",
    )
    parser.add_argument(
        "--output-root",
        type=str,
        default=None,
        help="Optional explicit output root. If omitted, outputs/<gfs_YYYY-MM-DD_HH> is used.",
    )
    parser.add_argument(
        "--make-ai-package",
        action="store_true",
        default=True,
        help="Create an AI input ZIP package after all forecast hours are processed.",
    )
    parser.add_argument(
        "--script-retries",
        type=int,
        default=3,
        help="How many times to retry each script if it fails due to a transient download/network error.",
    )
    parser.add_argument(
        "--retry-delay",
        type=int,
        default=30,
        help="Delay in seconds between script retries.",
    )
    return parser.parse_args()


def output_id_from_run(run_time: str) -> str:
    dt = datetime.strptime(run_time, "%Y-%m-%d %H:%M")
    return f"gfs_{dt:%Y-%m-%d_%H}"


def run_script(
    src_dir: Path,
    script: str,
    run_time: str,
    fxx: int,
    priority: str,
    env: dict,
    attempts: int = 3,
    retry_delay: int = 30,
) -> None:
    path = src_dir / script

    for attempt in range(1, int(attempts) + 1):
        print(
            f"\nRunning {script} | run={run_time} UTC | fxx=+{fxx} h "
            f"| attempt {attempt}/{attempts}"
        )
        result = subprocess.run(
            [sys.executable, str(path), "--run", run_time, "--fxx", str(fxx), "--priority", priority],
            cwd=src_dir,
            env=env,
            check=False,
        )

        if result.returncode == 0:
            return

        if attempt < int(attempts):
            import time
            print(
                f"{script} failed with exit code {result.returncode}. "
                f"Retrying in {retry_delay} seconds..."
            )
            time.sleep(retry_delay)

    raise RuntimeError(
        f"{script} failed for run={run_time}, fxx={fxx} "
        f"after {attempts} attempts."
    )


def run_ai_package(src_dir: Path, run_time: str, priority: str, env: dict) -> None:
    path = src_dir / "prepare_ai_briefing_inputs.py"
    print("\nPreparing AI briefing input package...")
    result = subprocess.run(
        [sys.executable, str(path), "--run", run_time, "--priority", priority],
        cwd=src_dir,
        env=env,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"prepare_ai_briefing_inputs.py failed with exit code {result.returncode}.")


def main():
    args = parse_args()
    src_dir = Path(__file__).parent
    requested_run_time = resolve_run_time(args.run)

    priority = ",".join(parse_priority(args.priority))

    first_fxx = args.fxx_list[0]
    run_time = find_available_gfs_run(
        start_run_time=requested_run_time,
        fxx=first_fxx,
        priority=priority,
        max_back_cycles=args.fallback_cycles,
    )

    if run_time != requested_run_time:
        print(
            f"Requested GFS run {requested_run_time} UTC was not available "
            f"for fxx=+{first_fxx} h; using {run_time} UTC instead."
        )

    if args.classic_output:
        output_root = PROJECT_ROOT
    elif args.output_root:
        output_root = Path(args.output_root).resolve()
    else:
        output_root = PROJECT_ROOT / "outputs" / output_id_from_run(run_time)

    output_root.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["SYNOPTICS_OUTPUT_DIR"] = str(output_root)

    print(f"Using GFS run: {run_time} UTC")
    print(f"Forecast hours: {args.fxx_list}")
    print(f"Herbie source priority: {priority}")
    print(f"Output root: {output_root}")

    for fxx in args.fxx_list:
        print(f"\n=== Forecast hour +{fxx} h ===")
        for script in SCRIPTS:
            run_script(
                src_dir,
                script,
                run_time,
                fxx,
                priority,
                env,
                attempts=args.script_retries,
                retry_delay=args.retry_delay,
            )

    if args.make_ai_package:
        run_ai_package(src_dir, run_time, priority, env)

    print("\nAll maps, features, reports and AI package generated successfully.")


if __name__ == "__main__":
    main()
