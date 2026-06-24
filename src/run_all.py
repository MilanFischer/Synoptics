import argparse
import subprocess
import sys
import os
import smtplib
from email.message import EmailMessage
from pathlib import Path
from datetime import datetime

try:
    from dotenv import load_dotenv
except Exception:  # python-dotenv is optional for run_all.py, but recommended
    load_dotenv = None

from utils import resolve_run_time, parse_priority, find_available_gfs_run, PROJECT_ROOT


# Scripts in this list are intentionally executed for every requested forecast hour.
# generate_static_report.py and export_pdf.py are included because they create
# one static briefing/PDF per valid time; these per-timestep artefacts are later
# collected by prepare_ai_briefing_inputs.py into the AI ZIP.
PER_FXX_SCRIPTS = [
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
        "--no-ai-package",
        dest="make_ai_package",
        action="store_false",
        help="Skip creation of the AI input ZIP package.",
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
    parser.add_argument(
        "--generate-ai-report",
        dest="generate_ai_report",
        action="store_true",
        default=True,
        help="Generate the GPT Markdown/HTML/PDF report after the AI ZIP package is created. Default: enabled.",
    )
    parser.add_argument(
        "--no-generate-ai-report",
        dest="generate_ai_report",
        action="store_false",
        help="Skip GPT DOCX/PDF report generation.",
    )
    parser.add_argument(
        "--ai-model",
        type=str,
        default=None,
        help="OpenAI model used by generate_ai_report.py. Fallback: SYNOPTICS_OPENAI_MODEL or script default.",
    )
    parser.add_argument(
        "--ai-figure-hours",
        type=str,
        default="auto",
        help="Forecast hours for combined figures in the AI report. Use 'auto' to derive from --fxx-list.",
    )
    parser.add_argument(
        "--ai-max-figures",
        type=int,
        default=None,
        help="Maximum number of combined figures when --ai-figure-hours=auto. If omitted, generate_ai_report.py derives it automatically.",
    )
    parser.add_argument(
        "--ai-max-pages-hint",
        type=int,
        default=4,
        help="Target Word-page length hint for the AI text report.",
    )
    parser.add_argument(
        "--ai-no-vision",
        action="store_true",
        help="Generate AI report without sending combined figures to GPT vision.",
    )
    parser.add_argument(
        "--ai-no-pdf",
        action="store_true",
        help="Create Markdown/HTML only; do not export the AI report to PDF.",
    )
    parser.add_argument(
        "--email-report",
        action="store_true",
        help="Email the generated AI PDF report after completion. Implies --generate-ai-report.",
    )
    parser.add_argument(
        "--email-to",
        type=str,
        default=None,
        help="Comma-separated recipient list. Fallback: SYNOPTICS_EMAIL_TO.",
    )
    parser.add_argument(
        "--email-from",
        type=str,
        default=None,
        help="Sender address. Fallback: SYNOPTICS_EMAIL_FROM or SMTP user.",
    )
    parser.add_argument(
        "--smtp-host",
        type=str,
        default=None,
        help="SMTP host. Fallback: SYNOPTICS_SMTP_HOST.",
    )
    parser.add_argument(
        "--smtp-port",
        type=int,
        default=None,
        help="SMTP port. Fallback: SYNOPTICS_SMTP_PORT or 587.",
    )
    parser.add_argument(
        "--smtp-user",
        type=str,
        default=None,
        help="SMTP username. Fallback: SYNOPTICS_SMTP_USER.",
    )
    parser.add_argument(
        "--smtp-password",
        type=str,
        default=None,
        help="SMTP password/app password. Fallback: SYNOPTICS_SMTP_PASSWORD.",
    )
    parser.add_argument(
        "--smtp-no-starttls",
        action="store_true",
        help="Disable STARTTLS for SMTP.",
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


def run_climate_background(src_dir: Path, run_time: str, env: dict) -> None:
    """Download and summarize SST anomalies and teleconnection indices once per model run.

    This is intentionally not a per-forecast-hour script because OISST and
    teleconnection indices describe the large-scale background state, not a
    GFS forecast timestep. If the external NOAA/CPC data are temporarily
    unavailable, the script writes an unavailable-status JSON and the rest of
    the workflow can continue.
    """
    path = src_dir / "download_ocean_teleconnections.py"
    if not path.exists():
        print("Skipping climate background: download_ocean_teleconnections.py not found.")
        return

    print("\nDownloading ocean and teleconnection background data...")
    result = subprocess.run(
        [sys.executable, str(path), "--run", run_time],
        cwd=src_dir,
        env=env,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"download_ocean_teleconnections.py failed with exit code {result.returncode}.")


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




def run_precip_accum(src_dir: Path, run_time: str, fxx_list: list[int], priority: str, env: dict) -> None:
    """Generate cumulative precipitation maps/diagnostics for every requested forecast hour.

    This runs once after all per-fxx maps are finished and before the AI package
    is assembled. It creates, for each valid time:

    - maps/precip_accum_europe_*.png
    - reports/precip_accum_*.json

    The ordinary make_precip_map.py still creates maps/precip_europe_*.png per
    forecast hour. prepare_ai_briefing_inputs.py then places the period and
    cumulative precipitation maps side by side inside combined_overview_*.png.
    """
    path = src_dir / "make_precip_accum_map.py"
    if not path.exists():
        # Backward-compatible fallback for older local checkouts.
        fallback = src_dir / "make_precip_compare_map.py"
        if fallback.exists():
            path = fallback

    if not path.exists():
        raise FileNotFoundError(
            "Neither make_precip_accum_map.py nor make_precip_compare_map.py was found."
        )

    print("\nGenerating cumulative precipitation maps for all forecast hours...")
    result = subprocess.run(
        [
            sys.executable,
            str(path),
            "--run",
            run_time,
            "--fxx",
            str(fxx_list[-1]),
            "--fxx-list",
            ",".join(str(x) for x in fxx_list),
            "--priority",
            priority,
        ],
        cwd=src_dir,
        env=env,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"{path.name} failed with exit code {result.returncode}.")

def run_ai_report(src_dir: Path, run_time: str, output_root: Path, fxx_list: list[int], args, env: dict) -> Path:
    # Production AI report script. The user does not pass the ZIP manually;
    # run_all.py derives it from the current run output folder.
    path = src_dir / "generate_ai_report.py"
    if not path.exists():
        fallback = src_dir / "generate_ai_report_integrated.py"
        if fallback.exists():
            path = fallback

    zip_path = output_root / "ai_inputs" / f"{output_id_from_run(run_time)}.zip"

    if not zip_path.exists():
        raise FileNotFoundError(f"AI ZIP not found: {zip_path}")

    command = [
        sys.executable,
        str(path),
        "--project-root",
        str(src_dir.parent),
        "--zip",
        str(zip_path),
        "--fxx-list",
        ",".join(str(x) for x in fxx_list),
        "--figure-hours",
        args.ai_figure_hours,
        "--max-pages-hint",
        str(args.ai_max_pages_hint),
    ]

    if args.ai_model:
        command.extend(["--model", args.ai_model])
    if args.ai_max_figures is not None:
        command.extend(["--max-figures", str(args.ai_max_figures)])
    if args.ai_no_vision:
        command.append("--no-vision")
    if args.ai_no_pdf:
        command.append("--no-pdf")

    print("\nGenerating AI Markdown/HTML/PDF report...")
    print("AI ZIP:", zip_path)
    result = subprocess.run(command, cwd=src_dir, env=env, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"generate_ai_report.py failed with exit code {result.returncode}.")

    report_base = f"{output_id_from_run(run_time)}_gpt_report"
    pdf_path = output_root / "ai_inputs" / f"{report_base}.pdf"
    html_path = output_root / "ai_inputs" / f"{report_base}.html"

    # Backward-compatible fallbacks in case generate_ai_report.py has not yet been updated.
    legacy_pdf_path = output_root / "ai_inputs" / "gpt_report.pdf"
    legacy_html_path = output_root / "ai_inputs" / "gpt_report.html"

    for candidate in (pdf_path, html_path, legacy_pdf_path, legacy_html_path):
        if candidate.exists():
            return candidate

    raise FileNotFoundError(
        f"AI report was generated, but no report file was found. Expected one of: "
        f"{pdf_path.name}, {html_path.name}, {legacy_pdf_path.name}, {legacy_html_path.name}"
    )

def send_report_email(report_path: Path, run_time: str, args) -> None:
    smtp_host = args.smtp_host or os.getenv("SYNOPTICS_SMTP_HOST")
    smtp_port = args.smtp_port or int(os.getenv("SYNOPTICS_SMTP_PORT", "587"))
    smtp_user = args.smtp_user or os.getenv("SYNOPTICS_SMTP_USER")
    smtp_password = args.smtp_password or os.getenv("SYNOPTICS_SMTP_PASSWORD")
    sender = args.email_from or os.getenv("SYNOPTICS_EMAIL_FROM") or smtp_user
    recipients_raw = args.email_to or os.getenv("SYNOPTICS_EMAIL_TO")

    if not smtp_host:
        raise RuntimeError("SMTP host missing. Use --smtp-host or SYNOPTICS_SMTP_HOST.")
    if not sender:
        raise RuntimeError("Email sender missing. Use --email-from, SYNOPTICS_EMAIL_FROM, or SMTP user.")
    if not recipients_raw:
        raise RuntimeError("Email recipients missing. Use --email-to or SYNOPTICS_EMAIL_TO.")

    recipients = [item.strip() for item in recipients_raw.split(",") if item.strip()]
    if not recipients:
        raise RuntimeError("No valid email recipients were provided.")

    msg = EmailMessage()
    msg["Subject"] = f"Synoptický report GFS {run_time} UTC"
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg.set_content(
        "Dobrý den,\n\n"
        f"v příloze posílám automaticky generovaný synoptický report GFS pro běh {run_time} UTC.\n\n"
        "Synoptics workflow"
    )

    suffix = report_path.suffix.lower()
    if suffix == ".pdf":
        maintype, subtype = "application", "pdf"
    elif suffix == ".html":
        maintype, subtype = "text", "html"
    else:
        maintype, subtype = "application", "octet-stream"

    msg.add_attachment(
        report_path.read_bytes(),
        maintype=maintype,
        subtype=subtype,
        filename=report_path.name,
    )

    print(f"\nSending report email to: {', '.join(recipients)}")
    with smtplib.SMTP(smtp_host, smtp_port) as smtp:
        if not args.smtp_no_starttls:
            smtp.starttls()
        if smtp_user and smtp_password:
            smtp.login(smtp_user, smtp_password)
        smtp.send_message(msg)

    print("Email sent.")


def main():
    args = parse_args()
    src_dir = Path(__file__).parent

    # Load .env early so SMTP variables and other workflow settings are available
    # to both this process and subprocesses.
    if load_dotenv is not None:
        load_dotenv(src_dir.parent / ".env")

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
        output_root = src_dir.parent
    elif args.output_root:
        output_root = Path(args.output_root).resolve()
    else:
        output_root = src_dir.parent / "outputs" / output_id_from_run(run_time)

    output_root.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["SYNOPTICS_OUTPUT_DIR"] = str(output_root)
    env["SYNOPTICS_FXX_LIST"] = ",".join(str(x) for x in args.fxx_list)

    print(f"Using GFS run: {run_time} UTC")
    print(f"Forecast hours: {args.fxx_list}")
    print(f"Herbie source priority: {priority}")
    print(f"Output root: {output_root}")

    for fxx in args.fxx_list:
        print(f"\n=== Forecast hour +{fxx} h ===")
        for script in PER_FXX_SCRIPTS:
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

    # Cumulative precipitation must be generated after all per-fxx precipitation maps
    # exist and before prepare_ai_briefing_inputs.py builds the combined figures.
    run_precip_accum(src_dir, run_time, args.fxx_list, priority, env)

    # Ocean and teleconnection background is a run-level diagnostic, not fxx-specific.
    run_climate_background(src_dir, run_time, env)

    if args.make_ai_package:
        run_ai_package(src_dir, run_time, priority, env)

    report_path = None
    if args.generate_ai_report or args.email_report:
        report_path = run_ai_report(src_dir, run_time, output_root, args.fxx_list, args, env)

    if args.email_report:
        if report_path is None:
            raise RuntimeError("No report path available for email sending.")
        send_report_email(report_path, run_time, args)

    print("\nAll maps, features, reports and AI package generated successfully.")


if __name__ == "__main__":
    main()
