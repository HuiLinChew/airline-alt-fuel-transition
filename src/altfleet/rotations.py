"""Turn the route-level solution into daily tail rotations (feasibility check).

The optimiser only decides how many flights each aircraft type flies on each
route. Here those flights are chained into rotations for individual tails:

1. Per aircraft type, the flights form a directed multigraph where every airport
   has departures = arrivals (guaranteed by the balance constraint), so each
   connected part has an Eulerian circuit: one loop using every flight once.
2. Walk that loop, assigning flights to a tail until the next flight would
   arrive after curfew; then start the next tail.

Because tail t ends where tail t+1 starts, the schedule repeats cyclically:
tomorrow tail t flies today's line of tail t+1. This is not optimised (no
timing of departures to demand peaks, no maintenance); it checks whether the
route plan can be flown by roughly the fleet the optimiser sized.
"""

from __future__ import annotations

import networkx as nx
import pandas as pd

from .data import Inputs
from .model import Solution


def build_rotations(inp: Inputs, sol: Solution) -> tuple[pd.DataFrame, pd.DataFrame]:
    legs, summary = [], []
    for ac, F in sol.flights.groupby("type"):
        tat = inp.aircraft.loc[ac, "turnaround_min"] / 60
        G = nx.MultiDiGraph()
        for r in F.itertuples():
            for _ in range(r.flights):
                G.add_edge(r.origin, r.destination, block_h=r.block_h, fuel=r.fuel)
        tails = 0
        for comp in nx.weakly_connected_components(G):
            H = G.subgraph(comp)
            start = max(H.nodes, key=H.out_degree)  # begin at the busiest airport
            tail, t = None, None
            for o, d, key in nx.eulerian_circuit(H, source=start, keys=True):
                e = H.edges[o, d, key]
                if tail is None or t + e["block_h"] > inp.op_end_h:
                    tails += 1
                    tail, t = f"{ac}-{tails:02d}", inp.op_start_h
                legs.append(dict(tail_id=tail, type=ac, fuel=e["fuel"], origin=o, destination=d,
                                 dep_h=t, arr_h=t + e["block_h"]))
                t += e["block_h"] + tat
        summary.append(dict(type=ac, aircraft_optimiser=int(sol.fleet[ac]), tails_heuristic=tails))
    L = pd.DataFrame(legs)
    S = pd.DataFrame(summary)
    if not L.empty:
        L["block_h"] = L["arr_h"] - L["dep_h"]
        per = L.groupby("type").agg(block=("block_h", "sum"), n=("tail_id", "nunique"))
        S["block_h_per_tail"] = S["type"].map(per["block"] / per["n"])
        L = L.drop(columns="block_h")
    S["feasible_with_optimiser_fleet"] = S.tails_heuristic <= S.aircraft_optimiser
    return L, S
