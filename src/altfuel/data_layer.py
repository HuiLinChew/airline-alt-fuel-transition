"""Module 1 - Data layer.

Loads the raw tables and checks they are consistent. No modelling logic.
Outputs: airports, legs, aircraft_types (+ fuels), all keyed by shared IDs.
"""

from dataclasses import dataclass

import pandas as pd

from .utils import DATA_DIR, read_csv


@dataclass
class Data:
    airports: pd.DataFrame        # index station
    legs: pd.DataFrame            # index leg_id: origin, destination, dep_h, arr_h, distance_km, pax
    aircraft_types: pd.DataFrame  # index type: fuel, seats, range_km, turn_min, fuel burn fit
    fuels: pd.DataFrame           # index fuel: lhv, co2 factor, price


def load_data(data_dir=DATA_DIR) -> Data:
    d = Data(
        airports=read_csv(data_dir / "airports.csv").set_index("station"),
        legs=read_csv(data_dir / "legs.csv").set_index("leg_id"),
        aircraft_types=read_csv(data_dir / "aircraft_types.csv").set_index("type"),
        fuels=read_csv(data_dir / "fuels.csv").set_index("fuel"),
    )
    validate(d)
    return d


def validate(d: Data) -> None:
    """Fail early on broken inputs rather than getting odd optimiser results."""
    unknown = (set(d.legs.origin) | set(d.legs.destination)) - set(d.airports.index)
    assert not unknown, f"legs use stations missing from airports.csv: {unknown}"
    assert (d.legs.arr_h > d.legs.dep_h).all(), "a leg arrives before it departs"
    assert (d.legs.distance_km > 0).all(), "a leg has zero or negative distance"
    missing = set(d.aircraft_types.fuel) - set(d.fuels.index)
    assert not missing, f"aircraft use fuels missing from fuels.csv: {missing}"
