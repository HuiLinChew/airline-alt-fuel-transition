"""Module 3 - Aircraft performance.

Whether each aircraft type can fly each leg, its fuel burn and turn time.
Output: perf with one row per (type, leg): feasible, fuel_kg, energy_gj, co2_t,
block_h, turn_h.

Methods
- Range: feasible only if leg distance <= type range (Kamat et al.; Sirtori et al.).
- Fuel: refuel before every departure, so the fuel must be offered at the
  origin (Wu et al. 2025, rule that LH2 aircraft use LH2 airports). No tankering yet.
- Fuel burn: linear fit vs distance per type (planning sheet; fit to Henry's curves).
- Block time: taken from the schedule (same for every type on a leg).
- Turn time: base turn (Akinola et al. 2025) plus, for LH2, the extra refuelling
  time from Al-Timimi's equations: plug in/out + fuel mass / pump flow.
"""

import pandas as pd

from .data_layer import Data
from .scenario_config import Scenario

# Al-Timimi refuelling-time parameters, narrowbody (2 pumps); minutes and kg/s
REFUEL = {"lh2": dict(plug_min=5 + 4, flow_kg_s=2 * 5.0),
          "kerosene": dict(plug_min=2 + 2, flow_kg_s=2 * 20.0)}


def refuel_min(fuel: str, kg: float) -> float:
    p = REFUEL.get(fuel, REFUEL["kerosene"])  # no methane data yet: treat as kerosene
    return p["plug_min"] + kg / p["flow_kg_s"] / 60


def perf(data: Data, airport_fuel: pd.DataFrame, sc: Scenario) -> pd.DataFrame:
    ker = data.aircraft_types[data.aircraft_types.fuel == "kerosene"].iloc[0]  # reference type
    rows = []
    for ac_type, ac in data.aircraft_types.iterrows():
        if sc.fleet.get(ac_type, 0) == 0:
            continue                                   # type not in this scenario's fleet
        f = data.fuels.loc[ac.fuel]
        for leg_id, leg in data.legs.iterrows():
            fuel_kg = ac.fuel_kg_fixed + ac.fuel_kg_per_km * leg.distance_km
            extra = 0.0
            if sc.refuel_on_critical_path and ac.fuel != "kerosene":
                ker_kg = ker.fuel_kg_fixed + ker.fuel_kg_per_km * leg.distance_km
                extra = max(0.0, refuel_min(ac.fuel, fuel_kg) - refuel_min("kerosene", ker_kg))
            rows.append(dict(
                type=ac_type, leg_id=leg_id, fuel=ac.fuel, seats=ac.seats,
                feasible=(leg.distance_km <= ac.range_km
                          and airport_fuel.loc[(leg.origin, ac.fuel), "available"]),
                fuel_kg=fuel_kg,
                energy_gj=fuel_kg * f.lhv_mj_per_kg / 1000,
                co2_t=fuel_kg * f.co2_kg_per_kg / 1000,
                block_h=leg.arr_h - leg.dep_h,
                turn_h=(ac.turn_min + extra) / 60,
            ))
    return pd.DataFrame(rows).set_index(["type", "leg_id"]).sort_index()
