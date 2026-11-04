"""Module 2: which fuels each airport offers, at what price, and its capacity.

A fuel is offered at airports whose tier is <= the scenario's limit for that fuel
(tier 1 = large hub), plus any airports the scenario names. Smaller airports pay
more for alternative fuels (tier_price_factor).
"""

import pandas as pd

from .data_layer import Data
from .scenario_config import Scenario


def airport_fuel(data: Data, sc: Scenario) -> pd.DataFrame:
    """One row per (station, fuel): available, price_usd_per_kg."""
    rows = []
    for station, airport in data.airports.iterrows():
        for fuel, f in data.fuels.iterrows():
            max_tier = sc.fuel_max_tier.get(fuel, f.default_max_tier)
            named = station in sc.fuel_stations.get(fuel, [])
            factor = sc.tier_price_factor.get(fuel, {}).get(int(airport.tier), 1.0)
            rows.append({"station": station, "fuel": fuel,
                         "available": bool(airport.tier <= max_tier or named),
                         "price_usd_per_kg": f.price_usd_per_kg * factor})
    return pd.DataFrame(rows).set_index(["station", "fuel"])


def airport_capacity(data: Data, sc: Scenario) -> pd.DataFrame:
    """Runway movements per hour and stands available to this airline at each station."""
    share = sc.capacity_share
    if not isinstance(share, dict):
        share = {"movements_per_hour": share, "stands": share}
    airports = data.airports
    return pd.DataFrame({"movements_per_hour": airports.hourly_capacity * share["movements_per_hour"],
                         "stands": airports.stands * share["stands"]})
