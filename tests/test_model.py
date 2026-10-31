from dataclasses import replace

import pandas as pd
import pytest

from altfuel import analysis
from altfuel.aircraft_performance import fuel_kg
from altfuel.data_layer import load_data
from altfuel.scenario_config import Scenario, load_scenario, validate


@pytest.fixture(scope="module")
def data():
    return load_data(Scenario(name="x").data_path)


@pytest.fixture(scope="module")
def run_co2(data):
    return analysis.run(load_scenario("alt_min_co2"), data)


# --- model behaviour ---------------------------------------------------------

def test_every_leg_flown_exactly_once(data, run_co2):
    assign = run_co2.result.assign
    assert run_co2.result.status == "Optimal"
    assert sorted(assign.index) == sorted(data.legs.index)
    assert (assign.type != "dropped").all()           # allow_drop is false


def test_fuel_range_and_fleet_respected(data, run_co2):
    for r in run_co2.flown.itertuples():
        leg = data.legs.loc[r.leg_id]
        assert leg.distance_km <= data.aircraft_types.loc[r.type, "range_km"]
        assert run_co2.airport_fuel.loc[(leg.origin, r.fuel), "available"]
    for k, n in run_co2.result.fleet_used.items():
        assert n <= run_co2.scenario.fleet[k]


def test_rotations_cover_flown_legs_without_violations(run_co2):
    assert len(run_co2.rotations) == run_co2.kpis["legs_flown"]
    assert run_co2.violations == []


def test_baseline_is_all_kerosene(data):
    r = analysis.run(load_scenario("baseline"), data)
    assert r.kpis["share_kerosene"] == 1.0 and r.kpis["legs_dropped"] == 0


def test_explicit_station_adds_fuel(data):
    sc = replace(load_scenario("alt_min_co2"), fuel_stations={"lh2": ["DUB"]})
    r = analysis.run(sc, data)
    assert r.airport_fuel.loc[("DUB", "lh2"), "available"]


# --- robustness --------------------------------------------------------------

def test_leg_crossing_midnight_is_counted(data):
    """A late round trip that lands after midnight needs an aircraft at the count line."""
    late = pd.DataFrame(
        {"origin": ["LHR", "AMS"], "destination": ["AMS", "LHR"], "dep_min": [1380, 1300],
         "arr_min": [1435, 1355], "distance_km": [370.2, 370.2], "pax": [100, 100]},
        index=pd.Index(["X1", "X2"], name="leg_id"))
    # X1 lands 23:55, ready 00:35 the next day -> crosses the count line
    d = replace(data, legs=pd.concat([data.legs, late]))
    r = analysis.run(load_scenario("baseline"), d)
    assert r.result.status == "Optimal"
    base = analysis.run(load_scenario("baseline"), data)
    assert r.kpis["aircraft"] >= base.kpis["aircraft"]
    assert r.violations == []


def test_scenario_typos_are_caught(data):
    with pytest.raises(ValueError, match="fleet"):
        validate(Scenario(name="bad", fleet={"LH2-NBB": 4}), data)
    with pytest.raises(ValueError, match="fuel_max_tier"):
        validate(Scenario(name="bad", fuel_max_tier={"hydrogen": 1}), data)
    with pytest.raises(ValueError, match="allow_drop"):
        validate(Scenario(name="bad", objective="co2", allow_drop=True), data)


def test_fuel_burn_table_overrides_linear_fit(data):
    table = pd.DataFrame({"type": ["LH2-NB"] * 2, "distance_km": [0, 1000], "fuel_kg": [500, 1500]})
    d = replace(data, fuel_burn=table)
    assert fuel_kg(d, "LH2-NB", 500) == pytest.approx(1000)
    assert pd.isna(fuel_kg(d, "LH2-NB", 2000))           # beyond the table -> no data
    assert fuel_kg(d, "KER-NB", 500) == pytest.approx(fuel_kg(data, "KER-NB", 500))


def test_override_changes_input(data):
    sc = replace(load_scenario("alt_min_co2"), aircraft_overrides={"LH2-NB": {"range_km": 300}})
    r = analysis.run(sc, data)
    assert (r.flown[r.flown.type == "LH2-NB"].leg_id.map(data.legs.distance_km) <= 300).all()
