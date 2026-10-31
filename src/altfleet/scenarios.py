"""Scenarios as "disturbances" to the baseline parameter tables.

A scenario never edits model code; it lists changes to input tables:
    ("aircraft", "LH2-NB", "fleet_max"): 4      set a cell
    ("airports", "MAD", "fuels"): {"lh2"}       add fuels at an airport
Global settings (objective, airline_share, year, ...) go in `settings`.
Results are reported as deltas against the baseline.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from .data import Inputs
from .model import Solution, solve


@dataclass
class Scenario:
    name: str
    description: str
    changes: dict = field(default_factory=dict)
    objective: str = "energy"
    settings: dict = field(default_factory=dict)


def apply(inp: Inputs, sc: Scenario) -> Inputs:
    tables = {"airports": inp.airports.copy(), "aircraft": inp.aircraft.copy(),
              "fuels": inp.fuels.copy()}
    for (table, row, col), value in sc.changes.items():
        df = tables[table]
        if col == "fuels":  # additive: make a fuel available at an airport
            df.at[row, col] = frozenset(df.at[row, col]) | frozenset(value)
        else:
            df.at[row, col] = value
    return inp.with_(**tables, **sc.settings)


ALT_FLEET = {("aircraft", "LH2-NB", "fleet_max"): 4, ("aircraft", "CH4-NB", "fleet_max"): 4}

SCENARIOS = [
    Scenario("baseline", "Kerosene-only fleet, minimise fuel energy"),
    Scenario("alt_min_energy", "Up to 4 LH2 + 4 CH4 aircraft available, minimise fuel energy",
             ALT_FLEET, "energy"),
    Scenario("alt_min_co2", "Same fleet, minimise well-to-wake CO2",
             ALT_FLEET, "co2"),
    Scenario("alt_min_co2_lh2_mad_dub", "As alt_min_co2, plus LH2 supply at MAD and DUB",
             {**ALT_FLEET, ("airports", "MAD", "fuels"): {"lh2"},
              ("airports", "DUB", "fuels"): {"lh2"}}, "co2"),
]


def run_all(inp: Inputs, scenarios=SCENARIOS) -> tuple[dict[str, Solution], pd.DataFrame]:
    sols = {sc.name: solve(apply(inp, sc), sc.objective) for sc in scenarios}
    table = pd.DataFrame({k: s.kpis for k, s in sols.items()}).T.fillna(0)
    base = table.loc[scenarios[0].name]
    for c in ["energy_gj", "co2_t", "fuel_cost_usd", "aircraft", "flights"]:
        table[f"d_{c}"] = table[c] - base[c]
        if c in ("energy_gj", "co2_t", "fuel_cost_usd"):
            table[f"d_{c}_pct"] = 100 * table[f"d_{c}"] / base[c]
    return sols, table
