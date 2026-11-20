# Running the model yourself

Commands are typed in a terminal: PowerShell on Windows, Terminal on a Mac. Everything
runs from the project folder.

## 1. One-time setup

| Step | Windows (PowerShell) | Mac |
|---|---|---|
| Install git | <https://git-scm.com/download/win> | `xcode-select --install` |
| Install uv (installs Python and the packages for you) | `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 \| iex"` | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Get the code | `git clone https://github.com/HuiLinChew/airline-alt-fuel-transition` | same |
| Go into the folder | `cd airline-alt-fuel-transition` | same |
| Install the packages | `uv sync` | same |

Close and reopen the terminal after installing uv. To get the latest code later: `git pull`.

## 2. Everyday commands

| What | Command | Where the results go |
|---|---|---|
| Check the model works (about 10 s) | `uv run pytest` | prints `41 passed` |
| Run one scenario | `uv run scripts/run_one.py lcc_carbon_200` | prints the results; map and schedule in `outputs/one/` |
| Run every scenario | `uv run scripts/run_scenarios.py` | `outputs/<folder>/` and `outputs/scenario_summary.csv` |
| Slide figures (a few minutes; needs the Ryanair data, section 4) | `uv run scripts/slide_figures.py` | `outputs/slides/` |

## 3. Trying your own scenario

1. Copy a scenario file, e.g. `scenarios/lcc/lcc_carbon_200.yaml`, to
   `scenarios/lcc/my_test.yaml`.
2. Change `name:` to `my_test` and change the settings you want, e.g.
   `carbon_price: 300` or `max_delay_min: 30`. Every setting is listed in
   `docs/code_guide.md` (Scenario settings).
3. `uv run scripts/run_one.py my_test`

## 4. The Ryanair days (real data)

1. Log in to EUROCONTROL's Aviation Data Repository for Research
   (<https://ext.eurocontrol.int/prisme_data_provision_hmi/>) and download the **Flights** file
   for a month, e.g. `Flights_20250901_20250930.csv` (about 200 MB). The other files
   (trajectory points, airspace) aren't needed. The data may not be shared: keep it out of git.
2. Build the inputs (a minute or two): file, first day, number of days
   `uv run scripts/make_ryanair_data.py path/to/Flights_20250901_20250930.csv 2025-09-17 1`
   This writes `data/ryanair_1d/` (or `_4d`, `_7d` for 4 or 7 days), including the whole
   cleaned month as `flights_clean.csv`. Any date in that month works. There are scenarios for
   1, 4 and 7 days (`scenarios/ryanair/ryanair_1d.yaml` etc.); for another number of days,
   copy one and set `data_dir` and `period_min` (1440 × days).
3. Compare the model with what Ryanair really flew:
   `uv run scripts/compare_ryanair.py ryanair_1d` (table printed; `outputs/ryanair/`).
4. Run it like any other scenario: `uv run scripts/run_one.py ryanair_1d`.
   To try fuels on it, copy `scenarios/ryanair/ryanair_1d.yaml` and add, for example,
   `carbon_price: 200`, `fleet: {KER-NB: 1000, LH2-NB: 1000, CH4-NB: 1000}` and
   `fuel_stations: {lh2: [STN, DUB, BGY]}`.

## If something goes wrong

| Message | Fix |
|---|---|
| `uv` not recognised | Close and reopen the terminal after installing uv |
| `IndexError` from `load_scenario` | No scenario file with that name: check the `name` and file name match |
| `Infeasible` | No way to fly every leg with these settings. Try `allow_drop: true` to see which legs cause it |
| `skipped: no data/ryanair_1d/` | Run step 4.2 first |
