"""Figures for the analysis: network map, tail Gantt, scenario comparison, sweep.

Fuel colours follow the row order of fuels.csv (fixed palette order, so a fuel
keeps its colour in every figure); labels come from its "label" column.
"""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import FancyArrowPatch, Patch

PALETTE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
INK, INK2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "text.color": INK, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "axes.edgecolor": GRID, "font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
})


def fuel_style(fuels: pd.DataFrame):
    """(colour, label) per fuel from fuels.csv order."""
    colour = {f: PALETTE[i % len(PALETTE)] for i, f in enumerate(fuels.index)}
    return colour, fuels.label.to_dict()


def _style(ax, grid_axis="both"):
    ax.grid(axis=grid_axis, color=GRID, lw=0.6)
    ax.set_axisbelow(True)


def network_map(run):
    """One curved line per (airport pair, fuel); width = legs per period."""
    airports, colour, label = run.data.airports, *fuel_style(run.data.fuels)
    fuels = list(colour)
    fig, ax = plt.subplots(figsize=(8.5, 6))
    f = run.flown.merge(run.rotations[["leg_id", "origin", "destination"]], on="leg_id")
    f["pair"] = [tuple(sorted(p)) for p in zip(f.origin, f.destination)]
    for (pair, fuel), n in f.groupby(["pair", "fuel"]).size().items():
        a, b = (airports.loc[s, ["lon", "lat"]].values for s in pair)
        bend = 0.08 + 0.12 * fuels.index(fuel)        # separate fuels on one pair
        ax.add_patch(FancyArrowPatch(a, b, arrowstyle="-", color=colour[fuel],
                                     lw=0.6 + 0.45 * n, connectionstyle=f"arc3,rad={bend}"))
    ax.scatter(airports.lon, airports.lat, s=90, c=SURFACE, edgecolors=INK, lw=1.5, zorder=3)
    always = [fu for fu in fuels if run.airport_fuel.xs(fu, level="fuel").available.all()]
    for s, ap in airports.iterrows():
        offered = [label[fu] for fu in fuels
                   if fu not in always and run.airport_fuel.loc[(s, fu), "available"]]
        ax.annotate(f"{s} (tier {ap.tier})\n{' · '.join(offered)}", (ap.lon, ap.lat),
                    xytext=(9, 6), textcoords="offset points", fontsize=8.5, zorder=4)
    ax.set_aspect(1 / np.cos(np.radians(airports.lat.mean())))
    ax.margins(0.18)
    ax.set_xlabel("Longitude (°)"); ax.set_ylabel("Latitude (°)")
    _style(ax)
    used = [fu for fu in fuels if fu in set(f.fuel)]
    handles = [Line2D([], [], color=colour[fu], lw=3, label=label[fu]) for fu in used]
    handles += [Line2D([], [], color=INK2, lw=0.6 + 0.45 * n, label=f"{n} legs") for n in (2, 6)]
    ax.legend(handles=handles, loc="lower left", bbox_to_anchor=(1.04, 0), frameon=False, fontsize=8.5)
    k = run.kpis
    ax.set_title(f"{run.scenario.name}: {k['legs_flown']} legs, {k['aircraft']} aircraft",
                 loc="left", fontsize=11, pad=22)
    note = f"(offered everywhere: {', '.join(label[fu] for fu in always)})" if always else ""
    ax.text(0, 1.015, f"Labels: airport tier and fuels offered {note}",
            transform=ax.transAxes, fontsize=8, color=INK2, va="bottom")
    fig.tight_layout()
    return fig


def tail_gantt(run):
    colour, label = fuel_style(run.data.fuels)
    fuel_of_type = run.data.aircraft_types.fuel.to_dict()
    rot = run.rotations
    tails = list(dict.fromkeys(rot.tail_id))
    fig, ax = plt.subplots(figsize=(10, 0.45 * len(tails) + 1.2))
    for r in rot.itertuples():
        y, w = tails.index(r.tail_id), (r.arr_min - r.dep_min) / 60
        ax.barh(y, w, left=r.dep_min / 60, height=0.62, color=colour[fuel_of_type[r.type]],
                edgecolor=SURFACE, lw=2)
        if w > 0.8:
            ax.text(r.dep_min / 60 + w / 2, y, f"{r.origin}–{r.destination}", ha="center",
                    va="center", fontsize=5.8 if w < 1.2 else 6.5, color="white")
    ax.set_yticks(range(len(tails)), tails, fontsize=8)
    ax.invert_yaxis()
    end_h = max(24, int(np.ceil(rot.arr_min.max() / 60)))
    ax.set_xlim(6, end_h)
    ax.set_xticks(range(6, end_h + 1, 2), [f"{h % 24:02d}:00" for h in range(6, end_h + 1, 2)])
    _style(ax, "x")
    ax.spines["left"].set_visible(False)
    used = [fu for fu in colour if fu in {fuel_of_type[t] for t in rot.type}]
    ax.legend(handles=[Patch(color=colour[fu], label=label[fu]) for fu in used],
              loc="upper left", bbox_to_anchor=(1.0, 1.0), frameon=False, fontsize=8.5)
    ax.set_title(f"{run.scenario.name}: tail rotations", loc="left", fontsize=11)
    fig.tight_layout()
    return fig


def scenario_comparison(runs):
    """CO2 and total cost by fuel per scenario: two panels, one measure each."""
    colour, label = fuel_style(runs[0].data.fuels)
    names = [r.scenario.name for r in runs]
    fig, axes = plt.subplots(1, 2, figsize=(11, 0.55 * len(names) + 1.8), sharey=True)
    panels = [("co2_t", "CO₂, tank-to-wake (t)", 1), ("cost_usd", "Operating cost ($k)", 1e3)]
    for ax, (col, axis_label, scale) in zip(axes, panels):
        left = np.zeros(len(names))
        for fuel in colour:
            v = np.array([r.flown.loc[r.flown.fuel == fuel, col].sum() / scale for r in runs])
            ax.barh(range(len(names)), v, left=left, height=0.6, color=colour[fuel],
                    edgecolor=SURFACE, lw=2, label=label[fuel])
            left += v
        for i, tot in enumerate(left):
            delta = "" if i == 0 else f"  ({100 * (tot / left[0] - 1):+.0f}%)"
            ax.text(tot, i, f" {tot:,.0f}{delta}", va="center", fontsize=8.5)
        ax.set_xlim(0, left.max() * 1.4)
        ax.set_xlabel(axis_label)
        _style(ax, "x")
        ax.spines["left"].set_visible(False)
    axes[0].set_yticks(range(len(names)), names)
    axes[0].invert_yaxis()
    fig.suptitle("Scenario comparison (Δ vs baseline in brackets)", x=0.01, ha="left", fontsize=11)
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, loc="upper right", ncol=len(h), frameon=False, fontsize=8.5)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    return fig


def sweep_chart(sweep: pd.DataFrame, parameter: str, scenario_name: str, reference_fuel="kerosene"):
    """Share of legs not flown on the reference fuel, against the swept parameter."""
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(sweep[parameter], 100 * (1 - sweep[f"share_{reference_fuel}"]), color=PALETTE[1],
            lw=2, marker="o", ms=8, mec=SURFACE, mew=2)
    ax.set_xlabel(parameter.replace("_", " "))
    ax.set_ylabel("Legs flown on alternative fuel (%)")
    ax.set_ylim(0, 100)
    _style(ax)
    ax.set_title(f"Sweep of {parameter} ({scenario_name})", loc="left", fontsize=11)
    fig.tight_layout()
    return fig
