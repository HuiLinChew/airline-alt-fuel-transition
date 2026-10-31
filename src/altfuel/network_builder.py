"""Module 6 - Network builder.

Turns the schedule into one time-space network per aircraft type, keeping only
feasible flights (Hane et al. 1995, as presented by Sherali et al. 2006; Kamat et al.).

The schedule repeats every period (a day by default, or a week). For each type
and station, a node is a moment in the period when something happens: a
departure of a leg the type can fly, or an arrival plus that type's turn time
(the moment the aircraft is ready again). Then:
- flight arc: departure node at origin -> ready node at destination
- ground arc: one node -> the next node at the same station (aircraft waiting)
- wrap-around arc: last node of the period -> first node (e.g. overnight)

Count line = the end of the period. A flight whose ready time falls after it
(e.g. a late leg that lands after midnight) is marked `crosses`; its ready node
is placed at (ready time - period) and the optimiser counts it as an aircraft.

Output: Network with, per type, the node times at each station and the flight
arcs. Times are integer minutes. v1 has one fuel state; tankering adds fuel layers.
"""

from dataclasses import dataclass, field

import pandas as pd

from .data_layer import Data


@dataclass
class Network:
    period_min: int
    nodes: dict = field(default_factory=dict)   # (type, station) -> sorted list of node times
    flights: pd.DataFrame = None                # type, leg_id, origin, destination, dep_node, arr_node, crosses


def build_network(data: Data, perf: pd.DataFrame, period_min: int) -> Network:
    f = perf[perf.feasible].reset_index()
    legs = data.legs.loc[f.leg_id]
    f["origin"] = legs.origin.values
    f["destination"] = legs.destination.values
    dep = legs.dep_min.values.astype(int)
    ready = legs.arr_min.values.astype(int) + f.turn_min.values.astype(int)
    if (dep >= period_min).any() or (ready - dep > period_min).any():
        raise ValueError("a leg departs after the period ends, or takes longer than one period")
    f["dep_t"] = dep
    f["ready_t"] = ready % period_min
    f["crosses"] = ready >= period_min

    net = Network(period_min)
    for ac_type, F in f.groupby("type"):
        events = pd.concat([F[["origin", "dep_t"]].set_axis(["station", "t"], axis=1),
                            F[["destination", "ready_t"]].set_axis(["station", "t"], axis=1)])
        for station, E in events.groupby("station"):
            net.nodes[ac_type, station] = sorted(E.t.unique())

    index = {key: {t: i for i, t in enumerate(times)} for key, times in net.nodes.items()}
    f["dep_node"] = [index[k, s][t] for k, s, t in zip(f.type, f.origin, f.dep_t)]
    f["arr_node"] = [index[k, s][t] for k, s, t in zip(f.type, f.destination, f.ready_t)]
    net.flights = f[["type", "leg_id", "origin", "destination", "dep_node", "arr_node", "crosses"]]
    return net
