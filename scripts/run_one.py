"""Run one scenario, print its results and save its network map and schedule.

    uv run scripts/run_one.py lcc_carbon_200
    uv run scripts/run_one.py path/to/my_scenario.yaml

Figures go in outputs/one/.
"""

import sys

import matplotlib.pyplot as plt

from altfuel import analysis, plots
from altfuel.scenario_config import load_scenario
from altfuel.utils import OUTPUT_DIR


def main():
    sc = load_scenario(sys.argv[1])
    run = analysis.run(sc)
    for name, value in run.kpis.items():
        print(f"{name:22s} {value:,.3f}" if isinstance(value, float) else f"{name:22s} {value}")

    out = OUTPUT_DIR / "one"
    out.mkdir(parents=True, exist_ok=True)
    if run.kpis["status"] in analysis.SOLVED:
        for figure, name in [(plots.network_map(run), "network"), (plots.tail_gantt(run), "schedule")]:
            figure.savefig(out / f"{name}_{sc.name}.png", dpi=180, bbox_inches="tight")
            plt.close(figure)
        print(f"\nfigures saved in {out}")


if __name__ == "__main__":
    main()
