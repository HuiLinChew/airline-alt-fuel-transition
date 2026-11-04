"""Module 1: load the input tables and check they make sense.

Times are whole minutes from the start of the period.
"""

from dataclasses import dataclass, replace

import pandas as pd

from .utils import read_csv

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
    """Catch input mistakes that would otherwise give a wrong answer without any error."""
    legs, aircraft = data.legs, data.aircraft_types
    problems = []

    if not legs.index.is_unique:
        problems.append("duplicate leg_id in legs.csv")

    unknown = (set(legs.origin) | set(legs.destination)) - set(data.airports.index)
    if unknown:
        problems.append(f"legs use stations missing from airports.csv: {sorted(unknown)}")

    if not (pd.api.types.is_integer_dtype(legs.dep_min) and pd.api.types.is_integer_dtype(legs.arr_min)):
        problems.append("dep_min and arr_min must be whole minutes")

    unknown_fuels = set(aircraft.fuel) - set(data.fuels.index)
    if unknown_fuels:
        problems.append(f"aircraft use fuels missing from fuels.csv: {sorted(unknown_fuels)}")

    for ac_type, row in aircraft.iterrows():
        has_fit = pd.notna(row.fuel_kg_fixed) and pd.notna(row.fuel_kg_per_km)
        has_table = ac_type in set(data.fuel_burn.type)
        if not (has_fit or has_table):
            problems.append(f"{ac_type} has no fuel burn data")

    if problems:
        raise ValueError("\n".join(problems))
