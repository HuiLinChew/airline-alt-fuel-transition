# Methods and precedents

Each modelling choice, where it comes from, and what is still a placeholder.
Module numbers follow the planning sheet (FYP_Papers.xlsx, "Code modules").

## Method choices

| Module | Choice in the code | Precedent | Status |
|---|---|---|---|
| 0 Scenario config | One YAML per scenario; baseline = all kerosene; changes are "disturbances" to parameters | Planning sheet; Peter et al. (reference vs LH2 scenarios); Randeraad et al. (carbon-tax sweep) | Done |
| 1 Data layer | Separate airport, leg and aircraft tables with shared IDs, validated on load | Al-Timimi (separate airport/route/aircraft data, from Sanford) | Done (dummy data) |
| 2 Airport capability | Fuel offered at airports up to a tier; price = base × tier factor | Sirtori et al. (LH2 at all vs only large airports); Hoelzen et al. 2025 (price varies by airport) | Tier factors are placeholders |
| 3 Aircraft performance | Range check; fuel at origin required (refuel every departure) | Kamat et al. (range in FAM); Wu et al. 2025 (LH2 aircraft use LH2 airports); Sirtori et al. | Done; tankering later (Sirtori half-range rule, Randeraad) |
| 3 Aircraft performance | Fuel burn linear in distance per type | Planning sheet; fit to Sanford's short-haul range-fuel curves (as used by Al-Timimi), R² > 0.999 | To be replaced by Maria's non-linear data |
| 3 Aircraft performance | LH2 turn time = base + extra refuel time (plug in/out + mass ÷ pump flow) | Al-Timimi refuelling-time equations; base turn 40 min from Akinola et al. | Mangold et al. find LH2 refuelling need not extend turns: switch off with `refuel_on_critical_path: false` |
| 5 Cost/revenue | c = fuel × local price + carbon price × CO2 + block hours × hourly cost | Rau et al., Dray et al. (DOC per flight); Wu et al. (Eq. 10 carbon tax in objective) | Hourly cost and fares are placeholders |
| 5 Cost/revenue | Dropping a leg costs its lost revenue | Wu et al. 2025 (Eq. 2 cancellation) | Off by default (serve every passenger) |
| 5 Cost/revenue | Alternative objectives: energy, CO2 | Justin et al. 2022 (CO2 as second objective); meeting note (least fuel burn) | Done |
| 6 Network builder | Time-space network per type: flight, ground and wrap-around arcs | Hane et al. 1995 via Sherali et al. 2006; Kamat et al. | Done; fuel-state layers later (Randeraad) |
| 7 Optimiser | Basic FAM: cover, balance, count (MILP, PuLP + HiGHS) | Hane et al. via Sherali et al.; Kamat et al.; Wu et al. | Done |
| 8 Rotation checker | Greedy first-ready matching per station after the FAM | Sherali et al., Justin et al. (FAM then routing is standard practice) | Done |
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
| Base turn time | 40 min | Akinola et al. 2025 (short turnaround) |
| LH2 refuel: plug in/out, flow | 5 + 4 min, 2 pumps × 5 kg/s | Al-Timimi (`parameters.py`) |
| Kerosene refuel: plug in/out, flow | 2 + 2 min, 2 pumps × 20 kg/s | Al-Timimi |
| CO2 factors | Kerosene 3.16, CH4 2.75, LH2 0 kg/kg (tank-to-wake) | Al-Timimi (kerosene); stoichiometry (CH4) |
| Kerosene price | 0.60 USD/kg | Hoelzen et al. 2025 |
| LH2 price | 2.50 USD/kg (tier 1) | Hoelzen et al. 2025 (2–3 USD/kg at main European airports, 2050) |
| Methane price | 1.46 USD/kg | LH2 price × Raab et al. 2024 e-LCH4/e-LH2 cost ratio |
| Carbon price | 0–400 USD/t; 200 in `alt_carbon_200` | Hoelzen et al. 2025 ETS cases (50/100/200) |
| Hourly cost, fares, tier price factors, airport tiers | — | Placeholders |

## Where the earlier version differed

The first version was a frequency-planning model (flights per route, with an
aggregate utilisation constraint, as in Kinene & Birolini 2024 and Rau et al. 2024).
It has been replaced by the leg-based FAM in the planning sheet, because real
timed schedules (ADS-B) are the planned data, and leg-level assignment is what
the airline-side precedents (Wu, Kamat, Sherali) use. The frequency model is
still a useful fallback if only untimed route demand is available.
