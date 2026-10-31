"""Module 2 - Airport capability.

Which fuels each airport offers, and at what price.
Output: airport_fuel with one row per (station, fuel): available, price_usd_per_kg.

Method: tier lookup. A fuel is offered at every airport whose tier is <= the
scenario's limit for that fuel (kerosene everywhere). Price = base price x a
tier factor, since smaller airports pay more for LH2 (Hoelzen et al. 2025).
Single year for now; a year column comes with the stock-flow module.
"""

import pandas as pd

from .data_layer import Data
from .scenario_config import Scenario


def airport_fuel(data: Data, sc: Scenario) -> pd.DataFrame:
    rows = []
    for station, ap in data.airports.iterrows():
        for fuel, f in data.fuels.iterrows():
            if fuel == "kerosene":
                available, factor = True, 1.0
            else:
                available = ap.tier <= sc.fuel_max_tier.get(fuel, 0)
                factor = sc.tier_price_factor.get(int(ap.tier), 1.0)
            base = sc.fuel_price.get(fuel, f.price_usd_per_kg)
            rows.append(dict(station=station, fuel=fuel, available=available,
                             price_usd_per_kg=base * factor))
    return pd.DataFrame(rows).set_index(["station", "fuel"])
