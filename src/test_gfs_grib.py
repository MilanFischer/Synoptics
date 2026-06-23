from datetime import datetime, timezone
from herbie import Herbie
import xarray as xr

from utils import DATA_DIR
DATA_DIR.mkdir(parents=True, exist_ok=True)

# poslední dostupný běh GFS; pro test vezmeme 00 UTC dnešního dne
run_date = datetime.now(timezone.utc).strftime("%Y-%m-%d 00:00")

H = Herbie(
    run_date,
    model="gfs",
    product="pgrb2.0p25",
    fxx=6,
    save_dir=DATA_DIR,
)

# stáhneme T850
grib_file = H.download(":TMP:850 mb")
print("Staženo:", grib_file)

ds = xr.open_dataset(
    grib_file,
    engine="cfgrib",
    backend_kwargs={"filter_by_keys": {"typeOfLevel": "isobaricInhPa", "level": 850}},
)

print(ds)