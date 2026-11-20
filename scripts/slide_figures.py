"""Figures for the Michaelmas presentation slides.

    uv run scripts/slide_figures.py

Needs the Ryanair data (scripts/make_ryanair_data.py, 1 and 4 days). Saves PNGs in
outputs/slides/, numbered by slide.
"""

from dataclasses import replace

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap

from altfuel import analysis, plots, validation
from altfuel.scenario_config import load_scenario
from altfuel.utils import OUTPUT_DIR

OUT = OUTPUT_DIR / "slides"

GREY, BLUE, GREEN, PURPLE, YELLOW = plots.COLOURS[:5]   # kerosene, LH2, LNG, then accents
DARK = "#3c4043"
LIGHT = "#e8eaed"
BASES = LinearSegmentedColormap.from_list("bases", ["#ddd3f2", "#4b2a8a"])   # light to dark purple

plt.rcParams.update({
    "font.size": 14, "axes.titlesize": 16, "axes.labelsize": 14, "legend.fontsize": 13,
    "axes.spines.top": False, "axes.spines.right": False, "axes.facecolor": "white",
    "axes.edgecolor": DARK, "axes.labelcolor": DARK, "xtick.color": DARK, "ytick.color": DARK,
})


def save(fig, name):
    """Save a slide figure (white background, trimmed) and close it."""
    fig.savefig(OUT / f"{name}.png", dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def fuel_shares(kpis):
    """Percentage of flights on each fuel."""
    return {"kerosene": kpis["share_kerosene"] * 100, "lng": kpis["share_ch4"] * 100,
            "lh2": kpis["share_lh2"] * 100}


def legend_outside(ax):
    """Legend to the right of the plot, top entry first (as stacked from the bottom)."""
    handles, labels = ax.get_legend_handles_labels()
    ax.legend(handles[::-1], labels[::-1], loc="upper left", bbox_to_anchor=(1.01, 1), frameon=False)


# ---------- Ryanair ----------

def ryanair_run(name):
    """A Ryanair scenario, with Ryanair's real aircraft count and the next-flight check."""
    run = analysis.run(load_scenario(name))
    real = validation.real_rotations(run)
    run.real_aircraft = real.aircraft.nunique()
    run.turns = validation.same_next_flight(run, real)
    return run


def ryanair_network(run):
    """Slide 1: every route the kept aircraft flew that day. Bubble area = aircraft that
    start the day there (on the ground at 01:00 UTC)."""
    airports = run.data.airports
    based = validation.aircraft_per_base(validation.real_rotations(run), "aircraft")

    fig, ax = plt.subplots(figsize=(10, 8))
    pairs = run.data.legs[["origin", "destination"]].drop_duplicates()
    for o, d in zip(pairs.origin, pairs.destination):
        ax.plot(airports.lon[[o, d]], airports.lat[[o, d]], color=BLUE, lw=0.4, alpha=0.35, zorder=1)
    ax.scatter(airports.lon, airports.lat, s=8, color=DARK, zorder=2)
    bubbles = ax.scatter(airports.lon[based.index], airports.lat[based.index], s=based * 12,
                         c=based, cmap=BASES, vmin=0, alpha=0.85, edgecolor="white", lw=1, zorder=3)
    for station in based.index[:6]:
        ax.annotate(station, (airports.lon[station], airports.lat[station]), xytext=(8, 8),
                    textcoords="offset points", fontsize=12, color=DARK, zorder=4)

    ax.set_xlim(airports.lon.min() - 2, airports.lon.max() + 2)
    ax.set_ylim(airports.lat.min() - 1, airports.lat.max() + 1)
    ax.set_aspect(1.5)
    plots.draw_land(ax)
    ax.set_facecolor("#f7fafc")
    ax.set_xticks([])
    ax.set_yticks([])
    for side in ["top", "right", "bottom", "left"]:
        ax.spines[side].set_visible(False)
    # Bubble size and colour both grow with the aircraft based there; the colour bar reads it off
    bar = fig.colorbar(bubbles, ax=ax, shrink=0.5, pad=0.02)
    bar.set_label("Aircraft based")
    bar.outline.set_visible(False)
    save(fig, "1_ryanair_network")


def validation_figure(one_day, four_days):
    """Slide 7: aircraft needed, real vs model, and the forced next flights."""
    fig, (left, right) = plt.subplots(1, 2, figsize=(12, 4.8), gridspec_kw={"width_ratios": [1.1, 1]})

    labels = ["1 day\n17 Sep 2025", "4 days\n17–20 Sep 2025"]
    real = [one_day.real_aircraft, four_days.real_aircraft]
    model = [one_day.kpis["aircraft"], four_days.kpis["aircraft"]]
    x = [0, 1]
    left.bar([i - 0.2 for i in x], real, width=0.38, color=PURPLE, label="Ryanair (real)")
    left.bar([i + 0.2 for i in x], model, width=0.38, color=BLUE, label="Model")
    for i in x:
        left.text(i - 0.2, real[i] + 5, real[i], ha="center", fontsize=13)
        left.text(i + 0.2, model[i] + 5, model[i], ha="center", fontsize=13)
    left.set_xticks(x, labels)
    left.set_ylabel("Aircraft needed")
    left.set_ylim(0, max(real) * 1.2)
    left.legend(frameon=False, loc="upper right")

    turns = one_day.turns
    shares = [turns[turns.alone].same.mean() * 100, turns[~turns.alone].same.mean() * 100]
    right.barh([1, 0], shares, color=[BLUE, LIGHT], height=0.5)
    for y, share in zip([1, 0], shares):
        right.text(share + 2, y, f"{share:.0f}%", va="center", fontsize=14)
    right.set_yticks([1, 0], ["One aircraft\non the ground", "Several aircraft\non the ground"])
    right.set_xlim(0, 115)
    right.set_xlabel("Same next flight as Ryanair (%)")
    fig.tight_layout(w_pad=4)
    save(fig, "7_validation")


def bases_scatter(one_day):
    """Backup: aircraft per night stop, real vs model."""
    real = validation.aircraft_per_base(validation.real_rotations(one_day), "aircraft")
    model = validation.aircraft_per_base(one_day.rotations, "tail_id")
    both = pd.DataFrame({"real": real, "model": model}).fillna(0)

    fig, ax = plt.subplots(figsize=(6, 6))
    top = both.max().max() + 3
    ax.plot([0, top], [0, top], color=GREY, lw=1, ls="--", zorder=1)
    ax.scatter(both.real, both.model, s=60, color=BLUE, alpha=0.7, edgecolor="white", zorder=2)
    ax.set_xlim(0, top)
    ax.set_ylim(0, top)
    ax.set_xlabel("Aircraft based at each airport: Ryanair")
    ax.set_ylabel("Aircraft based at each airport: model")
    save(fig, "backup_aircraft_per_base")


def fuel_at_airports():
    """Slide 8: the real Ryanair day at 200 $/t with LH2 and LNG sold only at the busiest
    N airports (most Ryanair flights first); kerosene everywhere."""
    base = load_scenario("ryanair_1d")
    legs = pd.read_csv(base.data_path / "legs.csv")
    busiest = list(pd.concat([legs.origin, legs.destination]).value_counts().index)
    rows = []
    for n in [5, 10, 20, 40, 80, len(busiest)]:
        top = busiest[:n]
        sc = replace(base, carbon_price=200, fleet={"KER-NB": 1000, "LH2-NB": 1000, "CH4-NB": 1000},
                     fuel_max_tier={"lh2": 0, "ch4": 0}, fuel_stations={"lh2": top, "ch4": top})
        rows.append({"airports": n, **fuel_shares(analysis.run(sc).kpis)})
    sweep = pd.DataFrame(rows)
    sweep.round(1).to_csv(OUT / "8_fuel_at_airports.csv", index=False)

    fig, ax = plt.subplots(figsize=(10, 5))
    x = range(len(sweep))
    ax.bar(x, sweep.kerosene, color=GREY, label="Kerosene")
    ax.bar(x, sweep.lng, bottom=sweep.kerosene, color=GREEN, label="LNG")
    ax.bar(x, sweep.lh2, bottom=sweep.kerosene + sweep.lng, color=BLUE, label="LH₂")
    names = [str(n) for n in sweep.airports[:-1]] + [f"All {sweep.airports.iloc[-1]}"]
    ax.set_xticks(x, names)
    ax.set_ylim(0, 100)
    ax.set_xlabel("Airports selling LH₂ and LNG (busiest first)")
    ax.set_ylabel("Flights (%)")
    legend_outside(ax)
    save(fig, "8_fuel_at_airports")


# ---------- Fuels on the test network ----------

# Out-and-back test network: LH2 at 2 airports, LNG at 3, kerosene at all 5
TIERS = {"fuel_max_tier": {"lh2": 0, "ch4": 0},
         "fuel_stations": {"lh2": ["LHR", "MAD"], "ch4": ["LHR", "MAD", "CDG"]}}
TIERED = replace(load_scenario("alt_carbon_200"), **TIERS)


def carbon_sweep():
    """Fuel mix, CO2 and cost at each carbon price, against the all-kerosene baseline."""
    def cost_of_flying(k):
        """Fuel, crew, maintenance and aircraft: everything except the carbon price itself."""
        return k["operating_cost_usd"] - k["carbon_cost_usd"] + k["ownership_cost_usd"]

    baseline = analysis.run(load_scenario("baseline")).kpis
    rows = []
    for price in range(0, 401, 25):
        k = analysis.run(replace(TIERED, carbon_price=price)).kpis
        rows.append({"price": price, **fuel_shares(k),
                     "co2_cut": 100 * (1 - k["co2_t"] / baseline["co2_t"]),
                     "cost_rise": 100 * (cost_of_flying(k) / cost_of_flying(baseline) - 1)})
    return pd.DataFrame(rows)


def fuel_mix(sweep):
    """Slide 8: share of flights on each fuel as the carbon price rises."""
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.stackplot(sweep.price, sweep.kerosene, sweep.lng, sweep.lh2, step="post",
                 colors=[GREY, GREEN, BLUE], labels=["Kerosene", "LNG", "LH₂"])
    ax.set_xlim(0, 400)
    ax.set_ylim(0, 100)
    ax.set_xlabel("Carbon price ($ per tonne CO₂)")
    ax.set_ylabel("Flights (%)")
    legend_outside(ax)
    save(fig, "8_fuel_mix")


def cost_vs_co2(sweep):
    """Backup: CO2 cut against the extra cost of flying (fuel, crew, maintenance, aircraft;
    not the carbon price itself), one point per carbon price."""
    fig, ax = plt.subplots(figsize=(8, 5.5))
    ax.plot(sweep.cost_rise, sweep.co2_cut, color=GREY, lw=1.5, zorder=1)
    ax.scatter(sweep.cost_rise, sweep.co2_cut, s=70, color=BLUE, zorder=2)
    for r in sweep.drop_duplicates("co2_cut").itertuples():
        ax.annotate(f"{r.price} $/t", (r.cost_rise, r.co2_cut), xytext=(8, -14),
                    textcoords="offset points", fontsize=12, color=DARK)
    ax.set_xlabel("Cost of flying vs all kerosene (%)")
    ax.set_ylabel("CO₂ cut vs all kerosene (%)")
    ax.grid(color=LIGHT)
    save(fig, "backup_cost_vs_co2")


def lh2_routes():
    """Slide 8: which routes each fuel takes at 200 $/t."""
    fig = plots.network_map(analysis.run(TIERED))
    ax = fig.axes[0]
    ax.set_title("", loc="left")
    for text in ax.texts:
        if text.get_text().startswith("Numbers"):     # the explanation goes on the slide instead
            text.remove()
    save(fig, "8_routes_by_fuel")


def retiming():
    """Slide 9: flights on LH2 or LNG as departures may move later, for two refuelling rules,
    on the tight low-cost timetable with the same fuel airports as slide 8. (The out-and-back
    timetable has enough slack that the rule makes no difference.)"""
    base = replace(load_scenario("lcc_carbon_200"), **TIERS)
    delays = [0, 10, 20, 30, 45, 60]
    fig, ax = plt.subplots(figsize=(10, 5))
    for name, rule, colour, width, style in [
            ("Refuelling while passengers board", [], GREEN, 6, "-"),
            ("No passengers aboard while refuelling", base.sequential_refuel, PURPLE, 2.5, "--")]:
        share = []
        for d in delays:
            sc = replace(base, sequential_refuel=rule, max_delay_min=d, delay_step_min=5)
            k = analysis.run(sc).kpis
            share.append((k["share_lh2"] + k["share_ch4"]) * 100)
        ax.plot(delays, share, style, marker="o", lw=width, ms=width + 5, color=colour, label=name)
    ax.set_xticks(delays)
    ax.set_ylim(-1, 25)
    ax.set_xlabel("Departures allowed to move later by up to (minutes)")
    ax.set_ylabel("Flights on LH₂ or LNG (%)")
    ax.legend(frameon=False, loc="upper left", bbox_to_anchor=(1.01, 1))
    ax.grid(axis="y", color=LIGHT)
    save(fig, "9_retiming")


# ---------- Method diagram ----------

def time_space_network():
    """Slide 6: a small time-space network. Each airport is a timeline; flights go
    between timelines; aircraft wait along them; the last wait wraps to the next morning."""
    stations = {"Dublin": 2, "London": 1, "Madrid": 0}
    turn = 0.5
    aircraft = {BLUE: [("Dublin", "London", 6.0, 7.2), ("London", "Madrid", 8.0, 10.4),
                       ("Madrid", "London", 11.2, 13.6), ("London", "Dublin", 15.0, 16.2)],
                PURPLE: [("Madrid", "Dublin", 7.0, 9.6), ("Dublin", "Madrid", 10.5, 13.1),
                         ("Madrid", "Dublin", 16.5, 19.1)]}

    fig, ax = plt.subplots(figsize=(12, 4.8))
    for name, y in stations.items():
        ax.plot([5, 21], [y, y], color=LIGHT, lw=6, solid_capstyle="round", zorder=0)
        ax.text(4.8, y, name, ha="right", va="center", fontsize=14, color=DARK)
    for colour, flights in aircraft.items():
        for o, d, dep, arr in flights:
            ax.annotate("", (arr, stations[d]), (dep, stations[o]),
                        arrowprops=dict(arrowstyle="-|>", color=colour, lw=2.5, shrinkA=0, shrinkB=0))
            ax.plot([arr, arr + turn], [stations[d]] * 2, color=YELLOW, lw=6, zorder=1)
        for (_, d, _, arr), (o, _, dep, _) in zip(flights, flights[1:]):
            ax.plot([arr + turn, dep], [stations[d]] * 2, color=colour, lw=2, ls=":", zorder=1)
        departures = [(dep, stations[o]) for o, _, dep, _ in flights]
        ax.scatter(*zip(*departures), s=40, color=colour, zorder=3)

    ax.plot([], [], color=BLUE, lw=2.5, label="Flight (aircraft 1)")
    ax.plot([], [], color=PURPLE, lw=2.5, label="Flight (aircraft 2)")
    ax.plot([], [], color=YELLOW, lw=6, label="Turn (unload, refuel, board)")
    ax.plot([], [], color=DARK, lw=2, ls=":", label="Waiting on the ground")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=4, frameon=False, fontsize=12)
    ax.set_xlim(4, 21.5)
    ax.set_ylim(-0.5, 2.5)
    ax.set_xticks(range(6, 22, 3), [f"{h:02d}:00" for h in range(6, 22, 3)])
    ax.set_yticks([])
    ax.spines["left"].set_visible(False)
    save(fig, "6_time_space_network")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    one_day, four_days = ryanair_run("ryanair_1d"), ryanair_run("ryanair_4d")
    ryanair_network(one_day)
    validation_figure(one_day, four_days)
    bases_scatter(one_day)
    fuel_at_airports()
    time_space_network()
    sweep = carbon_sweep()
    fuel_mix(sweep)
    cost_vs_co2(sweep)
    lh2_routes()
    retiming()
    print(f"saved in {OUT}")
