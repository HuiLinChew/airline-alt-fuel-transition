"""Module 3 - Aircraft performance.

Whether each aircraft type can fly each leg, its fuel burn and turn time.
Output: perf with one row per (type, leg): feasible, fuel_kg, energy_gj, co2_t,
block_min, turn_min.

Methods
- Range: feasible only if leg distance <= type range (Kamat et al.; Sirtori et al.).
- Fuel: refuel before every departure, so the fuel must be offered at the
  origin (Wu et al. 2025, rule that LH2 aircraft use LH2 airports). No tankering yet.
- Fuel burn: from fuel_burn.csv (interpolated) if the type has a table there,
  otherwise the linear fit fixed + per_km x distance in aircraft_types.csv.
- Block time: taken from the schedule (same for every type on a leg).
- Turn time: base turn (Akinola et al. 2025) plus, if refuelling is on the critical
  path, the extra refuelling time vs the reference type (Al-Timimi):
  refuel time = plug in/out + fuel mass / (pumps x flow per pump).
"""

import warnings

import numpy as np
import pandas as pd

from .data_layer import Data
from .scenario_config import Scenario


def fuel_kg(data: Data, ac_type: str, distance_km: float) -> float:
    table = data.fuel_burn[data.fuel_burn.type == ac_type].sort_values("distance_km")
    if len(table):
        if distance_km > table.distance_km.max():
            return float("nan")                      # beyond the table: no data, treat as infeasible
        return float(np.interp(distance_km, table.distance_km, table.fuel_kg))
    ac = data.aircraft_types.loc[ac_type]
    return ac.fuel_kg_fixed + ac.fuel_kg_per_km * distance_km


def refuel_min(data: Data, ac_type: str, kg: float) -> float:
    """Refuelling time in minutes; NaN if the fuel has no refuelling data."""
    ac = data.aircraft_types.loc[ac_type]
    f = data.fuels.loc[ac.fuel]
    return f.refuel_plug_min + kg / (ac.refuel_pumps * f.refuel_flow_kg_s_per_pump) / 60


def perf(data: Data, airport_fuel: pd.DataFrame, sc: Scenario) -> pd.DataFrame:
    ref = sc.reference_type
    rows, no_refuel_data = [], set()
    for ac_type, ac in data.aircraft_types.iterrows():
        if sc.fleet.get(ac_type, 0) == 0:
            continue                                   # type not in this scenario's fleet
        f = data.fuels.loc[ac.fuel]
        for leg_id, leg in data.legs.iterrows():
            kg = fuel_kg(data, ac_type, leg.distance_km)
            extra = 0.0
            if sc.refuel_on_critical_path and ac_type != ref:
                extra = refuel_min(data, ac_type, kg) - refuel_min(data, ref, fuel_kg(data, ref, leg.distance_km))
                if np.isnan(extra):
                    no_refuel_data.add(ac_type)
                    extra = 0.0
            rows.append(dict(
                type=ac_type, leg_id=leg_id, fuel=ac.fuel, seats=ac.seats,
                feasible=bool(leg.distance_km <= ac.range_km and not np.isnan(kg)
                              and airport_fuel.loc[(leg.origin, ac.fuel), "available"]),
                fuel_kg=kg,
                energy_gj=kg * f.lhv_mj_per_kg / 1000,
                co2_t=kg * f.co2_kg_per_kg / 1000,
                block_min=int(leg.arr_min - leg.dep_min),
                turn_min=int(round(ac.turn_min + max(0.0, extra))),
            ))
    for ac_type in sorted(no_refuel_data):
        warnings.warn(f"no refuelling data for {ac_type}'s fuel: no extra turn time added")
    return pd.DataFrame(rows).set_index(["type", "leg_id"]).sort_index()
