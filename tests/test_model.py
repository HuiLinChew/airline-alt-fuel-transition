from altfleet.data import daily_demand, load_inputs
from altfleet.rotations import build_rotations
from altfleet.scenarios import SCENARIOS, apply
from altfleet.model import solve


def _solved(name):
    inp = load_inputs()
    sc = next(s for s in SCENARIOS if s.name == name)
    i = apply(inp, sc)
    return i, solve(i, sc.objective)


def test_all_passengers_served_and_balanced():
    inp, sol = _solved("alt_min_co2")
    assert sol.status == "Optimal"
    F = sol.flights
    cap = (F.flights * F.pax_cap).groupby([F.origin, F.destination]).sum()
    D = daily_demand(inp)
    assert (cap.reindex(D.index, fill_value=0) >= D).all()
    for k, g in F.groupby("type"):
        dep = g.groupby("origin").flights.sum()
        arr = g.groupby("destination").flights.sum()
        assert dep.sub(arr, fill_value=0).abs().sum() == 0


def test_fuel_and_range_respected():
    inp, sol = _solved("alt_min_co2")
    F = sol.flights
    for r in F.itertuples():
        assert r.fuel in inp.airports.loc[r.origin, "fuels"]
        assert r.distance_km <= inp.aircraft.loc[r.type, "range_km"]


def test_rotations_cover_every_flight_within_curfew():
    inp, sol = _solved("alt_min_co2")
    legs, summary = build_rotations(inp, sol)
    assert len(legs) == sol.flights.flights.sum()
    assert (legs.arr_h <= inp.op_end_h + 1e-9).all()
    assert summary.feasible_with_optimiser_fleet.all()
