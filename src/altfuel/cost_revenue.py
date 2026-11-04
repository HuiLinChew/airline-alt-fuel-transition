"""Module 5: the cost of each (type, leg), and of dropping a leg or owning an aircraft.

    c          = fuel cost + carbon cost + hourly cost + spilled passengers x fare
    drop cost  = passengers x fare
    ownership  = aircraft price x (annuity + insurance) / 365, per aircraft per day

With the energy or co2 objective, c is the energy or CO2 instead.
Sources in docs/methods.md.
"""

import pandas as pd

from .data_layer import Data
from .scenario_config import DEFAULT_OWNERSHIP, Scenario


def add_costs(perf: pd.DataFrame, data: Data, airport_fuel: pd.DataFrame, sc: Scenario) -> pd.DataFrame:
    p = perf.copy()
    types = p.index.get_level_values("type")
    leg_ids = p.index.get_level_values("leg_id")

    # Fuel is bought at the origin, at that airport's price
    origins = data.legs.loc[leg_ids, "origin"]
    prices = airport_fuel.price_usd_per_kg.reindex(pd.MultiIndex.from_arrays([origins, p.fuel]))
    p["fuel_cost_usd"] = p.fuel_kg * prices.to_numpy()

    # The carbon price is paid on CO2 burnt, except by fuels exempt from it
    share = data.fuels.carbon_price_share.reindex(p.fuel).to_numpy()
    p["carbon_cost_usd"] = p.co2_ttw_t * sc.carbon_price * share

    hourly = data.aircraft_types.cost_per_block_hour.reindex(types).to_numpy()
    p["hourly_cost_usd"] = p.block_min / 60 * hourly
    p["spill_cost_usd"] = p.spill_pax * fare_per_pax(data, sc).loc[leg_ids].to_numpy()

    p["operating_cost_usd"] = p.fuel_cost_usd + p.carbon_cost_usd + p.hourly_cost_usd
    p["cost_usd"] = p.operating_cost_usd + p.spill_cost_usd

    if sc.objective == "cost":
        p["c"] = p.cost_usd
    elif sc.objective == "energy":
        p["c"] = p.energy_gj
    else:
        p["c"] = p.co2_t
    return p


def fare_per_pax(data: Data, sc: Scenario) -> pd.Series:
    legs = data.legs
    if "fare_usd" in legs:
        return legs.fare_usd
    return legs.distance_km * sc.yield_usd_per_pax_km


def drop_cost(data: Data, sc: Scenario) -> pd.Series:
    """Revenue lost by not flying each leg."""
    return data.legs.pax * fare_per_pax(data, sc)


def ownership_per_day(data: Data, sc: Scenario) -> pd.Series:
    """Daily cost of owning one aircraft of each type (Hoelzen et al. 2022, Eqs. A7-A8)."""
    o = {**DEFAULT_OWNERSHIP, **sc.ownership}
    rate, years, residual = o["interest_rate"], o["depreciation_years"], o["residual_value"]
    if rate > 0:
        annuity = rate * (1 - residual / (1 + rate) ** years) / (1 - 1 / (1 + rate) ** years)
    else:
        annuity = (1 - residual) / years

    if "price_usd" in data.aircraft_types:
        price = data.aircraft_types.price_usd.fillna(0)
    else:
        price = pd.Series(0.0, index=data.aircraft_types.index)
    return price * (annuity + o["insurance_rate"]) / 365
