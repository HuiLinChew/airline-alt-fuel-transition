"""Run every scenario in scenarios/ and save the results and figures in outputs/.

    uv run scripts/run_scenarios.py

Scenarios are grouped by folder (one per timetable); each group's results go in
outputs/<folder>/ and its figures in outputs/<folder>/figures/. scenarios/stress_tests/
is not run here (the tests use it).
"""

import matplotlib.pyplot as plt

from altfuel import analysis, plots
from altfuel.scenario_config import load_scenario, scenario_files
from altfuel.utils import OUTPUT_DIR


def save(fig, path):
    fig.savefig(path, dpi=180)
    plt.close(fig)


def main():
    runs, groups = [], {}
    for path in scenario_files():
        sc = load_scenario(path)
        out = OUTPUT_DIR / path.parent.name
        figures = out / "figures"
        figures.mkdir(parents=True, exist_ok=True)

        r = analysis.run(sc)
        runs.append(r)
        groups.setdefault(out, []).append(r)
        k = r.kpis
        if k["status"] not in analysis.SOLVED:
            print(f"{sc.name:24s} {k['status']}: no solution")
            continue
        print(f"{sc.name:24s} {k['legs_flown']:2d} legs  {k['aircraft']:2d} aircraft  "
              f"{k['co2_t']:6.1f} t CO2  ${k['total_cost_usd']:9,.0f}  {k['pax_spilled']} spilled  "
              f"{k.get('capacity_breaches', '-')} capacity breaches  "
              f"longest cycle {k['longest_cycle_days']} d  {r.violations or 'rotations OK'}")

        r.result.assign.to_csv(out / f"assign_{sc.name}.csv")
        r.rotations.to_csv(out / f"rotations_{sc.name}.csv", index=False)
        r.cycles.to_csv(out / f"cycles_{sc.name}.csv", index=False)
        if len(r.result.capacity):
            r.result.capacity.round(3).to_csv(out / f"capacity_{sc.name}.csv", index=False)
        save(plots.network_map(r), figures / f"network_{sc.name}.png")
        save(plots.network_map(r, background=False), figures / f"network_{sc.name}_plain.png")
        save(plots.tail_gantt(r), figures / f"gantt_{sc.name}.png")

        if sc.sweep:
            parameter = sc.sweep["parameter"]
            results = analysis.sweep(sc, parameter, sc.sweep["values"])
            results.round(3).to_csv(out / f"sweep_{sc.name}_{parameter}.csv", index=False)
            save(plots.sweep_chart(results, parameter, sc.name, r.data.fuels),
                 figures / f"sweep_{sc.name}_{parameter}.png")

    analysis.compare(runs).round(3).to_csv(OUTPUT_DIR / "scenario_summary.csv")
    for out, group in groups.items():     # each group against its own baseline
        save(plots.scenario_comparison(group), out / "figures" / "scenario_comparison.png")


if __name__ == "__main__":
    main()
