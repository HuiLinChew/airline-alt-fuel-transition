# Methods and precedents

Each modelling choice, where it comes from, and what is still a placeholder.
Module numbers follow the planning sheet (FYP_Papers.xlsx, "Code modules").

## Method choices

| Module | Choice in the code | Precedent | Status |
|---|---|---|---|
| 0 Scenario config | One YAML per scenario; baseline = all kerosene; changes are "disturbances" to parameters | Planning sheet; Peter et al. (reference vs LH2 scenarios); Randeraad et al. (carbon-tax sweep) | Done |
| 1 Data layer | Separate airport, leg and aircraft tables with shared IDs, validated on load | Al-Timimi (separate airport/route/aircraft data, from Sanford) | Done (dummy data) |
| 2 Airport capability | Fuel offered at airports up to a tier; price = base × tier factor | Sirtori et al. (LH2 at all vs only large airports); Hoelzen et al. 2025 (price varies by airport) | Tier factors are placeholders |
| 2 Airport capability | Runway movements per hour and stands, × the airline's share | Kinene & Birolini 2024 (constraint 16: movements per period ≤ airport capacity); Rau et al. 2024 (constraint 6: slot limit); Al-Timimi (stand/gate capacity) | Airline share is a placeholder; Hasan's absorption factor (rerouting overflow) to come |
| 3 Aircraft performance | Range check; fuel at origin required (refuel every departure) | Kamat et al. (range in FAM); Wu et al. 2025 (LH2 aircraft use LH2 airports); Sirtori et al. | Done; tankering later (Sirtori half-range rule, Randeraad) |
| 3 Aircraft performance | Fuel burn linear in distance per type | Planning sheet; fit to Sanford's short-haul range-fuel curves (as used by Al-Timimi), R² > 0.999 | To be replaced by Maria's non-linear data |
| 3 Aircraft performance | LH2 turn time = base + extra refuel time (plug in/out + mass ÷ pump flow) | Al-Timimi refuelling-time equations; base turn 40 min from Akinola et al. | Mangold et al. find LH2 refuelling need not extend turns: switch off with `refuel_on_critical_path: false` |
| 5 Cost/revenue | c = fuel × local price + carbon price × CO2 + block hours × hourly cost | Rau et al., Dray et al. (DOC per flight); Wu et al. (Eq. 10 carbon tax in objective) | Hourly cost and fares are placeholders |
| 5 Cost/revenue | Ownership per aircraft used per day = price × (annuity + insurance) / 365 | Hoelzen et al. 2022 (App. A, Eqs. A7–A8); fixed cost per aircraft in the FAM: Justin et al. 2022, Kinene & Birolini 2024; Proesmans et al. 2023 | Done |
| 5 Cost/revenue | Dropping a leg costs its lost revenue | Wu et al. 2025 (Eq. 2 cancellation) | Off by default (serve every passenger) |
| 3/5 Spill | Passengers above seats × max load factor are lost at their fare; without spill such types can't fly the leg | Planning sheet cost formula; spill cost in the FAM (Sherali et al. 2006); LF max 0.83 (Rau et al.) | Off by default; no recapture onto other flights yet; fares are placeholders |
| 5 Cost/revenue | Alternative objectives: energy, CO2 | Justin et al. 2022 (CO2 as second objective); meeting note (least fuel burn) | Done |
| 6 Network builder | Time-space network per type: flight, ground and wrap-around arcs | Hane et al. 1995 via Sherali et al. 2006; Kamat et al. | Done; fuel-state layers later (Randeraad) |
| 7 Optimiser | Basic FAM: cover, balance, count (MILP, PuLP + HiGHS) | Hane et al. via Sherali et al.; Kamat et al.; Wu et al. | Done |
| 7 Optimiser | Capacity: hourly movements ≤ limit; aircraft on the ground or turning ≤ stands | As module 2 | `check` mode by default (report only); `constrain` enforces |
| 8 Rotation checker | Greedy first-ready matching per station after the FAM; days joined into multi-day cycles (an aircraft ending at X flies, next day, a rotation starting at X) | Sherali et al., Justin et al. (FAM then routing is standard practice); a daily FAM's rotations can take several days to repeat (Sherali et al.) | Done; no maintenance rule (return to base every ≤ N days) yet |
| 9 Analysis | Deltas vs all-kerosene baseline; carbon-price sweep | Peter, Sirtori, Kamat, Kinene (compare to reference case) | Done |
| 4 Fleet stock-flow | Not built yet: fleet is fixed per scenario | Rau, Dray, Sirtori, Oesingmann | Next |

## Parameter sources

| Parameter | Value | Source |
|---|---|---|
| Route demand, distances | 2015 O-D data | Sanford database via Al-Timimi (`segment_data.csv`) |
| Airline share of each route | 15% | Placeholder |
| Max load factor | 0.83 | Rau et al. 2024 |
| Seats (all types) | 180 | Hoelzen et al. 2025 (single-aisle design PAX) |
| LH2 narrowbody range | 2,778 km (1,500 NM) | Hoelzen et al. 2025, SA-1500 design |
| Methane aircraft energy | +10% vs kerosene | Rompokos et al. 2020 (LNG 737-800, typical 1000–2000 NM flights) |
| Aircraft price, kerosene narrowbody | 49.4 M USD | IBA (2021): new-delivery A320neo market value |
| LH₂ aircraft price | +12% vs kerosene | Hoelzen et al. 2022 (short-range aircraft CAPEX) |
| Methane aircraft price | +9% vs kerosene (low case +7.1%) | Raab et al. 2024 Table 12, 180-seat narrowbody: LCH₄ +7.1%, LH₂ +9.5% vs SAF. Their ratio (75%) applied to our LH₂ +12% |
| Fossil LNG price | 0.57 USD/kg | LNG Japan 10.5 USD/mmbtu, 2027 forecast (World Bank CMO, Oct 2025) + airport handling 6.5 € cents/kg (Raab et al. 2024) |
| Ownership finance | 5% interest, 14 years, 5% residual value, 0.5% insurance | Hoelzen et al. 2022, App. A |
| Fare (yield) | 0.148 USD per pax-km | Proesmans et al. 2023, Table 3 |
| Cruise speed (all types) | 830 km/h | Hoelzen et al. 2025: design Mach 0.78 for kerosene and LH2 single-aisle designs |
| Well-to-tank CO2 | 0 (placeholder) | To source per fuel and production route (fossil LNG vs e-methane; grey vs green LH2) |
| Crew cost | 940 USD/block hour, all types | Derived from Hoelzen et al. 2022 salaries. Same for every type, so it only matters for dropped legs and fleet-size differences |
| Maintenance cost | 2,060 USD/block hour, all types | Placeholder (keeps crew + maintenance at 3,000). Differences not applied yet: Hoelzen et al. 2022 give +11% for LH₂ (short-range), which moves LH₂'s entry from 200 to 250 USD/t; methane difference not sourced |
| Base turn time | 40 min | Akinola et al. 2025 (short turnaround) |
| LH2 refuel: plug in/out, flow | 5 + 4 min, 2 pumps × 5 kg/s | Al-Timimi (`parameters.py`) |
| LNG refuel: plug in/out, flow | 9 min (low case 6), 2 pumps × 10.4 kg/s | Al-Timimi Eq. 9 with Mangold et al. 2022's cryogenic connect, chill-down and purge times (9 min with purging, 6 without), assumed to apply to LNG; flow = kerosene 20 kg/s × density 423/810 (Raab et al. 2024 Table 14), same hose and speed as kerosene. No LNG-specific data found |
| Kerosene refuel: plug in/out, flow | 2 + 2 min, 2 pumps × 20 kg/s | Al-Timimi |
| CO2 factors | Kerosene 3.16, CH4 2.75, LH2 0 kg/kg (tank-to-wake) | Al-Timimi (kerosene); stoichiometry (CH4) |
| Kerosene price | 0.60 USD/kg | Hoelzen et al. 2025 |
| LH2 price | 2.50 USD/kg (tier 1) | Hoelzen et al. 2025 (2–3 USD/kg at main European airports, 2050) |
| Methane price | 1.46 USD/kg | LH2 price × Raab et al. 2024 e-LCH4/e-LH2 cost ratio |
| Carbon price | 0–400 USD/t; 200 in `alt_carbon_200` | Hoelzen et al. 2025 ETS cases (50/100/200) |
| Tier price factors, airport tiers | — | Placeholders |

## Known approximations (state these in the report)

| Approximation | Effect |
|---|---|
| Extra LH₂ refuelling time is added to the turn after a leg, using that (inbound) leg's fuel as a proxy for the next leg's | On this network the extra is 6 min on every leg, so no difference; matters only for very unequal consecutive legs |
| Extra refuelling time is never negative: if an alternative fuel refuels faster than kerosene, no time is saved | Conservative |
| Ownership is charged for aircraft used, not for aircraft owned but idle | Correct for planning one schedule; the stock-flow module will charge the whole owned fleet |
| Spilled passengers are lost, not rebooked (no recapture) | Overstates the cost of spill |
| Runway capacity is checked per clock hour | Two flights at 06:55 and 07:05 count in different hours |
| Rotations and multi-day cycles come from a simple greedy matching, not an optimisation | Cycle lengths are one valid answer, not the shortest; the fleet assignment itself is unaffected |
| Inputs come from different years: route demand 2015 (Sanford), kerosene/LH₂ and carbon prices for 2050 (Hoelzen et al. 2025), LNG price 2027 (World Bank), aircraft price 2021 (IBA) | Results are illustrative until the inputs are put on one year basis |

## Methane: fossil LNG by default, e-methane by switching

`ch4` in fuels.csv is fossil LNG (decided Nov 2026): fossil price, fossil CO₂, pays the carbon price.
`ch4_e` is e-methane: synthetic price; its burnt CO₂ was taken from the air when it was made
(well-to-tank −2.75 kg/kg, a placeholder that ignores production energy), and it is zero-rated
for the carbon price (`carbon_price_share` 0). To switch, a scenario points the methane aircraft at
the other fuel and offers it: see `scenarios/out_and_back/alt_carbon_200_emethane.yaml`.

| | Fossil LNG (`ch4`) | e-methane (`ch4_e`) | Kerosene | LH₂ |
|---|---|---|---|---|
| Price, USD/GJ | 11.4 | 29.2 | 13.9 | 20.8 |
| CO₂ burnt, kg/GJ (pays carbon price) | 55 (yes) | 55 (no) | 73 (yes) | 0 |

With these prices fossil LNG is cheaper per GJ than kerosene, so the LNG aircraft premium decides
how much LNG flies with no carbon price. On the dummy network (unlimited fleets, no carbon price):
premium 0% → 100% of legs LNG; +5% → 65%; +7.1% → 35%; +9% (used) → 15%; +12% → 0%.
LNG refuels about 6 min slower than kerosene, like LH₂ (connection time dominates; the LNG pumping
itself is fast). On tight timetables this keeps LNG out unless legs can be delayed; the 6-min
connection low case lets it back in (low-cost timetable at 200 USD/t, fixed times: 0% → 21% LNG).
Methane slip (unburnt CH₄, a strong greenhouse gas) is not modelled, so LNG's CO₂ saving is overstated.

## Planned: tankering and boil-off

Tankering will be added as fuel states in the network (Randeraad et al.: time-space-fuel
network; Sirtori et al.: half-range rule). With no boil-off figure yet, the default
assumption is the cautious one: fuel carried for a return leg cannot be held overnight,
so an LH₂ aircraft must end the day at an airport supplying LH₂ (the planning sheet's
"overnight at a capable airport" rule; Maria's point that LH₂ boils off). The optimistic
case (fuel held overnight) will be a scenario setting, so the two bracket the answer.
Within the day, holding time will be unlimited until a cited `max_hold_min` is found.

## Where the earlier version differed

The first version was a frequency-planning model (flights per route, with an
aggregate utilisation constraint, as in Kinene & Birolini 2024 and Rau et al. 2024).
It has been replaced by the leg-based FAM in the planning sheet, because real
timed schedules (ADS-B) are the planned data, and leg-level assignment is what
the airline-side precedents (Wu, Kamat, Sherali) use. The frequency model is
still a useful fallback if only untimed route demand is available.
