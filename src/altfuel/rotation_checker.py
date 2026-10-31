"""Module 8 - Rotation checker.

Turns the type-level assignment into tail rotations and flags rule breaks.
Outputs: rotations (one row per leg flown, with its tail) and violations.

Method (greedy, first-ready): go through each type's legs in departure order.
Give each leg the aircraft at the origin that became ready earliest; if none is
ready, a new aircraft starts the period there. An aircraft is ready again at its
arrival time plus that type's turn time. This sequential FAM-then-routing order
is standard airline practice (Sherali et al. 2006; Justin et al. 2022).

Checks: tails needed <= fleet available, and every tail ends the period at a
station where another tail of that type starts (so the schedule can repeat).
"""

from collections import Counter

import pandas as pd

from .data_layer import Data


def build_rotations(data: Data, perf: pd.DataFrame, assign: pd.DataFrame, fleet: dict):
    flown = assign[assign.type != "dropped"].join(data.legs).sort_values("dep_min")
    rows, violations = [], []
    for ac_type, legs in flown.groupby("type"):
        ready = {}        # station -> list of (ready minute, tail id) for aircraft waiting there
        start, end = {}, {}
        for leg_id, leg in legs.iterrows():
            waiting = [(t, tail) for t, tail in ready.get(leg.origin, []) if t <= leg.dep_min]
            if waiting:
                t, tail = min(waiting)
                ready[leg.origin].remove((t, tail))
            else:
                tail = f"{ac_type}-{len(start) + 1:02d}"
                start[tail] = leg.origin
            ready.setdefault(leg.destination, []).append(
                (leg.arr_min + perf.at[(ac_type, leg_id), "turn_min"], tail))
            end[tail] = leg.destination
            rows.append(dict(tail_id=tail, type=ac_type, leg_id=leg_id, origin=leg.origin,
                             destination=leg.destination, dep_min=leg.dep_min, arr_min=leg.arr_min))
        if len(start) > fleet.get(ac_type, 0):
            violations.append(f"{ac_type}: needs {len(start)} aircraft, only {fleet.get(ac_type, 0)} available")
        if Counter(start.values()) != Counter(end.values()):
            violations.append(f"{ac_type}: end-of-period positions do not match next period's starts")
    return pd.DataFrame(rows), violations
