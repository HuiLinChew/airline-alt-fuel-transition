"""Module 0 - Scenario config.

Reads one YAML file per scenario into a Scenario object that every other module
uses. A scenario is the baseline plus "disturbances". Any column of
aircraft_types.csv or fuels.csv can be changed from the YAML through
aircraft_overrides / fuel_overrides, so new what-ifs need no code changes.

validate() checks a scenario against the data and stops on typos (an unknown
aircraft type, fuel, station or column would otherwise be silently ignored).
"""

from dataclasses import dataclass, field, fields
from pathlib import Path

import yaml

from .utils import ROOT, SCENARIO_DIR

OBJECTIVES = ("cost", "energy", "co2")


@dataclass
class Scenario:
    name: str
    description: str = ""
    data_dir: str = "data/dummy"       # folder with the input CSVs, relative to the repo
    objective: str = "cost"            # "cost", "energy" or "co2"
    fleet: dict = field(default_factory=lambda: {"KER-NB": 30})   # A[type]: aircraft available
    reference_type: str = "KER-NB"     # type whose refuel time the base turn already includes

    # Fuel availability: offered at tiers <= fuel_max_tier[fuel] (default: fuels.csv
    # default_max_tier), plus any stations listed in fuel_stations[fuel].
    fuel_max_tier: dict = field(default_factory=dict)
    fuel_stations: dict = field(default_factory=dict)
    # fuel -> {tier: price multiplier}; fuels not listed cost the same everywhere (placeholder bands)
    tier_price_factor: dict = field(default_factory=lambda: {
        "lh2": {1: 1.0, 2: 1.1, 3: 1.25}, "ch4": {1: 1.0, 2: 1.1, 3: 1.25}})

    # Disturbances to input tables: {type or fuel: {column: value}}
    aircraft_overrides: dict = field(default_factory=dict)
    fuel_overrides: dict = field(default_factory=dict)

    carbon_price: float = 0.0          # USD per t CO2 (Hoelzen et al. 2025 use 50/100/200)
    yield_usd_per_pax_km: float = 0.10 # fare if legs.csv has no fare column (placeholder)
    allow_drop: bool = False           # True = optimiser may drop legs that lose money (cost objective only)
    refuel_on_critical_path: bool = True   # Al-Timimi: extra refuel time adds to the turn

    period_min: int = 1440             # schedule length: 1440 = one day, 10080 = one week
    solver: dict = field(default_factory=lambda: {"time_limit_s": 60, "mip_gap": 0.0})
    sweep: dict = field(default_factory=dict)   # optional {parameter: name, values: [...]}

    @property
    def data_path(self) -> Path:
        return ROOT / self.data_dir


def load_scenario(name_or_path) -> Scenario:
    path = Path(name_or_path)
    if not path.suffix:
        path = SCENARIO_DIR / f"{name_or_path}.yaml"
    with open(path) as f:
        cfg = yaml.safe_load(f) or {}
    unknown = set(cfg) - {f.name for f in fields(Scenario)}
    if unknown:
        raise ValueError(f"{path.name}: unknown setting(s) {sorted(unknown)}")
    return Scenario(**cfg)


def load_all() -> list[Scenario]:
    """Every scenario in scenarios/, baseline first."""
    paths = sorted(SCENARIO_DIR.glob("*.yaml"), key=lambda p: (p.stem != "baseline", p.stem))
    return [load_scenario(p) for p in paths]


def validate(sc: Scenario, data) -> None:
    """Raise ValueError listing every setting that does not match the data."""
    types, fuels, stations = set(data.aircraft_types.index), set(data.fuels.index), set(data.airports.index)
    errors = []

    def check(label, given, allowed):
        bad = set(given) - allowed
        if bad:
            errors.append(f"{label}: {sorted(bad)} not in {sorted(allowed)}")

    check("fleet", sc.fleet, types)
    check("reference_type", [sc.reference_type], types)
    check("fuel_max_tier", sc.fuel_max_tier, fuels)
    check("fuel_stations", sc.fuel_stations, fuels)
    check("tier_price_factor", sc.tier_price_factor, fuels)
    for fuel, listed in sc.fuel_stations.items():
        check(f"fuel_stations[{fuel}]", listed, stations)
    check("aircraft_overrides", sc.aircraft_overrides, types)
    for t, cols in sc.aircraft_overrides.items():
        check(f"aircraft_overrides[{t}]", cols, set(data.aircraft_types.columns))
    check("fuel_overrides", sc.fuel_overrides, fuels)
    for fu, cols in sc.fuel_overrides.items():
        check(f"fuel_overrides[{fu}]", cols, set(data.fuels.columns))
    check("objective", [sc.objective], set(OBJECTIVES))
    if sc.allow_drop and sc.objective != "cost":
        errors.append("allow_drop needs objective 'cost' (dropping a leg has a cost, not an energy or CO2)")
    if errors:
        raise ValueError(f"scenario '{sc.name}':\n  " + "\n  ".join(errors))
