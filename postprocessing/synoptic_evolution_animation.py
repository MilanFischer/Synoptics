from PIL import Image
from pathlib import Path

maps_dir = Path(r"d:\Git\GitHub\GitHubRepositories\Synoptics\outputs\_manual\maps\animation")

files = sorted(maps_dir.glob("z500_t850_animation_*.png"))

print(f"Found {len(files)} files")

if not files:
    raise FileNotFoundError(f"No PNG files found in {maps_dir}")

frames = [Image.open(f).convert("P", palette=Image.ADAPTIVE) for f in files]

out_gif = maps_dir / "synoptic_evolution.gif"

frames[0].save(
    out_gif,
    save_all=True,
    append_images=frames[1:],
    duration=800,
    loop=0,
)

print(f"GIF created: {out_gif}")