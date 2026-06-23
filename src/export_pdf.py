from pathlib import Path
import argparse
import re

from utils import add_model_run_args, resolve_run_time, valid_time_from_run, PROJECT_ROOT, REPORTS_DIR

import markdown
from weasyprint import HTML, CSS


# PROJECT_ROOT and REPORTS_DIR are imported from utils and respect SYNOPTICS_OUTPUT_DIR.


def find_markdown(run_time=None, fxx=None):
    if run_time is not None and fxx is not None:
        valid_time = valid_time_from_run(run_time, fxx)
        target = REPORTS_DIR / f"briefing_static_{valid_time.replace(':', '-')}.md"
        if target.exists():
            return target
        raise FileNotFoundError(f"No markdown report found for valid time {valid_time}.")

    files = sorted(REPORTS_DIR.glob("briefing_static_*.md"))

    if not files:
        raise FileNotFoundError("No briefing_static_*.md file found in reports/.")

    return files[-1]


def parse_args():
    parser = argparse.ArgumentParser()
    add_model_run_args(parser)
    return parser.parse_args()


def fix_image_paths(md_text):
    def replace(match):
        alt_text = match.group(1)
        image_path = match.group(2)

        path = Path(image_path)

        if not path.is_absolute():
            path = PROJECT_ROOT / path

        uri = path.resolve().as_uri()
        return f"![{alt_text}]({uri})"

    return re.sub(r"!\[(.*?)\]\((.*?)\)", replace, md_text)


def main():
    args = parse_args()
    run_filter = resolve_run_time(args.run) if args.run else None
    fxx_filter = args.fxx if args.run else None

    md_file = find_markdown(run_filter, fxx_filter)

    with open(md_file, "r", encoding="utf-8") as f:
        md_text = f.read()

    md_text = fix_image_paths(md_text)

    html_body = markdown.markdown(
        md_text,
        extensions=["extra", "tables"],
        output_format="html5",
    )

    html = f"""
<!doctype html>
<html lang="cs">
<head>
<meta charset="utf-8">
<title>{md_file.stem}</title>
</head>
<body>
{html_body}
</body>
</html>
"""

    css = CSS(string="""
@page {
    size: A4;
    margin: 14mm 12mm 14mm 12mm;
}

body {
    font-family: Arial, sans-serif;
    font-size: 10pt;
    line-height: 1.35;
    color: #111;
}

h1 {
    font-size: 19pt;
}

h2 {
    font-size: 14pt;
    margin-top: 18px;
    border-bottom: 1px solid #ccc;
    padding-bottom: 4px;
}

h3 {
    font-size: 12pt;
    margin-top: 14px;
}

img {
    display: block;
    width: 100%;
    max-width: 100%;
    height: auto;
    margin: 8px 0 18px 0;
    page-break-inside: avoid;
}

code {
    font-family: Consolas, monospace;
    font-size: 9pt;
}

hr {
    border: none;
    border-top: 1px solid #ccc;
    margin: 16px 0;
}
""")

    out_pdf = REPORTS_DIR / f"{md_file.stem}.pdf"

    HTML(
        string=html,
        base_url=PROJECT_ROOT.as_uri(),
    ).write_pdf(
        out_pdf,
        stylesheets=[css],
    )

    print(f"Saved: {out_pdf}")


if __name__ == "__main__":
    main()