"""Module 9: run a scenario through the whole chain, and compare scenarios.

data_layer -> airport_capability -> aircraft_performance -> cost_revenue
-> network_builder -> optimiser -> rotation_checker
"""

from dataclasses import dataclass, replace

import pandas as pd

from . import (aircraft_performance, airport_capability, cost_revenue, network_builder,
               optimiser, rotation_checker)
from .data_layer import Data, apply_overrides, delay_copies, load_data
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
    cycles: pd.DataFrame        # multi-day aircraft cycles
    flown: pd.DataFrame         # the perf rows of the legs actually flown
    ownership: pd.Series        # ownership cost per aircraft for the period, by type
    kpis: dict


def run(sc: Scenario, data: Data = None) -> Run:
    if data is None:
        data = load_data(sc.data_path)
    validate(sc, data)
    data = apply_overrides(data, sc.aircraft_overrides, sc.fuel_overrides)
    validate_data(data)
    legs = delay_copies(data.legs, sc.max_delay_min, sc.delay_step_min, sc.period_min)
    data = replace(data, legs=legs)

    fuel = airport_capability.airport_fuel(data, sc)
    capacity = airport_capability.airport_capacity(data, sc)
    perf = aircraft_performance.perf(data, fuel, sc)
    perf = cost_revenue.add_costs(perf, data, fuel, sc)
    drop = cost_revenue.drop_cost(data, sc)
    ownership = cost_revenue.ownership_per_day(data, sc)

    net = network_builder.build_network(data, perf, sc.period_min)
    result = optimiser.solve(net, perf, drop, ownership, capacity, sc)
    rotations, violations = rotation_checker.build_rotations(data, perf, result.assign,
                                                             result.fleet_used)
    cycles = rotation_checker.day_cycles(rotations, sc.period_min)

    flown = perf.reset_index().merge(result.assign.reset_index(), on=["leg_id", "type"])
    ownership = ownership * sc.period_min / 1440
    kpi = kpis(data, flown, result, drop, ownership, cycles)
    return Run(sc, data, fuel, capacity, perf, result, rotations, violations, cycles, flown,
               ownership, kpi)


def kpis(data: Data, flown: pd.DataFrame, result, drop_cost: pd.Series, ownership: pd.Series,
         cycles: pd.DataFrame) -> dict:
    if result.status not in SOLVED:
        return {"status": result.status}

    dropped = result.assign.index[result.assign.type == "dropped"]
    ownership_cost = sum(n * ownership[k] for k, n in result.fleet_used.items())
    delays = data.legs.delay_min.loc[flown.leg_id]
    out = {
        "status": result.status,
        "legs_flown": len(flown),
        "legs_dropped": len(dropped),
        "aircraft": sum(result.fleet_used.values()),
        "legs_delayed": int((delays > 0).sum()),
        "total_delay_min": int(delays.sum()),
        "pax_demand": int(data.legs.pax[data.legs.delay_min == 0].sum()),
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
        "longest_cycle_days": int(cycles.days.max()) if len(cycles) else 0,
    }
    out["total_cost_usd"] = (out["operating_cost_usd"] + out["ownership_cost_usd"]
                             + out["spill_cost_usd"] + out["dropped_revenue_usd"])

    for fuel in data.fuels.index:
        out[f"share_{fuel}"] = (flown.fuel == fuel).mean()

    cap = result.capacity
    if len(cap):          # empty when capacity_mode is "off"
        out["capacity_breaches"] = int(cap.over.sum())
        peak = cap.groupby("measure").utilisation.max()
        out["peak_util_movements_per_hour"] = peak["movements_per_hour"]
        out["peak_util_stands"] = peak["stands"]
    return out


def compare(runs: list[Run]) -> pd.DataFrame:
    """KPIs of every run, with differences from its baseline: the first run on the same data."""
    table = pd.DataFrame({r.scenario.name: r.kpis for r in runs}).T
    first = {}
    for r in runs:
        first.setdefault(r.scenario.data_dir, r.scenario.name)
    baselines = [first[r.scenario.data_dir] for r in runs]
    base = table.loc[baselines].set_index(table.index)
    table.insert(0, "baseline", baselines)
    for col in ["total_cost_usd", "co2_t", "energy_gj", "aircraft", "legs_dropped"]:
        table[f"d_{col}"] = table[col].astype(float) - base[col].astype(float)
    for col in ["total_cost_usd", "co2_t"]:
        table[f"d_{col}_pct"] = 100 * table[f"d_{col}"] / base[col].astype(float)
    return table


def sweep(sc: Scenario, parameter: str, values, data: Data = None) -> pd.DataFrame:
    """Re-run a scenario for each value of one setting, e.g. sweep(sc, "carbon_price", [0, 200])."""
    if data is None:
        data = load_data(sc.data_path)
    rows = []
    for value in values:
        kpi = run(replace(sc, **{parameter: value}), data).kpis
        rows.append({parameter: value, **kpi})
    return pd.DataFrame(rows)
