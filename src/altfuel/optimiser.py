"""Module 7 - Optimiser: basic fleet assignment model (FAM) on time-space networks.

Chooses which aircraft type flies each leg, or drops it, within the fleet owned.

Formulation (Hane et al. 1995 via Sherali et al. 2006, Eqs. cover/balance/count;
cancellation as in Wu et al. 2025, Eq. 2):

    min   sum_{k,l} c[k,l] x[k,l]  +  sum_l drop_cost[l] y[l]

    cover    sum_k x[k,l] + y[l] = 1                 every leg flown once or dropped
    balance  at every node: arrivals + ground in = departures + ground out
    count    aircraft on wrap-around arcs + flights crossing the count line <= A[k]

    x[k,l], y[l] binary;  g (aircraft on the ground) integer >= 0

Range and fuel availability are already enforced: infeasible flights have no arc.
Outputs: assign (leg -> type or "dropped"), fleet used per type, objective value.
"""

from collections import defaultdict
from dataclasses import dataclass

import pandas as pd
import pulp

from .network_builder import Network
from .scenario_config import Scenario


@dataclass
class Result:
    status: str               # "Optimal", "Feasible (time limit)", or the solver's failure status
    assign: pd.DataFrame      # leg_id -> type ("dropped" if not flown)
    fleet_used: dict          # type -> aircraft needed
    objective: float


def solve(net: Network, perf_c: pd.DataFrame, drop_cost: pd.Series, sc: Scenario) -> Result:
    m = pulp.LpProblem("fleet_assignment", pulp.LpMinimize)
    F = net.flights

    # Decision variables
    x = {(r.type, r.leg_id): pulp.LpVariable(f"x_{r.type}_{r.leg_id}", cat="Binary")
         for r in F.itertuples()}
    # (PuLP ignores bounds on "Binary" variables, so y is an integer bounded to 0..1, or 0..0)
    y = {l: pulp.LpVariable(f"y_{l}", lowBound=0, upBound=1 if sc.allow_drop else 0, cat="Integer")
         for l in drop_cost.index}
    g = {(k, s, i): pulp.LpVariable(f"g_{k}_{s}_{i}", lowBound=0, cat="Integer")
         for (k, s), times in net.nodes.items() for i in range(len(times))}

    # Group flight arcs once, so each constraint is a dictionary lookup
    by_leg, out_of, into = defaultdict(list), defaultdict(list), defaultdict(list)
    for r in F.itertuples():
        var = x[r.type, r.leg_id]
        by_leg[r.leg_id].append(var)
        out_of[r.type, r.origin, r.dep_node].append(var)
        into[r.type, r.destination, r.arr_node].append(var)

    # Objective: cost of flown legs + cost of dropped legs
    m += (pulp.lpSum(perf_c.at[kl, "c"] * var for kl, var in x.items())
          + pulp.lpSum(drop_cost[l] * y[l] for l in y))

    # Cover: each leg is flown by exactly one type, or dropped
    for l in y:
        m += pulp.lpSum(by_leg[l]) + y[l] == 1, f"cover_{l}"

    # Balance: at node i of station s, aircraft in = aircraft out.
    # Ground arc g[k,s,i] runs from node i to node i+1; the last one wraps to node 0.
    for (k, s), times in net.nodes.items():
        n = len(times)
        for i in range(n):
            m += (pulp.lpSum(into[k, s, i]) + g[k, s, (i - 1) % n]
                  == pulp.lpSum(out_of[k, s, i]) + g[k, s, i]), f"balance_{k}_{s}_{i}"

    # Count: aircraft crossing the count line (end of period) <= fleet available.
    # Those are aircraft on the ground overnight plus flights still flying/turning then.
    fleet_used = {}
    for k in F.type.unique():
        on_ground = [g[k, s, len(t) - 1] for (kk, s), t in net.nodes.items() if kk == k]
        in_air = [x[k, r.leg_id] for r in F[(F.type == k) & F.crosses].itertuples()]
        fleet_used[k] = pulp.lpSum(on_ground + in_air)
        m += fleet_used[k] <= sc.fleet.get(k, 0), f"count_{k}"

    opts = sc.solver
    m.solve(pulp.HiGHS(msg=opts.get("msg", False), timeLimit=opts.get("time_limit_s", 60),
                       gapRel=opts.get("mip_gap", 0.0)))
    if m.sol_status == pulp.LpSolutionOptimal:
        status = "Optimal"
    elif m.sol_status == pulp.LpSolutionIntegerFeasible:
        status = "Feasible (time limit)"   # best solution found; not proven optimal
    else:
        return Result(pulp.LpStatus[m.status], pd.DataFrame(columns=["type"]), {}, float("nan"))

    flown = {l: k for (k, l), var in x.items() if var.value() > 0.5}
    assign = pd.DataFrame({"type": [flown.get(l, "dropped") for l in y]}, index=list(y))
    assign.index.name = "leg_id"
    used = {k: round(expr.value()) for k, expr in fleet_used.items()}
    return Result(status, assign, used, pulp.value(m.objective))
