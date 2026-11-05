"""Run every scenario in scenarios/ and save the results and figures in outputs/.

    uv run scripts/run_scenarios.py
"""

from pathlib import Path

import matplotlib.pyplot as plt

from altfuel import analysis, plots
from altfuel.scenario_config import load_all
from altfuel.utils import OUTPUT_DIR

FIGURES = OUTPUT_DIR / "figures"


def save(fig, name):
    fig.savefig(FIGURES / f"{name}.png", dpi=180)
    plt.close(fig)


def main():
    FIGURES.mkdir(parents=True, exist_ok=True)
    runs = []
    for sc in load_all():
        r = analysis.run(sc)
        runs.append(r)
        k = r.kpis
        if k["status"] not in analysis.SOLVED:
            print(f"{sc.name:24s} {k['status']}: no solution")
            continue
        print(f"{sc.name:24s} {k['legs_flown']:2d} legs  {k['aircraft']:2d} aircraft  "
              f"{k['co2_t']:6.1f} t CO2  ${k['total_cost_usd']:9,.0f}  {k['pax_spilled']} spilled  "
              f"{k.get('capacity_breaches', '-')} capacity breaches  "
              f"longest cycle {k['longest_cycle_days']} d  {r.violations or 'rotations OK'}")

        r.result.assign.to_csv(OUTPUT_DIR / f"assign_{sc.name}.csv")
        r.rotations.to_csv(OUTPUT_DIR / f"rotations_{sc.name}.csv", index=False)
        r.cycles.to_csv(OUTPUT_DIR / f"cycles_{sc.name}.csv", index=False)
        if len(r.result.capacity):
            r.result.capacity.round(3).to_csv(OUTPUT_DIR / f"capacity_{sc.name}.csv", index=False)
        save(plots.network_map(r), f"network_{sc.name}")
        save(plots.tail_gantt(r), f"gantt_{sc.name}")

        if sc.sweep:
            parameter = sc.sweep["parameter"]
            results = analysis.sweep(sc, parameter, sc.sweep["values"])
            results.round(3).to_csv(OUTPUT_DIR / f"sweep_{sc.name}_{parameter}.csv", index=False)
            save(plots.sweep_chart(results, parameter, sc.name), f"sweep_{sc.name}_{parameter}")

    analysis.compare(runs).round(3).to_csv(OUTPUT_DIR / "scenario_summary.csv")

    # One comparison figure per input dataset, each against its own baseline
    by_data = {}
    for r in runs:
        by_data.setdefault(r.scenario.data_dir, []).append(r)
    for data_dir, group in by_data.items():
        suffix = "" if data_dir == "data/dummy" else "_" + Path(data_dir).name
        save(plots.scenario_comparison(group), f"scenario_comparison{suffix}")


if __name__ == "__main__":
    main()
