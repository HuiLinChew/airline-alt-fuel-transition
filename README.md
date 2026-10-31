# Alternative-Fuel Fleet Transition: An Airline Network Perspective

Cambridge MEng (Part IIB) project, Hui Lin Chew, 2026–27. Supervisor: Dr Maria Vera-Morales (Whittle Laboratory).

How an airline's network, fleet and costs change as some aircraft switch from
kerosene to liquid hydrogen (LH₂) or methane. Builds on the airport-side models
of Henry Sanford and Hasan Al-Timimi.

**Status:** dummy network (5 airports, 40 daily legs, 3 aircraft types) to fix
the model structure before real data. Values are from the literature where
possible (see `docs/methods.md`); the rest are flagged placeholders.

<p align="center"><img src="outputs/figures/network_alt_carbon_200.png" width="60%"></p>

## Quick start

```bash
uv sync                           # install the pinned environment
uv run scripts/run_scenarios.py   # run all scenarios, write outputs/
uv run pytest                     # model checks
```

## Model

A basic fleet assignment model (Hane et al. 1995, via Sherali et al. 2006) on a
time-space network per aircraft type: each timed leg is assigned one aircraft
type (or dropped), subject to aircraft flow balance and the fleet available.
Range and fuel availability decide which types can fly which legs.

Modules follow the planning sheet:

| # | Module | File |
|---|---|---|
| 0 | Scenario config | `scenario_config.py` + `scenarios/*.yaml` |
| 1 | Data layer | `data_layer.py` |
| 2 | Airport capability | `airport_capability.py` |
| 3 | Aircraft performance | `aircraft_performance.py` |
| 4 | Fleet stock-flow | not yet built |
| 5 | Cost/revenue | `cost_revenue.py` |
| 6 | Network builder | `network_builder.py` |
| 7 | Optimiser | `optimiser.py` |
| 8 | Rotation checker | `rotation_checker.py` |
| 9 | Analysis | `analysis.py`, `plots.py` |

Full walk-through and every scenario setting: `docs/code_guide.md`. Sources for every method and number: `docs/methods.md`.

## First results (dummy data)

| Scenario | Aircraft | Alt-fuel legs | CO₂ vs baseline | Cost vs baseline |
|---|---|---|---|---|
| `baseline` (kerosene) | 9 | 0% | — | — |
| `alt_min_energy` | 9 | 0% | 0% | 0% |
| `alt_carbon_200` | 10 | 65% | −66% | +28% |
| `alt_min_co2` | 10 | 100% | −72% | +32% |

- Minimising fuel burn never picks LH₂ or methane: they need more energy per flight.
- With these prices LH₂ beats kerosene once carbon costs more than about 100–150 USD/t,
  consistent with Hoelzen et al. (2025). Above that, use is capped by the LH₂
  fleet (6 aircraft) and by Dublin having no LH₂.
- `alt_carbon_200_drop` shows the leg-dropping option; with placeholder fares it
  drops most legs, so it is a mechanism check, not a result.
