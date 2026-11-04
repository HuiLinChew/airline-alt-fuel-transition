"""Module 7: which aircraft type flies each leg (fleet assignment).

A mixed-integer program on the time-space networks (Hane et al. 1995, via
Sherali et al. 2006), with optional leg cancellation (Wu et al. 2025):

    minimise   sum c[k,l] x[k,l] + sum drop_cost[l] y[l] + sum ownership[k] n[k]

    cover      each leg is flown by one type or dropped:  sum_k x[k,l] + y[l] = 1
    balance    at every node, aircraft in = aircraft out
    count      n[k] = aircraft on the ground at the end of the period
                      + aircraft still flying or turning then;  n[k] <= fleet[k]
    capacity   (constrain mode) runway movements per hour <= limit, aircraft at a station <= stands

x[k,l] = 1 if type k flies leg l; y[l] = 1 if leg l is dropped; g = aircraft on the ground.
A type that can't fly a leg simply has no x for it.
"""

from collections import defaultdict
from dataclasses import dataclass, field

import pandas as pd
import pulp

from .network_builder import Network
from .scenario_config import Scenario


@dataclass
class Result:
    status: str
    assign: pd.DataFrame          # type per leg_id, or "dropped"
    fleet_used: dict              # aircraft needed per type
    objective: float
    capacity: pd.DataFrame = field(default_factory=pd.DataFrame)   # use vs limit


def solve(net: Network, perf: pd.DataFrame, drop_cost: pd.Series, ownership: pd.Series,
          capacity: pd.DataFrame, sc: Scenario) -> Result:
    F = net.flights
    if not sc.allow_drop:
        check_every_leg_can_fly(F, perf, drop_cost.index)
    model = pulp.LpProblem("fleet_assignment", pulp.LpMinimize)

    # Variables. y has an upper bound of 0 when legs can't be dropped. (It's an
    # integer from 0 to 1 rather than "Binary" because PuLP ignores bounds on binaries.)
    x = {}
    for r in F.itertuples():
        x[r.type, r.leg_id] = pulp.LpVariable(f"x_{r.type}_{r.leg_id}", cat="Binary")
    y = {}
    for leg in drop_cost.index:
        y[leg] = pulp.LpVariable(f"y_{leg}", lowBound=0, upBound=1 if sc.allow_drop else 0, cat="Integer")
    g = {}
    for (k, s), times in net.nodes.items():
        for i in range(len(times)):
            g[k, s, i] = pulp.LpVariable(f"g_{k}_{s}_{i}", lowBound=0, cat="Integer")

    # Group the flight variables by leg and by the node they leave or reach
    by_leg = defaultdict(list)
    leaving = defaultdict(list)
    reaching = defaultdict(list)
    for r in F.itertuples():
        var = x[r.type, r.leg_id]
        by_leg[r.leg_id].append(var)
        leaving[r.type, r.origin, r.dep_node].append(var)
        reaching[r.type, r.destination, r.arr_node].append(var)

    # Cover
    for leg in y:
        model += pulp.lpSum(by_leg[leg]) + y[leg] == 1, f"cover_{leg}"

    # Balance. g[k,s,i] is the ground arc from node i to node i+1; the last one wraps to node 0.
    for (k, s), times in net.nodes.items():
        n = len(times)
        for i in range(n):
            arriving = pulp.lpSum(reaching[k, s, i]) + g[k, s, i - 1 if i > 0 else n - 1]
            departing = pulp.lpSum(leaving[k, s, i]) + g[k, s, i]
            model += arriving == departing, f"balance_{k}_{s}_{i}"

    # Count
    fleet_used = {}
    for k in F.type.unique():
        on_ground = [g[k, s, len(times) - 1] for (kk, s), times in net.nodes.items() if kk == k]
        in_air = [x[k, r.leg_id] for r in F[(F.type == k) & F.crosses].itertuples()]
        fleet_used[k] = pulp.lpSum(on_ground + in_air)
        model += fleet_used[k] <= sc.fleet.get(k, 0), f"count_{k}"

    # Objective. Ownership only counts in cost runs. A tiny cost per aircraft is
    # added in every run so the solver never keeps spare aircraft it doesn't need.
    objective = pulp.lpSum(perf.at[kl, "c"] * var for kl, var in x.items())
    objective += pulp.lpSum(drop_cost[leg] * y[leg] for leg in y)
    days = net.period_min / 1440
    tiny = 1e-6 * perf.c.abs().max()
    for k, n in fleet_used.items():
        own = ownership[k] * days if sc.objective == "cost" else 0
        objective += (own + tiny) * n
    model += objective

    # Capacity: the same expressions are either limited (constrain) or just reported (check)
    usage = []
    if sc.capacity_mode != "off":
        usage = capacity_usage(net, x, g, capacity)
        if sc.capacity_mode == "constrain":
            for i, u in enumerate(usage):
                model += u["expr"] <= u["limit"], f"capacity_{i}"

    model.solve(pulp.HiGHS(msg=sc.solver.get("msg", False),
                           timeLimit=sc.solver.get("time_limit_s", 60),
                           gapRel=sc.solver.get("mip_gap", 0.0)))
    if model.sol_status == pulp.LpSolutionOptimal:
        status = "Optimal"
    elif model.sol_status == pulp.LpSolutionIntegerFeasible:
        status = "Feasible (time limit)"
    else:
        no_assign = pd.DataFrame(columns=["type"], index=pd.Index([], name="leg_id"))
        return Result(pulp.LpStatus[model.status], no_assign, {}, float("nan"))

    flown_by = {leg: k for (k, leg), var in x.items() if var.value() > 0.5}
    assign = pd.DataFrame({"type": [flown_by.get(leg, "dropped") for leg in y]},
                          index=pd.Index(list(y), name="leg_id"))
    used = {k: round(n.value()) for k, n in fleet_used.items()}

    rows = []
    for u in usage:
        rows.append({"station": u["station"], "measure": u["measure"], "time_min": u["time_min"],
                     "limit": u["limit"], "used": round(pulp.value(u["expr"]))})
    cap = pd.DataFrame(rows)
    if len(cap):
        cap["utilisation"] = cap.used / cap.limit
        cap["over"] = cap.used > cap.limit
    return Result(status, assign, used, pulp.value(model.objective), cap)


def capacity_usage(net: Network, x: dict, g: dict, capacity: pd.DataFrame) -> list:
    """Runway: flights departing or arriving at a station in each clock hour (each
    type lands at its own time). Stands: aircraft at a station at each arrival time,
    either waiting on the ground or still turning. Stand use only goes up when an
    aircraft arrives, so checking at arrival times finds every peak."""
    F = net.flights
    usage = []

    movements = defaultdict(list)
    for r in F.itertuples():
        movements[r.origin, r.dep_t // 60].append(x[r.type, r.leg_id])
        movements[r.destination, r.arr_t // 60].append(x[r.type, r.leg_id])
    for (s, hour), terms in sorted(movements.items()):
        usage.append({"station": s, "measure": "movements_per_hour", "time_min": hour * 60,
                      "limit": capacity.at[s, "movements_per_hour"], "expr": pulp.lpSum(terms)})

    def turning(t, arrive, ready):
        if arrive <= ready:
            return arrive <= t < ready
        return t >= arrive or t < ready          # the turn runs past the end of the period

    for s in sorted(set(F.destination)):
        arrivals = F[F.destination == s]
        for t in sorted(set(arrivals.arr_t)):
            terms = []
            for (k, station), times in net.nodes.items():
                if station == s:
                    i = sum(1 for node_t in times if node_t <= t) - 1   # last node at or before t
                    terms.append(g[k, s, i if i >= 0 else len(times) - 1])
            for r in arrivals.itertuples():
                if turning(t, r.arr_t, r.ready_t):
                    terms.append(x[r.type, r.leg_id])
            usage.append({"station": s, "measure": "stands", "time_min": t,
                          "limit": capacity.at[s, "stands"], "expr": pulp.lpSum(terms)})
    return usage


def check_every_leg_can_fly(F: pd.DataFrame, perf: pd.DataFrame, legs) -> None:
    """Every leg needs at least one type that can fly it, or the model has no solution."""
    stranded = sorted(set(legs) - set(F.leg_id))
    if not stranded:
        return
    lines = []
    for leg in stranded:
        reasons = []
        for k, r in perf.xs(leg, level="leg_id").iterrows():
            why = []
            if not r.in_range:
                why.append("out of range")
            if not r.fuel_at_origin:
                why.append("no fuel at origin")
            if not r.fits:
                why.append("too few seats")
            reasons.append(f"{k}: {', '.join(why)}")
        lines.append(f"{leg} ({'; '.join(reasons)})")
    raise ValueError("no aircraft type can fly these legs and allow_drop is false:\n  "
                     + "\n  ".join(lines) + "\nAllow spill or drops, or change the fleet or fuels.")

