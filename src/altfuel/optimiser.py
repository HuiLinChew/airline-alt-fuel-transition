"""Module 7 - Optimiser: basic fleet assignment model (FAM) on time-space networks.

Chooses which aircraft type flies each leg, or drops it, within the fleet owned.

Formulation (Hane et al. 1995 via Sherali et al. 2006, Eqs. cover/balance/count;
cancellation as in Wu et al. 2025, Eq. 2):

    min   sum_{k,l} c[k,l] x[k,l]  +  sum_l drop_cost[l] y[l]

    cover    sum_k x[k,l] + y[l] = 1                 every leg flown once or dropped
    balance  at every node: arrivals + ground in = departures + ground out
    count    sum of wrap-around (overnight) arcs of type k <= A[k]

    x[k,l], y[l] binary;  g (aircraft on the ground) integer >= 0

Range and fuel availability are already enforced: infeasible flights have no arc.
Outputs: assign (leg -> type or "dropped"), fleet used per type, objective value.
"""

from dataclasses import dataclass

import pandas as pd
import pulp

from .network_builder import Network
from .scenario_config import Scenario


@dataclass
class Result:
    status: str
    assign: pd.DataFrame      # leg_id -> type ("dropped" if not flown)
    fleet_used: dict          # type -> aircraft needed (overnight count)
    objective: float


def solve(net: Network, perf_c: pd.DataFrame, drop_cost: pd.Series, sc: Scenario,
          time_limit_s: int = 60) -> Result:
    m = pulp.LpProblem("fleet_assignment", pulp.LpMinimize)
    F = net.flights

    # Decision variables
    x = {(r.type, r.leg_id): pulp.LpVariable(f"x_{r.type}_{r.leg_id}", cat="Binary")
         for r in F.itertuples()}
    y = {l: pulp.LpVariable(f"y_{l}", cat="Binary") for l in drop_cost.index}
    g = {(k, s, i): pulp.LpVariable(f"g_{k}_{s}_{i}", lowBound=0, cat="Integer")
         for (k, s), times in net.nodes.items() for i in range(len(times))}

    # Objective: cost of flown legs + cost of dropped legs
    m += (pulp.lpSum(perf_c.at[kl, "c"] * var for kl, var in x.items())
          + pulp.lpSum(drop_cost[l] * y[l] for l in y))

    # Cover: each leg is flown by exactly one type, or dropped
    for l in y:
        flown = [x[k, l] for (k, leg) in x if leg == l]
        m += pulp.lpSum(flown) + y[l] == 1, f"cover_{l}"
        if not sc.allow_drop:
            m += y[l] == 0, f"no_drop_{l}"

    # Balance: at node i of station s, aircraft in = aircraft out.
    # Ground arc g[k,s,i] runs from node i to node i+1; the last one wraps to node 0.
    for (k, s), times in net.nodes.items():
        n = len(times)
        for i in range(n):
            arrive = [x[k, r.leg_id] for r in F[(F.type == k) & (F.destination == s)
                                              & (F.arr_node == i)].itertuples()]
            depart = [x[k, r.leg_id] for r in F[(F.type == k) & (F.origin == s)
                                              & (F.dep_node == i)].itertuples()]
            ground_in = g[k, s, (i - 1) % n]
            m += pulp.lpSum(arrive) + ground_in == pulp.lpSum(depart) + g[k, s, i], \
                 f"balance_{k}_{s}_{i}"

    # Count: aircraft on the overnight (wrap-around) arcs <= fleet available.
    # No leg is airborne at the count time (midnight) in a day schedule.
    overnight = {k: pulp.lpSum(g[k, s, len(t) - 1] for (kk, s), t in net.nodes.items() if kk == k)
                 for k in F.type.unique()}
    for k, expr in overnight.items():
        m += expr <= sc.fleet.get(k, 0), f"count_{k}"

    m.solve(pulp.HiGHS(msg=False, timeLimit=time_limit_s))
    status = pulp.LpStatus[m.status]
    if status != "Optimal":
        return Result(status, pd.DataFrame(), {}, float("nan"))

    flown = {l: k for (k, l), var in x.items() if var.value() > 0.5}
    assign = pd.DataFrame({"type": [flown.get(l, "dropped") for l in y]}, index=list(y))
    assign.index.name = "leg_id"
    fleet_used = {k: round(expr.value()) for k, expr in overnight.items()}
    return Result(status, assign, fleet_used, pulp.value(m.objective))
