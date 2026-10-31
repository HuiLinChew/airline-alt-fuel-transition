"""Module 9 - Analysis.

Runs the chain for each scenario and compares it with the baseline.
Outputs: per-scenario results, a summary table of deltas vs baseline, and a
carbon-price sweep (sensitivity). Comparing against an all-kerosene reference is
the standard way results are reported (Peter, Sirtori, Kamat, Kinene).

Chain:  data_layer -> airport_capability -> aircraft_performance -> cost_revenue
        -> network_builder -> optimiser -> rotation_checker
"""

from dataclasses import dataclass, replace

import pandas as pd

from . import (aircraft_performance, airport_capability, cost_revenue, network_builder,
               optimiser, rotation_checker)
from .data_layer import Data
from .scenario_config import Scenario


@dataclass
class Run:
    scenario: Scenario
    perf: pd.DataFrame        # perf with costs, (type, leg) rows
    result: optimiser.Result
    rotations: pd.DataFrame
    violations: list
    flown: pd.DataFrame       # assigned legs joined with their perf row
    kpis: dict


def run(data: Data, sc: Scenario) -> Run:
    fuel = airport_capability.airport_fuel(data, sc)
    perf = aircraft_performance.perf(data, fuel, sc)
    perf = cost_revenue.add_costs(perf, data, fuel, sc)
    drop = cost_revenue.drop_cost(data, sc, perf)
    net = network_builder.build_network(data, perf)
    res = optimiser.solve(net, perf, drop, sc)
    rot, viol = rotation_checker.build_rotations(data, perf, res.assign, sc.fleet)
    flown = perf.reset_index().merge(res.assign.reset_index(), on=["leg_id", "type"])
    return Run(sc, perf, res, rot, viol, flown, kpis(data, flown, res))


def kpis(data: Data, flown: pd.DataFrame, res) -> dict:
    ask = (flown.seats * data.legs.loc[flown.leg_id, "distance_km"].values).sum()
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
    for fuel in ["kerosene", "lh2", "ch4"]:
        out[f"share_{fuel}"] = (flown.fuel == fuel).mean() if len(flown) else 0
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


def carbon_price_sweep(data: Data, sc: Scenario, prices=range(0, 401, 50)) -> pd.DataFrame:
    """Re-run one scenario across carbon prices (a parameter 'disturbance')."""
    rows = []
    for p in prices:
        k = run(data, replace(sc, carbon_price=float(p))).kpis
        rows.append(dict(carbon_price=p, **k))
    return pd.DataFrame(rows)
