# Ryanair validation: method, fixes, assumptions, caveats

Question: given only Ryanair's real flights, does the model need the same number of aircraft
and fly them the same way as Ryanair did? Scripts: `scripts/make_ryanair_data.py`,
`scripts/compare_ryanair.py`; scenario `scenarios/ryanair/ryanair_baseline.yaml`.

## Data
- OpenSky flight list (Zenodo record 7923702), September 2022; one file per month, 2019–2022
  only (made for COVID-19 tracking, stopped at the end of 2022). Non-commercial licence, so
  `data/ryanair/` is not committed.
- Ryanair group callsigns: RYR (Ryanair), RUK (Ryanair UK), MAY (Malta Air), LDM (Lauda),
  RYS (Buzz). About 500 aircraft and 2,900 flights a day.
- Airport positions: OurAirports (GitHub copy).
- Newer data: OpenSky Trino access granted (same source, more receivers by 2025);
  EUROCONTROL research data (every filed flight, real gate times) applied for.

## Cleaning, in order
| Problem | Fix | Evidence |
|---|---|---|
| 10 codes not in OurAirports (491 flights a month) | Coordinates added (`EXTRA_AIRPORTS`); LEDS is Castellón's new code (was LECH) | Web lookups: small or closed fields next to Ryanair airports (EPBD Bydgoszcz Aeroklub, EVEA Jelgava, LBWV Izgrev, LD57 Sepurine, ...) |
| Airport missing | Nearest Ryanair airport (≤ 100 km) to where the aircraft was first or last seen | |
| Same airport under two codes | Airfields < 20 km apart merged into the one Ryanair uses most | Closest real pair of Ryanair airports is further apart (e.g. CIA–FCO ~25 km) |
| Airport still missing | From the aircraft's previous or next flight | |
| Not seen landing or taking off | Ryanair airport nearest both where it vanished and where it reappeared (≤ 400 km summed) | Right 94% of the time on 3,879 turns where the airport is known |
| Lands at A, next takes off from B < 100 km away | It landed at B | OpenSky names the arrival from the last point seen, often over a neighbouring field on approach; take-off position agrees with B 99% of the time (945 cases), landing position only 18% |
| Lands at A, next takes off from B further away | Missing flight added in the middle of the gap, block time from a fit to tracked flights (minutes = a × km + b) | Only 1–3 a day |
| Tracking times aren't gate times | Off-block = first seen − climb (height ÷ 600 m/min) − 10 min taxi; on-block = last seen + descent + 5 min taxi | Median ground time then 46 min; 2% under 26 min |
| Delivery flights (e.g. Seattle → Dublin) | Aircraft with a flight > 4,500 km left out | |

## Which aircraft are used
- Day starts 03:00 UTC (no Ryanair departures 01:00–03:00 UTC).
- An aircraft is kept if every flight in the stretch is known and joined up, and every turn
  is ≥ 25 min.
- Run as a one-off stretch (`repeat: false`): aircraft start and end where they really did;
  every night in between at a night stop (airports where kept aircraft really spent a night,
  `overnight_at_bases`). An earlier version made the day repeat, which needed every airport to
  balance overnight and kept only 344 aircraft (69%).

## Assumptions
- One type: 737-800, 189 seats, 25-min turn (Ryanair's published turn), max load factor 95%.
- Passengers 189 × 94% (Ryanair's reported load factor) on every flight.
- Kerosene only; fuel burn, costs and range from the dummy narrowbody (A320-like).
- Capacity limits off (no runway or stand data for these airports).

## Results (14 Sep 2022 unless stated)
| Version | Aircraft kept | Flights | Ryanair / model aircraft | Same next flight, one aircraft waiting | Several waiting |
|---|---|---|---|---|---|
| 1 day, repeating, balanced (old) | 344 (69%) | 1,985 | 344 / 341 | 100% | ~50% |
| **1 day, one-off (main)** | **406 (81%)** | **2,355** | **406 / 402** | **100%** | 48% |
| 4 days (14–17 Sep), one-off | 231 (46%) | 5,166 | 231 / 231 | 100% | 44% |
| 1 day, one-off, 20-min turns | 433 (87%) | 2,531 | 433 / 426 | 100% | |

Repeating-day version on 7, 21, 28 Sep: 335/334, 353/349, 330/326; forced turns 100% each day.

## How to read it
- Ryanair's real rotations are one valid answer, so the model can never need more aircraft.
  Matching within 1% says the model reproduces how tightly Ryanair uses its aircraft; the
  extra 1–4 are probably slack for crew or maintenance, which the model doesn't include.
- Routes are an input (the real timetable), so they match by construction. What is tested is
  which flights each aircraft strings together. Where only one aircraft was on the ground,
  the answer is forced and the model matches 100%. Where several were waiting, any could take
  the next flight equally well (one aircraft type), so those can't be compared tail by tail.
- Four days: fewer aircraft (one bad day removes the aircraft) but an exact match.

## Caveats
- Covers 81% of Ryanair's aircraft, not all; the rest have an airport that can't be
  identified, times that don't fit, or a delivery flight.
- About 6% of airports guessed from positions could be wrong.
- Gate times are estimates (± a few minutes).
- 2022 data; passengers assumed; single aircraft type.
- 20-min turns would keep more aircraft but credit Ryanair with turns it doesn't schedule.
