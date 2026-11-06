"""Module 3: what each aircraft type does on each leg.

For every (type, leg) pair: can it fly it, how much fuel, energy and CO2,
block time, turn time and spilled passengers. Methods and sources are listed
in docs/methods.md.
"""

import warnings

import numpy as np
import pandas as pd

from .data_layer import Data
from .scenario_config import Scenario


def fuel_kg_many(data: Data, types, distances) -> np.ndarray:
    """Fuel burn in kg. Uses the type's fuel_burn.csv table if it has one
    (NaN past the end of the table), otherwise the straight-line fit."""
    types = np.asarray(types)
    distances = np.asarray(distances, dtype=float)
    aircraft = data.aircraft_types
    fixed = aircraft.fuel_kg_fixed.reindex(types).to_numpy(float)
    per_km = aircraft.fuel_kg_per_km.reindex(types).to_numpy(float)
    kg = fixed + per_km * distances

    for ac_type, table in data.fuel_burn.groupby("type"):
        rows = types == ac_type
        if rows.any():
            table = table.sort_values("distance_km")
            kg[rows] = np.interp(distances[rows], table.distance_km, table.fuel_kg, right=np.nan)
    return kg


def fuel_kg(data: Data, ac_type: str, distance_km: float) -> float:
    return float(fuel_kg_many(data, [ac_type], [distance_km])[0])


def refuel_minutes(data: Data, types, kg) -> np.ndarray:
    """Plug-in/out time + fuel mass / (pumps x flow per pump). NaN if the fuel has no data."""
    aircraft = data.aircraft_types.reindex(np.asarray(types))
    fuel = data.fuels.reindex(aircraft.fuel)
    pumps = aircraft.refuel_pumps.to_numpy(float)
    flow_kg_s = pumps * fuel.refuel_flow_kg_s_per_pump.to_numpy(float)
    return fuel.refuel_plug_min.to_numpy(float) + np.asarray(kg, dtype=float) / flow_kg_s / 60


def in_curfew(t, start, end):
    """True where time t (minutes, any day) falls in an airport's night curfew.
    Curfews usually run over midnight (start > end, e.g. 23:30-06:00). No curfew = blank."""
    t = t % 1440
    over_midnight = (t >= start) | (t < end)
    same_day = (t >= start) & (t < end)
    return np.where(start > end, over_midnight, same_day)


def perf(data: Data, airport_fuel: pd.DataFrame, sc: Scenario) -> pd.DataFrame:
    aircraft = data.aircraft_types
    ref = sc.reference_type
    in_fleet = [t for t in aircraft.index if sc.fleet.get(t, 0) > 0]

    # One row for every (type, leg) pair
    p = aircraft.loc[in_fleet].rename_axis("type").reset_index()
    p = p.merge(data.legs.reset_index(), how="cross")
    distance = p.distance_km.to_numpy(float)
    fuels = data.fuels.reindex(p.fuel)

    # Fuel, energy and CO2
    p["fuel_kg"] = fuel_kg_many(data, p.type, distance)
    p["energy_gj"] = p.fuel_kg * fuels.lhv_mj_per_kg.to_numpy() / 1000
    p["co2_ttw_t"] = p.fuel_kg * fuels.co2_kg_per_kg.to_numpy() / 1000
    # Well-to-tank CO2 per kg of fuel: fuels.csv, unless the scenario gives a value
    wtt = data.fuels.wtt_co2_kg_per_kg.to_dict()
    wtt.update(sc.wtt_co2_kg_per_kg)
    p["co2_wtt_t"] = p.fuel_kg * p.fuel.map(wtt) / 1000
    p["co2_t"] = p.co2_ttw_t + p.co2_wtt_t

    # Block time: the schedule's time is right for the reference type; other types
    # add the difference from flying the distance at their own cruise speed.
    scheduled = (p.arr_min - p.dep_min).to_numpy(float)
    speed = p.type.map(aircraft.cruise_kmh).to_numpy(float)
    ref_speed = aircraft.cruise_kmh[ref]
    block = np.round(scheduled + distance * (1 / speed - 1 / ref_speed) * 60).astype(int)
    if (block <= 0).any():
        raise ValueError("a block time is <= 0: check arr_min in legs.csv and cruise_kmh")
    p["block_min"] = block
    p["arr_min"] = p.dep_min.astype(int) + block

    # Turn time: the type's turn + any extra refuelling time compared with the reference type
    extra = np.zeros(len(p))
    if sc.refuel_on_critical_path:
        ref_types = np.full(len(p), ref)
        ref_kg = fuel_kg_many(data, ref_types, distance)
        extra = refuel_minutes(data, p.type, p.fuel_kg) - refuel_minutes(data, ref_types, ref_kg)
        extra[(p.type == ref).to_numpy()] = 0
        no_data = np.isnan(extra)
        for ac_type in sorted(p.type[no_data].unique()):
            warnings.warn(f"no refuelling data for {ac_type}'s fuel, so no extra turn time")
        extra = np.where(no_data, 0, np.maximum(extra, 0))
    p["turn_min"] = np.round(p.turn_min.to_numpy(float) + extra).astype(int)

    # Seats and spilled passengers
    p["pax_cap"] = np.floor(p.seats * p.max_load_factor).astype(int)
    p["spill_pax"] = (p.pax - p.pax_cap).clip(lower=0).astype(int)

    # Can this type fly this leg? Separate reasons, so error messages can say which.
    p["in_range"] = (distance <= p.range_km.to_numpy(float)) & p.fuel_kg.notna().to_numpy()
    origin_fuel = pd.MultiIndex.from_arrays([p.origin, p.fuel])
    p["fuel_at_origin"] = airport_fuel.available.reindex(origin_fuel).to_numpy(bool)
    p["fits"] = (p.spill_pax == 0) | sc.allow_spill
    start, end = data.airports.curfew_start, data.airports.curfew_end
    leaves_in_curfew = in_curfew(p.dep_min, p.origin.map(start), p.origin.map(end))
    lands_in_curfew = in_curfew(p.arr_min, p.destination.map(start), p.destination.map(end))
    p["outside_curfew"] = ~leaves_in_curfew & ~lands_in_curfew
    p["feasible"] = p.in_range & p.fuel_at_origin & p.fits & p.outside_curfew

    columns = ["fuel", "seats", "in_range", "fuel_at_origin", "fits", "outside_curfew",
               "pax_cap", "spill_pax", "fuel_kg", "energy_gj", "co2_ttw_t", "co2_wtt_t",
               "block_min", "arr_min", "turn_min", "co2_t", "feasible"]
    return p.set_index(["type", "leg_id"])[columns].sort_index()
