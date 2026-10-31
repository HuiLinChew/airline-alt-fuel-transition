"""Run every scenario on the 5-airport / 3-aircraft dummy network.

    uv run scripts/run_dummy.py

Writes to outputs/: scenario_summary.csv, per-scenario flights and rotations,
and figures (network map + Gantt per scenario, scenario comparison).
"""


import matplotlib.pyplot as plt
import pandas as pd

from altfleet.data import ROOT, load_inputs
from altfleet.plots import network_map, scenario_comparison, tail_gantt
from altfleet.rotations import build_rotations
from altfleet.scenarios import SCENARIOS, apply, run_all

OUT = ROOT / "outputs"
FIG = OUT / "figures"


def main():
    FIG.mkdir(parents=True, exist_ok=True)
    inp = load_inputs()
    sols, table = run_all(inp)
    table.round(3).to_csv(OUT / "scenario_summary.csv")

    feas = []
    for sc in SCENARIOS:
        s, i = sols[sc.name], apply(inp, sc)
        print(f"{sc.name:26s} {s.status:8s} {s.kpis['flights']:3d} flights  "
              f"{s.kpis['aircraft']:2d} aircraft  {s.kpis['co2_t']:7.1f} t CO2")
        s.flights.to_csv(OUT / f"flights_{sc.name}.csv", index=False)
        legs, summ = build_rotations(i, s)
        legs.round(2).to_csv(OUT / f"rotations_{sc.name}.csv", index=False)
        feas.append(summ.assign(scenario=sc.name))

        fig, ax = plt.subplots(figsize=(8.5, 6))
        network_map(i, s, f"{sc.name}: {s.kpis['flights']} flights/day, "
                          f"{s.kpis['aircraft']} aircraft", ax)
        fig.tight_layout(); fig.savefig(FIG / f"network_{sc.name}.png", dpi=180); plt.close(fig)

        ax = tail_gantt(i, legs, f"{sc.name}: daily tail rotations")
        ax.figure.tight_layout(); ax.figure.savefig(FIG / f"gantt_{sc.name}.png", dpi=180)
        plt.close(ax.figure)

    fig = scenario_comparison(sols)
    fig.savefig(FIG / "scenario_comparison.png", dpi=180); plt.close(fig)


    F = pd.concat(feas)[["scenario", "type", "aircraft_optimiser", "tails_heuristic",
                         "block_h_per_tail", "feasible_with_optimiser_fleet"]]
    F.round(2).to_csv(OUT / "rotation_feasibility.csv", index=False)
    print("\nRotation feasibility check:\n", F.round(1).to_string(index=False))


if __name__ == "__main__":
    main()
