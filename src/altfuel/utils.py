"""Folder paths and a CSV reader shared by the other modules."""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SCENARIO_DIR = ROOT / "scenarios"
OUTPUT_DIR = ROOT / "outputs"


def read_csv(path) -> pd.DataFrame:
    # Keep the region code "NA" (North America) as text instead of a missing value
    return pd.read_csv(path, keep_default_na=False, na_values=[""])
