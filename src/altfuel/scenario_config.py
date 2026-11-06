"""Module 0: scenario settings.

Each scenario is a YAML file in scenarios/<timetable>/. It only lists the settings that
differ from the defaults below.
"""

from dataclasses import dataclass, field
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

    # Departure times: each leg may leave at its timetabled time or up to max_delay_min
    # later, in steps of delay_step_min. 0 = fixed timetable (fleet assignment only).
    max_delay_min: int = 0
    delay_step_min: int = 10

    # Bases (column `base` in airports.csv). With overnight_at_bases, every aircraft spends
    # the night at a base (any base).
    overnight_at_bases: bool = False

    period_min: int = 1440                   # 1440 = one day, 10080 = one week
    solver: dict = field(default_factory=lambda: {"time_limit_s": 60, "mip_gap": 0.0})
    sweep: dict = field(default_factory=dict)  # {parameter: ..., values: [...]}

    @property
    def data_path(self) -> Path:
        return ROOT / self.data_dir


def load_scenario(name_or_path) -> Scenario:
    path = Path(name_or_path)
    if not path.suffix:
        path = list(SCENARIO_DIR.rglob(f"{name_or_path}.yaml"))[0]   # in any folder
    with open(path) as f:
        return Scenario(**yaml.safe_load(f))


def scenario_files() -> list[Path]:
    """Scenario files, one folder per timetable, baselines first.
    scenarios/stress_tests/ is left out (only the tests use it)."""
    paths = [p for p in sorted(SCENARIO_DIR.glob("*/*.yaml")) if p.parent.name != "stress_tests"]
    paths.sort(key=lambda p: not p.stem.endswith("baseline"))   # baselines first
    return paths


def validate(sc: Scenario, data) -> None:
    """Catch misspelt names in a scenario. Without this, a typo like "LH2-NBB" in the
    fleet would just be ignored and the run would quietly be kerosene-only."""
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
    check("capacity_mode", [sc.capacity_mode], CAPACITY_MODES)

    # Lost passengers are costed in dollars, so they can't be mixed into an energy or CO2 objective
    if sc.objective != "cost" and (sc.allow_spill or sc.allow_drop):
        errors.append("allow_spill and allow_drop only work with the cost objective")

    if errors:
        raise ValueError(f"scenario '{sc.name}':\n  " + "\n  ".join(errors))
