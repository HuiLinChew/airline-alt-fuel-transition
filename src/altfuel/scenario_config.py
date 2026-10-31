"""Module 0 - Scenario config.

Reads one YAML file per scenario into a Scenario object that every other module
uses. A scenario is the baseline plus "disturbances": fleet available, which
airport tiers offer each fuel, prices, carbon price, objective.
"""

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .utils import SCENARIO_DIR


@dataclass
class Scenario:
    name: str
    description: str = ""
    objective: str = "cost"            # "cost", "energy" or "co2"
    fleet: dict = field(default_factory=lambda: {"KER-NB": 30})   # A[type]: aircraft available
    fuel_max_tier: dict = field(default_factory=dict)  # fuel -> offered at tiers <= this (kerosene: all)
    fuel_price: dict = field(default_factory=dict)     # fuel -> USD/kg, overrides fuels.csv
    tier_price_factor: dict = field(default_factory=lambda: {1: 1.0, 2: 1.1, 3: 1.25})
    carbon_price: float = 0.0          # USD per t CO2 (Hoelzen et al. 2025 use 50/100/200)
    cost_per_block_hour: float = 3000  # crew + maintenance + ownership, USD/h (placeholder)
    yield_usd_per_pax_km: float = 0.10 # lost revenue if a leg is dropped (placeholder)
    allow_drop: bool = False           # True = optimiser may drop legs that lose money
    refuel_on_critical_path: bool = True   # Al-Timimi: extra LH2 refuel time adds to turn time


def load_scenario(name_or_path) -> Scenario:
    path = Path(name_or_path)
    if not path.suffix:
        path = SCENARIO_DIR / f"{name_or_path}.yaml"
    with open(path) as f:
        cfg = yaml.safe_load(f)
    return Scenario(**cfg)


def load_all() -> list[Scenario]:
    """Every scenario in scenarios/, baseline first."""
    paths = sorted(SCENARIO_DIR.glob("*.yaml"), key=lambda p: (p.stem != "baseline", p.stem))
    return [load_scenario(p) for p in paths]
