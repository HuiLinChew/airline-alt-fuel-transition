"""Build a few real days of Ryanair flying from an OpenSky flight list.

    uv run scripts/make_ryanair_data.py path/to/flightlist_20220901_20220930.csv.gz 2022-09-14 4

(file, first day, number of days). The flight lists are free to download (one file per
month, 2019-2022): https://zenodo.org/records/7923702 (non-commercial licence, so
data/ryanair_*/ is not committed). Airport positions come from OurAirports (downloaded here).

Writes to data/ryanair_<days>d/ (e.g. data/ryanair_1d/):
  flights_clean.csv                                        every Ryanair flight that month, cleaned
  airports.csv, legs.csv, aircraft_types.csv, fuels.csv   inputs for the model (the chosen days)
  real_rotations.csv                                       what each real aircraft flew

Cleaning (load_flights):
1. Keep Ryanair group flights (callsigns RYR Ryanair, RUK Ryanair UK, MAY Malta Air,
   LDM Lauda, RYS Buzz).
2. Missing airports: the nearest Ryanair airport to where the aircraft was first or last
   seen (within 100 km); else the airport its previous or next flight used; else, if it
   wasn't seen landing or taking off, the Ryanair airport nearest both where it vanished
   and where it reappeared (right 94% of the time on turns where we know the airport).
3. Airfields under 20 km apart are one airport (OpenSky sometimes names a neighbouring
   field); we use the name Ryanair flights use most.
4. If an aircraft lands at A and its next flight leaves from B under 100 km away, it
   landed at B: OpenSky names the arrival airport from where the aircraft was last seen,
   which is often over a neighbouring airfield on the way down. Where it was seen taking
   off agrees with B 99% of the time.
5. Gate times: OpenSky gives when the aircraft was first and last seen, so we add the
   time to climb to or descend from that height (about 600 m a minute) and taxiing
   (10 min out, 5 min in).

Then the chosen days (one_off_days), from 03:00 UTC, when Ryanair aircraft are all on
the ground. Where an aircraft lands at A and next leaves from B further away, tracking
missed a flight and we add one in the gap. Aircraft are kept if their whole stretch is
known. The days don't repeat (scenario setting repeat: false), so aircraft can start and
end anywhere; bases are the airports where the kept aircraft spend a night.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
AIRPORTS_URL = "https://raw.githubusercontent.com/davidmegginson/ourairports-data/main/airports.csv"

CALLSIGNS = ("RYR", "RUK", "MAY", "LDM", "RYS")
DAY_START_UTC = 3         # hours
TAXI_OUT, TAXI_IN = 10, 5 # minutes
CLIMB_M_PER_MIN = 600     # about 2,000 ft a minute, for climb and descent alike
SEATS = 189               # Boeing 737-800 in Ryanair's layout
LOAD_FACTOR = 0.94        # Ryanair's reported load factor (FY23-FY27 results: 93-94%)
TURN_MIN = 25             # Ryanair's published turn time

# Codes in the flight list that OurAirports files under another code. Castellón's
# code changed from LECH to LEDS; the rest are small or closed airfields next to a
# Ryanair airport (OurAirports' records for them, or airfield.directory / fshub).
RENAMED = {"LEDS": "LECH"}
EXTRA_AIRPORTS = {          # code: (name, latitude, longitude)
    "EVEA": ("Jelgava", 56.6728, 23.6792),
    "EPBD": ("Bydgoszcz Aeroklub", 53.1052, 17.9604),
    "LBWV": ("Izgrev", 43.2772, 27.7019),
    "EPLE": ("Legnica", 51.1828, 16.1782),
    "LD57": ("Sepurine", 44.2100, 15.1632),
    "EGQB": ("Ballykelly", 55.0603, -7.0203),
    "LAGJ": ("Gjirokastër", 40.0873, 20.1523),
    "EGCN": ("Doncaster Sheffield", 53.4753, -1.0043),
    "EPSO": ("Sochaczew", 52.1986, 20.2928),
    "EGVT": ("Wethersfield", 51.9719, 0.5094),
}


def km_between(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371 * np.arcsin(np.sqrt(a))


def load_airports():
    airports = pd.read_csv(AIRPORTS_URL, usecols=["ident", "type", "name", "latitude_deg",
                                                  "longitude_deg", "iata_code"]).set_index("ident")
    extra = pd.DataFrame.from_dict(EXTRA_AIRPORTS, orient="index",
                                   columns=["name", "latitude_deg", "longitude_deg"])
    return pd.concat([airports, extra.assign(type="small_airport")])


def load_flights(path, airports):
    flights = pd.read_csv(path, low_memory=False, parse_dates=["firstseen", "lastseen"])
    flights = flights[flights.callsign.str.startswith(CALLSIGNS, na=False)].copy()
    for end in ["origin", "destination"]:
        flights[end] = flights[end].replace(RENAMED)
        flights.loc[~flights[end].isin(airports.index), end] = None
    lat, lon = airports.latitude_deg, airports.longitude_deg

    # Nearest Ryanair airport to where the aircraft was first or last seen
    used = airports.loc[airports.index.isin(set(flights.origin) | set(flights.destination))]
    for end, la, lo in [("origin", "latitude_1", "longitude_1"),
                        ("destination", "latitude_2", "longitude_2")]:
        for i in flights.index[flights[end].isna() & flights[la].notna()]:
            km = km_between(flights.at[i, la], flights.at[i, lo], used.latitude_deg, used.longitude_deg)
            if km.min() < 100:
                flights.at[i, end] = km.idxmin()

    # Airfields under 20 km apart are one airport: the name Ryanair flights use most
    uses = pd.concat([flights.origin, flights.destination]).value_counts()
    used = airports.loc[uses.index]
    same = {}
    for code, airport in used.iterrows():
        km = km_between(airport.latitude_deg, airport.longitude_deg, used.latitude_deg, used.longitude_deg)
        same[code] = uses[km < 20].idxmax()
    flights["origin"] = flights.origin.map(same)
    flights["destination"] = flights.destination.map(same)

    # The airport the previous or next flight used
    flights = flights.sort_values(["icao24", "firstseen"])
    by_aircraft = flights.groupby("icao24")
    flights["origin"] = flights.origin.fillna(by_aircraft.destination.shift(1))
    flights["destination"] = flights.destination.fillna(by_aircraft.origin.shift(-1))

    # Not seen landing or taking off: the Ryanair airport closest to both where the
    # aircraft vanished and where it reappeared on its next flight
    after = pd.Series(flights.index, index=flights.index).groupby(flights.icao24).shift(-1)
    turns = flights.destination.isna() & after.notna()
    turns &= flights.origin.reindex(after).isna().to_numpy()
    ryanair = airports.loc[sorted(set(same.values()))]
    for i in flights.index[turns]:
        j = after[i]
        km = (km_between(flights.latitude_2[i], flights.longitude_2[i], ryanair.latitude_deg, ryanair.longitude_deg)
              + km_between(flights.latitude_1[j], flights.longitude_1[j], ryanair.latitude_deg, ryanair.longitude_deg))
        if km.min() < 400:
            flights.loc[[i], "destination"] = flights.loc[[j], "origin"] = km.idxmin()

    # Lands at A, next leaves from B under 100 km away: it landed at B
    next_origin = flights.groupby("icao24").origin.shift(-1)
    known = flights.destination.notna() & next_origin.notna()
    km = pd.Series(np.inf, index=flights.index)
    km[known] = km_between(lat[flights.destination[known]].to_numpy(), lon[flights.destination[known]].to_numpy(),
                           lat[next_origin[known]].to_numpy(), lon[next_origin[known]].to_numpy())
    flights.loc[km < 100, "destination"] = next_origin

    # Gate times
    climb = flights.altitude_1.fillna(0).clip(lower=0) / CLIMB_M_PER_MIN
    descent = flights.altitude_2.fillna(0).clip(lower=0) / CLIMB_M_PER_MIN
    flights["off_block"] = flights.firstseen - pd.to_timedelta(climb + TAXI_OUT, unit="min")
    flights["on_block"] = flights.lastseen + pd.to_timedelta(descent + TAXI_IN, unit="min")
    flights = flights[flights.origin != flights.destination]
    return flights[["icao24", "callsign", "typecode", "origin", "destination", "off_block", "on_block"]]


def one_off_days(flights, airports, date, days):
    """Each aircraft's flights over the chosen days, joined up. Where it lands at A and
    next leaves from B, tracking missed a flight: we add an A to B flight with the usual
    block time for that distance, in the middle of the gap. Aircraft are dropped if an
    airport is unknown, an added flight doesn't fit with 25-min turns either side, a
    tracked turn is under 25 min, or it flies a delivery flight (over 4,500 km)."""
    start = pd.Timestamp(date, tz="UTC") + pd.Timedelta(hours=DAY_START_UTC)
    window = flights[(flights.off_block >= start) & (flights.off_block < start + pd.Timedelta(days=days))].copy()
    window["dep_min"] = (window.off_block - start).dt.total_seconds() / 60
    window["arr_min"] = (window.on_block - start).dt.total_seconds() / 60
    lat, lon = airports.latitude_deg, airports.longitude_deg

    def km(a, b):
        return km_between(np.asarray(lat[a]), np.asarray(lon[a]), np.asarray(lat[b]), np.asarray(lon[b]))

    # Usual block time for a distance, from the tracked flights: minutes = a * km + b
    known = window.dropna(subset=["origin", "destination"])
    a, b = np.polyfit(km(known.origin, known.destination), known.arr_min - known.dep_min, 1)

    rows = []
    for tail, f in window.groupby("icao24"):
        if f.origin.isna().any() or f.destination.isna().any():
            continue
        if (km(f.origin, f.destination) > 4500).any():    # a delivery flight, e.g. from Seattle
            continue
        flights_in_order = f.to_dict("records")
        joined = [flights_in_order[0]]
        for nxt in flights_in_order[1:]:
            prev = joined[-1]
            if prev["destination"] != nxt["origin"]:
                block = a * km(prev["destination"], nxt["origin"]) + b
                spare = nxt["dep_min"] - prev["arr_min"] - 2 * TURN_MIN - block
                dep = prev["arr_min"] + TURN_MIN + spare / 2
                joined.append({"icao24": tail, "callsign": "added", "origin": prev["destination"],
                               "destination": nxt["origin"], "dep_min": dep, "arr_min": dep + block})
            joined.append(nxt)
        ground = [n["dep_min"] - p["arr_min"] for p, n in zip(joined, joined[1:])]
        if min(ground, default=TURN_MIN) >= TURN_MIN:
            rows += joined
    kept = pd.DataFrame(rows)
    kept["dep_min"] = kept.dep_min.round().astype(int)
    kept["arr_min"] = kept.arr_min.round().astype(int)
    print(f"{date}, {days} days: {window.icao24.nunique()} Ryanair aircraft, {len(window)} flights")
    print(f"  kept {kept.icao24.nunique()} aircraft whose whole stretch is known: {len(kept)} flights, "
          f"{(kept.callsign == 'added').sum()} of them added")
    return kept


def night_stops(kept, days):
    """Airports where a kept aircraft is at 03:00 UTC (the start of each day): on the
    ground there, or flying or turning towards it. Includes the first morning and last night."""
    stops = set()
    for tail, f in kept.sort_values("dep_min").groupby("icao24"):
        stops.add(f.origin.iloc[0])
        stops.add(f.destination.iloc[-1])
        for midnight in range(1440, days * 1440, 1440):
            before = f[f.dep_min < midnight]
            stops.add(before.destination.iloc[-1] if len(before) else f.origin.iloc[0])
    return stops


def main():
    path, date, days = sys.argv[1], sys.argv[2], int(sys.argv[3])
    out = ROOT / "data" / f"ryanair_{days}d"
    airports = load_airports()
    flights = load_flights(path, airports)
    out.mkdir(parents=True, exist_ok=True)
    flights.to_csv(out / "flights_clean.csv", index=False)
    kept = one_off_days(flights, airports, date, days)

    # Airports, named by their IATA code (STN, DUB ...). Tier from OurAirports' size.
    used = airports.loc[sorted(set(kept.origin) | set(kept.destination))]
    code = used.iata_code.fillna(pd.Series(used.index, index=used.index))
    bases = night_stops(kept, days)
    tier = used.type.map({"large_airport": 1, "medium_airport": 2}).fillna(3).astype(int)
    pd.DataFrame({
        "station": code, "name": used.name, "lat": used.latitude_deg.round(4),
        "lon": used.longitude_deg.round(4), "tier": tier,
        "runways": None, "stands": None, "hourly_capacity": None,   # not needed yet (capacity off)
        "base": used.index.isin(bases).astype(int), "curfew_start": None, "curfew_end": None,
    }).sort_values("station").to_csv(out / "airports.csv", index=False)

    # Legs
    kept = kept.sort_values("dep_min")
    kept["leg_id"] = [f"R{i:05d}" for i in range(len(kept))]
    lat, lon = used.latitude_deg, used.longitude_deg
    distance = km_between(kept.origin.map(lat), kept.origin.map(lon),
                          kept.destination.map(lat), kept.destination.map(lon))
    legs = pd.DataFrame({
        "leg_id": kept.leg_id, "origin": kept.origin.map(code), "destination": kept.destination.map(code),
        "dep_min": kept.dep_min, "arr_min": kept.arr_min, "distance_km": distance.round(1),
        "pax": round(SEATS * LOAD_FACTOR), "added": (kept.callsign == "added").astype(int),
    })
    legs.to_csv(out / "legs.csv", index=False)
    kept.sort_values(["icao24", "dep_min"])[["icao24", "leg_id"]].to_csv(
        out / "real_rotations.csv", index=False)

    # Aircraft and fuels: as the dummy low-cost network, with a Ryanair 737-800 cabin and turn
    types = pd.read_csv(ROOT / "data" / "dummy_lcc" / "aircraft_types.csv")
    types["seats"] = SEATS
    types["max_load_factor"] = 0.95
    types["turn_min"] = TURN_MIN
    types.to_csv(out / "aircraft_types.csv", index=False)
    pd.read_csv(ROOT / "data" / "dummy_lcc" / "fuels.csv").to_csv(out / "fuels.csv", index=False)

    print(f"wrote {len(legs)} legs, {len(used)} airports ({len(bases)} with a night stop) to {out}")


if __name__ == "__main__":
    main()
