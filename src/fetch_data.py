from pathlib import Path
import requests
import json

from utils import DATA_DIR
DATA_DIR.mkdir(parents=True, exist_ok=True)

url = "https://api.open-meteo.com/v1/ecmwf"

params = {
    "latitude": 50.08,
    "longitude": 14.44,
    "hourly": "temperature_850hPa,geopotential_height_500hPa",
    "forecast_days": 3
}

r = requests.get(url, params=params, timeout=30)
r.raise_for_status()

data = r.json()

with open(DATA_DIR / "test.json", "w") as f:
    json.dump(data, f, indent=2)

print("Data uložena")