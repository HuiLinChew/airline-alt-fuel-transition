"""Module 5 - Cost/revenue.

One number per (type, leg) for the optimiser to compare, plus the cost of
dropping a leg.
Outputs: c[type, leg] (column "c" added to perf) and drop_cost[leg].

    c = fuel_kg x local price + carbon price x CO2 + block hours x type's hourly cost
    drop_cost = lost revenue = fare x pax   (Wu et al. 2025 cancellation)

fare = legs.csv "fare_usd" column if present, else distance x scenario yield.
The objective switch replaces c with energy or CO2 for "least fuel burn" or
"least emissions" runs (Justin et al. 2022 use CO2 as a second objective);
dropping legs is only allowed with the cost objective (checked in scenario_config).
Landing/nav fees are left out for now: they are the same for every type on a leg.
"""

import pandas as pd

from .data_layer import Data
from .scenario_config import Scenario


def add_costs(perf: pd.DataFrame, data: Data, airport_fuel: pd.DataFrame,
              sc: Scenario) -> pd.DataFrame:
    p = perf.copy()
    types = p.index.get_level_values("type")
    origin = data.legs.loc[p.index.get_level_values("leg_id"), "origin"].values
    price = [airport_fuel.loc[(o, f), "price_usd_per_kg"] for o, f in zip(origin, p.fuel)]
    p["fuel_cost_usd"] = p.fuel_kg * price
    p["carbon_cost_usd"] = p.co2_t * sc.carbon_price
    p["hourly_cost_usd"] = p.block_min / 60 * data.aircraft_types.loc[types, "cost_per_block_hour"].values
    p["cost_usd"] = p.fuel_cost_usd + p.carbon_cost_usd + p.hourly_cost_usd
    p["c"] = {"cost": p.cost_usd, "energy": p.energy_gj, "co2": p.co2_t}[sc.objective]
    return p


def drop_cost(data: Data, sc: Scenario) -> pd.Series:
    """Revenue lost by not flying each leg (only used when allow_drop is true)."""
    legs = data.legs
    fare = legs.fare_usd if "fare_usd" in legs else legs.distance_km * sc.yield_usd_per_pax_km
    return legs.pax * fare
