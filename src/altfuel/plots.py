"""Figures for the analysis: network map, tail Gantt, scenario comparison, carbon sweep."""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import FancyArrowPatch, Patch

FUEL_COLOURS = {"kerosene": "#2a78d6", "lh2": "#eb6834", "ch4": "#1baf7a"}
FUEL_LABELS = {"kerosene": "Kerosene", "lh2": "LH₂", "ch4": "Methane"}
INK, INK2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "text.color": INK, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "axes.edgecolor": GRID, "font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
})


def _style(ax, grid_axis="both"):
    ax.grid(axis=grid_axis, color=GRID, lw=0.6)
    ax.set_axisbelow(True)


def network_map(run, airports: pd.DataFrame, airport_fuel: pd.DataFrame):
    """One curved line per (airport pair, fuel); width = legs per day."""
    fig, ax = plt.subplots(figsize=(8.5, 6))
    f = run.flown.merge(run.rotations[["leg_id", "origin", "destination"]], on="leg_id")
    f["pair"] = [tuple(sorted(p)) for p in zip(f.origin, f.destination)]
    counts = f.groupby(["pair", "fuel"]).size()
    for (pair, fuel), n in counts.items():
        a, b = (airports.loc[s, ["lon", "lat"]].values for s in pair)
        bend = 0.08 + 0.12 * list(FUEL_COLOURS).index(fuel)   # separate fuels on one pair
        ax.add_patch(FancyArrowPatch(a, b, arrowstyle="-", color=FUEL_COLOURS[fuel],
                                     lw=0.6 + 0.45 * n, connectionstyle=f"arc3,rad={bend}"))
    ax.scatter(airports.lon, airports.lat, s=90, c=SURFACE, edgecolors=INK, lw=1.5, zorder=3)
    for s, ap in airports.iterrows():
        offered = [FUEL_LABELS[fu] for fu in ("lh2", "ch4") if airport_fuel.loc[(s, fu), "available"]]
        ax.annotate(f"{s} (tier {ap.tier})\n{' · '.join(offered)}", (ap.lon, ap.lat),
                    xytext=(9, 6), textcoords="offset points", fontsize=8.5, zorder=4)
    ax.set_aspect(1 / np.cos(np.radians(airports.lat.mean())))
    ax.margins(0.18)
    ax.set_xlabel("Longitude (°)"); ax.set_ylabel("Latitude (°)")
    _style(ax)
    used = [fu for fu in FUEL_COLOURS if fu in set(f.fuel)]
    handles = [Line2D([], [], color=FUEL_COLOURS[fu], lw=3, label=FUEL_LABELS[fu]) for fu in used]
    handles += [Line2D([], [], color=INK2, lw=0.6 + 0.45 * n, label=f"{n} legs/day") for n in (2, 6)]
    ax.legend(handles=handles, loc="lower left", bbox_to_anchor=(1.04, 0), frameon=False, fontsize=8.5)
    k = run.kpis
    ax.set_title(f"{run.scenario.name}: {k['legs_flown']} legs/day, {k['aircraft']} aircraft",
                 loc="left", fontsize=11, pad=22)
    ax.text(0, 1.015, "Labels: airport tier and alternative fuels offered (kerosene everywhere)",
            transform=ax.transAxes, fontsize=8, color=INK2, va="bottom")
    fig.tight_layout()
    return fig


def tail_gantt(run, fuel_of_type: dict):
    rot = run.rotations
    tails = list(dict.fromkeys(rot.tail_id))
    fig, ax = plt.subplots(figsize=(10, 0.45 * len(tails) + 1.2))
    for r in rot.itertuples():
        y, w = tails.index(r.tail_id), r.arr_h - r.dep_h
        ax.barh(y, w, left=r.dep_h, height=0.62, color=FUEL_COLOURS[fuel_of_type[r.type]],
                edgecolor=SURFACE, lw=2)
        if w > 0.8:
            ax.text(r.dep_h + w / 2, y, f"{r.origin}–{r.destination}", ha="center", va="center",
                    fontsize=5.8 if w < 1.2 else 6.5, color="white")
    ax.set_yticks(range(len(tails)), tails, fontsize=8)
    ax.invert_yaxis()
    ax.set_xlim(6, 24)
    ax.set_xticks(range(6, 25, 2), [f"{h:02d}:00" for h in range(6, 25, 2)])
    _style(ax, "x")
    ax.spines["left"].set_visible(False)
    used = [fu for fu in FUEL_COLOURS if fu in {fuel_of_type[t] for t in rot.type}]
    ax.legend(handles=[Patch(color=FUEL_COLOURS[fu], label=FUEL_LABELS[fu]) for fu in used],
              loc="upper left", bbox_to_anchor=(1.0, 1.0), frameon=False, fontsize=8.5)
    ax.set_title(f"{run.scenario.name}: daily tail rotations", loc="left", fontsize=11)
    fig.tight_layout()
    return fig


def scenario_comparison(runs):
    """CO2 and total cost by fuel per scenario: two panels, one measure each."""
    names = [r.scenario.name for r in runs]
    fig, axes = plt.subplots(1, 2, figsize=(11, 0.55 * len(names) + 1.8), sharey=True)
    panels = [("co2_t", "CO₂, tank-to-wake (t/day)", 1), ("cost_usd", "Operating cost ($k/day)", 1e3)]
    for ax, (col, label, scale) in zip(axes, panels):
        left = np.zeros(len(names))
        for fuel in FUEL_COLOURS:
            v = np.array([r.flown.loc[r.flown.fuel == fuel, col].sum() / scale for r in runs])
            ax.barh(range(len(names)), v, left=left, height=0.6, color=FUEL_COLOURS[fuel],
                    edgecolor=SURFACE, lw=2, label=FUEL_LABELS[fuel])
            left += v
        for i, tot in enumerate(left):
            delta = "" if i == 0 else f"  ({100 * (tot / left[0] - 1):+.0f}%)"
            ax.text(tot, i, f" {tot:,.0f}{delta}", va="center", fontsize=8.5)
        ax.set_xlim(0, left.max() * 1.4)
        ax.set_xlabel(label)
        _style(ax, "x")
        ax.spines["left"].set_visible(False)
    axes[0].set_yticks(range(len(names)), names)
    axes[0].invert_yaxis()
    fig.suptitle("Scenario comparison (Δ vs baseline in brackets)", x=0.01, ha="left", fontsize=11)
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, loc="upper right", ncol=3, frameon=False, fontsize=8.5)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    return fig


def carbon_sweep(sweep: pd.DataFrame, name: str):
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(sweep.carbon_price, 100 * (1 - sweep.share_kerosene), color=FUEL_COLOURS["lh2"],
            lw=2, marker="o", ms=8, mec=SURFACE, mew=2)
    ax.set_xlabel("Carbon price (USD per t CO₂)")
    ax.set_ylabel("Legs flown on alternative fuel (%)")
    ax.set_ylim(0, 100)
    _style(ax)
    ax.set_title(f"Carbon-price sweep ({name})", loc="left", fontsize=11)
    fig.tight_layout()
    return fig
