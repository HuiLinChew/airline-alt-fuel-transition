# Future work

Ideas and to-dos not built yet, roughly in priority order. Sources for anything already
built are in `methods.md`.

## Model

| Item | What | Notes |
|---|---|---|
| Tankering + boil-off | Fuel-state layers in the time-space network, so an aircraft can carry fuel for the return leg | Randeraad et al. (time-space-fuel network); Sirtori et al. (half-range rule). Default: no fuel held overnight (LH₂ aircraft end the day at LH₂ airports); optimistic case (held overnight) as a setting. `max_hold_min` unlimited until sourced. Multiplies model size ×3–5 |
| Fleet stock-flow (module 4) | Fleet changes year by year (retirements, deliveries) instead of a fixed fleet per scenario | Rau, Dray, Sirtori, Oesingmann. Ownership would then be charged on the whole owned fleet |
| Split hourly cost | Crew vs maintenance instead of one 3,000 $/h placeholder | Crew ≈ 940 $/block h from Hoelzen salaries; needs a sourced maintenance base (Hoelzen gives +11% for LH₂ but not the cost burden) |
| Spill recapture | Spilled passengers rebook onto other flights | Currently all lost, which overstates spill cost |
| Maintenance routing | Rule that every aircraft returns to a maintenance base every ≤ N days; choose rotations to keep cycles short | Cycles are now reported (`day_cycles`) but come from a greedy matching. Becomes important with tankering: an LH₂ aircraft parked overnight at a non-LH₂ airport has the boil-off problem |
| Schedule design (discuss with Maria) | Let the model choose which flights to operate, not just which type flies each: give it candidate flights (out-and-backs and chains) and require each airport pair's daily passengers to be carried by some of them | Lohatepanont & Barnhart 2004 (integrated schedule design and fleet assignment). Then LH₂ airport limits and turn times reshape the network itself, e.g. picking chains only where they beat back-and-forth. Bigger model: demand becomes a constraint and there are many more candidate flights |
| Absorption factor | Overflow at a capacity-limited airport rerouted (Hasan) | Capacity is currently check or hard limit only |
| Weekly schedules | Use `period_min: 10080` with real weekly timetables | Already supported and tested |

## Data to source

| Item | Why it matters |
|---|---|
| LNG aircraft price premium | Decides whether LNG wins at all (0% → 100% of legs, +5% → 65%, +12% → 0%) |
| LNG turnaround / refuelling rates | Currently no extra turn time for methane |
| Well-to-tank CO₂ per fuel and production route | Placeholder 0 (e-methane −2.75) |
| Maria's fuel-burn curves | Drop into `fuel_burn.csv`; replaces the straight-line fit |
| Airport tier mapping (1–6) and tier price factors | Placeholders |
| Airline capacity share | Placeholder 15% |
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

Not expected from her (still to source elsewhere): `price_usd`, `cost_per_block_hour`,
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
