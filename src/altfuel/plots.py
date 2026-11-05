"""Figures: network map, tail Gantt chart, scenario comparison and sweep chart.

Each fuel gets the colour at its row number in fuels.csv, so it keeps the same
colour in every figure.
"""

import json

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import FancyArrowPatch, Patch, Polygon

from .utils import ROOT

COLOURS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
BLACK, GREY, LIGHT_GREY, BACKGROUND = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
LAND, BORDER = "#efeee9", "#d3d1cb"
LAND_FILE = ROOT / "data" / "europe_outline.geojson"   # coastlines and borders (GSHHG)
LABEL_DIRECTION = {"LHR": (-1, -0.7), "DUB": (-0.35, 1)}   # hand-placed for the dummy network
UNITS = {"carbon_price": "USD per t CO₂", "yield_usd_per_pax_km": "USD per pax-km"}

plt.rcParams.update({
    "figure.facecolor": BACKGROUND, "axes.facecolor": BACKGROUND, "savefig.facecolor": BACKGROUND,
    "text.color": BLACK, "axes.labelcolor": GREY, "xtick.color": GREY, "ytick.color": GREY,
    "axes.edgecolor": LIGHT_GREY, "font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
})


def fuel_colours(fuels: pd.DataFrame) -> dict:
    return {fuel: COLOURS[i % len(COLOURS)] for i, fuel in enumerate(fuels.index)}


def add_grid(ax, axis="both"):
    ax.grid(axis=axis, color=LIGHT_GREY, lw=0.6)
    ax.set_axisbelow(True)


def draw_land(ax):
    """Land shapes and country borders under the network, from LAND_FILE."""
    with open(LAND_FILE) as f:
        features = json.load(f)["features"]
    for feature in features:
        points = feature["geometry"]["coordinates"]
        if feature["properties"]["kind"] == "land":
            ax.add_patch(Polygon(points[0], closed=True, fc=LAND, ec=BORDER, lw=0.5, zorder=0))
        else:
            lon, lat = zip(*points)
            ax.plot(lon, lat, color=BORDER, lw=0.5, zorder=0.5)


def network_map(run, background=True):
    """One curved line per airport pair and fuel; thicker = more legs.
    background=False gives a plain latitude/longitude grid instead of the map."""
    airports = run.data.airports
    colour = fuel_colours(run.data.fuels)
    label = run.data.fuels.label
    fuels = list(colour)

    flown = run.flown.merge(run.rotations[["leg_id", "origin", "destination"]], on="leg_id")
    flown["pair"] = [tuple(sorted(p)) for p in zip(flown.origin, flown.destination)]

    fig, ax = plt.subplots(figsize=(8.5, 6))
    lines = []
    for (pair, fuel), n in flown.groupby(["pair", "fuel"]).size().items():
        start = airports.loc[pair[0], ["lon", "lat"]].to_numpy()
        end = airports.loc[pair[1], ["lon", "lat"]].to_numpy()
        bend = 0.08 + 0.12 * fuels.index(fuel)     # so two fuels on one route don't overlap
        ax.add_patch(FancyArrowPatch(start, end, arrowstyle="-", color=colour[fuel], lw=0.6 + 0.45 * n,
                                     connectionstyle=f"arc3,rad={bend}"))
        lines.append((start, end, bend, fuel, n))
    ax.scatter(airports.lon, airports.lat, s=90, c=BACKGROUND, edgecolors=BLACK, lw=1.5, zorder=3)

    # Label each airport with its tier and the fuels it offers (except fuels offered
    # everywhere), on the side facing away from the middle of the network, where there
    # are fewest lines. LABEL_DIRECTION overrides this for airports in the middle.
    everywhere = [f for f in fuels if run.airport_fuel.xs(f, level="fuel").available.all()]
    middle = airports[["lon", "lat"]].mean().to_numpy()
    for station, airport in airports.iterrows():
        offered = [label[f] for f in fuels
                   if f not in everywhere and run.airport_fuel.loc[(station, f), "available"]]
        away = np.array(LABEL_DIRECTION.get(station, [airport.lon, airport.lat] - middle), dtype=float)
        away = away / np.hypot(*away)
        ha = "center" if abs(away[0]) < 0.4 else ("left" if away[0] > 0 else "right")
        ax.annotate(f"{station} (tier {airport.tier})\n{' · '.join(offered)}", (airport.lon, airport.lat),
                    xytext=14 * away, textcoords="offset points", fontsize=8.5, zorder=6,
                    ha=ha, va="bottom" if away[1] >= 0 else "top", linespacing=1.1)

    # Frame the airports with some space around them, then put the map underneath
    lon, lat = airports.lon, airports.lat
    pad_lon, pad_lat = 0.4 * (lon.max() - lon.min()), 0.25 * (lat.max() - lat.min())
    ax.set_xlim(lon.min() - pad_lon, lon.max() + pad_lon)
    ax.set_ylim(lat.min() - pad_lat, lat.max() + pad_lat)
    ax.set_aspect(1 / np.cos(np.radians(lat.mean())))
    if background:
        draw_land(ax)
        ax.set_facecolor("#f7fafc")                  # sea
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_visible(True)
            spine.set_color(LIGHT_GREY)
    else:
        ax.set_xlabel("Longitude (°)")
        ax.set_ylabel("Latitude (°)")
        add_grid(ax)

    handles = [Line2D([], [], color=colour[f], lw=3, label=label[f]) for f in fuels if f in set(flown.fuel)]
    handles += [Line2D([], [], color=GREY, lw=0.6 + 0.45 * n, label=f"{n} legs") for n in (2, 6)]
    ax.legend(handles=handles, loc="lower left", bbox_to_anchor=(1.04, 0), frameon=False, fontsize=8.5)

    ax.set_title(f"{run.scenario.name}: {run.kpis['legs_flown']} legs, {run.kpis['aircraft']} aircraft",
                 loc="left", fontsize=11, pad=30)
    note = f" (offered everywhere: {', '.join(label[f] for f in everywhere)})" if everywhere else ""
    ax.text(0, 1.015, f"Numbers: legs per day on each line, both directions\n"
                      f"Labels: airport tier and fuels offered{note}",
            transform=ax.transAxes, fontsize=8, color=GREY, va="bottom")
    fig.tight_layout()

    # Number of legs on each line, placed on its curve. The curves are bent in screen
    # space, so positions are worked out there once the layout is final. Each fuel's
    # number sits at a different point along the curve, so two fuels on a short route
    # don't put their numbers on top of each other.
    fig.canvas.draw()
    to_screen, to_data = ax.transData, ax.transData.inverted()
    for start, end, bend, fuel, n in lines:
        a, b = to_screen.transform(start), to_screen.transform(end)
        dx, dy = b - a
        control = (a + b) / 2 + bend * np.array([dy, -dx])        # control point of the arc3 curve
        t = 0.35 + 0.15 * (fuels.index(fuel) % 3)
        point = (1 - t) ** 2 * a + 2 * (1 - t) * t * control + t ** 2 * b
        ax.text(*to_data.transform(point), str(n), ha="center", va="center", fontsize=7,
                color=colour[fuel], fontweight="bold", zorder=7,
                bbox=dict(boxstyle="circle,pad=0.2", fc=BACKGROUND, ec=colour[fuel], lw=0.8))
    return fig


def tail_gantt(run):
    """One row per aircraft, one bar per flight."""
    colour = fuel_colours(run.data.fuels)
    fuel_of = run.data.aircraft_types.fuel
    rot = run.rotations
    tails = list(dict.fromkeys(rot.tail_id))

    fig, ax = plt.subplots(figsize=(10, 0.45 * len(tails) + 1.2))
    for r in rot.itertuples():
        row = tails.index(r.tail_id)
        start, hours = r.dep_min / 60, (r.arr_min - r.dep_min) / 60
        ax.barh(row, hours, left=start, height=0.62, color=colour[fuel_of[r.type]],
                edgecolor=BACKGROUND, lw=2)
        if hours > 0.8:
            ax.text(start + hours / 2, row, f"{r.origin}–{r.destination}", ha="center", va="center",
                    fontsize=6, color="white")

    ax.set_yticks(range(len(tails)), tails, fontsize=8)
    ax.invert_yaxis()
    first_hour = min(6, rot.dep_min.min() // 60)
    last_hour = max(24, int(np.ceil(rot.arr_min.max() / 60)))
    ax.set_xlim(first_hour, last_hour)
    ticks = range(first_hour, last_hour + 1, 2)
    ax.set_xticks(ticks, [f"{h % 24:02d}:00" for h in ticks])
    add_grid(ax, "x")
    ax.spines["left"].set_visible(False)

    used = {fuel_of[t] for t in rot.type}
    patches = [Patch(color=colour[f], label=run.data.fuels.label[f]) for f in colour if f in used]
    ax.legend(handles=patches, loc="upper left", bbox_to_anchor=(1.0, 1.0), frameon=False, fontsize=8.5)
    ax.set_title(f"{run.scenario.name}: tail rotations", loc="left", fontsize=11)
    fig.tight_layout()
    return fig


def scenario_comparison(runs):
    """CO2 by fuel, and total cost by fuel (operating + ownership) plus lost revenue."""
    runs = [r for r in runs if "total_cost_usd" in r.kpis]       # skip runs with no solution
    colour = fuel_colours(runs[0].data.fuels)
    label = runs[0].data.fuels.label
    names = [r.scenario.name for r in runs]

    def co2(r, fuel):
        return r.flown.loc[r.flown.fuel == fuel, "co2_t"].sum()

    def cost_k(r, fuel):
        types = r.data.aircraft_types.index[r.data.aircraft_types.fuel == fuel]
        owning = sum(r.result.fleet_used.get(t, 0) * r.ownership.get(t, 0) for t in types)
        return (r.flown.loc[r.flown.fuel == fuel, "operating_cost_usd"].sum() + owning) / 1000

    lost_k = np.array([(r.kpis["spill_cost_usd"] + r.kpis["dropped_revenue_usd"]) / 1000 for r in runs])

    fig, axes = plt.subplots(1, 2, figsize=(11, 0.55 * len(names) + 1.8), sharey=True)
    for ax, value, xlabel in [(axes[0], co2, "CO₂, well-to-wake (t)"), (axes[1], cost_k, "Total cost ($k)")]:
        left = np.zeros(len(runs))
        for fuel in colour:
            widths = np.array([value(r, fuel) for r in runs])
            if widths.any():
                ax.barh(range(len(runs)), widths, left=left, height=0.6, color=colour[fuel],
                        edgecolor=BACKGROUND, lw=2, label=label[fuel])
                left += widths
        if value is cost_k and lost_k.any():
            ax.barh(range(len(runs)), lost_k, left=left, height=0.6, color=LIGHT_GREY,
                    edgecolor=BACKGROUND, lw=2, hatch="///", label="Lost revenue (spill, drops)")
            left += lost_k
        for i, total in enumerate(left):
            change = "" if i == 0 else f"  ({100 * (total / left[0] - 1):+.0f}%)"
            ax.text(total, i, f" {total:,.0f}{change}", va="center", fontsize=8.5)
        ax.set_xlim(0, left.max() * 1.4)
        ax.set_xlabel(xlabel)
        add_grid(ax, "x")
        ax.spines["left"].set_visible(False)

    axes[0].set_yticks(range(len(runs)), names)
    axes[0].invert_yaxis()
    fig.suptitle("Scenario comparison (change vs baseline in brackets)", x=0.01, ha="left", fontsize=11)
    handles, labels = axes[1].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper right", ncol=len(handles), frameon=False, fontsize=8.5)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    return fig


def sweep_chart(sweep: pd.DataFrame, parameter: str, scenario_name: str, fuels: pd.DataFrame):
    """Share of legs flown on each fuel, against the swept setting."""
    colour = fuel_colours(fuels)
    fig, ax = plt.subplots(figsize=(7, 4))
    for fuel in colour:
        share = sweep.get(f"share_{fuel}")
        if share is not None and share.any():
            ax.plot(sweep[parameter], 100 * share, color=colour[fuel], lw=2, marker="o", ms=7,
                    mec=BACKGROUND, mew=2, label=fuels.label[fuel])
    unit = f" ({UNITS[parameter]})" if parameter in UNITS else ""
    ax.set_xlabel(parameter.replace("_", " ").capitalize() + unit)
    ax.set_ylabel("Legs flown (%)")
    ax.set_ylim(-3, 103)
    ax.legend(frameon=False, fontsize=8.5)
    add_grid(ax)
    ax.set_title(f"Sweep of {parameter} ({scenario_name})", loc="left", fontsize=11)
    fig.tight_layout()
    return fig
