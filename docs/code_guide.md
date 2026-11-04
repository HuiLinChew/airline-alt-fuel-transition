# Code guide

What every file does, what feeds into what, and how the optimiser works inside.

## How the pieces connect

```
scripts/make_dummy_data.py ──► data/dummy/*.csv          (run once)
scenarios/*.yaml ─────────────► scenario_config ─┐
data/dummy/*.csv ─────────────► data_layer ──────┤
                                                 ▼
          airport_capability   (which fuels where, at what price; runway and stand limits)
                 ▼
          aircraft_performance (can type k fly leg l? fuel, turn time, spill)
                 ▼
          cost_revenue         (c[k,l] incl. spill, drop cost)
                 ▼
          network_builder      (time-space network per type)
                 ▼
          optimiser            (which type flies each leg; capacity use)
                 ▼
          rotation_checker     (tails and rule breaks)
                 ▼
          analysis ──► plots   (KPIs, deltas vs baseline, sweeps, figures)
                 ▲
scripts/run_scenarios.py drives the whole chain and writes outputs/
```

`analysis.run()` is the one function that calls modules 2–8 in order for one scenario.

## Files

### Top level
| File | Purpose |
|---|---|
| `pyproject.toml` | Project name, Python version and dependencies (PuLP, HiGHS, pandas, matplotlib, PyYAML) |
| `uv.lock` | Exact pinned versions of every package, so results reproduce |
| `.python-version` | Python version uv uses (3.12) |
| `README.md` | Overview and quick start |
| `docs/methods.md` | Every modelling choice and parameter with its paper |
| `docs/code_guide.md` | This file |

### Inputs
| File | Contents |
|---|---|
| `data/dummy/airports.csv` | `station`, coordinates, `tier`, runways, stands, hourly capacity (from Henry's database) |
| `data/dummy/legs.csv` | The timed schedule: `leg_id`, origin, destination, `dep_min`, `arr_min` (whole minutes from the start of the period; `arr_min` may pass midnight), distance, pax, optional `fare_usd` |
| `data/dummy/aircraft_types.csv` | Per type: fuel, seats, max load factor, range, base turn, refuel pumps, cost per block hour, cruise speed, purchase price, fuel-burn fit (`fuel_kg_fixed + fuel_kg_per_km × d`), source |
| `data/dummy/fuel_burn.csv` (optional) | Burn-vs-distance table (`type, distance_km, fuel_kg`). A type listed here uses the table (interpolated) instead of the linear fit, e.g. Maria's non-linear curves |
| `data/dummy/fuels.csv` | Per fuel: label, LHV, CO2 per kg burnt, default well-to-tank CO2, `carbon_price_share` (1 = pays the carbon price on CO2 burnt, 0 = zero-rated e-fuel), price, `default_max_tier` (99 = everywhere, 0 = nowhere), refuel flow per pump and plug time, source. Rows: kerosene, LH₂, fossil LNG (`ch4`), e-methane (`ch4_e`). Adding a fuel (e.g. SAF) = one row here plus an aircraft type; switching an aircraft to another fuel = `aircraft_overrides: {TYPE: {fuel: ...}}` |
| `scenarios/*.yaml` | One file per scenario, listing only what differs from the defaults (see settings below) |

### Scripts (things you run)
| File | Purpose |
|---|---|
| `scripts/make_dummy_data.py` | Builds airports, legs and aircraft_types from Hasan's raw CSVs. Legs: frequency per pair = seats needed for the busier direction; outbound spread over 06:30–22:30, return 1 h after landing |
| `scripts/run_scenarios.py` | Runs every scenario, saves assignments, rotations, capacity use, summary table, sweeps and figures to `outputs/` |

### Package `src/altfuel/` (the model)
`src/altfuel/` is the model itself as an installable Python package. `src/` is
the folder convention; `altfuel` is the package name, so code anywhere can write
`from altfuel import optimiser`. It is not a utils folder: it holds all the modules.

| Module | Planning sheet | In → out |
|---|---|---|
| `utils.py` | — | Shared helpers only: folder paths and an NA-safe `read_csv` |
| `scenario_config.py` | 0 Scenario config | YAML → `Scenario` (every setting has a default; a YAML only lists what it changes). `validate` stops on unknown settings, types, fuels, stations or columns |
| `data_layer.py` | 1 Data layer | CSVs → `Data(airports, legs, aircraft_types, fuels, fuel_burn)`; `validate` stops on broken IDs, times, fuels or missing burn data; `apply_overrides` applies the scenario's table changes |
| `airport_capability.py` | 2 Airport capability | airports + scenario → `airport_fuel[station, fuel]`: available, price; `airport_capacity[station]`: movements per hour, stands (× the airline's share) |
| `aircraft_performance.py` | 3 Aircraft performance | legs, aircraft_types, airport_fuel → `perf[type, leg]`: in_range, fuel_at_origin, fits, feasible, pax_cap, spill_pax, fuel_kg, energy, CO2, block_min, turn_min |
| `cost_revenue.py` | 5 Cost/revenue | perf + prices → adds `fuel_cost`, `carbon_cost`, `hourly_cost`, `operating_cost`, `spill_cost`, `cost_usd` and `c`; `fare_per_pax[leg]`, `drop_cost[leg]`, `ownership_per_day[type]` |
| `network_builder.py` | 6 Network builder | perf (feasible rows) → `Network`: node times per (type, station) + flight arcs |
| `optimiser.py` | 7 Optimiser | Network, c, drop cost, fleet A, airport_capacity → `Result`: `assign[leg]`, `fleet_used`, objective, `capacity` (use vs limit) |
| `rotation_checker.py` | 8 Rotation checker | assign + the optimiser's fleet → tail rotations + list of violations |
| `analysis.py` | 9 Analysis | `run(scenario)` runs the chain; `kpis`, `compare` (deltas vs baseline), `sweep(scenario, parameter, values)` for any setting |
| `plots.py` | (part of 9) | network map, tail Gantt, scenario comparison, sweep chart; fuel colours and labels come from `fuels.csv` |

Module 4 (fleet stock-flow) is not built yet; for now `fleet` in the scenario is A[type].

### Scenario settings
| Setting | Default | What it does |
|---|---|---|
| `data_dir` | `data/dummy` | Input folder; point at real data here |
| `objective` | `cost` | `cost`, `energy` or `co2` |
| `fleet` | `{KER-NB: 30}` | A[type]: aircraft available |
| `reference_type` | `KER-NB` | Type whose refuelling the base turn already includes |
| `fuel_max_tier` | from `fuels.csv` | Fuel offered at airports with tier ≤ this |
| `fuel_stations` | — | Extra stations offering a fuel, e.g. `{lh2: [DUB]}` |
| `tier_price_factor` | LH₂, fossil LNG, e-methane: 1.0 / 1.1 / 1.25 by tier (placeholder) | Price multiplier per fuel and tier |
| `aircraft_overrides`, `fuel_overrides` | — | Change any CSV cell, e.g. `{LH2-NB: {range_km: 2000}}` |
| `carbon_price` | 0 | USD per t CO2 burnt (tank-to-wake, as in the EU ETS) |
| `wtt_co2_kg_per_kg` | `fuels.csv` value (0 placeholder; e-methane −2.75) | Well-to-tank CO2 per kg fuel, e.g. `{lh2: 9.0}`. Added to `co2_t` and the `co2` objective, not to the carbon price |
| `yield_usd_per_pax_km` | 0.148 | Fare when `legs.csv` has no `fare_usd` (Proesmans et al. 2023) |
| `ownership` | 5%, 14 yr, 5%, 0.5% | `interest_rate`, `depreciation_years`, `residual_value`, `insurance_rate` for the daily ownership cost; give only the ones you change |
| `allow_spill` | false | Fly a leg even if some passengers don't fit; they are lost at their fare (cost objective only) |
| `allow_drop` | false | Let the optimiser drop loss-making legs (cost objective only) |
| `refuel_on_critical_path` | true | Add extra refuel time to turns |
| `capacity_mode` | `check` | `off`; `check` = report runway/stand use after solving (solution unchanged); `constrain` = enforce the limits |
| `capacity_share` | 0.15 | Share of each airport's movements and stands available to this airline; one number, or `{movements_per_hour: a, stands: b}` (both keys) |
| `period_min` | 1440 | Schedule length: a day, or 10080 for a week |
| `solver` | 60 s, gap 0 | `time_limit_s`, `mip_gap`, `msg` |
| `sweep` | — | `{parameter: ..., values: [...]}`: re-run across values |

### Tests
`tests/test_model.py` (run with `uv run pytest`) checks: every leg flown exactly
once; range, fuel and fleet limits respected; rotations match with no violations;
baseline is all kerosene; explicit fuel stations work; a leg landing after
midnight is counted; scenario typos are caught; a fuel-burn table overrides the
linear fit; overrides change the inputs; small aircraft can't take full legs
without spill; spill is costed at the fare; unservable legs and runway overloads
give clear errors; capacity check mode leaves the solution unchanged; stand use
matches the tail rotations; the stand constraint binds; bad input data raises.

### Passengers: the three cases
| `allow_spill` | `allow_drop` | Behaviour |
|---|---|---|
| false | false | Serve every passenger: a type with too few seats (seats × load factor) has no arc on that leg |
| true | false | Every leg flown; passengers who don't fit are lost at their fare |
| either | true | A leg may also be dropped entirely, losing all its fares |

If a run has no solution (e.g. capacity too tight), its KPIs are just its status: no misleading zeros.

`total_cost_usd` = operating cost + ownership cost + spill cost + revenue lost on dropped legs, so scenarios with spill or drops are compared fairly with ones that fly everything.

## Inside the main modules

### aircraft_performance.perf
Vectorised: a table with one row per (type in the fleet, leg) is built with a cross join,
and each column below is computed for all rows at once (about 300× faster than a row loop
on 3,000 legs). For every row:
1. `fuel_kg`: from the type's `fuel_burn.csv` table if it has one, else `fuel_kg_fixed + fuel_kg_per_km × distance`. Energy and CO2 follow from LHV and the CO2 factor.
2. Seats: `pax_cap = floor(seats × max_load_factor)`, `spill_pax = max(0, pax − pax_cap)`.
   `feasible = in_range and fuel_at_origin and fits`, where `fits` = no spill, or spill allowed.
   The three checks are kept as separate columns so error messages can say why a type can't fly a leg.
   CO2: `co2_ttw_t` (burning) + `co2_wtt_t` (producing the fuel; scenario placeholder, 0) = `co2_t`.
   Block time: the schedule's block is taken as right for the reference type; other types add
   `distance × (1/v_type − 1/v_ref)` for their own cruise speed. `arr_min = dep_min + block`, so a
   slower type arrives later, and the network, capacity and rotations all use that arrival.
3. `turn_min` = base turn, plus (if `refuel_on_critical_path`) the extra refuelling
   time vs the reference type: `refuel_minutes(type, kg) − refuel_minutes(reference, kg_ref)`,
   with `refuel_minutes = plug time + kg ÷ (pumps × flow per pump) ÷ 60` (Al-Timimi).
   A fuel with no refuelling data in `fuels.csv` gets no extra time and a warning.

### network_builder.build_network
For each type, at each station, it collects the event times in whole minutes:
departures of legs that type can fly, and "ready" times (arrival + that type's
turn). A ready time past the end of the period is wrapped to the start and the
flight marked `crosses`. The sorted unique times are the nodes. Each flight arc is stored by its departure node index
at the origin and its ready node index at the destination. Ground arcs are not
stored: at every station there is one ground arc after each node, and the one
after the last node wraps round to the first (overnight).

### optimiser.solve, step by step
1. **Variables.**
   `x[k, l]` = 1 if type k flies leg l (one per feasible flight arc).
   `y[l]` = 1 if leg l is dropped.
   `g[k, s, i]` = number of type-k aircraft on the ground at station s between node i and node i+1 (integer).
0. **Pre-checks.** If drops aren't allowed: every leg must have at least one arc (else an error lists each leg and why each type fails), and, in `constrain` mode, no station-hour can already exceed its runway limit with every leg flown (movements don't depend on type, so this would be infeasible).
2. **Objective.** `Σ c[k,l]·x[k,l] + Σ drop_cost[l]·y[l] + Σ ownership[k]·(aircraft used of k) + ε·(aircraft used)`. Ownership (daily cost × days in the period) is only included with the cost objective. `c` is cost, energy or CO2 depending on the scenario's objective, and already includes spill cost. ε is a tiny tie-break (10⁻⁶ × the largest c): without it nothing penalises extra aircraft, and the solver could report parked spare aircraft.
3. **Cover.** For each leg, the x's of all types that can fly it plus y sum to 1. If `allow_drop` is false, y is forced to 0.
4. **Balance.** For each node i at station s of type k:
   legs arriving at i + aircraft on the ground coming in (g at i−1) = legs departing at i + aircraft on the ground going out (g at i).
   `(i − 1) % n` makes node 0's incoming ground arc the overnight arc from the last node.
5. **Count.** At the end of the period, every aircraft is either on the ground (`g` at the last node of each station, the wrap-around arc) or on a flight still flying or turning (`crosses`, e.g. a leg landing after midnight). That total is the aircraft of type k in use and must be ≤ the scenario's fleet for k.
6. **Capacity** (unless `capacity_mode` is off). The same expressions are built either way; `constrain` adds them as ≤ limit, `check` only evaluates them after solving.
   - Runway: for each station and clock hour, Σ x over arcs departing or arriving then. Each type uses its own arrival time (a slower type may land in a later hour).
   - Stands: for each station, at each arrival time t: aircraft on the ground (the `g` arc covering t; before the first node that is the overnight arc) + aircraft still turning (arrived, not yet ready). Occupancy only rises at arrivals, so these times catch every peak.
7. **Solve** with HiGHS using the scenario's `solver` settings. If the time limit is hit, the best solution found is kept and marked "Feasible (time limit)"; if there is none, an empty result is returned with the solver status.
8. **Read out.** For each leg, the type whose x = 1 (or "dropped"); `fleet_used[k]` = value of the overnight count; capacity table with used, limit, utilisation and `over` per row.

Range, fuel and seats never appear as constraints: an infeasible (type, leg) simply has no x.

### rotation_checker.build_rotations
Per type, legs in departure order. A dictionary `ready[station]` holds (ready time, tail) for aircraft waiting there. For each leg, take the earliest-ready aircraft at the origin that is ready by departure; if none, start a new tail there. Put the aircraft into `ready[destination]` at that type's arrival + turn. Afterwards, flag a violation if more tails are needed than the optimiser counted, or if the stations where tails end do not match where tails start (the day could not repeat).

### analysis.run
Calls, in order: `airport_fuel` → `perf` → `add_costs` → `airport_capacity` → `build_network` → `drop_cost` → `solve` → `build_rotations`, then joins the assignment back to perf so KPIs can be summed: legs flown/dropped, aircraft, passengers demanded/spilled/on dropped legs, energy, CO2, operating/spill/dropped/total cost, fuel shares, capacity breaches and peak runway/stand utilisation.
