"""Module 9 - Analysis.

Runs the chain for each scenario and compares it with the baseline.
Outputs: per-scenario results, a summary table of deltas vs baseline, and
parameter sweeps (sensitivity). Comparing against an all-kerosene reference is
the standard way results are reported (Peter, Sirtori, Kamat, Kinene).

Chain:  data_layer -> airport_capability -> aircraft_performance -> cost_revenue
        -> network_builder -> optimiser -> rotation_checker
"""

from dataclasses import dataclass, replace

import pandas as pd

from . import (aircraft_performance, airport_capability, cost_revenue, network_builder,
               optimiser, rotation_checker)
from .data_layer import Data, apply_overrides, load_data
from .scenario_config import Scenario, validate


@dataclass
class Run:
    scenario: Scenario
    data: Data                # the data after this scenario's overrides
    airport_fuel: pd.DataFrame
    perf: pd.DataFrame        # perf with costs, (type, leg) rows
    result: optimiser.Result
    rotations: pd.DataFrame
    violations: list
    flown: pd.DataFrame       # assigned legs joined with their perf row
    kpis: dict


def run(sc: Scenario, data: Data = None) -> Run:
    """Run one scenario. Loads its data folder unless data is passed in."""
    data = data if data is not None else load_data(sc.data_path)
    validate(sc, data)
    data = apply_overrides(data, sc.aircraft_overrides, sc.fuel_overrides)
    fuel = airport_capability.airport_fuel(data, sc)
    perf = aircraft_performance.perf(data, fuel, sc)
    perf = cost_revenue.add_costs(perf, data, fuel, sc)
    net = network_builder.build_network(data, perf, sc.period_min)
    res = optimiser.solve(net, perf, cost_revenue.drop_cost(data, sc), sc)
    rot, viol = rotation_checker.build_rotations(data, perf, res.assign, sc.fleet)
    flown = perf.reset_index().merge(res.assign.reset_index(), on=["leg_id", "type"])
    return Run(sc, data, fuel, perf, res, rot, viol, flown, kpis(data, flown, res))


def kpis(data: Data, flown: pd.DataFrame, res) -> dict:
    out = dict(
        status=res.status,
        legs_flown=len(flown),
        legs_dropped=int((res.assign.type == "dropped").sum()),
        aircraft=sum(res.fleet_used.values()),
        energy_gj=flown.energy_gj.sum(),
        co2_t=flown.co2_t.sum(),
        fuel_cost_usd=flown.fuel_cost_usd.sum(),
        carbon_cost_usd=flown.carbon_cost_usd.sum(),
        total_cost_usd=flown.cost_usd.sum(),
    )
    for fuel in data.fuels.index:
        out[f"share_{fuel}"] = (flown.fuel == fuel).mean() if len(flown) else 0.0
    return out


def compare(runs: list[Run]) -> pd.DataFrame:
    """KPI table with deltas vs the first run (the baseline)."""
    table = pd.DataFrame({r.scenario.name: r.kpis for r in runs}).T
    base = table.iloc[0]
    for col in ["total_cost_usd", "co2_t", "energy_gj", "aircraft", "legs_dropped"]:
        table[f"d_{col}"] = table[col].astype(float) - float(base[col])
    for col in ["total_cost_usd", "co2_t"]:
        table[f"d_{col}_pct"] = 100 * table[f"d_{col}"] / float(base[col])
    return table


def sweep(sc: Scenario, parameter: str, values, data: Data = None) -> pd.DataFrame:
    """Re-run one scenario for each value of one top-level setting, e.g.
    sweep(sc, "carbon_price", range(0, 401, 50)) or sweep(sc, "fleet", [{...}, {...}])."""
    data = data if data is not None else load_data(sc.data_path)
    rows = []
    for v in values:
        k = run(replace(sc, **{parameter: v}), data).kpis
        rows.append({parameter: v if isinstance(v, (int, float, str)) else str(v), **k})
    return pd.DataFrame(rows)
