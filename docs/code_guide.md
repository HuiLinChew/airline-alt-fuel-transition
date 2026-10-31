# Code guide

What every file does, what feeds into what, and how the optimiser works inside.

## How the pieces connect

```
scripts/make_dummy_data.py ──► data/dummy/*.csv          (run once)
scenarios/*.yaml ─────────────► scenario_config ─┐
data/dummy/*.csv ─────────────► data_layer ──────┤
                                                 ▼
          airport_capability   (which fuels where, at what price)
                 ▼
          aircraft_performance (can type k fly leg l? fuel, turn time)
                 ▼
          cost_revenue         (c[k,l], drop cost)
                 ▼
          network_builder      (time-space network per type)
                 ▼
          optimiser            (which type flies each leg)
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
| `data/dummy/legs.csv` | The timed schedule: `leg_id`, origin, destination, `dep_h`, `arr_h`, distance, pax |
| `data/dummy/aircraft_types.csv` | Per type: fuel, seats, range, base turn, fuel-burn fit (`fuel_kg_fixed + fuel_kg_per_km × d`), source |
| `data/dummy/fuels.csv` | Per fuel: LHV, CO2 per kg burnt, price, source (written by hand) |
| `scenarios/*.yaml` | One file per scenario: fleet, fuel tiers, prices, carbon price, objective |

### Scripts (things you run)
| File | Purpose |
|---|---|
| `scripts/make_dummy_data.py` | Builds airports, legs and aircraft_types from Hasan's raw CSVs. Legs: frequency per pair = seats needed for the busier direction; outbound spread over 06:30–22:30, return 1 h after landing |
| `scripts/run_scenarios.py` | Runs every scenario, saves assignments, rotations, summary table, carbon sweep and figures to `outputs/` |

### Package `src/altfuel/` (the model)
`src/altfuel/` is the model itself as an installable Python package. `src/` is
the folder convention; `altfuel` is the package name, so code anywhere can write
`from altfuel import optimiser`. It is not a utils folder: it holds all the modules.

| Module | Planning sheet | In → out |
|---|---|---|
| `utils.py` | — | Shared helpers only: folder paths, an NA-safe `read_csv`, `hhmm` time format |
| `scenario_config.py` | 0 Scenario config | YAML → `Scenario` (every setting has a default; a YAML only lists what it changes) |
| `data_layer.py` | 1 Data layer | CSVs → `Data(airports, legs, aircraft_types, fuels)`; `validate` stops on broken IDs, times or fuels |
| `airport_capability.py` | 2 Airport capability | airports + scenario → `airport_fuel[station, fuel]`: available, price |
| `aircraft_performance.py` | 3 Aircraft performance | legs, aircraft_types, airport_fuel → `perf[type, leg]`: feasible, fuel_kg, energy, CO2, block_h, turn_h |
| `cost_revenue.py` | 5 Cost/revenue | perf + prices → adds `fuel_cost`, `carbon_cost`, `hourly_cost`, `cost_usd` and `c`; `drop_cost[leg]` |
| `network_builder.py` | 6 Network builder | perf (feasible rows) → `Network`: node times per (type, station) + flight arcs |
| `optimiser.py` | 7 Optimiser | Network, c, drop cost, fleet A → `Result`: `assign[leg]`, `fleet_used`, objective |
| `rotation_checker.py` | 8 Rotation checker | assign → tail rotations + list of violations |
| `analysis.py` | 9 Analysis | runs the chain; `kpis`, `compare` (deltas vs baseline), `carbon_price_sweep` |
| `plots.py` | (part of 9) | network map, tail Gantt, scenario comparison, sweep chart |

Module 4 (fleet stock-flow) is not built yet; for now `fleet` in the scenario is A[type].

### Tests
`tests/test_model.py` checks: every leg flown exactly once; range, fuel tier and
fleet limits respected; rotations cover all flown legs with no violations;
baseline is all kerosene. Run with `uv run pytest`.

## Inside the main modules

### aircraft_performance.perf
For every aircraft type in the scenario's fleet and every leg:
1. `fuel_kg = fuel_kg_fixed + fuel_kg_per_km × distance`; energy and CO2 follow from LHV and the CO2 factor.
2. `feasible` = distance ≤ range **and** the type's fuel is offered at the leg's origin.
3. `turn_h` = base turn, plus for alternative fuels the extra refuelling time:
   `refuel_min(fuel, kg) − refuel_min(kerosene, kg_kerosene)`, where
   `refuel_min = plug-in + plug-out + kg ÷ (pumps × flow) ÷ 60` (Al-Timimi).

### network_builder.build_network
For each type, at each station, it collects the event times: departures of legs
that type can fly, and "ready" times (arrival + that type's turn). The sorted
unique times are the nodes. Each flight arc is stored by its departure node index
at the origin and its ready node index at the destination. Ground arcs are not
stored: at every station there is one ground arc after each node, and the one
after the last node wraps round to the first (overnight).

### optimiser.solve, step by step
1. **Variables.**
   `x[k, l]` = 1 if type k flies leg l (one per feasible flight arc).
   `y[l]` = 1 if leg l is dropped.
   `g[k, s, i]` = number of type-k aircraft on the ground at station s between node i and node i+1 (integer).
2. **Objective.** `Σ c[k,l]·x[k,l] + Σ drop_cost[l]·y[l]`. `c` is cost, energy or CO2 depending on the scenario's objective.
3. **Cover.** For each leg, the x's of all types that can fly it plus y sum to 1. If `allow_drop` is false, y is forced to 0.
4. **Balance.** For each node i at station s of type k:
   legs arriving at i + aircraft on the ground coming in (g at i−1) = legs departing at i + aircraft on the ground going out (g at i).
   `(i − 1) % n` makes node 0's incoming ground arc the overnight arc from the last node.
5. **Count.** The overnight arcs (`g` at the last node of each station) count the aircraft of type k in use. That total must be ≤ the scenario's fleet for k. No legs fly across midnight, so nothing else crosses the count line.
6. **Solve** with HiGHS. If not optimal, an empty result is returned with the status.
7. **Read out.** For each leg, the type whose x = 1 (or "dropped"); `fleet_used[k]` = value of the overnight count.

Range and fuel never appear as constraints: an infeasible (type, leg) simply has no x.

### rotation_checker.build_rotations
Per type, legs in departure order. A dictionary `ready[station]` holds (ready time, tail) for aircraft waiting there. For each leg, take the earliest-ready aircraft at the origin that is ready by departure; if none, start a new tail there. Put the aircraft into `ready[destination]` at arrival + turn. Afterwards, flag a violation if more tails are needed than the fleet has, or if the stations where tails end do not match where tails start (the day could not repeat).

### analysis.run
Calls, in order: `airport_fuel` → `perf` → `add_costs` → `drop_cost` → `build_network` → `solve` → `build_rotations`, then joins the assignment back to perf so KPIs (legs, aircraft, energy, CO2, costs, fuel shares) can be summed.
