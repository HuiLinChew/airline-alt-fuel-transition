"""Build a few real days of Ryanair flying from EUROCONTROL flight data.

    uv run scripts/make_ryanair_data.py path/to/Flights_20250901_20250930.csv 2025-09-17 4

(file, first day, number of days). The file is the "Flights" file from EUROCONTROL's
Aviation Data Repository for Research (ADRR): every scheduled and non-scheduled commercial
flight in Europe, four months a year, two years behind. Free for research after
registering; it may not be shared, so data/ryanair_*/ is not committed. Airport positions
come from OurAirports (downloaded here). An earlier version used OpenSky flight lists
(commit 6d2b6fe).

Writes to data/ryanair_<days>d/ (e.g. data/ryanair_1d/):
  flights_clean.csv                                        every Ryanair flight that month, cleaned
  airports.csv, legs.csv, aircraft_types.csv, fuels.csv   inputs for the model (the chosen days)
  real_rotations.csv                                       what each real aircraft flew

Cleaning (load_flights):
1. Keep every flight by a Ryanair group aircraft: operator RYR (Ryanair, Malta Air, Lauda,
   Buzz scheduled) or RYS (Buzz charters), plus the few flights the same aircraft fly under
   an unknown operator (ZZZ). Aircraft are told apart by registration.
2. Gate times: the off-block time is given; the arrival time is the landing time, so we add
   5 min taxiing in (EUROCONTROL's average).

Then the chosen days (one_off_days), from 01:00 UTC, when the fewest Ryanair aircraft
are flying. Where an aircraft lands at A and next leaves from B, a flight is missing
(EUROCONTROL leaves out empty positioning flights) and we add one in the gap. Aircraft
are kept if every turn is at least TURN_MIN (20 min). The days don't repeat (scenario
setting repeat: false), so aircraft can start and end anywhere; bases are the airports
where the kept aircraft spend a night.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
AIRPORTS_URL = "https://raw.githubusercontent.com/davidmegginson/ourairports-data/main/airports.csv"

OPERATORS = ["RYR", "RYS"]
DAY_START_UTC = 1         # hours
TAXI_IN = 5               # minutes
SEATS = 189               # Boeing 737-800 in Ryanair's layout
LOAD_FACTOR = 0.94        # Ryanair's reported load factor (FY23-FY27 results: 93-94%)
TURN_MIN = 20             # Ryanair publishes 25 min; 20 allows for the taxi-in estimate
                          # and the quicker turns Ryanair makes when running late

def km_between(lat1, lon1, lat2, lon2):
    """Great-circle distance in km (haversine)."""
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371 * np.arcsin(np.sqrt(a))


def load_airports():
    """Every airport in OurAirports, by ICAO code: name, size, position and IATA code."""
    columns = ["ident", "type", "name", "latitude_deg", "longitude_deg", "iata_code"]
    return pd.read_csv(AIRPORTS_URL, usecols=columns).set_index("ident")


def load_flights(path):
    """Every flight a Ryanair group aircraft flew that month, with gate times."""
    flights = pd.read_csv(path, dtype=str)

    # Ryanair's aircraft are the registrations flying for RYR or RYS; keep everything they
    # flew, including the few flights filed under an unknown operator (ZZZ)
    ryanair = flights["AC Registration"][flights["AC Operator"].isin(OPERATORS)].dropna()
    flights = flights[flights["AC Registration"].isin(set(ryanair))]

    # Off-block is a gate time already; arrival is the landing, so add the taxi in
    time = "%d-%m-%Y %H:%M:%S"
    off_block = pd.to_datetime(flights["ACTUAL OFF BLOCK TIME"], format=time, utc=True)
    landing = pd.to_datetime(flights["ACTUAL ARRIVAL TIME"], format=time, utc=True)
    flights = pd.DataFrame({
        "aircraft": flights["AC Registration"], "type": flights["AC Type"],
        "origin": flights.ADEP, "destination": flights.ADES,
        "off_block": off_block, "on_block": landing + pd.Timedelta(minutes=TAXI_IN), "added": False,
    })

    # A few rows are flights that went nowhere, or the same flight twice
    flights = flights[flights.origin != flights.destination]
    return flights.drop_duplicates(["aircraft", "off_block"]).sort_values(["aircraft", "off_block"])


def km_between_airports(airports, a, b):
    """Distance between airports a and b (ICAO codes, or lists of them)."""
    lat, lon = airports.latitude_deg, airports.longitude_deg
    return km_between(np.asarray(lat[a]), np.asarray(lon[a]), np.asarray(lat[b]), np.asarray(lon[b]))


def one_off_days(flights, airports, date, days):
    """The flights of every aircraft whose whole stretch of days can be joined up (see
    join_up), with times in minutes from the start. Aircraft with a delivery flight
    (over 4,500 km, e.g. from Seattle) are left out."""
    start = pd.Timestamp(date, tz="UTC") + pd.Timedelta(hours=DAY_START_UTC)
    end = start + pd.Timedelta(days=days)
    window = flights[(flights.off_block >= start) & (flights.off_block < end)].copy()
    window["dep_min"] = (window.off_block - start).dt.total_seconds() / 60
    window["arr_min"] = (window.on_block - start).dt.total_seconds() / 60

    # Usual block time for a distance, from the real flights: minutes = a * km + b
    km = km_between_airports(airports, window.origin, window.destination)
    a, b = np.polyfit(km, window.arr_min - window.dep_min, 1)

    rows = []
    for tail, f in window.groupby("aircraft"):
        if (km_between_airports(airports, f.origin, f.destination) <= 4500).all():
            rows += join_up(f.to_dict("records"), tail, airports, a, b)
    kept = pd.DataFrame(rows)
    kept["dep_min"] = kept.dep_min.round().astype(int)
    kept["arr_min"] = kept.arr_min.round().astype(int)
    print(f"{date}, {days} days: {window.aircraft.nunique()} Ryanair aircraft, {len(window)} flights")
    print(f"  kept {kept.aircraft.nunique()} aircraft whose whole stretch is known: "
          f"{len(kept)} flights, {kept.added.sum()} of them added")
    return kept


def join_up(flights, tail, airports, a, b):
    """One aircraft's flights in order. Where it lands at A and next leaves from B, a flight
    is missing: add an A to B flight (block time a * km + b) in the middle of the gap.
    Returns no flights if any turn, including either side of an added flight, is under TURN_MIN."""
    joined = [flights[0]]
    for nxt in flights[1:]:
        prev = joined[-1]
        if prev["destination"] != nxt["origin"]:
            block = a * km_between_airports(airports, prev["destination"], nxt["origin"]) + b
            spare = nxt["dep_min"] - prev["arr_min"] - 2 * TURN_MIN - block
            dep = prev["arr_min"] + TURN_MIN + spare / 2
            joined.append({"aircraft": tail, "added": True, "origin": prev["destination"],
                           "destination": nxt["origin"], "dep_min": dep, "arr_min": dep + block})
        joined.append(nxt)
    ground = [n["dep_min"] - p["arr_min"] for p, n in zip(joined, joined[1:])]
    return joined if min(ground, default=TURN_MIN) >= TURN_MIN else []


def night_stops(kept, days):
    """Airports where a kept aircraft is at 01:00 UTC (the start of each day): on the
    ground there, or flying or turning towards it. Includes the first morning and last night."""
    stops = set()
    for tail, f in kept.sort_values("dep_min").groupby("aircraft"):
        stops.add(f.origin.iloc[0])
        stops.add(f.destination.iloc[-1])
        for midnight in range(1440, days * 1440, 1440):
            before = f[f.dep_min < midnight]
            stops.add(before.destination.iloc[-1] if len(before) else f.origin.iloc[0])
    return stops


def airports_table(kept, airports, days):
    """The model's airports.csv: every airport the kept aircraft use, named by IATA code
    (STN, DUB ...). Tier from OurAirports' size; bases are the night stops."""
    used = airports.loc[sorted(set(kept.origin) | set(kept.destination))]
    tier = used.type.map({"large_airport": 1, "medium_airport": 2}).fillna(3).astype(int)
    return pd.DataFrame({
        "station": used.iata_code.fillna(pd.Series(used.index, index=used.index)),
        "name": used.name, "lat": used.latitude_deg.round(4), "lon": used.longitude_deg.round(4),
        "tier": tier, "runways": None, "stands": None, "hourly_capacity": None,   # capacity off
        "base": used.index.isin(night_stops(kept, days)).astype(int),
        "curfew_start": None, "curfew_end": None,
    })


def legs_table(kept, airports, code):
    """The model's legs.csv. Every flight carries 94% of a 737-800's seats."""
    distance = km_between_airports(airports, kept.origin, kept.destination)
    return pd.DataFrame({
        "leg_id": kept.leg_id,
        "origin": kept.origin.map(code), "destination": kept.destination.map(code),
        "dep_min": kept.dep_min, "arr_min": kept.arr_min, "distance_km": distance.round(1),
        "pax": round(SEATS * LOAD_FACTOR), "added": kept.added.astype(int),
    })


def main():
    """Build the model inputs for the chosen days: file, first day, number of days."""
    path, date, days = sys.argv[1], sys.argv[2], int(sys.argv[3])
    out = ROOT / "data" / f"ryanair_{days}d"
    out.mkdir(parents=True, exist_ok=True)
    airports = load_airports()
    flights = load_flights(path)
    flights.to_csv(out / "flights_clean.csv", index=False)

    kept = one_off_days(flights, airports, date, days).sort_values("dep_min")
    kept["leg_id"] = [f"R{i:05d}" for i in range(len(kept))]
    stations = airports_table(kept, airports, days)
    legs = legs_table(kept, airports, stations.station)
    stations.sort_values("station").to_csv(out / "airports.csv", index=False)
    legs.to_csv(out / "legs.csv", index=False)
    kept.sort_values(["aircraft", "dep_min"])[["aircraft", "leg_id"]].to_csv(
        out / "real_rotations.csv", index=False)

    # Aircraft and fuels: as the dummy low-cost network, with a Ryanair 737-800 cabin and turn
    types = pd.read_csv(ROOT / "data" / "dummy_lcc" / "aircraft_types.csv")
    types["seats"] = SEATS
    types["max_load_factor"] = 0.95
    types["turn_min"] = TURN_MIN
    types.to_csv(out / "aircraft_types.csv", index=False)
    pd.read_csv(ROOT / "data" / "dummy_lcc" / "fuels.csv").to_csv(out / "fuels.csv", index=False)
    print(f"wrote {len(legs)} legs, {len(stations)} airports "
          f"({stations.base.sum()} with a night stop) to {out}")


if __name__ == "__main__":
    main()
