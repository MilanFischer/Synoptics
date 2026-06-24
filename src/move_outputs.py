from pathlib import Path
import shutil

SOURCE_DIR = Path("/mnt/data_local/Synoptics/outputs")
TARGET_DIR = Path("/mnt/monospace-mendelu/Milan/Synoptics/outputs")

TARGET_DIR.mkdir(parents=True, exist_ok=True)

for item in SOURCE_DIR.iterdir():
    target = TARGET_DIR / item.name

    if target.exists():
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()

    shutil.move(str(item), str(target))
    print(f"Moved: {item.name}")

print("Outputs successfully moved to Monospace.")