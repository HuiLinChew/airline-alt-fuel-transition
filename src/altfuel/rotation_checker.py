"""Module 8: turn the assignment into rotations for individual aircraft.

For each type, go through its legs in departure order and give each leg the
aircraft at the origin that has been ready longest. If none is ready, a new
aircraft starts the day there. This is a check on the optimiser's answer, not
an optimisation.

It flags two problems: needing more aircraft than the optimiser counted, and
aircraft ending the day somewhere other than where the next day's flights start.
"""

from collections import Counter

import pandas as pd

from .data_layer import Data


def build_rotations(data: Data, perf: pd.DataFrame, assign: pd.DataFrame, fleet_used: dict):
    flown = assign[assign.type != "dropped"].join(data.legs).sort_values("dep_min")
    rows = []
    problems = []

    for ac_type, legs in flown.groupby("type"):
        waiting = {}              # station -> list of (ready time, tail)
        first_station = {}        # tail -> where it starts the day
        last_station = {}         # tail -> where it ends the day

        for leg_id, leg in legs.iterrows():
            ready_here = [(t, tail) for t, tail in waiting.get(leg.origin, []) if t <= leg.dep_min]
            if ready_here:
                t, tail = min(ready_here)
                waiting[leg.origin].remove((t, tail))
            else:
                tail = f"{ac_type}-{len(first_station) + 1:02d}"
                first_station[tail] = leg.origin

            arr = perf.at[(ac_type, leg_id), "arr_min"]
            ready = arr + perf.at[(ac_type, leg_id), "turn_min"]
            waiting.setdefault(leg.destination, []).append((ready, tail))
            last_station[tail] = leg.destination
            rows.append({"tail_id": tail, "type": ac_type, "leg_id": leg_id, "origin": leg.origin,
                         "destination": leg.destination, "dep_min": leg.dep_min, "arr_min": arr})

        needed, counted = len(first_station), fleet_used.get(ac_type, 0)
        if needed > counted:
            problems.append(f"{ac_type}: rotations need {needed} aircraft, the optimiser counted {counted}")
        if Counter(first_station.values()) != Counter(last_station.values()):
            problems.append(f"{ac_type}: aircraft end the day where the next day's flights don't start")

    return pd.DataFrame(rows), problems
