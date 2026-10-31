import pytest

from altfuel import analysis
from altfuel.data_layer import load_data
from altfuel.scenario_config import load_scenario


@pytest.fixture(scope="module")
def data():
    return load_data()


@pytest.fixture(scope="module")
def run_co2(data):
    return analysis.run(data, load_scenario("alt_min_co2"))


def test_every_leg_flown_exactly_once(data, run_co2):
    assign = run_co2.result.assign
    assert run_co2.result.status == "Optimal"
    assert sorted(assign.index) == sorted(data.legs.index)
    assert (assign.type != "dropped").all()           # allow_drop is false


def test_fuel_range_and_fleet_respected(data, run_co2):
    sc = run_co2.scenario
    for r in run_co2.flown.itertuples():
        leg = data.legs.loc[r.leg_id]
        ac = data.aircraft_types.loc[r.type]
        assert leg.distance_km <= ac.range_km
        if ac.fuel != "kerosene":
            assert data.airports.loc[leg.origin, "tier"] <= sc.fuel_max_tier[ac.fuel]
    for k, n in run_co2.result.fleet_used.items():
        assert n <= sc.fleet[k]


def test_rotations_cover_flown_legs_without_violations(run_co2):
    assert len(run_co2.rotations) == run_co2.kpis["legs_flown"]
    assert run_co2.violations == []


def test_baseline_is_all_kerosene(data):
    r = analysis.run(data, load_scenario("baseline"))
    assert r.kpis["share_kerosene"] == 1.0
