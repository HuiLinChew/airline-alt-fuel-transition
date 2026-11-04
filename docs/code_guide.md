# Code guide

What each file does, how they connect, and how the optimiser works.

## How it fits together

```
scripts/make_dummy_data.py  ->  data/dummy/*.csv   (run once)

scenarios/*.yaml  ->  scenario_config
data/dummy/*.csv  ->  data_layer
                        |
        airport_capability     which fuels each airport has, prices, capacity limits
        aircraft_performance   can type k fly leg l; fuel, block and turn times, spill
        cost_revenue           cost of each (type, leg); drop and ownership costs
        network_builder        time-space network per type
        optimiser              which type flies each leg
        rotation_checker       individual aircraft rotations
        analysis, plots        KPIs, comparison with the baseline, sweeps, figures
```

`analysis.run(scenario)` runs the whole chain for one scenario.
`scripts/run_scenarios.py` runs every scenario and saves everything in `outputs/`.

## Files

### Inputs (`data/dummy/`)
| File | Contents |
|---|---|
| `airports.csv` | Station, coordinates, tier, runways, stands, hourly runway capacity (Henry's database) |
| `legs.csv` | The timetable: `leg_id`, origin, destination, `dep_min`, `arr_min` (minutes from the start of the period), distance, passengers, and optionally `fare_usd` |
| `aircraft_types.csv` | Per type: fuel, seats, max load factor, range, turn time, refuel pumps, cost per block hour, cruise speed, price, fuel burn (`fuel_kg_fixed + fuel_kg_per_km × distance`) |
| `fuel_burn.csv` | Optional. A fuel-vs-distance table for any type that shouldn't use the straight line (e.g. Maria's curves) |
| `fuels.csv` | Per fuel: energy content, CO₂ when burnt, default well-to-tank CO₂, share of CO₂ that pays the carbon price, price, which tiers have it by default, refuelling rates. Rows: kerosene, LH₂, fossil LNG (`ch4`), e-methane (`ch4_e`) |

### Model (`src/altfuel/`)
`src/altfuel/` is the model as a Python package, so any script can write
`from altfuel import optimiser`.

| Module | Planning sheet | What it does |
|---|---|---|
| `utils.py` | | Folder paths and a CSV reader that keeps "NA" as text |
| `scenario_config.py` | 0 | Reads a scenario YAML; catches misspelt names |
| `data_layer.py` | 1 | Loads the CSVs; catches input mistakes that would otherwise go unnoticed; applies a scenario's overrides |
| `airport_capability.py` | 2 | Fuel availability and price per airport; runway and stand limits |
| `aircraft_performance.py` | 3 | One row per (type, leg): can it fly it, fuel, energy, CO₂, block time, arrival, turn time, spill |
| `cost_revenue.py` | 5 | Adds costs to those rows; cost of dropping a leg; daily ownership cost per aircraft |
| `network_builder.py` | 6 | Nodes and flight arcs of each type's time-space network |
| `optimiser.py` | 7 | The fleet assignment model |
| `rotation_checker.py` | 8 | Builds aircraft rotations from the assignment and flags problems |
| `analysis.py`, `plots.py` | 9 | Runs the chain, KPIs, comparison with the baseline, sweeps, figures |

Module 4 (fleet stock-flow) isn't built yet: for now the scenario just says how many aircraft of each type are available.

### Scripts and tests
| File | What it does |
|---|---|
| `scripts/make_dummy_data.py` | Builds the dummy airports, legs and aircraft types from Hasan's raw data |
| `scripts/run_scenarios.py` | Runs every scenario and saves results and figures |
| `tests/test_model.py` | `uv run pytest`. Basic behaviour, input checks, and checks that the answers are physically right (shifting the timetable, a repeated week, brute force on a small network) |

## Scenario settings
A scenario YAML only lists what differs from these defaults.

| Setting | Default | Meaning |
|---|---|---|
| `data_dir` | `data/dummy` | Input folder |
| `objective` | `cost` | `cost`, `energy` or `co2` |
| `fleet` | `{KER-NB: 30}` | Aircraft available per type |
| `reference_type` | `KER-NB` | The type the timetable's block and turn times are for |
| `fuel_max_tier` | from `fuels.csv` | A fuel is offered at airports with tier ≤ this |
| `fuel_stations` | | Extra airports offering a fuel, e.g. `{lh2: [DUB]}` |
| `tier_price_factor` | 1.0 / 1.1 / 1.25 by tier for LH₂ and methane (placeholder) | Smaller airports pay more |
| `aircraft_overrides`, `fuel_overrides` | | Change one cell of a CSV, e.g. `{LH2-NB: {range_km: 2000}}` or `{CH4-NB: {fuel: ch4_e}}` |
| `carbon_price` | 0 | USD per tonne of CO₂ burnt |
| `wtt_co2_kg_per_kg` | `fuels.csv` value | Well-to-tank CO₂ per kg of fuel (0 until sourced) |
| `ownership` | 5%, 14 years, 5%, 0.5% | Interest rate, depreciation years, residual value, insurance rate. List only the ones you change |
| `yield_usd_per_pax_km` | 0.148 | Fare, if `legs.csv` has no `fare_usd` |
| `allow_spill` | false | Fly a leg even if some passengers don't fit; they're lost at their fare |
| `allow_drop` | false | Let the model drop legs that cost more than they earn |
| `refuel_on_critical_path` | true | Extra refuelling time adds to the turn |
| `capacity_mode` | `check` | `off`, `check` (report runway and stand use) or `constrain` (enforce the limits) |
| `capacity_share` | 0.15 | Share of each airport's runway movements and stands this airline can use. One number, or `{movements_per_hour: a, stands: b}` |
| `period_min` | 1440 | 1440 for a day, 10080 for a week |
| `solver` | 60 s, gap 0 | `time_limit_s`, `mip_gap`, `msg` |
| `sweep` | | `{parameter: ..., values: [...]}` to re-run across values |

Spill and drops only work with the cost objective. With both off, every passenger
must be carried, so a type with too few seats can't fly that leg.

Total cost = operating cost + ownership + revenue lost to spilled passengers and dropped legs.
If a run has no solution, its KPIs just give the solver status.

## Inside the main modules

### aircraft_performance.perf
It builds a table with a row for every (type in the fleet, leg) pair, then works
out each column for all rows at once:

1. Fuel burn from the type's table if it has one, otherwise the straight line.
   Energy and CO₂ follow from the fuel's energy content and CO₂ factor. CO₂ is
   split into burning (tank-to-wake) and producing the fuel (well-to-tank).
2. Block time. The timetable's block time is taken as right for the reference
   type; other types add `distance × (1/their speed − 1/reference speed)`. Arrival =
   departure + block time, so a slower type lands later.
3. Turn time = base turn + any extra refuelling time compared with the reference
   type, where refuelling time = plug in/out + fuel mass ÷ (pumps × flow per pump).
4. Usable seats = seats × max load factor (rounded down); spilled passengers =
   passengers above that.
5. Whether the type can fly the leg: in range, fuel available at the origin, and
   enough seats (unless spill is allowed).

### network_builder.build_network
For each type and station, the nodes are the times when one of that type's
flights departs or one of its aircraft is ready again (arrival + turn). Each
flight arc records which node it leaves from and which it reaches. Ground arcs
aren't stored: there is one after every node, and the last one wraps round to the
first (overnight). A flight still flying or turning at the end of the period is
marked `crosses` and its ready node goes at (ready time − period).

### optimiser.solve
1. Variables: `x[k, l]` = 1 if type k flies leg l; `y[l]` = 1 if leg l is dropped
   (always 0 unless drops are allowed); `g[k, s, i]` = type-k aircraft waiting at
   station s between node i and the next.
2. If drops aren't allowed, it first checks every leg has at least one type that
   can fly it, and if not, says which legs and why.
3. Cover: for each leg, the x's plus y add up to 1.
4. Balance: at each node, flights arriving + aircraft already waiting = flights
   departing + aircraft left waiting.
5. Count: aircraft in use = those waiting overnight + those still flying or
   turning at the end of the period. This must be ≤ the fleet.
6. Objective: sum of c × x + drop cost × y + ownership × aircraft used (cost runs
   only) + a tiny cost per aircraft so it never keeps spare ones.
7. Capacity (unless off): runway movements per station per clock hour, and aircraft
   at each station at each arrival time (waiting or still turning). In `constrain`
   mode these must be ≤ the limits; in `check` mode they're just reported.
8. Solve with HiGHS and read off each leg's type, the aircraft used and the capacity use.

A type that can't fly a leg never gets an x for it, so range, fuel and seats
don't need their own constraints.

### rotation_checker.build_rotations
For each type, it goes through the legs in departure order and gives each one the
aircraft at the origin that has been ready longest, or a new aircraft if none is
ready. It flags it if this needs more aircraft than the optimiser counted, or if
aircraft end the day somewhere other than where the next day's flights start.
