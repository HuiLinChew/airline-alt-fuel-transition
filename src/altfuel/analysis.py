"""Module 9: run a scenario through the whole chain, and compare scenarios.

data_layer -> airport_capability -> aircraft_performance -> cost_revenue
-> network_builder -> optimiser -> rotation_checker
"""

from dataclasses import dataclass, replace

import pandas as pd

from . import (aircraft_performance, airport_capability, cost_revenue, network_builder,
               optimiser, rotation_checker)
from .data_layer import Data, apply_overrides, load_data
from .data_layer import validate as validate_data
from .scenario_config import Scenario, validate

SOLVED = ["Optimal", "Feasible (time limit)"]


@dataclass
class Run:
    scenario: Scenario
    data: Data                  # after the scenario's overrides
    airport_fuel: pd.DataFrame
    airport_capacity: pd.DataFrame
    perf: pd.DataFrame          # one row per (type, leg), with costs
    result: optimiser.Result
    rotations: pd.DataFrame
    violations: list
    flown: pd.DataFrame         # the perf rows of the legs actually flown
    ownership: pd.Series        # ownership cost per aircraft for the period, by type
    kpis: dict


def run(sc: Scenario, data: Data = None) -> Run:
    if data is None:
        data = load_data(sc.data_path)
    validate(sc, data)
    data = apply_overrides(data, sc.aircraft_overrides, sc.fuel_overrides)
    validate_data(data)

    fuel = airport_capability.airport_fuel(data, sc)
    capacity = airport_capability.airport_capacity(data, sc)
    perf = aircraft_performance.perf(data, fuel, sc)
    perf = cost_revenue.add_costs(perf, data, fuel, sc)
    drop = cost_revenue.drop_cost(data, sc)
    ownership = cost_revenue.ownership_per_day(data, sc)

    net = network_builder.build_network(data, perf, sc.period_min)
    result = optimiser.solve(net, perf, drop, sc, capacity, ownership)
    rotations, violations = rotation_checker.build_rotations(data, perf, result.assign, result.fleet_used)

    flown = perf.reset_index().merge(result.assign.reset_index(), on=["leg_id", "type"])
    ownership = ownership * sc.period_min / 1440
    return Run(sc, data, fuel, capacity, perf, result, rotations, violations, flown, ownership,
               kpis(data, flown, result, drop, ownership))


def kpis(data: Data, flown: pd.DataFrame, result, drop_cost: pd.Series, ownership: pd.Series) -> dict:
    if result.status not in SOLVED:
        return {"status": result.status}

    dropped = result.assign.index[result.assign.type == "dropped"]
    ownership_cost = sum(n * ownership.get(k, 0) for k, n in result.fleet_used.items())
    out = {
        "status": result.status,
        "legs_flown": len(flown),
        "legs_dropped": len(dropped),
        "aircraft": sum(result.fleet_used.values()),
        "pax_demand": int(data.legs.pax.sum()),
        "pax_spilled": int(flown.spill_pax.sum()),
        "pax_on_dropped_legs": int(data.legs.pax.loc[dropped].sum()),
        "energy_gj": flown.energy_gj.sum(),
        "co2_ttw_t": flown.co2_ttw_t.sum(),
        "co2_wtt_t": flown.co2_wtt_t.sum(),
        "co2_t": flown.co2_t.sum(),
        "fuel_cost_usd": flown.fuel_cost_usd.sum(),
        "carbon_cost_usd": flown.carbon_cost_usd.sum(),
        "operating_cost_usd": flown.operating_cost_usd.sum(),
        "ownership_cost_usd": ownership_cost,
        "spill_cost_usd": flown.spill_cost_usd.sum(),
        "dropped_revenue_usd": drop_cost.loc[dropped].sum(),
    }
    out["total_cost_usd"] = (out["operating_cost_usd"] + out["ownership_cost_usd"]
                             + out["spill_cost_usd"] + out["dropped_revenue_usd"])

    for fuel in data.fuels.index:
        out[f"share_{fuel}"] = (flown.fuel == fuel).mean() if len(flown) else 0.0

    cap = result.capacity
    out["capacity_breaches"] = int(cap.over.sum()) if len(cap) else 0
    for measure in ["movements_per_hour", "stands"]:
        rows = cap[cap.measure == measure] if len(cap) else cap
        out[f"peak_util_{measure}"] = rows.utilisation.max() if len(rows) else float("nan")
    return out


def compare(runs: list[Run]) -> pd.DataFrame:
    """KPIs of every run, with differences from the first run (the baseline)."""
    table = pd.DataFrame({r.scenario.name: r.kpis for r in runs}).T
    base = table.iloc[0]
    for col in ["total_cost_usd", "co2_t", "energy_gj", "aircraft", "legs_dropped"]:
        table[f"d_{col}"] = table[col].astype(float) - float(base[col])
    for col in ["total_cost_usd", "co2_t"]:
        table[f"d_{col}_pct"] = 100 * table[f"d_{col}"] / float(base[col])
    return table


def sweep(sc: Scenario, parameter: str, values, data: Data = None) -> pd.DataFrame:
    """Re-run a scenario for each value of one setting, e.g. sweep(sc, "carbon_price", [0, 100, 200])."""
    if data is None:
        data = load_data(sc.data_path)
    rows = []
    for value in values:
        kpi = run(replace(sc, **{parameter: value}), data).kpis
        label = value if isinstance(value, (int, float, str)) else str(value)
        rows.append({parameter: label, **kpi})
    return pd.DataFrame(rows)
