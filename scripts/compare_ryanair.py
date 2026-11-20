"""Compare the model with what Ryanair really flew on the same days.

    uv run scripts/compare_ryanair.py ryanair_1d      (or ryanair_4d, ryanair_7d)

Needs the scenario's data folder (scripts/make_ryanair_data.py). The model gets Ryanair's real
timetable for the aircraft whose whole stretch is known, kerosene only, and chooses its
own rotations. Saves outputs/ryanair/<scenario>_real_vs_model.csv and a figure of aircraft per base.
"""

import sys

import matplotlib.pyplot as plt
import pandas as pd

from altfuel import analysis, plots, validation
from altfuel.scenario_config import load_scenario
from altfuel.utils import OUTPUT_DIR

OUT = OUTPUT_DIR / "ryanair"


def bases_figure(bases, real_aircraft, model_aircraft, name):
    """Aircraft based at the 15 busiest bases, real vs model."""
    top = bases.head(15)
    fig, ax = plt.subplots(figsize=(10, 4.5))
    x = range(len(top))
    ax.bar([i - 0.2 for i in x], top.real, width=0.4, color=plots.GREY, label="Ryanair (real)")
    ax.bar([i + 0.2 for i in x], top.model, width=0.4, color=plots.BLACK, label="Model")
    ax.set_xticks(x, top.index)
    ax.set_ylabel("Aircraft based there")
    ax.set_title(f"Aircraft needed: Ryanair {real_aircraft}, model {model_aircraft}", loc="left")
    ax.legend(frameon=False)
    plots.add_grid(ax, "y")
    fig.savefig(OUT / f"{name}_aircraft_per_base.png", dpi=200, bbox_inches="tight")


def main():
    """Run the scenario, then compare aircraft, bases and next flights with Ryanair's."""
    OUT.mkdir(parents=True, exist_ok=True)
    run = analysis.run(load_scenario(sys.argv[1]))
    legs = run.data.legs
    real = validation.real_rotations(run)

    real_aircraft = real.aircraft.nunique()
    model_aircraft = run.kpis["aircraft"]
    block_hours = (legs.arr_min - legs.dep_min).sum() / 60
    summary = pd.DataFrame({
        "real": [real_aircraft, len(legs) / real_aircraft, block_hours / real_aircraft],
        "model": [model_aircraft, len(legs) / model_aircraft, block_hours / model_aircraft],
    }, index=["aircraft", "flights per aircraft", "block hours per aircraft"])
    print(f"{len(legs)} flights, {legs.origin.nunique()} airports\n")
    print(summary.round(2).to_string())

    bases = pd.DataFrame({"real": validation.aircraft_per_base(real, "aircraft"),
                          "model": validation.aircraft_per_base(run.rotations, "tail_id")})
    bases = bases.fillna(0).astype(int).sort_values("real", ascending=False)
    print("\nbases where the model differs:\n" + bases[bases.real != bases.model].to_string())
    pd.concat([summary, bases]).round(2).to_csv(OUT / f"{run.scenario.name}_real_vs_model.csv")

    turns = validation.same_next_flight(run, real)
    turns["waiting"] = turns.alone.map({True: "one aircraft", False: "several aircraft"})
    print("\nturns where the model's aircraft flies the same next flight as the real one:")
    print(turns.groupby("waiting").same.agg(turns="count", same="mean").round(2).to_string())

    bases_figure(bases, real_aircraft, model_aircraft, run.scenario.name)


if __name__ == "__main__":
    main()
