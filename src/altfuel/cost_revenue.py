"""Module 5 - Cost/revenue.

One number per (type, leg) for the optimiser to compare, plus the cost of
dropping a leg.
Outputs: c[type, leg] (column "c" added to perf) and drop_cost[leg].

    c = fuel_kg x local price + carbon price x CO2 + block hours x cost per hour
    drop_cost = lost revenue = pax x distance x yield   (Wu et al. 2025 cancellation)

The objective switch replaces c with energy or CO2 for "least fuel burn" or
"least emissions" runs (Justin et al. 2022 use CO2 as a second objective).
Landing/nav fees are left out for now: they are the same for every type on a leg.
"""

import pandas as pd

from .data_layer import Data
from .scenario_config import Scenario


def add_costs(perf: pd.DataFrame, data: Data, airport_fuel: pd.DataFrame,
              sc: Scenario) -> pd.DataFrame:
    p = perf.copy()
    origin = data.legs.loc[p.index.get_level_values("leg_id"), "origin"].values
    price = [airport_fuel.loc[(o, f), "price_usd_per_kg"] for o, f in zip(origin, p.fuel)]
    p["fuel_cost_usd"] = p.fuel_kg * price
    p["carbon_cost_usd"] = p.co2_t * sc.carbon_price
    p["hourly_cost_usd"] = p.block_h * sc.cost_per_block_hour
    p["cost_usd"] = p.fuel_cost_usd + p.carbon_cost_usd + p.hourly_cost_usd
    p["c"] = {"cost": p.cost_usd, "energy": p.energy_gj, "co2": p.co2_t}[sc.objective]
    return p


def drop_cost(data: Data, sc: Scenario, perf_c: pd.DataFrame) -> pd.Series:
    """Penalty for not flying a leg, in the same units as c."""
    revenue = data.legs.pax * data.legs.distance_km * sc.yield_usd_per_pax_km
    if sc.objective == "cost":
        return revenue
    return pd.Series(10 * perf_c.c.max(), index=data.legs.index)  # energy/CO2 runs: never drop
