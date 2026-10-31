"""Figures: network map, tail Gantt chart, scenario comparison."""

from __future__ import annotations

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import FancyArrowPatch, Patch

from .data import Inputs
from .model import Solution

FUEL_COLOURS = {"kerosene": "#2a78d6", "lh2": "#eb6834", "ch4": "#1baf7a"}
FUEL_LABELS = {"kerosene": "Kerosene", "lh2": "LH₂", "ch4": "Methane (LNG)"}
INK, INK2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "text.color": INK, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "axes.edgecolor": GRID, "font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
})


def network_map(inp: Inputs, sol: Solution, title: str = "", ax=None):
    """Airports as nodes; one curved line per (airport pair, fuel), width ∝ daily flights."""
    ax = ax or plt.subplots(figsize=(8.5, 6))[1]
    ap = inp.airports
    F = sol.flights.copy()
    F["pair"] = [tuple(sorted(p)) for p in zip(F.origin, F.destination)]
    agg = F.groupby(["pair", "fuel"])["flights"].sum().reset_index()
    fuels = list(FUEL_COLOURS)
    for r in agg.itertuples():
        a, b = r.pair
        k = fuels.index(r.fuel)
        p, q = (ap.at[a, "lon"], ap.at[a, "lat"]), (ap.at[b, "lon"], ap.at[b, "lat"])
        ax.add_patch(FancyArrowPatch(p, q, arrowstyle="-", color=FUEL_COLOURS[r.fuel],
                                     lw=0.6 + 0.45 * r.flights, alpha=0.9, capstyle="round",
                                     connectionstyle=f"arc3,rad={0.08 + 0.12 * k}", zorder=2))
    dep = F.groupby("origin")["flights"].sum().reindex(ap.index, fill_value=0)
    ax.scatter(ap.lon, ap.lat, s=60 + 6 * dep, c=SURFACE, edgecolors=INK, linewidths=1.5, zorder=3)
    for iata, r in ap.iterrows():
        supply = " · ".join(FUEL_LABELS[f] for f in fuels if f in r.fuels and f != "kerosene")
        ax.annotate(f"{iata}  (tier {r.tier})\n{supply}", (r.lon, r.lat), xytext=(9, 6),
                    textcoords="offset points", fontsize=8.5, color=INK, zorder=4)
    ax.set_aspect(1 / np.cos(np.radians(ap.lat.mean())))
    ax.margins(0.18)
    ax.set_xlabel("Longitude (°)"); ax.set_ylabel("Latitude (°)")
    ax.grid(color=GRID, lw=0.6); ax.set_axisbelow(True)
    used = [f for f in fuels if f in set(agg.fuel)]
    handles = [Line2D([], [], color=FUEL_COLOURS[f], lw=3, label=FUEL_LABELS[f]) for f in used]
    handles += [Line2D([], [], color=INK2, lw=0.6 + 0.45 * n, label=f"{n} flights/day")
                for n in (2, 6)]
    ax.legend(handles=handles, loc="lower left", bbox_to_anchor=(1.04, 0.0), frameon=False,
              fontsize=8.5)
    k = sol.kpis
    ax.set_title(title or f"{k['flights']} flights/day · {k['aircraft']} aircraft",
                 loc="left", fontsize=11, pad=22)
    ax.text(0, 1.015, "Labels: airport tier and alternative fuels supplied (kerosene everywhere)",
            transform=ax.transAxes, fontsize=8, color=INK2, va="bottom")
    return ax


def tail_gantt(inp: Inputs, legs: pd.DataFrame, title: str = "", ax=None):
    tails = list(dict.fromkeys(legs["tail_id"]))
    ax = ax or plt.subplots(figsize=(10, 0.45 * len(tails) + 1.2))[1]
    y = {t: i for i, t in enumerate(tails)}
    for r in legs.itertuples():
        w = r.arr_h - r.dep_h
        ax.barh(y[r.tail_id], w, left=r.dep_h, height=0.62, color=FUEL_COLOURS[r.fuel],
                edgecolor=SURFACE, linewidth=2)
        if w > 0.8:
            ax.text(r.dep_h + w / 2, y[r.tail_id], f"{r.origin}–{r.destination}", ha="center",
                    va="center", fontsize=5.8 if w < 1.2 else 6.5, color="white")
    ax.set_yticks(range(len(tails)), tails, fontsize=8)
    ax.invert_yaxis()
    ax.set_xlim(inp.op_start_h - 0.25, inp.op_end_h + 0.25)
    ax.set_xticks(range(int(inp.op_start_h), int(inp.op_end_h) + 1, 2),
                  [f"{h:02d}:00" for h in range(int(inp.op_start_h), int(inp.op_end_h) + 1, 2)])
    ax.grid(axis="x", color=GRID, lw=0.6); ax.set_axisbelow(True)
    ax.spines["left"].set_visible(False)
    used = [f for f in FUEL_COLOURS if f in set(legs.fuel)]
    ax.legend(handles=[Patch(color=FUEL_COLOURS[f], label=FUEL_LABELS[f]) for f in used],
              loc="upper left", bbox_to_anchor=(1.0, 1.0), frameon=False, fontsize=8.5)
    ax.set_title(title or "Daily tail rotations", loc="left", fontsize=11)
    return ax


def scenario_comparison(sols: dict[str, Solution]):
    """CO2 and fuel cost by fuel for each scenario (two panels, one measure each)."""
    rows = []
    for name, s in sols.items():
        g = s.flights.assign(co2=s.flights.flights * s.flights.co2_t,
                             cost=s.flights.flights * s.flights.fuel_cost_usd / 1e3)
        for fuel, v in g.groupby("fuel")[["co2", "cost"]].sum().iterrows():
            rows.append(dict(scenario=name, fuel=fuel, co2=v.co2, cost=v.cost))
    D = pd.DataFrame(rows)
    names = list(sols)
    fig, axes = plt.subplots(1, 2, figsize=(11, 0.55 * len(names) + 1.6), sharey=True)
    for ax, col, label in zip(axes, ["co2", "cost"], ["Well-to-wake CO₂ (t/day)", "Fuel cost ($k/day)"]):
        left = np.zeros(len(names))
        for fuel in FUEL_COLOURS:
            v = D[D.fuel == fuel].set_index("scenario")[col].reindex(names, fill_value=0).values
            ax.barh(range(len(names)), v, left=left, height=0.6, color=FUEL_COLOURS[fuel],
                    edgecolor=SURFACE, linewidth=2, label=FUEL_LABELS[fuel])
            left += v
        base = left[0]
        for i, tot in enumerate(left):
            delta = "" if i == 0 else f"  ({100 * (tot / base - 1):+.0f}%)"
            ax.text(tot, i, f" {tot:,.0f}{delta}", va="center", fontsize=8.5, color=INK)
        ax.set_xlim(0, left.max() * 1.35)
        ax.set_xlabel(label); ax.grid(axis="x", color=GRID, lw=0.6); ax.set_axisbelow(True)
        ax.spines["left"].set_visible(False)
    axes[0].set_yticks(range(len(names)), names); axes[0].invert_yaxis()
    fig.suptitle("Scenario comparison (Δ vs baseline in brackets)", x=0.01, ha="left", fontsize=11)
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, loc="upper right", ncol=3, frameon=False, fontsize=8.5)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    return fig
