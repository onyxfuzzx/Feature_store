"""Run both real trained-model examples with private credentials from an env file."""

import argparse
import os
import runpy
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--env-file", default=".env.docker")
parser.add_argument("--url", default="http://localhost:5173/api")
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
values = dict(
    line.split("=", 1)
    for line in Path(args.env_file).read_text().splitlines()
    if "=" in line and not line.startswith("#")
)
os.environ.update(
    ADMIN_EMAIL=values["ADMIN_EMAIL"],
    ADMIN_PASSWORD=values["ADMIN_PASSWORD"],
    FEATURE_STORE_URL=args.url,
)
for example in ("01_churn_prediction_e2e.py", "02_registered_logistic_model.py"):
    runpy.run_path(str(root / "examples" / example), run_name="__main__")
