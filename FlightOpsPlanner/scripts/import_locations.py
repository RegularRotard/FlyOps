"""One-time (repeat-safe) seed import into the local FlyOps database."""

from pathlib import Path

from flightops.locations.catalog import import_seed

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "databases" / "flightops.db"
SEED = ROOT / "data" / "seed"

if __name__ == "__main__":
    result = import_seed(
        DB,
        SEED / "flyops_airports_v3.csv",
        SEED / "flyops_waypoints_seed.csv",
    )
    print(
        f"FlyOps locations: {result['inserted']} inserted, {result['already_present']} already present"
    )
