"""Module 1 - Data layer.

Loads the raw tables and checks they are consistent. No modelling logic.
Outputs: airports, legs, aircraft_types, fuels (+ optional fuel_burn table),
all keyed by shared IDs. Times are integer minutes after the start of the period.
"""

from dataclasses import dataclass, replace

import pandas as pd

from .utils import read_csv


@dataclass
class Data:
    airports: pd.DataFrame        # index station
    legs: pd.DataFrame            # index leg_id: origin, destination, dep_min, arr_min, distance_km, pax[, fare_usd]
    aircraft_types: pd.DataFrame  # index type: fuel, seats, range, turn, pumps, hourly cost, burn fit
    fuels: pd.DataFrame           # index fuel: lhv, co2 factor, price, availability default, refuel rates
    fuel_burn: pd.DataFrame       # optional table: type, distance_km, fuel_kg (empty if no file)


def load_data(data_dir) -> Data:
    burn_file = data_dir / "fuel_burn.csv"
    d = Data(
        airports=read_csv(data_dir / "airports.csv").set_index("station"),
        legs=read_csv(data_dir / "legs.csv").set_index("leg_id"),
        aircraft_types=read_csv(data_dir / "aircraft_types.csv").set_index("type"),
        fuels=read_csv(data_dir / "fuels.csv").set_index("fuel"),
        fuel_burn=read_csv(burn_file) if burn_file.exists() else pd.DataFrame(
            columns=["type", "distance_km", "fuel_kg"]),
    )
    validate(d)
    return d


def apply_overrides(d: Data, aircraft_overrides: dict, fuel_overrides: dict) -> Data:
    """Copy of the data with scenario changes to aircraft_types / fuels cells."""
    ac, fu = d.aircraft_types.copy(), d.fuels.copy()
    for table, overrides in [(ac, aircraft_overrides), (fu, fuel_overrides)]:
        for row, cols in overrides.items():
            for col, value in cols.items():
                table.at[row, col] = value
    return replace(d, aircraft_types=ac, fuels=fu)


def validate(d: Data) -> None:
    """Fail early on broken inputs rather than getting odd optimiser results."""
    legs, ac = d.legs, d.aircraft_types
    assert legs.index.is_unique, "duplicate leg_id in legs.csv"
    unknown = (set(legs.origin) | set(legs.destination)) - set(d.airports.index)
    assert not unknown, f"legs use stations missing from airports.csv: {unknown}"
    assert (legs.origin != legs.destination).all(), "a leg starts and ends at the same station"
    assert pd.api.types.is_integer_dtype(legs.dep_min), "dep_min must be whole minutes"
    assert (legs.arr_min > legs.dep_min).all(), "a leg arrives before it departs"
    assert (legs.distance_km > 0).all(), "a leg has zero or negative distance"
    missing = set(ac.fuel) - set(d.fuels.index)
    assert not missing, f"aircraft use fuels missing from fuels.csv: {missing}"
    table_types = set(d.fuel_burn.type)
    no_burn = [t for t in ac.index if t not in table_types
               and pd.isna(ac.loc[t, ["fuel_kg_fixed", "fuel_kg_per_km"]]).any()]
    assert not no_burn, f"no fuel burn (fit or fuel_burn.csv table) for types: {no_burn}"
