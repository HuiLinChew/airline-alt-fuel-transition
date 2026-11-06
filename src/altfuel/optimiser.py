"""Module 7: which aircraft type flies each leg (fleet assignment).

A mixed-integer program on the time-space networks (Hane et al. 1995, via
Sherali et al. 2006), with optional leg cancellation (Wu et al. 2025):

    minimise   sum c[k,l] x[k,l] + sum drop_cost[l] y[l] + sum ownership[k] n[k]

    cover      each leg is flown by one type or dropped:  sum_k x[k,l] + y[l] = 1
               (with max_delay_min > 0, the sum also runs over the leg's delayed copies,
               so the model picks the departure time too; Rexing et al. 2000. A second
               solve then keeps the best objective and minimises total delay minutes)
    balance    at every node, aircraft in = aircraft out
    count      n[k] = aircraft on the ground at the end of the period
                      + aircraft still flying or turning then;  n[k] <= fleet[k]
    capacity   (constrain mode) runway movements per hour <= limit, aircraft at a station <= stands
    nights     (overnight_at_bases) at every midnight, no aircraft at or heading to
               an airport that isn't a base

x[k,l] = 1 if type k flies leg l; y[l] = 1 if leg l is dropped; g = aircraft on the ground.
A type that can't fly a leg simply has no x for it.
"""

from bisect import bisect_right
from collections import defaultdict
from dataclasses import dataclass, field

import numpy as np
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
    most = 1 if sc.allow_drop else 0
    for leg in drop_cost.index:
        y[leg] = pulp.LpVariable(f"y_{leg}", lowBound=0, upBound=most, cat="Integer")
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
        by_leg[r.leg].append(var)       # all delayed copies of a leg count towards its cover
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

    # Overnight at bases: at every midnight in the period, no aircraft is on the ground
    # at, or still flying or turning towards, an airport that isn't a base
    if sc.overnight_at_bases:
        for midnight in range(0, net.period_min, 1440):
            for (k, s), times in net.nodes.items():
                if s not in net.bases:
                    # the ground arc from the last node before midnight (or the overnight arc)
                    before = [i for i, t in enumerate(times) if t < midnight]
                    i = before[-1] if before else len(times) - 1
                    model += g[k, s, i] == 0, f"no_night_{midnight}_{k}_{s}"
            for r in F[~F.destination.isin(net.bases)].itertuples():
                if busy_at(midnight, r):
                    model += x[r.type, r.leg_id] == 0, f"no_night_{midnight}_{r.type}_{r.leg_id}"

    # Objective. Ownership only counts in cost runs. A tiny cost per aircraft is
    # added in every run so the solver never keeps spare aircraft it doesn't need.
    days = net.period_min / 1440
    tiny = 1e-6 * perf.c.abs().max()
    c = perf.c.reindex(list(x)).to_numpy()
    objective = pulp.lpSum(ci * var for ci, var in zip(c, x.values()))
    objective += pulp.lpSum(drop_cost[leg] * y[leg] for leg in y)
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

    status = run_solver(model, sc)
    if status not in ("Optimal", "Feasible (time limit)"):
        no_assign = pd.DataFrame(columns=["type"], index=pd.Index([], name="leg_id"))
        return Result(status, no_assign, {}, float("nan"))
    best = pulp.value(objective)

    # Second solve, only if some legs were delayed: keep the best objective and the
    # same aircraft, and use as few delay minutes as possible (a tiny cost per minute
    # is too small for the solver to notice, so it would leave delays that gain nothing).
    delay = pulp.lpSum(d * x[k, leg] for k, leg, d in zip(F.type, F.leg_id, F.delay_min) if d)
    if pulp.value(delay):
        model += objective <= best + 1e-6 * abs(best), "keep_best"
        for k, n in fleet_used.items():
            model += n <= round(n.value()), f"keep_fleet_{k}"
        model.setObjective(delay)
        status = run_solver(model, sc)

    # One row per leg: the copy flown (its leg_id shows any delay), or the leg itself if dropped
    flown = {r.leg: (r.leg_id, r.type) for r in F.itertuples() if x[r.type, r.leg_id].value() > 0.5}
    leg_ids, types = [], []
    for leg in y:
        leg_id, k = flown.get(leg, (leg, "dropped"))
        leg_ids.append(leg_id)
        types.append(k)
    assign = pd.DataFrame({"type": types}, index=pd.Index(leg_ids, name="leg_id"))
    used = {k: round(n.value()) for k, n in fleet_used.items()}

    rows = []
    for u in usage:
        rows.append({"station": u["station"], "measure": u["measure"], "time_min": u["time_min"],
                     "limit": u["limit"], "used": round(pulp.value(u["expr"]))})
    cap = pd.DataFrame(rows)
    if len(cap):
        cap["utilisation"] = cap.used / cap.limit
        cap["over"] = cap.used > cap.limit
    return Result(status, assign, used, best, cap)


def run_solver(model, sc: Scenario) -> str:
    model.solve(pulp.HiGHS(msg=sc.solver.get("msg", False),
                           timeLimit=sc.solver.get("time_limit_s", 60),
                           gapRel=sc.solver.get("mip_gap", 0.0)))
    if model.sol_status == pulp.LpSolutionOptimal:
        return "Optimal"
    if model.sol_status == pulp.LpSolutionIntegerFeasible:
        return "Feasible (time limit)"
    return pulp.LpStatus[model.status]


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

    for s in sorted(set(F.destination)):
        arrivals = F[F.destination == s]
        arrive = arrivals.arr_t.to_numpy()
        ready = arrivals.ready_t.to_numpy()
        arc_vars = [x[k, leg] for k, leg in zip(arrivals.type, arrivals.leg_id)]
        node_lists = [(k, times) for (k, station), times in net.nodes.items() if station == s]
        for t in sorted(set(arrive)):
            # Ground arc after the last node at or before t (the overnight arc if there is none);
            # bisect_right finds that position quickly in the sorted node times
            terms = [g[k, s, (bisect_right(times, t) - 1) % len(times)] for k, times in node_lists]
            # Flights that have landed but are still turning; some turns run past the period end
            wraps = arrive > ready
            turning = np.where(wraps, (t >= arrive) | (t < ready), (arrive <= t) & (t < ready))
            terms += [var for var, busy in zip(arc_vars, turning) if busy]
            usage.append({"station": s, "measure": "stands", "time_min": t,
                          "limit": capacity.at[s, "stands"], "expr": pulp.lpSum(terms)})
    return usage


def busy_at(t, r) -> bool:
    """Is the aircraft on flight r flying or turning just before time t (0 = end of period)?"""
    if r.crosses:
        return t > r.dep_t or t <= r.ready_t
    return r.dep_t < t <= r.ready_t


def check_every_leg_can_fly(F: pd.DataFrame, perf: pd.DataFrame, legs) -> None:
    """Every leg needs at least one type that can fly it, or the model has no solution."""
    stranded = sorted(set(legs) - set(F.leg))
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
            if not r.outside_curfew:
                why.append("in a night curfew")
            reasons.append(f"{k}: {', '.join(why)}")
        lines.append(f"{leg} ({'; '.join(reasons)})")
    raise ValueError("no aircraft type can fly these legs and allow_drop is false:\n  "
                     + "\n  ".join(lines) + "\nAllow spill or drops, or change the fleet or fuels.")

