"""Module 6 - Network builder.

Turns the schedule into one time-space network per aircraft type, keeping only
feasible flights (Hane et al. 1995, as presented by Sherali et al. 2006; Kamat et al.).

For each type and station, a node is a moment when something happens:
a departure of a leg the type can fly, or an arrival plus that type's turn time
(the moment the aircraft is ready again). Then:
- flight arc: departure node at origin -> ready node at destination
- ground arc: one node -> the next node at the same station (aircraft waiting)
- wrap-around arc: last node of the day -> first node (aircraft staying overnight)

Output: Network with, per type, the node times at each station and the flight arcs.
Ground arcs are implicit: at station s there is one after every node, the last
being the wrap-around. v1 has one fuel state; tankering adds fuel layers later.
"""

from dataclasses import dataclass, field

import pandas as pd

from .data_layer import Data


@dataclass
class Network:
    nodes: dict = field(default_factory=dict)   # (type, station) -> sorted list of node times
    flights: pd.DataFrame = None                # type, leg_id, origin, destination, dep_node, arr_node


def build_network(data: Data, perf: pd.DataFrame) -> Network:
    feasible = perf[perf.feasible].reset_index()
    legs = data.legs.loc[feasible.leg_id]
    feasible["origin"] = legs.origin.values
    feasible["destination"] = legs.destination.values
    feasible["dep_t"] = legs.dep_h.values
    feasible["ready_t"] = legs.arr_h.values + feasible.turn_h.values

    net = Network()
    for ac_type, F in feasible.groupby("type"):
        events = pd.concat([F[["origin", "dep_t"]].set_axis(["station", "t"], axis=1),
                            F[["destination", "ready_t"]].set_axis(["station", "t"], axis=1)])
        for station, E in events.groupby("station"):
            net.nodes[ac_type, station] = sorted(E.t.unique())

    def node_index(row, station_col, time_col):
        return net.nodes[row.type, row[station_col]].index(row[time_col])

    feasible["dep_node"] = feasible.apply(node_index, axis=1, args=("origin", "dep_t"))
    feasible["arr_node"] = feasible.apply(node_index, axis=1, args=("destination", "ready_t"))
    net.flights = feasible[["type", "leg_id", "origin", "destination", "dep_node", "arr_node"]]
    return net
