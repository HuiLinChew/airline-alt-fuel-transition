"""Compare the model with what Ryanair really flew on the same day.

    uv run scripts/compare_ryanair.py ryanair_1d      (or ryanair_4d)

Needs the scenario's data folder (scripts/make_ryanair_data.py). The model gets Ryanair's real
timetable for the aircraft whose whole day is known, kerosene only, and chooses its
own rotations. Saves outputs/ryanair/<scenario>_real_vs_model.csv and a figure of aircraft per base.
"""

import sys

import matplotlib.pyplot as plt
import pandas as pd

from altfuel import analysis, plots
from altfuel.scenario_config import load_scenario
from altfuel.utils import OUTPUT_DIR

OUT = OUTPUT_DIR / "ryanair"


def first_station(rotations, tail):
    return rotations.sort_values([tail, "dep_min"]).groupby(tail).origin.first()


def connections(rotations, tail):
    """Each pair of flights one aircraft flies back to back: the airport in between and
    when the aircraft is on the ground there."""
    rotations = rotations.sort_values([tail, "dep_min"])
    after = rotations.groupby(tail).shift(-1)
    turns = after.leg_id.notna()
    return pd.DataFrame({"first": rotations.leg_id[turns], "then": after.leg_id[turns],
                         "at": rotations.destination[turns], "lands": rotations.arr_min[turns],
                         "leaves": after.dep_min[turns]})


def only_one_waiting(turns, real):
    """True where no other real aircraft is on the ground at that airport at the same
    time (turning, or waiting there since the night), so the next flight's aircraft is forced."""
    by_tail = real.sort_values("dep_min").groupby("icao24")
    mornings = pd.DataFrame({"at": by_tail.origin.first(), "lands": -1e9, "leaves": by_tail.dep_min.first()})
    evenings = pd.DataFrame({"at": by_tail.destination.last(), "lands": by_tail.arr_min.last(), "leaves": 1e9})
    ground = pd.concat([turns, mornings, evenings], ignore_index=True)
    alone = []
    for r in turns.itertuples():
        busy = (ground["at"] == r.at) & (ground.lands < r.leaves) & (ground.leaves > r.lands)
        alone.append(busy.sum() == 1)       # only itself
    return alone


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    run = analysis.run(load_scenario(sys.argv[1]))
    legs = run.data.legs
    real = pd.read_csv(run.scenario.data_path / "real_rotations.csv").join(legs, on="leg_id")

    real_aircraft = real.icao24.nunique()
    model_aircraft = run.kpis["aircraft"]
    block_hours = (legs.arr_min - legs.dep_min).sum() / 60
    summary = pd.DataFrame({
        "real": [real_aircraft, len(legs) / real_aircraft, block_hours / real_aircraft],
        "model": [model_aircraft, len(legs) / model_aircraft, block_hours / model_aircraft],
    }, index=["aircraft", "flights per aircraft", "block hours per aircraft"])
    print(f"{len(legs)} flights, {legs.origin.nunique()} airports\n")
    print(summary.round(2).to_string())

    # Aircraft starting the day at each base
    bases = pd.DataFrame({"real": first_station(real, "icao24").value_counts(),
                          "model": first_station(run.rotations, "tail_id").value_counts()})
    bases = bases.fillna(0).astype(int).sort_values("real", ascending=False)
    print("\nbases where the model differs:\n" + bases[bases.real != bases.model].to_string())
    pd.concat([summary, bases]).round(2).to_csv(OUT / f"{run.scenario.name}_real_vs_model.csv")

    # Does each model aircraft fly the same next flight as the real one did? Only testable
    # where one aircraft was waiting: where several were, any of them could take it and
    # the model has no reason to prefer one (Ryanair picks by crew and maintenance).
    real_turns = connections(real, "icao24").reset_index(drop=True)
    model_turns = set(zip(*connections(run.rotations, "tail_id")[["first", "then"]].to_numpy().T))
    real_turns["same"] = [pair in model_turns for pair in zip(real_turns["first"], real_turns.then)]
    real_turns["waiting"] = pd.Series(only_one_waiting(real_turns, real)).map(
        {True: "one aircraft", False: "several aircraft"})
    print("\nturns where the model's aircraft flies the same next flight as the real one:")
    print(real_turns.groupby("waiting").same.agg(turns="count", same="mean").round(2).to_string())

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
    fig.savefig(OUT / f"{run.scenario.name}_aircraft_per_base.png", dpi=200, bbox_inches="tight")


if __name__ == "__main__":
    main()
