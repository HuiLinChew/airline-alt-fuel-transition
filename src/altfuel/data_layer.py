"""Module 1: load the input tables and check they make sense.

Times are whole minutes from the start of the period.
"""

from dataclasses import dataclass, replace

import pandas as pd

from .utils import read_csv

AIRCRAFT_COLUMNS = ["fuel", "seats", "max_load_factor", "range_km", "turn_min", "refuel_pumps",
                    "cost_per_block_hour", "fuel_kg_fixed", "fuel_kg_per_km"]
FUEL_COLUMNS = ["label", "lhv_mj_per_kg", "co2_kg_per_kg", "wtt_co2_kg_per_kg", "carbon_price_share",
                "price_usd_per_kg", "default_max_tier", "refuel_flow_kg_s_per_pump", "refuel_plug_min"]


@dataclass
class Data:
    airports: pd.DataFrame        # one row per station
    legs: pd.DataFrame            # one row per leg_id
    aircraft_types: pd.DataFrame  # one row per type
    fuels: pd.DataFrame           # one row per fuel
    fuel_burn: pd.DataFrame       # optional fuel-vs-distance table (empty if no file)


def load_data(data_dir) -> Data:
    burn_file = data_dir / "fuel_burn.csv"
    if burn_file.exists():
        fuel_burn = read_csv(burn_file)
    else:
        fuel_burn = pd.DataFrame(columns=["type", "distance_km", "fuel_kg"])

    data = Data(
        airports=read_csv(data_dir / "airports.csv").set_index("station"),
        legs=read_csv(data_dir / "legs.csv").set_index("leg_id"),
        aircraft_types=read_csv(data_dir / "aircraft_types.csv").set_index("type"),
        fuels=read_csv(data_dir / "fuels.csv").set_index("fuel"),
        fuel_burn=fuel_burn,
    )
    validate(data)
    return data


def apply_overrides(data: Data, aircraft_overrides: dict, fuel_overrides: dict) -> Data:
    """Return a copy of the data with a scenario's changes to single cells."""
    aircraft = data.aircraft_types.copy()
    fuels = data.fuels.copy()
    for ac_type, changes in aircraft_overrides.items():
        for col, value in changes.items():
            aircraft.at[ac_type, col] = value
    for fuel, changes in fuel_overrides.items():
        for col, value in changes.items():
            fuels.at[fuel, col] = value
    return replace(data, aircraft_types=aircraft, fuels=fuels)


def validate(data: Data) -> None:
    legs, aircraft, fuels = data.legs, data.aircraft_types, data.fuels
    problems = []

    missing = [c for c in AIRCRAFT_COLUMNS if c not in aircraft.columns]
    if missing:
        problems.append(f"aircraft_types.csv is missing columns {missing}")
    missing = [c for c in FUEL_COLUMNS if c not in fuels.columns]
    if missing:
        problems.append(f"fuels.csv is missing columns {missing}")
    if problems:
        raise ValueError("\n".join(problems))

    if not legs.index.is_unique:
        problems.append("duplicate leg_id in legs.csv")
    unknown = (set(legs.origin) | set(legs.destination)) - set(data.airports.index)
    if unknown:
        problems.append(f"legs use stations missing from airports.csv: {sorted(unknown)}")
    if (legs.origin == legs.destination).any():
        problems.append("a leg starts and ends at the same station")
    if not (pd.api.types.is_integer_dtype(legs.dep_min) and pd.api.types.is_integer_dtype(legs.arr_min)):
        problems.append("dep_min and arr_min must be whole minutes")
    if (legs.dep_min < 0).any():
        problems.append("a leg departs before the start of the period")
    if (legs.arr_min <= legs.dep_min).any():
        problems.append("a leg arrives before it departs")
    if (legs.distance_km <= 0).any():
        problems.append("a leg has zero or negative distance")
    if (legs.pax < 0).any():
        problems.append("a leg has negative passengers")

    for col in ["seats", "max_load_factor", "range_km", "turn_min"]:
        if (aircraft[col] <= 0).any():
            problems.append(f"aircraft_types.csv: {col} must be > 0")
    unknown_fuels = set(aircraft.fuel) - set(fuels.index)
    if unknown_fuels:
        problems.append(f"aircraft use fuels missing from fuels.csv: {sorted(unknown_fuels)}")
    for ac_type, row in aircraft.iterrows():
        has_fit = pd.notna(row.fuel_kg_fixed) and pd.notna(row.fuel_kg_per_km)
        has_table = ac_type in set(data.fuel_burn.type)
        if not (has_fit or has_table):
            problems.append(f"{ac_type} has no fuel burn data")

    if problems:
        raise ValueError("\n".join(problems))
