"""Build the dummy input tables from Hasan's raw data.

    uv run scripts/make_dummy_data.py [path/to/hydrogen-airport-model/data/raw]

Writes airports.csv, legs.csv and aircraft_types.csv to two folders:
  data/dummy/         out-and-back timetable: every aircraft can be home each night
  data/dummy_chains/  chains timetable: aircraft end the day at different airports
                      and take several days to get back to where they started
fuels.csv is written by hand (constants and literature prices) in data/dummy/ and
copied to data/dummy_chains/.

The dummy schedule is invented: real timed schedules (ADS-B / OpenSky) will
replace legs.csv later. Everything else traces to Henry's/Hasan's data or a paper.
"""

import math
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "dummy"
OUT_CHAINS = ROOT / "data" / "dummy_chains"
RAW = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT.parent / "hydrogen-airport-model" / "data" / "raw"

STATIONS = ["LHR", "CDG", "AMS", "MAD", "DUB"]
AIRLINE_SHARE = 0.15      # share of each route's passengers our airline carries
SEATS = 180               # all three types share the same cabin (Hoelzen et al. 2025 design PAX)
LOAD_FACTOR = 0.83        # max load factor (Rau et al. 2024)
FIRST_DEP, LAST_ARR = 390, 1350  # schedule window, minutes after midnight (06:30-22:30)
TIER = {"INT": 1, "MAJ": 2, "SMA": 3}   # placeholder until the tier 1-6 mapping is defined
KER_PRICE_USD = 49.4e6    # new-delivery A320neo market value, IBA (Nov 2021)
LH2_PRICE_FACTOR = 1.12   # +12% aircraft CAPEX, short-range LH2 aircraft (Hoelzen et al. 2022)
CREW_PER_BLOCK_HOUR = 940          # USD, same for all types (from Hoelzen et al. 2022 salaries)
MAINT_PER_BLOCK_HOUR = 2060        # USD, kerosene. Placeholder: keeps crew + maintenance at 3,000
LH2_MAINT_FACTOR = 1.0             # same as kerosene for now; Hoelzen et al. 2022 give +11% (short-range)
CRUISE_KMH = 830          # same for all types: Hoelzen et al. 2025 design Mach 0.78 for both
                          # kerosene and LH2 single-aisle designs; also used to time the schedule
CHAIN_TURN = 60           # minutes on the ground between legs in the chains timetable

# Chains timetable: one line of stations per aircraft-day. Each group of lines is
# a cycle: the next line starts where the previous one ends, so an aircraft flying
# them in turn is back where it started after (number of lines) days.
CHAIN_CYCLES = {
    "3-day": [["LHR", "CDG", "LHR", "DUB", "LHR", "MAD", "CDG"],
              ["CDG", "AMS", "CDG", "MAD", "AMS"],
              ["AMS", "DUB", "AMS", "CDG", "LHR"]],
    "2-day": [["AMS", "LHR", "AMS", "MAD", "DUB"],
              ["DUB", "CDG", "DUB", "LHR", "AMS"]],
    "4-day": [["MAD", "CDG", "MAD", "LHR"],
              ["LHR", "AMS", "LHR", "CDG"],
              ["CDG", "LHR", "CDG", "AMS"],
              ["AMS", "CDG", "AMS", "MAD"]],
    "1-day": [["DUB", "LHR", "DUB", "AMS", "DUB"],
              ["MAD", "DUB", "MAD", "LHR", "MAD"]],
}


def read(path):
    return pd.read_csv(path, keep_default_na=False, na_values=[""])  # keep region "NA"


def build_airports():
    ap = read(RAW / "airport_all.csv")
    ap = ap[ap.iata.isin(STATIONS)]
    return pd.DataFrame({
        "station": ap.iata, "name": ap.airport_name, "lat": ap.lat, "lon": ap.long,
        "tier": ap.classification.map(TIER), "runways": ap.num_runways, "stands": ap.stands,
        "hourly_capacity": ap.base_hourly_capacity,
    })


def route_data():
    """Daily passengers for our airline and distance, per (origin, destination)."""
    seg, ap = read(RAW / "segment_data.csv"), read(RAW / "airport_all.csv")
    iata = ap.set_index("airport_id").iata
    seg = seg.assign(o=seg.origin_id.map(iata), d=seg.destination_id.map(iata))
    seg = seg[seg.o.isin(STATIONS) & seg.d.isin(STATIONS)]
    pax = {(r.o, r.d): r.base_pax_demand * AIRLINE_SHARE / 365 for r in seg.itertuples()}
    km = {(r.o, r.d): r.stage_length_km for r in seg.itertuples()}
    return pax, km


def to5(minutes):
    """Round to 5 minutes."""
    return int(round(minutes / 5) * 5)


def number_legs(rows):
    legs = pd.DataFrame(rows).sort_values(["dep_min", "origin"]).reset_index(drop=True)
    legs.insert(0, "leg_id", [f"L{i:03d}" for i in range(len(legs))])
    return legs


def build_legs():
    """Daily timed legs. Frequency per airport pair = enough seats for the busier
    direction; outbound departures are spread over the day and each return leaves
    one hour after the outbound lands, so every station is balanced."""
    pax, km = route_data()
    rows = []
    for o, d in sorted(pax):
        if o > d:          # handle each pair once, from its alphabetically first station
            continue
        block = to5(km[o, d] / CRUISE_KMH * 60 + 30)              # cruise + 30 min
        freq = math.ceil(max(pax[o, d], pax[d, o]) / (SEATS * LOAD_FACTOR))
        span = LAST_ARR - FIRST_DEP - 2 * block - 60               # room for out + 1 h + back
        for k in range(freq):
            dep = to5(FIRST_DEP + (span * k / (freq - 1) if freq > 1 else span / 2))
            back = dep + block + 60
            for a, b, t in [(o, d, dep), (d, o, back)]:
                rows.append(dict(origin=a, destination=b, dep_min=t, arr_min=t + block,
                                 distance_km=round(km[a, b], 1), pax=round(pax[a, b] / freq)))
    return number_legs(rows)


def build_chain_legs():
    """Daily timed legs from CHAIN_CYCLES. Each line starts between 06:30 and about
    10:30 and its legs follow each other with CHAIN_TURN minutes on the ground.
    A route's daily passengers are split over its legs, capped at seats x load
    factor so every leg can be flown (this timetable tests rotations, not demand)."""
    pax, km = route_data()
    lines = [line for cycle in CHAIN_CYCLES.values() for line in cycle]
    trips = [(a, b) for line in lines for a, b in zip(line, line[1:])]
    legs_per_route = {route: trips.count(route) for route in set(trips)}
    max_pax = math.floor(SEATS * LOAD_FACTOR)

    rows = []
    for i, line in enumerate(lines):
        t = FIRST_DEP + 20 * i
        for a, b in zip(line, line[1:]):
            block = to5(km[a, b] / CRUISE_KMH * 60 + 30)
            rows.append(dict(origin=a, destination=b, dep_min=t, arr_min=t + block,
                             distance_km=round(km[a, b], 1),
                             pax=min(round(pax[a, b] / legs_per_route[a, b]), max_pax)))
            t += block + CHAIN_TURN
    return number_legs(rows)


def build_aircraft_types():
    """Fuel burn is a linear fit (fixed + per km) to Henry's short-haul range-fuel
    curves as used by Hasan (aircraft_data.csv, R^2 > 0.999 over 0-3000 km).
    Methane: kerosene energy +10% (Rompokos et al. 2020) at LHV 50 MJ/kg.
    Refuel pumps: narrowbody = 2 (Al-Timimi, after FlyZero). Crew cost is the same for
    all types; maintenance is a placeholder base, also the same for all types for now.
    A type can instead use a burn-vs-distance table in fuel_burn.csv (see README)."""
    curves = read(RAW / "aircraft_data.csv")
    curves = curves[curves.range_km <= 3000]
    fit = {c: np.polyfit(curves.range_km, curves[c], 1) for c in ["ker_sh", "lh2_sh"]}
    ker_per_km, ker_fixed = fit["ker_sh"]
    lh2_per_km, lh2_fixed = fit["lh2_sh"]
    ch4 = 1.10 * 43.2 / 50.0   # kerosene kg -> methane kg at +10% energy
    return pd.DataFrame([
        dict(type="KER-NB", fuel="kerosene", seats=SEATS, max_load_factor=LOAD_FACTOR,
             range_km=6000, turn_min=40, refuel_pumps=2, cruise_kmh=CRUISE_KMH,
             crew_cost_per_block_hour=CREW_PER_BLOCK_HOUR, maintenance_cost_per_block_hour=MAINT_PER_BLOCK_HOUR,
             price_usd=KER_PRICE_USD, fuel_kg_fixed=ker_fixed, fuel_kg_per_km=ker_per_km,
             source="A320-class; fuel: Sanford/Al-Timimi SH curve; turn: Akinola et al. 2025; price: IBA 2021"),
        dict(type="LH2-NB", fuel="lh2", seats=SEATS, max_load_factor=LOAD_FACTOR,
             range_km=2778, turn_min=40, refuel_pumps=2, cruise_kmh=CRUISE_KMH,
             crew_cost_per_block_hour=CREW_PER_BLOCK_HOUR,
             maintenance_cost_per_block_hour=MAINT_PER_BLOCK_HOUR * LH2_MAINT_FACTOR,
             price_usd=KER_PRICE_USD * LH2_PRICE_FACTOR, fuel_kg_fixed=lh2_fixed, fuel_kg_per_km=lh2_per_km,
             source="Hoelzen et al. 2025 SA-1500 (1500 NM); fuel: Sanford/Al-Timimi SH curve; price +12% Hoelzen et al. 2022"),
        dict(type="CH4-NB", fuel="ch4", seats=SEATS, max_load_factor=LOAD_FACTOR,
             range_km=5000, turn_min=40, refuel_pumps=2, cruise_kmh=CRUISE_KMH,
             crew_cost_per_block_hour=CREW_PER_BLOCK_HOUR, maintenance_cost_per_block_hour=MAINT_PER_BLOCK_HOUR,
             price_usd=KER_PRICE_USD, fuel_kg_fixed=ker_fixed * ch4, fuel_kg_per_km=ker_per_km * ch4,
             source="Rompokos et al. 2020 LNG 737-800 retrofit (+10% energy); fuel ch4 = fossil LNG (switch to ch4_e for e-methane); range approx.; price: kerosene price, no LNG premium sourced (gap)"),
    ]).round(4)


if __name__ == "__main__":
    airports, aircraft = build_airports(), build_aircraft_types()
    for folder, legs in [(OUT, build_legs()), (OUT_CHAINS, build_chain_legs())]:
        folder.mkdir(parents=True, exist_ok=True)
        for name, df in [("airports", airports), ("legs", legs), ("aircraft_types", aircraft)]:
            df.to_csv(folder / f"{name}.csv", index=False)
        print(f"{folder.name}: {len(legs)} legs")
    shutil.copy(OUT / "fuels.csv", OUT_CHAINS / "fuels.csv")
