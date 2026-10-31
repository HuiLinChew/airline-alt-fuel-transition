"""Load model inputs and derive per-route, per-aircraft quantities.

All inputs live in plain CSVs (data/dummy/ for now) so they can be swapped for
real data without touching the model. Scenario "disturbances" are applied to
these tables before the model is built (see scenarios.py).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DUMMY_DIR = ROOT / "data" / "dummy"

BASE_YEAR = 2015  # year of the route demand data (from Hasan's segment_data.csv)


@dataclass(frozen=True)
class Inputs:
    airports: pd.DataFrame   # index: iata
    aircraft: pd.DataFrame   # index: type
    fuel_burn: pd.DataFrame  # long table: type, distance_km, energy_gj
    fuels: pd.DataFrame      # index: fuel
    demand: pd.DataFrame     # origin, destination, distance_km, annual_pax_2015, growth_pct
    airline_share: float = 0.15   # share of each route's market our airline carries
    year: int = BASE_YEAR
    op_start_h: float = 6.0       # first departure
    op_end_h: float = 23.0        # last arrival (curfew)
    taxi_overhead_h: float = 0.5  # taxi + climb/descent allowance added to block time

    @property
    def op_hours(self) -> float:
        return self.op_end_h - self.op_start_h

    def with_(self, **kwargs) -> "Inputs":
        return replace(self, **kwargs)


def _read(path: Path) -> pd.DataFrame:
    # keep_default_na=False so a region code "NA" is never read as missing
    return pd.read_csv(path, keep_default_na=False, na_values=[""])


def load_inputs(data_dir: Path = DUMMY_DIR, **kwargs) -> Inputs:
    airports = _read(data_dir / "airports.csv").set_index("iata")
    airports["fuels"] = airports["fuels"].str.split(";").apply(frozenset)
    return Inputs(
        airports=airports,
        aircraft=_read(data_dir / "aircraft.csv").set_index("type"),
        fuel_burn=_read(data_dir / "fuel_burn.csv"),
        fuels=_read(data_dir / "fuels.csv").set_index("fuel"),
        demand=_read(data_dir / "demand.csv"),
        **kwargs,
    )


def daily_demand(inp: Inputs) -> pd.Series:
    """Daily pax our airline must carry on each directed route, index (origin, destination)."""
    d = inp.demand
    growth = (1 + d["growth_pct"] / 100) ** (inp.year - BASE_YEAR)
    pax = d["annual_pax_2015"] * growth * inp.airline_share / 365
    return pd.Series(np.ceil(pax).astype(int).values,
                     index=pd.MultiIndex.from_frame(d[["origin", "destination"]]))


def route_distances(inp: Inputs) -> pd.Series:
    d = inp.demand
    return pd.Series(d["distance_km"].values,
                     index=pd.MultiIndex.from_frame(d[["origin", "destination"]]))


def energy_per_flight_gj(inp: Inputs, ac_type: str, distance_km: float) -> float:
    """Fuel energy for one flight, by linear interpolation of the (possibly
    non-linear) fuel-burn table. Distances are fixed per route, so a non-linear
    burn curve keeps the optimisation linear."""
    t = inp.fuel_burn[inp.fuel_burn["type"] == ac_type].sort_values("distance_km")
    if distance_km > t["distance_km"].max():
        return float("nan")  # outside the table: treat as out of range
    return float(np.interp(distance_km, t["distance_km"], t["energy_gj"]))


def block_time_h(inp: Inputs, ac_type: str, distance_km: float) -> float:
    return distance_km / inp.aircraft.loc[ac_type, "cruise_kmh"] + inp.taxi_overhead_h


def arcs(inp: Inputs) -> pd.DataFrame:
    """Every feasible (aircraft type, origin, destination) arc with its per-flight
    quantities. An arc is feasible if it is within range and the aircraft's fuel
    is available at the origin (i.e. refuel before every departure; no tankering)."""
    rows = []
    dist = route_distances(inp)
    for ac, a in inp.aircraft.iterrows():
        if a["fleet_max"] <= 0:
            continue
        for (o, d), km in dist.items():
            if km > a["range_km"] or a["fuel"] not in inp.airports.loc[o, "fuels"]:
                continue
            e = energy_per_flight_gj(inp, ac, km)
            if np.isnan(e):
                continue
            f = inp.fuels.loc[a["fuel"]]
            rows.append(dict(
                type=ac, fuel=a["fuel"], origin=o, destination=d, distance_km=km,
                seats=a["seats"], pax_cap=a["seats"] * a["max_load_factor"],
                block_h=block_time_h(inp, ac, km),
                cycle_h=block_time_h(inp, ac, km) + a["turnaround_min"] / 60,
                energy_gj=e,
                co2_t=e * f["co2_g_per_mj"] / 1000,          # GJ * g/MJ / 1000 = t
                fuel_cost_usd=e * f["price_usd_per_gj"],
            ))
    return pd.DataFrame(rows)
