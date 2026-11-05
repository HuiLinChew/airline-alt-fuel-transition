"""Module 8: turn the assignment into rotations for individual aircraft.

For each type, go through its legs in departure order and give each leg the
aircraft at the origin that has been ready longest. If none is ready, a new
aircraft starts the day there. This is a check on the optimiser's answer, not
an optimisation.

It flags two problems: needing more aircraft than the optimiser counted, and
aircraft ending the day somewhere other than where the next day's flights start.

day_cycles then joins the days together: an aircraft may end the day away from
where it started and take several days to get back (a multi-day cycle).
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

    columns = ["tail_id", "type", "leg_id", "origin", "destination", "dep_min", "arr_min"]
    return pd.DataFrame(rows, columns=columns), problems


def day_cycles(rotations: pd.DataFrame) -> pd.DataFrame:
    """Join one day's rotations into multi-day cycles.

    An aircraft that ends the day at X flies, the next day, the rotation of an
    aircraft that started the day at X. Following that chain until it comes back
    to its first rotation gives a cycle: the number of days an aircraft takes to
    get back to where it started, and where it spends each night. The matching is
    one valid choice; an airline would pick the one that suits its maintenance
    bases (maintenance routing).
    """
    rows = []
    for ac_type, rot in rotations.groupby("type"):
        days = rot.groupby("tail_id", sort=False)
        start = days.origin.first()
        end = days.destination.last()
        if sorted(start) != sorted(end):
            continue                     # already flagged by build_rotations

        # An aircraft back where it started keeps its own rotation; the rest are
        # matched in tail order with the rotations starting where they ended.
        next_day = {tail: tail for tail in start.index if start[tail] == end[tail]}
        starting_at = {}
        for tail, station in start.items():
            if tail not in next_day:
                starting_at.setdefault(station, []).append(tail)
        for tail, station in end.items():
            if tail not in next_day:
                next_day[tail] = starting_at[station].pop(0)

        seen = set()
        for first in start.index:
            if first in seen:
                continue
            nights = []
            tail = first
            while tail not in seen:
                seen.add(tail)
                nights.append(end[tail])
                tail = next_day[tail]
            rows.append({"type": ac_type, "first_rotation": first, "days": len(nights),
                         "home": start[first], "nights": " > ".join(nights)})
    return pd.DataFrame(rows, columns=["type", "first_rotation", "days", "home", "nights"])
