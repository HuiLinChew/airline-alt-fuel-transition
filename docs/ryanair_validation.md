# Ryanair validation: method, fixes, assumptions, caveats

Question: given only Ryanair's real flights, does the model need the same number of aircraft
and fly them the same way as Ryanair did? Scripts: `scripts/make_ryanair_data.py`,
`scripts/compare_ryanair.py`; scenarios `scenarios/ryanair/ryanair_{1,4,7}d.yaml`.

## Data
- EUROCONTROL Aviation Data Repository for Research (ADRR), "Flights" file for September
  2025: every scheduled (S) and non-scheduled (N) commercial flight in the EUROCONTROL area,
  969k flights that month. Source: EUROCONTROL. Research use only and may not be shared, so
  `data/ryanair_*/` is not committed. ADRR covers March, June, September and December, two
  years behind.
- Columns used: departure and arrival airport (ICAO), actual off-block time, actual arrival
  time (= landing, per the ADRR metadata), aircraft type, operator, registration.
- Ryanair group: operator RYR (Ryanair, Malta Air, Lauda and Buzz all fly under it) and RYS
  (Buzz charters). 105k flights, 616 aircraft, about 3,500 flights a day. Types: 737-800
  70k, 737-8200 30k, A320 (Lauda) 4.4k.
- Airport positions: OurAirports (all 244 Ryanair airports are in it).

## Cleaning, in order
| Problem | Fix | Evidence |
|---|---|---|
| A few flights by Ryanair aircraft filed under an unknown operator (ZZZ) | Keep every flight by a Ryanair registration | 200 flights a month |
| Arrival time is landing, not gate | On-block = landing + 5 min | EUROCONTROL's mean taxi-in is 5.3 min |
| Lands at A, next leaves from B | A positioning flight is missing: one A→B flight added in the middle of the gap, block time from a fit to real flights (min = 0.074 × km + 31) | 0.7% of consecutive flight pairs. The A→B flight isn't in the file under any operator: ADRR keeps only S and N flights, so empty positioning flights are left out. A few may be tail swaps (flight plan carries the planned aircraft); the added flight covers those too |
| Same aircraft, same off-block time twice | Duplicate dropped | |

Compared with OpenSky, airports and gate times are given, so the airport guessing,
neighbouring-airfield fixes and climb/taxi estimates are not needed.

## Which aircraft are used
- Day starts 01:00 UTC (fewest Ryanair departures: about 2 a day between 01:00 and 02:00 UTC).
- An aircraft is kept if every flight in the stretch is known or added, an added flight fits
  with a full turn either side, and every turn is at least 20 min.
- Why 20 min, not Ryanair's published 25: real gate turns depend on the 5-min taxi-in
  estimate (shorter at small airports), and Ryanair turns faster when running late. At 25 min,
  4% of turns are "too short" and most aircraft over a week have one (see sensitivity).
- Run as a one-off stretch (`repeat: false`): aircraft start and end where they really did;
  every night in between at a night stop (airports where kept aircraft really spent a night,
  `overnight_at_bases`).

## Assumptions
- One type: 737-800, 189 seats, 20-min turn, max load factor 95%.
- Passengers 189 × 94% (Ryanair's reported load factor) on every flight.
- Kerosene only; fuel burn, costs and range from the dummy narrowbody (A320-like).
- Capacity limits off (no runway or stand data for these airports).

## Results (from Wed 17 Sep 2025, 20-min turns)
| Stretch | Aircraft flying | Kept | Flights (added) | Ryanair / model aircraft | Same next flight, one aircraft waiting | Several waiting |
|---|---|---|---|---|---|---|
| **1 day** | 592 | **559 (94%)** | 3,281 (4) | **559 / 555** | 100% (454 turns) | 49% |
| 4 days | 598 | 513 (86%) | 12,013 (45) | 513 / 510 | 100% (1,895) | 41% |
| 7 days | 599 | 431 (72%) | 17,447 (84) | 431 / 428 | 100% (3,186) | 41% |

Other single days: 3 Sep 572/570, 10 Sep 556/554, Sat 20 Sep 574/571, 24 Sep 559/557
(93–97% of aircraft kept). The model solves each in a few seconds.

Why aircraft are dropped:
| Stretch | Short turn | Missing flight doesn't fit | Times overlap |
|---|---|---|---|
| 1 day | 32 | 1 | 0 |
| 4 days | 76 | 4 | 5 |
| 7 days | 153 | 6 | 9 |

Sensitivity, 25-min turns: 1 day 473 kept (80%), 473 / 472; 4 days 300 (50%), 300 / 299;
7 days 177 (30%), 177 / 175. Same match, much smaller samples.

## How to read it
- Ryanair's real rotations are one valid answer, so the model can never need more aircraft.
  Needing under 1% fewer says the model reproduces how tightly Ryanair uses its aircraft; the
  extra 2–4 are probably slack for crew or maintenance, which the model doesn't include.
- Routes are an input (the real timetable), so they match by construction. What is tested is
  which flights each aircraft strings together. Where only one aircraft was on the ground,
  the answer is forced and the model matches 100%. Where several were waiting, any could take
  the next flight equally well (one aircraft type), so those can't be compared tail by tail.
- It holds over a whole week, so overnight positioning between days works too.

## Caveats
- Covers 72–94% of Ryanair's aircraft, not all: mostly aircraft with a turn under 20 min.
- Gate arrival times assume 5 min taxiing in everywhere.
- Added positioning flights are guesses (route certain, times not); under 0.5% of flights.
- Passengers assumed; single aircraft type in the model, though the data has three
  (enables the aircraft-type test next).

## Earlier version: OpenSky (September 2022)
The first version (commit `6d2b6fe`, since removed) used the OpenSky flight list (Zenodo
record 7923702, 2019–2022). It is tracked by volunteers' receivers, so airports and gate times had to be estimated: missing
airports from where the aircraft was first or last seen, neighbouring airfields merged,
"lands at A, next takes off from B < 100 km away" read as landing at B (take-off position
agrees 99%), gate times from tracked times plus climb and taxi. 14 Sep 2022, 25-min turns:
406 of ~500 aircraft kept (81%), 406 / 402; 4 days 231 / 231. Replaced by EUROCONTROL because
it covers more aircraft with far less cleaning, and has registrations and aircraft types.
