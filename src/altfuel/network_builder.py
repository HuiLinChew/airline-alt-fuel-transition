"""Module 6: a time-space network for each aircraft type.

At each station, a type has a node at every time something happens: one of its
flights departs, or one of its aircraft is ready again (arrival + turn). Flight
arcs join a departure node to a ready node. Ground arcs join each node to the
next one at the same station, and the last one wraps round to the first
(aircraft staying overnight). Ground arcs aren't stored, since they follow from
the node lists.

The schedule repeats every period. A flight that is still flying or turning at
the end of the period is marked `crosses`; its ready node goes at
(ready time - period).
"""

from dataclasses import dataclass, field

import pandas as pd

from .data_layer import Data


@dataclass
class Network:
    period_min: int
    nodes: dict = field(default_factory=dict)   # (type, station) -> sorted node times
    flights: pd.DataFrame = None                # one row per flight arc


def build_network(data: Data, perf: pd.DataFrame, period_min: int) -> Network:
    f = perf[perf.feasible].reset_index()
    legs = data.legs.loc[f.leg_id]
    f["origin"] = legs.origin.to_numpy()
    f["destination"] = legs.destination.to_numpy()

    dep = legs.dep_min.to_numpy()
    ready = f.arr_min.to_numpy() + f.turn_min.to_numpy()
    if (dep >= period_min).any() or (ready - dep > period_min).any():
        raise ValueError("a leg departs after the period ends, or takes longer than a period")
    f["dep_t"] = dep
    f["arr_t"] = f.arr_min % period_min
    f["ready_t"] = ready % period_min
    f["crosses"] = ready >= period_min

    net = Network(period_min)
    for ac_type, flights in f.groupby("type"):
        departures = flights[["origin", "dep_t"]].rename(columns={"origin": "station", "dep_t": "t"})
        readies = flights[["destination", "ready_t"]].rename(columns={"destination": "station", "ready_t": "t"})
        for station, events in pd.concat([departures, readies]).groupby("station"):
            net.nodes[ac_type, station] = sorted(events.t.unique())

    # Position of each flight's departure and ready time in its station's node list
    position = {key: {t: i for i, t in enumerate(times)} for key, times in net.nodes.items()}
    f["dep_node"] = [position[k, s][t] for k, s, t in zip(f.type, f.origin, f.dep_t)]
    f["arr_node"] = [position[k, s][t] for k, s, t in zip(f.type, f.destination, f.ready_t)]
    net.flights = f[["type", "leg_id", "origin", "destination", "dep_node", "arr_node",
                     "crosses", "dep_t", "arr_t", "ready_t"]]
    return net
