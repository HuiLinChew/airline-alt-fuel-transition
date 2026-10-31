"""Run every scenario in scenarios/ and write results and figures to outputs/.

    uv run scripts/run_scenarios.py
"""

import matplotlib.pyplot as plt

from altfuel import analysis, plots
from altfuel.airport_capability import airport_fuel
from altfuel.data_layer import load_data
from altfuel.scenario_config import load_all, load_scenario
from altfuel.utils import OUTPUT_DIR

FIG = OUTPUT_DIR / "figures"


def save(fig, name):
    fig.savefig(FIG / f"{name}.png", dpi=180)
    plt.close(fig)


def main():
    FIG.mkdir(parents=True, exist_ok=True)
    data = load_data()
    fuel_of_type = data.aircraft_types.fuel.to_dict()

    runs = []
    for sc in load_all():
        r = analysis.run(data, sc)
        runs.append(r)
        k = r.kpis
        print(f"{sc.name:22s} {k['status']:8s} {k['legs_flown']:2d} legs  {k['aircraft']:2d} aircraft  "
              f"{k['co2_t']:6.1f} t CO2  ${k['total_cost_usd']:9,.0f}  {r.violations or 'no violations'}")
        r.result.assign.to_csv(OUTPUT_DIR / f"assign_{sc.name}.csv")
        r.rotations.round(3).to_csv(OUTPUT_DIR / f"rotations_{sc.name}.csv", index=False)
        save(plots.network_map(r, data.airports, airport_fuel(data, sc)), f"network_{sc.name}")
        save(plots.tail_gantt(r, fuel_of_type), f"gantt_{sc.name}")

    analysis.compare(runs).round(3).to_csv(OUTPUT_DIR / "scenario_summary.csv")
    save(plots.scenario_comparison(runs), "scenario_comparison")

    sweep = analysis.carbon_price_sweep(data, load_scenario("alt_carbon_200"))
    sweep.round(3).to_csv(OUTPUT_DIR / "carbon_price_sweep.csv", index=False)
    save(plots.carbon_sweep(sweep, "alt_carbon_200 fleet"), "carbon_price_sweep")


if __name__ == "__main__":
    main()
