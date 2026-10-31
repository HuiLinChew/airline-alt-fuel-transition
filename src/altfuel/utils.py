"""Small helpers shared by several modules (no modelling logic)."""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SCENARIO_DIR = ROOT / "scenarios"
OUTPUT_DIR = ROOT / "outputs"


def read_csv(path) -> pd.DataFrame:
    """Read a CSV without turning the text "NA" (North America) into a missing value."""
    return pd.read_csv(path, keep_default_na=False, na_values=[""])


def hhmm(minutes: int) -> str:
    """390 -> '06:30' (wraps past midnight: 1500 -> '01:00')."""
    h, m = divmod(int(minutes) % 1440, 60)
    return f"{h:02d}:{m:02d}"
