# Future work

Ideas and to-dos not built yet, roughly in priority order. Sources for anything already
built are in `methods.md`.

## Model

| Item | What | Notes |
|---|---|---|
| Tankering + boil-off (chosen: fuel bands) | Time-space-fuel network (Randeraad et al.): each node also has a fuel state = range left on board, in bands (e.g. 0, 500, 1,000 … km; band size a scenario setting). A flight moves the aircraft from band s to s − its distance, rounded down to be safe; at an airport with the fuel it can refuel to any band up to full; at one without it can only use what's on board | Replaces "fuel at origin" (refuel before every departure). Checks distance exactly (to band size) for any chain of legs, so multi-leg tankering comes for free. Cost: extra fuel burnt to carry fuel (rule of thumb for kerosene ~2.5–4% of carried fuel per flight hour; LH₂ value to source, maybe Maria's data). Boil-off default: no fuel held overnight (wrap-round ground arcs only in the empty band), so LH₂ aircraft end the day at LH₂ airports; optimistic case (held overnight) as a setting. In-day `max_hold_min` unlimited until sourced. Size: × number of bands (LH₂ 2,778 km at 500 km ≈ 6), roughly 10–30 s at 2,000 legs. Mostly a network_builder change; the optimiser gets one balance constraint per band. Rejected: a 2-state "fuel for one more leg" version, which can't tell a short next leg from a long one |
| Fleet stock-flow (module 4) | Fleet changes year by year (retirements, deliveries) instead of a fixed fleet per scenario | Rau, Dray, Sirtori, Oesingmann. Ownership would then be charged on the whole owned fleet |
| Maintenance base | Source the kerosene maintenance cost per block hour (now a 2,060 $/h placeholder) and the methane difference | Split from crew is done (crew 940 $/h); maintenance is the same for all types for now. To apply: LH₂ +11% (Hoelzen et al. 2022) via `LH2_MAINT_FACTOR`, which moves LH₂'s entry from 200 to 250 $/t. A320-class engineering cost studies should give the base |
| Spill recapture | Spilled passengers rebook onto other flights | Currently all lost, which overstates spill cost |
| Maintenance routing | Rule that every aircraft returns to a maintenance base every ≤ N days; choose rotations to keep cycles short | Cycles are now reported (`day_cycles`) but come from a greedy matching. Becomes important with tankering: an LH₂ aircraft parked overnight at a non-LH₂ airport has the boil-off problem |
| Schedule design (discuss with Maria) | Let the model choose which flights to operate, not just which type flies each: give it candidate flights (out-and-backs and chains) and require each airport pair's daily passengers to be carried by some of them | Lohatepanont & Barnhart 2004 (integrated schedule design and fleet assignment). Then LH₂ airport limits and turn times reshape the network itself, e.g. picking chains only where they beat back-and-forth. Bigger model: demand becomes a constraint and there are many more candidate flights |
| Airport capacity share | Replace the flat 15% with a per-airport share: limit = airline's current share at that airport × the airport's capacity in that year | Shares are sticky because of EU slot grandfather rights (80/20 use-it-or-lose-it), so when a hub fills up everyone's growth stops, not just ours. Current share from OpenSky (airline movements ÷ all movements) or slot coordinator data (e.g. ACL); capacity from Henry's data plus planned expansions. Demand above the limit → spill, drops or Hasan's absorption factor. Rejected: residual capacity (capacity − other airlines' traffic), which squeezes our airline to zero at hubs as demand grows. Gaps in share data: simple regression on base/hub status, airport size, distance from base; sensitivity sweep on the share. `capacity_share` already accepts a dict, so this is a small change in `airport_capacity` |
| Absorption factor | Overflow at a capacity-limited airport rerouted (Hasan) | Capacity is currently check or hard limit only |
| Weekly schedules | Use `period_min: 10080` with real weekly timetables | Already supported and tested |

## From the 5 Nov 2026 meeting

### Schedule optimisation (not just assignment)

Idea: the airline gives a target departure time (e.g. 09:00) and daily passengers; the model
builds the day. Arrival = departure + block time of the type chosen, then + turn time before the
next departure. The kerosene run gives the reference arrival times.

What has to be fixed for this to be solvable, from smallest to biggest change:

| Step | Fixed (inputs) | Model chooses | Change to code |
|---|---|---|---|
| 0. Now | Each leg's departure time; passengers per leg | Type per leg (arrival follows from its speed) | None |
| 1. Time windows (**built**, delays only) | Target departure + up to `max_delay_min` later, in `delay_step_min` steps; passengers per leg | Type **and** exact departure per leg | Done: `delay_copies` + cover per original leg. Rexing et al. 2000. Delays are free, but a second solve keeps only the delays that improve the objective; a cost per minute of delay (passengers prefer their booked time) is still to source |
| 2. Frequencies | Passengers per **airport pair per day**; candidate departure times (e.g. hourly 06:00–22:00) | How many flights per pair, at which times, which type | Demand constraint: seats flown ≥ daily passengers per pair. Lohatepanont & Barnhart 2004 |
| 3. Routings | Passengers per origin–destination; candidate routes (direct, or via a stop) | Direct long-haul or two medium-hauls via a stop | Passenger flow variables per route. Needed for "long-haul infeasible → fly 2 medium-hauls" |

Aircraft inputs needed at every step: seats, max load factor, cruise speed (block time),
turn time, range, price.

Objectives (all are weightings of terms already in the optimiser):

| Objective | How |
|---|---|
| Fewest aircraft | Minimise Σ n[k] (aircraft per type) |
| Lowest capital cost | Minimise Σ price[k] × n[k] |
| Lowest cost for the same passengers | Current cost objective, with the demand constraint of step 2 |

### Year-on-year fleet stock model

Start: the existing kerosene network (aircraft, passengers, legs). Each year, perturb it and
re-solve, with last year's fleet as this year's starting fleet (+ deliveries − retirements).

| Perturbation | How it enters |
|---|---|
| X% demand growth on every leg | Scale `pax` |
| X% growth only in some areas (by distance band or airport type) | Scale `pax` for the matching legs |
| Y% of fleet replaced by new-fuel aircraft, with X% growth | Fleet limits per type |
| New legs, serving the same passengers | Needs step 2 above (demand per pair) |
| Long-haul infeasible / too expensive → 2 medium-hauls | Needs step 3 above |

Objectives: minimise cost or minimise CO₂. Time step: 1 year, or 5-year steps.

### To do

- Research future aviation demand (growth rates per year, by region and distance).
- Try a multi-day cycle aircraft (chains data already gives aircraft that end the day away from base).
- Aircraft performance: ask Maria (she is most confident on medium haul).

### Low-cost carrier realism (built 6 Nov)

Built: bases (`base` in airports.csv, `overnight_at_bases`), night curfews
(`curfew_start`/`curfew_end`), and the
`data/dummy_lcc/` timetable (lines start and end at a base, any base). Still to do:
- source real curfew hours (LHR and AMS values are rough placeholders);
- night stops as an option at a cost per night (hotel + crew allowance) instead of all or nothing;
- a cost per minute of delay: in the LCC runs LH₂ needs many small delays (38 legs at ≤ 30 min);
- daily check at base every ≤ N days for multi-day cycles (maintenance routing);
- summer and winter timetables as separate scenarios, once real data is in.

### Hub-and-wave timetable (hub carriers)

Hub carriers (Emirates, BA, KLM) group arrivals and departures at the hub into waves
("banks") so passengers can connect; spoke flights go out and back from the hub. The
5-airport dummy network can't show this: every pair is flown direct (point-to-point),
so there is no hub. Needs:
- a network with a hub and spoke airports that only connect through it (real data, or a
  dummy with e.g. 1 hub + 8-10 spokes);
- waves: e.g. 3-6 a day, arrivals in a window before departures, set by the hub's
  minimum connection time;
- passengers per origin-destination with a connection at the hub (step 3 above), since
  a wave only matters if passengers connect;
- an LH₂ question this would answer: does LH₂'s longer turn break the wave (aircraft
  miss the outbound bank) and how much wave length it needs.
Ask Anil: wave length and number at Dubai, minimum connection time.

### Questions for Anil (Emirates)

- Hubs: where do airlines base aircraft, and how often must an aircraft return to base?
- Waves at the hub: how many a day, how long, minimum connection time?
- Safety checks: what checks, how often, where can they be done?
- Operations: anything else that constrains rotations.

### Presentation (end of Michaelmas)

10 minutes; very clear slides with few words; about one plot per slide with one bullet underneath;
consider putting the map below the network.

## Data to source

| Item | Why it matters |
|---|---|
| LNG aircraft price premium | Now +9% (Raab et al. ratio); a direct source for LNG narrowbodies would be better |
| LNG connection time (plug-in/out, purge) | Now 9 min, as LH₂ (6 min low case); no LNG-specific data. Decides LNG on tight timetables |
| Passenger safety zone during cryogenic refuelling | Al-Timimi: boarding and LH₂ refuelling can't overlap, narrowbody turn 37 → 48 min. Not modelled; would apply to LH₂ and maybe LNG. Add as a setting |
| Methane slip | Unburnt CH₄ (strong greenhouse gas) not modelled; overstates LNG's CO₂ saving |
| Well-to-tank CO₂ per fuel and production route | Placeholder 0 (e-methane −2.75) |
| Maria's fuel-burn curves | Drop into `fuel_burn.csv`; replaces the straight-line fit |
| Airport tier mapping (1–6) and tier price factors | Placeholders |
| Airline share of each airport's capacity | Placeholder 15%; method in the Model table above (current share × future capacity) |
| Real timetable (OpenSky / ADS-B) | Replaces the dummy 40 legs |
| Inputs on one year basis | Demand 2015, prices 2027/2050, aircraft price 2021 |

## What Maria's aircraft data will replace

Maria can provide non-linear aircraft characteristics for all fuels. Exactly which
quantities is still to confirm with her; the likely replacements in `aircraft_types.csv`:

| Now | Current source | Replaced by | How it goes in |
|---|---|---|---|
| `fuel_kg_fixed`, `fuel_kg_per_km` (straight-line fuel burn) | Fit to Henry's short-haul curves via Hasan | Her fuel-vs-distance curves | Rows in `fuel_burn.csv`; the code then interpolates them instead of using the line. No code change |
| Methane fuel burn = kerosene × 1.10 energy | Rompokos et al. 2020 | Her methane curve | Same as above |
| `range_km` | LH₂ 2,778 km (Hoelzen 2025); kerosene 6,000 and methane 5,000 approx. | Her ranges | Edit the CSV. The end of her fuel table also acts as a range limit |
| `seats` (180 for all) | Hoelzen 2025 design PAX | Her seat counts (LH₂ may lose seats to tanks) | Edit the CSV |
| `cruise_kmh` (830 for all) | Hoelzen 2025, Mach 0.78 | Her cruise speeds | Edit the CSV; block times adjust automatically |

Not expected from her (still to source elsewhere): `price_usd`, crew and maintenance costs,
`turn_min`, refuelling rates.

## Interactive exploration (marimo)

Add a marimo notebook as a layer on top of the package; don't move the model into it.

| Layer | What |
|---|---|
| `src/altfuel/` | The model, unchanged; tests cover it |
| `scripts/run_scenarios.py` | Batch runs and report figures |
| `notebooks/explore.py` (new) | Sliders → `analysis.run(replace(sc, carbon_price=...))` → charts |

- **Sliders:** carbon price, LH₂ price, LNG aircraft premium, fleet per type, capacity share, LH₂ range.
- **Live views:** network map, fuel split of legs, cost and CO₂ vs baseline, Gantt chart.
- **Why marimo:** reactive (only dependent cells re-run), saved as plain `.py` (clean git diffs), can be served as a web app (`marimo run`) for Maria and Peter. Streamlit is the alternative for a polished demo; Jupyter + ipywidgets is clunkier.
- **Charts:** existing matplotlib `plots.py` works as is; Plotly only for hover-to-read-values.
- **Keep model logic out of notebook cells**, so tests still cover it.
- **At full scale:** live re-solving works while a run takes about a second. For big grids
  (e.g. carbon price × LH₂ price × LNG premium, or with tankering), precompute with `sweep`,
  save the results, and let the sliders pick from saved runs; `mo.cache` makes revisited values instant.

## Scaling

Benchmark (synthetic network: dummy legs copied N times with shifted times, `alt_carbon_200`,
capacity check on), after the Nov 2026 speed-ups:

| Legs | Total time |
|---|---|
| 40 | 0.1 s |
| 400 | 0.3 s |
| 1,000 | 0.8 s |
| 2,000 | 1.4 s (was 12.9 s, mostly in `capacity_usage`) |

Real networks have more stations and less regular timetables, so solve times will be
higher; re-benchmark when real data arrives, and again once tankering layers are added.

## Housekeeping

- Delete the `temp` branch on GitHub (blocked from the coding session; do it in the UI).
