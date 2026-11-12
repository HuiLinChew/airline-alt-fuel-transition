"""Figures for the Michaelmas presentation, all on the low-cost test network.

    uv run scripts/presentation_figures.py

Saves PNGs in outputs/presentation/. Two turnaround rules are compared:
  "during boarding":      LH2 and LNG refuel while passengers get off and on (Mangold et al.)
  "no passengers aboard": they refuel with nobody on board (Al-Timimi), the scenario default
"""

from dataclasses import replace

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from altfuel import analysis, plots
from altfuel.scenario_config import load_scenario
from altfuel.utils import OUTPUT_DIR

OUT = OUTPUT_DIR / "presentation"
BASE = load_scenario("lcc_carbon_200")
DURING_BOARDING = replace(BASE, sequential_refuel=[])
CARBON_PRICES = range(0, 401, 25)
FUELS = ["kerosene", "ch4", "lh2"]          # bottom to top in the stacked chart

plt.rcParams.update({"font.size": 14, "axes.titlesize": 15, "legend.fontsize": 13})
data = analysis.run(BASE).data
colour = plots.fuel_colours(data.fuels)
label = data.fuels.label


def save(fig, name):
    fig.savefig(OUT / f"{name}.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


def share_of_flights(run):
    return {f: run.kpis[f"share_{f}"] * 100 for f in FUELS}


def carbon_sweep():
    """Fuel mix, CO2 and cost at each carbon price (refuelling during boarding)."""
    baseline = analysis.run(load_scenario("lcc_baseline")).kpis
    rows = []
    for price in CARBON_PRICES:
        k = analysis.run(replace(DURING_BOARDING, carbon_price=price)).kpis
        rows.append({"carbon_price": price,
                     **{f: k[f"share_{f}"] * 100 for f in FUELS},
                     "co2_cut": 100 * (1 - k["co2_t"] / baseline["co2_t"]),
                     "cost_rise": 100 * (k["total_cost_usd"] / baseline["total_cost_usd"] - 1)})
    return pd.DataFrame(rows)


def staircase(sweep):
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.stackplot(sweep.carbon_price, [sweep[f] for f in FUELS],
                 colors=[colour[f] for f in FUELS], labels=[label[f] for f in FUELS], alpha=0.9,
                 step="post")    # prices tested every 25 $/t
    ax.set_xlim(0, 400)
    ax.set_ylim(0, 100)
    ax.set_xlabel("Carbon price ($ per tonne CO₂)")
    ax.set_ylabel("Flights (%)")
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1), frameon=False, reverse=True)
    save(fig, "6_fuel_mix_vs_carbon_price")


def trade_off(sweep):
    fig, ax = plt.subplots(figsize=(8, 5.5))
    ax.plot(sweep.cost_rise, sweep.co2_cut, color=plots.GREY, lw=1.5, zorder=1)
    ax.scatter(sweep.cost_rise, sweep.co2_cut, s=70, color=plots.BLACK, zorder=2)
    for r in sweep[sweep.carbon_price % 100 == 0].itertuples():
        ax.annotate(f"{r.carbon_price} $/t", (r.cost_rise, r.co2_cut), xytext=(8, -16),
                    textcoords="offset points", fontsize=12, color=plots.GREY)
    ax.set_xlabel("Cost increase vs all kerosene (%)")
    ax.set_ylabel("CO₂ cut vs all kerosene (%)")
    plots.add_grid(ax)
    save(fig, "backup_co2_vs_cost")


def route_map():
    run = analysis.run(DURING_BOARDING)
    fig = plots.network_map(run)
    fig.axes[0].set_title("", loc="left")
    save(fig, "7_route_map")
    return run


def distance_strip(run):
    flights = run.flown.merge(run.data.legs[["distance_km"]], left_on="leg_id", right_index=True)
    used = [f for f in FUELS if f in set(flights.fuel)]
    fig, ax = plt.subplots(figsize=(9, 1 + 1.1 * len(used)))
    rng = np.random.default_rng(0)
    for row, fuel in enumerate(used):
        d = flights[flights.fuel == fuel].distance_km
        ax.scatter(d, row + rng.uniform(-0.15, 0.15, len(d)), s=60, color=colour[fuel], alpha=0.8)
    ax.set_yticks(range(len(used)), [label[f] for f in used])
    ax.set_ylim(-0.6, len(used) - 0.4)
    ax.set_xlabel("Flight distance (km)")
    plots.add_grid(ax, "x")
    save(fig, "backup_distance_by_fuel")


def retiming_curve():
    delays = [0, 15, 30, 45, 60]
    fig, ax = plt.subplots(figsize=(9, 5))
    for name, sc, style in [("Refuel during boarding", DURING_BOARDING, "--"),
                            ("Refuel with no passengers aboard", BASE, "-")]:
        alt = []
        for d in delays:
            k = analysis.run(replace(sc, max_delay_min=d, delay_step_min=5)).kpis
            alt.append((k["share_lh2"] + k["share_ch4"]) * 100)
        ax.plot(delays, alt, style, marker="o", lw=2.5, ms=8, color=plots.BLACK, label=name)
    ax.set_xticks(delays)
    ax.set_ylim(-3, 103)
    ax.set_xlabel("Re-timing allowed (minutes later than timetabled)")
    ax.set_ylabel("Flights on LH₂ or LNG (%)")
    ax.legend(loc="lower right", frameon=False)
    plots.add_grid(ax)
    save(fig, "8_retiming_curve")


def gantt_zoom():
    """An LH2 and an LNG aircraft from the re-timed schedule, each the one moved most:
    dotted outlines show the timetabled times."""
    run = analysis.run(replace(BASE, max_delay_min=30, delay_step_min=5))
    rot = run.rotations
    moved = rot.groupby(["type", "tail_id"]).delay_min.sum()
    shown = [moved[t].idxmax() for t in ["LH2-NB", "CH4-NB"]]
    fig = plots.tail_gantt(replace(run, rotations=rot[rot.tail_id.isin(shown)]))
    fig.set_size_inches(12, 2.6)
    fig.axes[0].set_title("", loc="left")
    save(fig, "5_two_aircraft_retimed")


def tornado():
    """Lowest carbon price at which LH2 flies any flight, as one input changes."""
    ker_price = data.aircraft_types.price_usd["KER-NB"]
    lh2 = data.aircraft_types.loc["LH2-NB"]
    tests = {
        "LH₂ price": ({"fuel_overrides": {"lh2": {"price_usd_per_kg": 2.0}}},
                      {"fuel_overrides": {"lh2": {"price_usd_per_kg": 3.0}}}, "2.0 / 3.0 $/kg"),
        "LH₂ aircraft price": ({"aircraft_overrides": {"LH2-NB": {"price_usd": ker_price * 1.095}}},
                               {"aircraft_overrides": {"LH2-NB": {"price_usd": ker_price * 1.2}}},
                               "+9.5% / +20%"),
        "LNG aircraft price": ({"aircraft_overrides": {"CH4-NB": {"price_usd": ker_price * 1.071}}},
                               {"aircraft_overrides": {"CH4-NB": {"price_usd": ker_price * 1.12}}},
                               "+7.1% / +12%"),
        "LH₂ maintenance": ({}, {"aircraft_overrides": {"LH2-NB": {
            "maintenance_cost_per_block_hour": lh2.maintenance_cost_per_block_hour * 1.11}}},
            "same / +11%"),
    }

    def entry_price(**changes):
        sc = replace(DURING_BOARDING, **changes)
        for price in range(0, 601, 25):
            if analysis.run(replace(sc, carbon_price=price)).kpis["share_lh2"] > 0:
                return price
        return 600

    central = entry_price()
    fig, ax = plt.subplots(figsize=(9, 4))
    for row, (name, (low, high, values)) in enumerate(tests.items()):
        a, b = entry_price(**low), entry_price(**high)
        ax.barh(row, b - a, left=a, height=0.5, color=colour["lh2"])
        note = values if a != b else f"{values}: no change"
        ax.text(max(a, b) + 8, row, note, va="center", fontsize=12, color=plots.GREY)
    ax.axvline(central, color=plots.BLACK, lw=1.5)
    ax.set_yticks(range(len(tests)), list(tests))
    ax.invert_yaxis()
    ax.set_xlim(0, 500)
    ax.set_xlabel("Carbon price at which LH₂ first flies ($ per tonne CO₂)")
    plots.add_grid(ax, "x")
    save(fig, "backup_hydrogen_entry_price")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    sweep = carbon_sweep()
    staircase(sweep)
    trade_off(sweep)
    distance_strip(route_map())
    retiming_curve()
    gantt_zoom()
    tornado()
    print(sweep.round(1).to_string(index=False))
