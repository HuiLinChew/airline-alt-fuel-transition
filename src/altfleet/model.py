"""Daily fleet-assignment MILP (route level).

Decision variables
    x[a]  integer  daily flights on arc a = (aircraft type, origin, destination)
    n[k]  integer  aircraft of type k used

Constraints
    demand       sum_k pax_cap_k * x[k,i,j] >= D_ij        every passenger is served
    balance      departures = arrivals, per type per airport  (aircraft end where they start)
    utilisation  sum x * (block + turnaround) <= n_k * operating hours
    fleet        n_k <= fleet_max_k
    slots        departures + arrivals at airport <= daily_slots
    range/fuel   handled by only creating feasible arcs (data.arcs)

Objective: minimise energy (GJ), CO2 (t) or fuel cost (USD), plus a tiny
penalty on aircraft count so ties break towards the smallest fleet.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import pulp

from .data import Inputs, arcs, daily_demand

OBJECTIVES = {"energy": "energy_gj", "co2": "co2_t", "cost": "fuel_cost_usd"}


@dataclass
class Solution:
    status: str
    objective: str
    flights: pd.DataFrame  # arcs with x > 0, column "flights"
    fleet: pd.Series       # aircraft used per type
    kpis: dict


def solve(inp: Inputs, objective: str = "energy", time_limit_s: int = 60,
          verbose: bool = False) -> Solution:
    A = arcs(inp)
    D = daily_demand(inp)
    types = sorted(A["type"].unique())
    m = pulp.LpProblem("fleet_assignment", pulp.LpMinimize)

    x = {i: pulp.LpVariable(f"x_{r.type}_{r.origin}_{r.destination}", lowBound=0, cat="Integer")
         for i, r in A.iterrows()}
    n = {k: pulp.LpVariable(f"n_{k}", lowBound=0,
                            upBound=int(inp.aircraft.loc[k, "fleet_max"]), cat="Integer")
         for k in types}

    col = OBJECTIVES[objective]
    eps = 1e-4 * A[col].min()  # tie-break: fewest aircraft
    m += pulp.lpSum(A.at[i, col] * x[i] for i in x) + eps * pulp.lpSum(n.values())

    for (o, d), pax in D.items():
        idx = A.index[(A.origin == o) & (A.destination == d)]
        m += pulp.lpSum(A.at[i, "pax_cap"] * x[i] for i in idx) >= pax, f"demand_{o}_{d}"

    for k in types:
        Ak = A[A.type == k]
        for ap in inp.airports.index:
            dep = Ak.index[Ak.origin == ap]
            arr = Ak.index[Ak.destination == ap]
            m += (pulp.lpSum(x[i] for i in dep) == pulp.lpSum(x[i] for i in arr)), f"balance_{k}_{ap}"
        m += (pulp.lpSum(A.at[i, "cycle_h"] * x[i] for i in Ak.index)
              <= n[k] * inp.op_hours), f"utilisation_{k}"

    for ap, row in inp.airports.iterrows():
        mov = A.index[(A.origin == ap) | (A.destination == ap)]
        m += pulp.lpSum(x[i] for i in mov) <= int(row["daily_slots"]), f"slots_{ap}"

    m.solve(pulp.HiGHS(msg=verbose, timeLimit=time_limit_s))
    status = pulp.LpStatus[m.status]
    if status != "Optimal":
        return Solution(status, objective, A.iloc[0:0].assign(flights=0), pd.Series(dtype=int), {})

    A["flights"] = [round(x[i].value()) for i in A.index]
    F = A[A.flights > 0].reset_index(drop=True)
    fleet = pd.Series({k: round(n[k].value()) for k in types}, name="aircraft")
    return Solution(status, objective, F, fleet, kpis(F, fleet, D))


def kpis(F: pd.DataFrame, fleet: pd.Series, D: pd.Series) -> dict:
    w = F["flights"]
    ask = (w * F["seats"] * F["distance_km"]).sum()
    ask_by_fuel = (w * F["seats"] * F["distance_km"]).groupby(F["fuel"]).sum()
    out = {
        "flights": int(w.sum()),
        "aircraft": int(fleet.sum()),
        "pax_demand": int(D.sum()),
        "seats": int((w * F["seats"]).sum()),
        "ask_m": ask / 1e6,
        "energy_gj": (w * F["energy_gj"]).sum(),
        "co2_t": (w * F["co2_t"]).sum(),
        "fuel_cost_usd": (w * F["fuel_cost_usd"]).sum(),
    }
    out["mj_per_ask"] = out["energy_gj"] * 1000 / ask
    out["g_co2_per_ask"] = out["co2_t"] * 1e6 / ask
    for fuel, v in ask_by_fuel.items():
        out[f"ask_share_{fuel}"] = v / ask
    for k, v in fleet.items():
        out[f"aircraft_{k}"] = int(v)
    return out
