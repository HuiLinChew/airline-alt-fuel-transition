"""Module 10: compare the model's rotations with a real airline's (the Ryanair check).

The data folder's real_rotations.csv (scripts/make_ryanair_data.py) says which real aircraft
flew each leg. Real rotations use the column `aircraft`; the model's use `tail_id`.
"""

import pandas as pd

from .analysis import Run


def real_rotations(run: Run) -> pd.DataFrame:
    """What each real aircraft flew: one row per leg, with the leg's details."""
    real = pd.read_csv(run.scenario.data_path / "real_rotations.csv")
    return real.join(run.data.legs, on="leg_id")


def aircraft_per_base(rotations: pd.DataFrame, tail: str) -> pd.Series:
    """How many aircraft start the period at each airport."""
    return rotations.sort_values("dep_min").groupby(tail).origin.first().value_counts()


def connections(rotations: pd.DataFrame, tail: str) -> pd.DataFrame:
    """Each pair of flights one aircraft flies back to back: the airport in between and
    when the aircraft is on the ground there."""
    rotations = rotations.sort_values([tail, "dep_min"])
    after = rotations.groupby(tail).shift(-1)
    turns = after.leg_id.notna()
    return pd.DataFrame({"first": rotations.leg_id[turns], "then": after.leg_id[turns],
                         "at": rotations.destination[turns], "lands": rotations.arr_min[turns],
                         "leaves": after.dep_min[turns]}).reset_index(drop=True)


def only_one_waiting(turns: pd.DataFrame, real: pd.DataFrame) -> list:
    """True where no other real aircraft is on the ground at that airport at the same
    time (turning, or waiting there since the night), so the next flight's aircraft is forced."""
    by_tail = real.sort_values("dep_min").groupby("aircraft")
    mornings = pd.DataFrame({"at": by_tail.origin.first(), "lands": -1e9,
                             "leaves": by_tail.dep_min.first()})
    evenings = pd.DataFrame({"at": by_tail.destination.last(), "lands": by_tail.arr_min.last(),
                             "leaves": 1e9})
    ground = pd.concat([turns, mornings, evenings], ignore_index=True)
    alone = []
    for r in turns.itertuples():
        busy = (ground["at"] == r.at) & (ground.lands < r.leaves) & (ground.leaves > r.lands)
        alone.append(busy.sum() == 1)       # only itself
    return alone


def same_next_flight(run: Run, real: pd.DataFrame) -> pd.DataFrame:
    """Every real turn, whether the model's aircraft flies the same next flight (`same`),
    and whether only one aircraft was on the ground then (`alone`), so the answer is forced.
    Where several were waiting, any of them could take it and the model has no reason to
    prefer one (the airline picks by crew and maintenance), so those can't be compared."""
    turns = connections(real, "aircraft")
    model = connections(run.rotations, "tail_id")
    model_pairs = set(zip(model["first"], model.then))
    turns["same"] = [pair in model_pairs for pair in zip(turns["first"], turns.then)]
    turns["alone"] = only_one_waiting(turns, real)
    return turns
