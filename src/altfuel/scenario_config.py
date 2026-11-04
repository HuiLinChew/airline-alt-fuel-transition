"""Module 0: scenario settings.

Each scenario is a YAML file in scenarios/. It only lists the settings that
differ from the defaults below.
"""

from dataclasses import dataclass, field, fields
from pathlib import Path

import yaml

from .utils import ROOT, SCENARIO_DIR

OBJECTIVES = ["cost", "energy", "co2"]
CAPACITY_MODES = ["off", "check", "constrain"]

# Aircraft financing (Hoelzen et al. 2022). A scenario can change any of these.
DEFAULT_OWNERSHIP = {"interest_rate": 0.05, "depreciation_years": 14,
                     "residual_value": 0.05, "insurance_rate": 0.005}


@dataclass
class Scenario:
    name: str
    description: str = ""
    data_dir: str = "data/dummy"
    objective: str = "cost"                  # cost, energy or co2
    fleet: dict = field(default_factory=lambda: {"KER-NB": 30})   # aircraft available per type
    reference_type: str = "KER-NB"           # the schedule's block and turn times are for this type

    # Fuel availability and price
    fuel_max_tier: dict = field(default_factory=dict)    # fuel offered at airports with tier <= this
    fuel_stations: dict = field(default_factory=dict)    # extra airports offering a fuel
    tier_price_factor: dict = field(default_factory=lambda: {
        "lh2": {1: 1.0, 2: 1.1, 3: 1.25},
        "ch4": {1: 1.0, 2: 1.1, 3: 1.25},
        "ch4_e": {1: 1.0, 2: 1.1, 3: 1.25}})               # placeholder price bands

    # Changes to single cells of aircraft_types.csv / fuels.csv, e.g. {LH2-NB: {range_km: 2000}}
    aircraft_overrides: dict = field(default_factory=dict)
    fuel_overrides: dict = field(default_factory=dict)

    # Costs and emissions
    carbon_price: float = 0.0                # USD per tonne of CO2 burnt
    wtt_co2_kg_per_kg: dict = field(default_factory=dict)   # well-to-tank CO2; unlisted fuels use fuels.csv
    ownership: dict = field(default_factory=dict)           # changes to DEFAULT_OWNERSHIP
    yield_usd_per_pax_km: float = 0.148      # fare, if legs.csv has no fare_usd column

    # Passengers: by default every passenger must be carried
    allow_spill: bool = False                # fly the leg and lose passengers who don't fit
    allow_drop: bool = False                 # drop whole legs that cost more than they earn
    refuel_on_critical_path: bool = True     # extra refuelling time adds to the turn

    # Airport capacity: limits are capacity_share x the airport totals in airports.csv
    capacity_mode: str = "check"             # off, check (report only) or constrain
    capacity_share: float | dict = 0.15      # or {movements_per_hour: a, stands: b}

    period_min: int = 1440                   # 1440 = one day, 10080 = one week
    solver: dict = field(default_factory=lambda: {"time_limit_s": 60, "mip_gap": 0.0})
    sweep: dict = field(default_factory=dict)  # {parameter: ..., values: [...]}

    @property
    def data_path(self) -> Path:
        return ROOT / self.data_dir


def load_scenario(name_or_path) -> Scenario:
    path = Path(name_or_path)
    if not path.suffix:
        path = SCENARIO_DIR / f"{name_or_path}.yaml"
    with open(path) as f:
        settings = yaml.safe_load(f) or {}

    known = {f.name for f in fields(Scenario)}
    unknown = set(settings) - known
    if unknown:
        raise ValueError(f"{path.name}: unknown settings {sorted(unknown)}")
    return Scenario(**settings)


def load_all() -> list[Scenario]:
    """All scenarios, with the baseline first."""
    paths = sorted(SCENARIO_DIR.glob("*.yaml"))
    paths.sort(key=lambda p: p.stem != "baseline")
    return [load_scenario(p) for p in paths]


def validate(sc: Scenario, data) -> None:
    """Stop on any setting that doesn't match the data (e.g. a misspelt aircraft type)."""
    types = set(data.aircraft_types.index)
    fuels = set(data.fuels.index)
    stations = set(data.airports.index)
    errors = []

    def check(name, given, allowed):
        bad = set(given) - set(allowed)
        if bad:
            errors.append(f"{name}: {sorted(bad)} not in {sorted(allowed)}")

    check("fleet", sc.fleet, types)
    check("reference_type", [sc.reference_type], types)
    check("objective", [sc.objective], OBJECTIVES)
    check("fuel_max_tier", sc.fuel_max_tier, fuels)
    check("fuel_stations", sc.fuel_stations, fuels)
    for fuel, listed in sc.fuel_stations.items():
        check(f"fuel_stations[{fuel}]", listed, stations)
    check("tier_price_factor", sc.tier_price_factor, fuels)
    check("wtt_co2_kg_per_kg", sc.wtt_co2_kg_per_kg, fuels)
    check("ownership", sc.ownership, DEFAULT_OWNERSHIP)
    check("aircraft_overrides", sc.aircraft_overrides, types)
    for ac_type, cols in sc.aircraft_overrides.items():
        check(f"aircraft_overrides[{ac_type}]", cols, data.aircraft_types.columns)
    check("fuel_overrides", sc.fuel_overrides, fuels)
    for fuel, cols in sc.fuel_overrides.items():
        check(f"fuel_overrides[{fuel}]", cols, data.fuels.columns)

    for ac_type, n in sc.fleet.items():
        if not isinstance(n, int) or n < 0:
            errors.append(f"fleet: {ac_type} must be a whole number >= 0, not {n}")
    if sum(sc.fleet.values()) == 0:
        errors.append("fleet has no aircraft")

    if sc.objective != "cost" and (sc.allow_spill or sc.allow_drop):
        errors.append("allow_spill and allow_drop need the cost objective (lost passengers are a cost)")

    check("capacity_mode", [sc.capacity_mode], CAPACITY_MODES)
    check("airports.csv columns", ["hourly_capacity", "stands"], data.airports.columns)
    if isinstance(sc.capacity_share, dict):
        if set(sc.capacity_share) != {"movements_per_hour", "stands"}:
            errors.append("capacity_share needs both movements_per_hour and stands")
        shares = list(sc.capacity_share.values())
    else:
        shares = [sc.capacity_share]
    if not all(0 < s <= 1 for s in shares):
        errors.append("capacity_share must be between 0 and 1")

    if errors:
        raise ValueError(f"scenario '{sc.name}':\n  " + "\n  ".join(errors))
