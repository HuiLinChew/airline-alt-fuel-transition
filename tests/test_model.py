import itertools
from dataclasses import replace

import pandas as pd
import pytest

from altfuel import aircraft_performance, airport_capability, analysis, cost_revenue
from altfuel.aircraft_performance import fuel_kg
from altfuel.cost_revenue import ownership_per_day
from altfuel.data_layer import load_data
from altfuel.data_layer import validate as validate_data
from altfuel.rotation_checker import build_rotations, day_cycles
from altfuel.scenario_config import DEFAULT_OWNERSHIP, Scenario, load_scenario, validate


@pytest.fixture(scope="module")
def data():
    return load_data(Scenario(name="test").data_path)


@pytest.fixture(scope="module")
def co2_run(data):
    return analysis.run(load_scenario("alt_min_co2"), data)


def counts_from_rotations(r):
    """Runway movements per hour and aircraft at each station, counted from the
    tail rotations: an independent check on the optimiser's capacity numbers."""
    rot, period = r.rotations.sort_values("dep_min"), r.scenario.period_min
    departures = rot.groupby(["origin", rot.dep_min // 60 * 60]).size()
    arrivals = rot.groupby(["destination", rot.arr_min % period // 60 * 60]).size()
    movements = pd.concat([departures, arrivals]).groupby(level=[0, 1]).sum()

    on_station = []       # (station, from, until)
    for _, tail in rot.groupby("tail_id"):
        legs = list(tail.itertuples())
        for a, b in zip(legs, legs[1:]):
            on_station.append((a.destination, a.arr_min, b.dep_min))
        on_station.append((legs[-1].destination, legs[-1].arr_min, period))
        on_station.append((legs[0].origin, 0, legs[0].dep_min))
    return movements, on_station


# Basic behaviour

def test_every_leg_flown_once(data, co2_run):
    assert co2_run.result.status == "Optimal"
    assert sorted(co2_run.result.assign.index) == sorted(data.legs.index)
    assert (co2_run.result.assign.type != "dropped").all()


def test_range_fuel_and_fleet_respected(data, co2_run):
    for r in co2_run.flown.itertuples():
        leg = data.legs.loc[r.leg_id]
        assert leg.distance_km <= data.aircraft_types.range_km[r.type]
        assert co2_run.airport_fuel.loc[(leg.origin, r.fuel), "available"]
    for ac_type, n in co2_run.result.fleet_used.items():
        assert n <= co2_run.scenario.fleet[ac_type]


def test_rotations_cover_every_flown_leg(co2_run):
    assert len(co2_run.rotations) == co2_run.kpis["legs_flown"]
    assert co2_run.violations == []


def test_baseline_is_all_kerosene(data):
    r = analysis.run(load_scenario("baseline"), data)
    assert r.kpis["share_kerosene"] == 1.0
    assert r.kpis["legs_dropped"] == 0


def test_named_station_gets_fuel(data):
    r = analysis.run(replace(load_scenario("alt_min_co2"), fuel_stations={"lh2": ["DUB"]}), data)
    assert r.airport_fuel.loc[("DUB", "lh2"), "available"]


def test_objective_equals_total_cost(data):
    for name in ["baseline", "alt_carbon_200", "alt_carbon_200_spill", "alt_carbon_200_drop"]:
        r = analysis.run(load_scenario(name), data)
        assert r.result.objective == pytest.approx(r.kpis["total_cost_usd"], abs=1.0)


# Checks that the answer is physically right, not just self-consistent

def test_shifting_the_timetable_changes_nothing(data):
    """The schedule repeats daily, so moving every flight 12 h later (some now land
    after midnight) must need the same aircraft and cost the same."""
    legs = data.legs.copy()
    block = legs.arr_min - legs.dep_min
    legs["dep_min"] = (legs.dep_min + 720) % 1440
    legs["arr_min"] = legs.dep_min + block
    for name in ["baseline", "alt_carbon_200"]:
        normal = analysis.run(load_scenario(name), data)
        shifted = analysis.run(load_scenario(name), replace(data, legs=legs))
        assert shifted.kpis["aircraft"] == normal.kpis["aircraft"]
        assert shifted.kpis["total_cost_usd"] == pytest.approx(normal.kpis["total_cost_usd"])
        assert shifted.violations == []


def test_a_week_of_identical_days(data):
    """Seven copies of the day as a weekly schedule: 7x the cost, same fleet."""
    days = []
    for d in range(7):
        day = data.legs.copy()
        day["dep_min"] += 1440 * d
        day["arr_min"] += 1440 * d
        day.index = [f"{leg}_day{d}" for leg in day.index]
        days.append(day)
    week = pd.concat(days).rename_axis("leg_id")
    sc = load_scenario("alt_carbon_200")
    one_day = analysis.run(sc, data)
    one_week = analysis.run(replace(sc, period_min=10080), replace(data, legs=week))
    assert one_week.kpis["aircraft"] == one_day.kpis["aircraft"]
    assert one_week.kpis["total_cost_usd"] == pytest.approx(7 * one_day.kpis["total_cost_usd"])


def test_optimiser_matches_brute_force(data):
    """On a 6-leg network, try every assignment and keep the cheapest that can be flown."""
    small = replace(data, legs=data.legs.loc[["L000", "L001", "L004", "L008", "L009", "L010"]])
    sc = replace(load_scenario("alt_carbon_200"), capacity_mode="off")
    fuel = airport_capability.airport_fuel(small, sc)
    perf = cost_revenue.add_costs(aircraft_performance.perf(small, fuel, sc), small, fuel, sc)
    own = cost_revenue.ownership_per_day(small, sc)

    best = None
    types = list(sc.fleet)
    for choice in itertools.product(types, repeat=len(small.legs)):
        if not all(perf.at[(k, leg), "feasible"] for k, leg in zip(choice, small.legs.index)):
            continue
        assign = pd.DataFrame({"type": choice}, index=pd.Index(small.legs.index, name="leg_id"))
        rot, _ = build_rotations(small, perf, assign, {k: 99 for k in types})
        first = rot.groupby("tail_id").first()
        last = rot.sort_values("dep_min").groupby("tail_id").last()
        if sorted(zip(first.type, first.origin)) != sorted(zip(last.type, last.destination)):
            continue          # can't repeat tomorrow
        aircraft = rot.groupby("type").tail_id.nunique()
        cost = sum(perf.at[(k, leg), "cost_usd"] for k, leg in zip(choice, small.legs.index))
        cost += sum(n * own[k] for k, n in aircraft.items())
        if best is None or cost < best:
            best = cost

    r = analysis.run(sc, small)
    assert r.kpis["total_cost_usd"] == pytest.approx(best)


# Input checks

def test_scenario_typos_are_caught(data):
    with pytest.raises(ValueError, match="fleet"):
        validate(Scenario(name="bad", fleet={"LH2-NBB": 4}), data)
    with pytest.raises(ValueError, match="fuel_max_tier"):
        validate(Scenario(name="bad", fuel_max_tier={"hydrogen": 1}), data)
    with pytest.raises(ValueError, match="only work with the cost objective"):
        validate(Scenario(name="bad", objective="co2", allow_drop=True), data)


def test_bad_input_data_is_rejected(data):
    legs = data.legs.copy()
    legs.loc["L000", "destination"] = "XXX"
    with pytest.raises(ValueError, match="missing from airports.csv"):
        validate_data(replace(data, legs=legs))
    with pytest.raises(ValueError, match="duplicate leg_id"):
        validate_data(replace(data, legs=pd.concat([data.legs, data.legs.head(1)])))


def test_overrides_change_the_inputs(data):
    sc = replace(load_scenario("alt_min_co2"), aircraft_overrides={"LH2-NB": {"range_km": 300}})
    r = analysis.run(sc, data)
    lh2_legs = r.flown[r.flown.type == "LH2-NB"].leg_id
    assert (data.legs.distance_km.loc[lh2_legs] <= 300).all()


# Fuel burn, block times, CO2

def test_fuel_burn_table_replaces_straight_line(data):
    table = pd.DataFrame({"type": ["LH2-NB", "LH2-NB"], "distance_km": [0, 1000], "fuel_kg": [500, 1500]})
    with_table = replace(data, fuel_burn=table)
    assert fuel_kg(with_table, "LH2-NB", 500) == pytest.approx(1000)
    assert pd.isna(fuel_kg(with_table, "LH2-NB", 2000))           # past the end of the table
    assert fuel_kg(with_table, "KER-NB", 500) == pytest.approx(fuel_kg(data, "KER-NB", 500))


def test_slower_type_arrives_later(data):
    sc = replace(load_scenario("alt_min_co2"), aircraft_overrides={"LH2-NB": {"cruise_kmh": 700}})
    r = analysis.run(sc, data)
    lh2 = r.perf.xs("LH2-NB", level="type")
    scheduled = (data.legs.arr_min - data.legs.dep_min).loc[lh2.index]
    extra = (data.legs.distance_km * (1 / 700 - 1 / 830) * 60).loc[lh2.index]
    assert (lh2.block_min - scheduled).to_numpy() == pytest.approx(extra.to_numpy(), abs=0.5)
    assert r.violations == []


def test_reference_type_keeps_the_schedule(data):
    r = analysis.run(load_scenario("baseline"), data)
    kerosene = r.perf.xs("KER-NB", level="type")
    assert (kerosene.arr_min == data.legs.arr_min.loc[kerosene.index]).all()


def test_well_to_tank_counts_in_co2_but_not_carbon_price(data):
    r = analysis.run(replace(load_scenario("alt_carbon_200"), wtt_co2_kg_per_kg={"lh2": 10.0}), data)
    lh2 = r.perf.xs("LH2-NB", level="type")
    assert (lh2.co2_wtt_t == lh2.fuel_kg * 10.0 / 1000).all()
    assert (r.perf.co2_t == r.perf.co2_ttw_t + r.perf.co2_wtt_t).all()
    kerosene = r.perf.xs("KER-NB", level="type")
    assert (kerosene.carbon_cost_usd == kerosene.co2_ttw_t * 200).all()


def test_fossil_lng_pays_carbon_price(data):
    r = analysis.run(load_scenario("alt_carbon_200"), data)
    lng = r.perf.xs("CH4-NB", level="type")
    assert (lng.fuel == "ch4").all()
    assert (lng.carbon_cost_usd == lng.co2_ttw_t * 200).all()


def test_switch_to_e_methane(data):
    r = analysis.run(load_scenario("alt_carbon_200_emethane"), data)
    e_methane = r.perf.xs("CH4-NB", level="type")
    assert (e_methane.fuel == "ch4_e").all()
    assert (e_methane.carbon_cost_usd == 0).all()
    assert e_methane.co2_t.abs().max() < 1e-9


# Spill and dropped legs

def test_without_spill_a_small_aircraft_cannot_take_a_full_leg(data):
    r = analysis.run(replace(load_scenario("alt_carbon_200"), aircraft_overrides={"LH2-NB": {"seats": 150}}), data)
    seats_usable = int(150 * data.aircraft_types.max_load_factor["LH2-NB"])
    lh2_legs = r.flown[r.flown.type == "LH2-NB"].leg_id
    assert (data.legs.pax.loc[lh2_legs] <= seats_usable).all()
    assert r.kpis["pax_spilled"] == 0


def test_spill_is_charged_at_the_fare(data):
    # Only one type, with 150 seats, so full legs must spill
    sc = replace(load_scenario("alt_carbon_200_spill"), fleet={"KER-NB": 30},
                 aircraft_overrides={"KER-NB": {"seats": 150}})
    r = analysis.run(sc, data)
    spilled = r.flown[r.flown.spill_pax > 0]
    assert len(spilled) > 0
    fare = data.legs.distance_km.loc[spilled.leg_id].to_numpy() * sc.yield_usd_per_pax_km
    assert spilled.spill_cost_usd.to_numpy() == pytest.approx(spilled.spill_pax.to_numpy() * fare)


def test_legs_nobody_can_fly_give_a_clear_error(data):
    sc = replace(load_scenario("baseline"), aircraft_overrides={"KER-NB": {"seats": 100}})
    with pytest.raises(ValueError, match="too few seats"):
        analysis.run(sc, data)


# Airport capacity

def test_check_mode_does_not_change_the_answer(data):
    sc = load_scenario("alt_carbon_200")
    checked = analysis.run(sc, data)
    off = analysis.run(replace(sc, capacity_mode="off"), data)
    assert checked.result.assign.equals(off.result.assign)
    assert len(checked.result.capacity) > 0 and len(off.result.capacity) == 0


def test_capacity_use_matches_rotations(data):
    # A slower LH2 type, so arrival times differ by type
    sc = replace(load_scenario("alt_min_co2"), aircraft_overrides={"LH2-NB": {"cruise_kmh": 500}})
    r = analysis.run(sc, data)
    movements, on_station = counts_from_rotations(r)
    cap = r.result.capacity

    runway = cap[cap.measure == "movements_per_hour"].set_index(["station", "time_min"]).used
    assert runway.reindex(movements.index, fill_value=0).equals(movements)
    assert runway.sum() == movements.sum()
    for c in cap[cap.measure == "stands"].itertuples():
        assert c.used == sum(s == c.station and a <= c.time_min < b for s, a, b in on_station)


def test_stand_limit_is_respected(data):
    sc = replace(load_scenario("alt_carbon_200"), capacity_mode="constrain",
                 capacity_share={"movements_per_hour": 1.0, "stands": 0.02})
    r = analysis.run(sc, data)
    assert r.result.status == "Optimal"
    assert r.kpis["capacity_breaches"] == 0
    assert r.kpis["total_cost_usd"] >= analysis.run(load_scenario("alt_carbon_200"), data).kpis["total_cost_usd"]


def test_overloaded_runway_has_no_solution(data):
    sc = replace(load_scenario("baseline"), capacity_mode="constrain", capacity_share=0.03)
    assert analysis.run(sc, data).kpis == {"status": "Infeasible"}


def test_no_solution_gives_no_numbers(data):
    sc = replace(load_scenario("alt_carbon_200"), capacity_mode="constrain",
                 capacity_share={"movements_per_hour": 1.0, "stands": 0.011})
    assert analysis.run(sc, data).kpis == {"status": "Infeasible"}


# Ownership

def test_ownership_matches_hoelzen_annuity(data):
    own = ownership_per_day(data, Scenario(name="test"))
    rate, years, residual = 0.05, 14, 0.05
    annuity = rate * (1 - residual / (1 + rate) ** years) / (1 - 1 / (1 + rate) ** years)
    assert own["KER-NB"] == pytest.approx(data.aircraft_types.price_usd["KER-NB"] * (annuity + 0.005) / 365)
    assert own["LH2-NB"] > own["KER-NB"]


def test_changing_one_ownership_setting_keeps_the_others(data):
    own = ownership_per_day(data, Scenario(name="test", ownership={"interest_rate": 0.07}))
    rate, years, residual = 0.07, DEFAULT_OWNERSHIP["depreciation_years"], DEFAULT_OWNERSHIP["residual_value"]
    annuity = rate * (1 - residual / (1 + rate) ** years) / (1 - 1 / (1 + rate) ** years)
    price = data.aircraft_types.price_usd["KER-NB"]
    assert own["KER-NB"] == pytest.approx(price * (annuity + DEFAULT_OWNERSHIP["insurance_rate"]) / 365)


def test_ownership_is_charged_per_aircraft_used(data):
    r = analysis.run(load_scenario("alt_carbon_200"), data)
    own = ownership_per_day(data, r.scenario)
    assert r.kpis["ownership_cost_usd"] == pytest.approx(sum(n * own[k] for k, n in r.result.fleet_used.items()))
    free = replace(r.scenario, aircraft_overrides={k: {"price_usd": 0} for k in data.aircraft_types.index})
    assert analysis.run(free, data).kpis["aircraft"] >= r.kpis["aircraft"]


# Multi-day cycles

def test_day_cycles_follow_aircraft_round_the_network():
    # Three aircraft-days: LHR->CDG, CDG->AMS, AMS->LHR. One aircraft flying them
    # in turn is back at LHR after three days.
    rot = pd.DataFrame({"tail_id": ["T1", "T2", "T3"], "type": "KER-NB",
                        "origin": ["LHR", "CDG", "AMS"], "destination": ["CDG", "AMS", "LHR"]})
    cycles = day_cycles(rot)
    assert len(cycles) == 1
    assert cycles.days[0] == 3
    assert cycles.nights[0] == "CDG > AMS > LHR"


def test_chains_timetable_gives_multi_day_cycles():
    sc = load_scenario("chains_carbon_200")
    r = analysis.run(sc)
    assert r.violations == []
    assert r.kpis["longest_cycle_days"] > 1
    # every aircraft-day belongs to exactly one cycle
    for ac_type, n in r.result.fleet_used.items():
        if n:
            assert r.cycles[r.cycles.type == ac_type].days.sum() == r.rotations[r.rotations.type == ac_type].tail_id.nunique()
