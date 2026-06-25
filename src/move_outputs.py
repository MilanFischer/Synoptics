from pathlib import Path
import shutil

SOURCE_DIR = Path("/mnt/data_local/Synoptics/outputs")
TARGET_DIR = Path("/mnt/monospace-mendelu/Milan/Synoptics/outputs")

# Important:
# _manual is kept on the local server because it contains persistent workflow data,
# especially outputs/_manual/data/ocean_climatology/oisst_region_timeseries.csv.
SKIP_NAMES = {
    "_manual",
}

TARGET_DIR.mkdir(parents=True, exist_ok=True)

if not SOURCE_DIR.exists():
    raise FileNotFoundError(f"Source directory does not exist: {SOURCE_DIR}")

moved_count = 0
skipped_count = 0

for item in SOURCE_DIR.iterdir():
    if item.name in SKIP_NAMES:
        print(f"Skipped: {item.name}")
        skipped_count += 1
        continue

    target = TARGET_DIR / item.name

    if target.exists():
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()

    shutil.move(str(item), str(target))
    print(f"Moved: {item.name}")
    moved_count += 1

print(
    f"Outputs successfully moved to Monospace. "
    f"Moved: {moved_count}, skipped: {skipped_count}."
)
