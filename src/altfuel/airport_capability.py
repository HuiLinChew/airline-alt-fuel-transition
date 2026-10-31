"""Module 2 - Airport capability.

Which fuels each airport offers, and at what price.
Output: airport_fuel with one row per (station, fuel): available, price_usd_per_kg.

Method: tier lookup. A fuel is offered at every airport whose tier is <= the
scenario's limit for that fuel (default from fuels.csv: kerosene everywhere,
others nowhere), plus any stations the scenario lists explicitly. Price = base
price x a tier factor, since smaller airports pay more for LH2 (Hoelzen et al. 2025).
Single year for now; a year column comes with the stock-flow module.
"""

import pandas as pd

from .data_layer import Data
from .scenario_config import Scenario


def airport_fuel(data: Data, sc: Scenario) -> pd.DataFrame:
    rows = []
    for station, ap in data.airports.iterrows():
        for fuel, f in data.fuels.iterrows():
            max_tier = sc.fuel_max_tier.get(fuel, f.default_max_tier)
            available = ap.tier <= max_tier or station in sc.fuel_stations.get(fuel, [])
            factor = sc.tier_price_factor.get(fuel, {}).get(int(ap.tier), 1.0)
            rows.append(dict(station=station, fuel=fuel, available=bool(available),
                             price_usd_per_kg=f.price_usd_per_kg * factor))
    return pd.DataFrame(rows).set_index(["station", "fuel"])
