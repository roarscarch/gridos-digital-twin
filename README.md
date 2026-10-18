# GridOS — Smart Grid Digital Twin (Distribution Operations Console)

A software-based **digital twin** of a small radial electricity distribution network.
It simulates how the grid behaves under changing demand, solar generation and switching states,
monitors operating conditions like a control room, flags violations, and lets you test
corrective ideas **before touching a real network**.

> Status: working prototype (control-room build v0.3) — simulation only.
> **Not** a SCADA system, protection relay, or grid controller. No telecontrol.
> Deploy target: **Vercel or any Python host** — single FastAPI service, no Docker / CI-CD / database required.

---

## 1. What does this application do?

GridOS models one **33/11 kV primary substation** with two 11 kV radial feeders and runs a
**balanced AC power-flow (load flow)** on it. You change the operating point and it tells you:

- **Bus voltages** — in per-unit and kV, against the statutory band (0.95–1.05 pu).
- **Feeder & transformer loading** — actual current vs rated current, as %.
- **Power flows** — MW / Mvar per line, grid import, solar infeed, power factor.
- **Losses** — technical I²R + transformer losses, split into line vs transformer totals.
- **Alarms** — P1 critical / P2 high / P3 advisory (ISA-18.2 style) with recommended actions.
- **N-1 security** — what happens if any one line trips: which buses black out, worst loading.
- **Switching studies** — open/close feeder breakers and watch the network island and de-energize.

Think of it as three tools in one:

| Role | What you get |
|---|---|
| **Monitoring console** | Live-style system banner, alarm list with ACK, bay measurements, feeder boards, SOE log |
| **Study / what-if lab** | Demand & PV sliders, presets (evening peak, PV export, stress), base-case comparison, saved cases |
| **Planning screener** | N-1 contingency table, CSV exports, JSON telemetry snapshot |

---

## 2. How to use it

### Run it (2 minutes)

```bash
cd power_system
python3 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn backend.app.main:app --reload --port 8000
```

Open **http://localhost:8000/** — the console loads and runs a baseline load flow automatically.
API docs (Swagger): **http://localhost:8000/docs**.

### The console, panel by panel

**Top banner** — grid status at a glance: `● SYSTEM NORMAL` (green) → `HIGH-PRIORITY` (amber) →
`N CRITICAL ALARMS` (pulsing red), plus live P1/P2/P3 counts, minimum voltage, maximum loading,
total losses and power factor.

**🎚 Operating point (left column)**

- **System demand slider (0.2–2.5 pu)** — scales every load (P and Q together, constant power factor).
  Readout shows the resulting total MW.
- **PV infeed slider (0–2.0 pu)** — scales both rooftop solar units (unity power factor).
- **Preset chips** — one click: Normal day · 🌆 Evening peak (high load, no sun) ·
  ☀️ Midday PV export (light load, surplus sun) · 🔥 N-0 stress (2.2× load, night) · 🌙 Night valley.
- **`live` checkbox** — re-runs the load flow as you drag (debounced ~350 ms). Uncheck for manual control.

**🔀 Switching (N-1)** — four feeder breaker cards (L1-2, L2-3, L1-4, L4-5). Click to OPEN/CLOSE.
Opening a head-end line (L1-2 or L1-4) **islands its feeder**: downstream buses read `DEAD`,
`DE-ENERGIZED` P1 alarms fire, and the event is written to the operations log — exactly what a
radial feeder does with no alternate supply. You can also click the ■ breaker squares on the diagram.

**🗺 11 kV single-line diagram** — substation bay layout, left → right:
`GRID 33kV source → T1 (two-circle transformer symbol, ONAN 5 MVA) → vertical 11 kV busbar →
Feeder A (top) / Feeder B (bottom)`. Animated dashes + arrows show flow direction; pill badges show
live loading %; `✕ … OPEN` red pills mark open lines; grey dashed nodes are de-energized.
Click any bay, transformer, line or bus for equipment data (voltage, angle, amps vs rated, MW, losses).

**🚨 Alarm & event list** — every breach with priority (P1/P2/P3), observed vs limit value,
cause message and recommended action. Filter tabs (All / P1 / P2 / P3). **ACK** acknowledges an
alarm into the operations log (ISA-18.2 acknowledge practice).

**📊 Bay measurements (tabs)**

- *Bus V* — bar chart with green statutory-band shading (0.95–1.05 pu).
- *Feeder loading* — thermal loading vs continuous rating, transformer included.
- *Power balance* — doughnut of PV infeed vs grid import vs losses.
- *N-1 summary* — press **🔀 N-1 screen**: opens each line in turn and tabulates P1 count,
  worst loading and minimum voltage per outage, with a chart.

**🔌 Feeder boards** — per-feeder demand, PV, net load, head-end current (A vs rated A) with bar.

**📜 Operations log (SOE)** — timestamped sequence of events: switching actions, acknowledged alarms,
saved cases, plus your own free-text notes (`+ log`). Newest first, in-memory.

**📁 Saved cases + 🧾 Telemetry snapshot** — save the current study (sliders + switching + full result),
click to reload it later; copy/download the raw JSON; export buses/lines/alarms as CSV.

### Try this (guided tour)

1. **Evening peak**: click 🌆 — watch T1 climb toward ~77%, voltages sag, P2 advisories appear.
2. **Stress it**: drag demand to 2.2×, PV to 0 — P1 overload/undervoltage alarms, red banner.
3. **Trip a feeder**: click breaker **L1-4** → Feeder B dies (`DEAD`, 0 MW), P1 de-energized alarms.
4. **N-1 screen**: press 🔀 — every single outage islands load (radial network, no ties).
5. **Compare**: ⚖ vs base case shows Δlosses, ΔT1, ΔP1 side by side.

---

## 3. What does it show? (every number, explained)

| Value | Where | Meaning |
|---|---|---|
| Bus voltage (pu / kV) | SLD nodes, V chart, JSON | `Vpu = Vactual / Vbase`. 1.000 = exactly nominal (11.00 kV on feeders, 33.66 kV at the grid source which is regulated to 1.02 pu). |
| Voltage angle (°) | asset detail, JSON | Phase angle vs the slack bus (Grid Supply = 0°). More negative downstream = power flowing outward. |
| Loading % | badges, loading chart, feeder boards | `Iactual / Irated × 100`. 100% = at continuous thermal rating (200 A per feeder, 5 MVA for T1). |
| Current (A) vs rated | asset detail, feeder boards | Head-end amps from the load flow vs nameplate rating. |
| P / Q (MW / Mvar) | nodes, detail, JSON | Active / reactive power. Loads consume both (pf ≈ 0.95); PV injects P only (unity pf). |
| Grid import (MW) | energy tab, JSON | What the 33 kV upstream grid must supply = demand − PV + losses. |
| Power factor | banner, JSON | `|P| / √(P²+Q²)` at the grid infeed. Drops when reactive demand is high relative to P. |
| Losses (MW) | banner, KPI, JSON | Technical losses: line I²R (`Σ pl_mw`) + transformer (`pl_mw`). Baseline ≈ 0.017 MW (~0.7% of demand). |
| P1 / P2 / P3 | banner, alarm list | Alarm counts by priority (§5). |
| N-1 table | N-1 tab | Per-outage: P1 count, worst surviving loading %, lowest energized voltage. |

---

## 4. Electrical principles & engineering behind it

### 4.1 AC power flow (the engine)

The core is a **balanced three-phase, steady-state AC load-flow** solved by
[pandapower](https://pandapower.readthedocs.io) (`runpp`, Newton–Raphson). For every bus `i` it solves the
nodal power-balance equations:

```
Pi = Vi · Σk Vk · (Gik·cos θik + Bik·sin θik)
Qi = Vi · Σk Vk · (Gik·sin θik − Bik·cos θik)
```

- **Grid Supply** is the *slack (swing) bus*: fixed at 1.02 pu / 0°, absorbs all mismatch — i.e. the
  infinite upstream transmission system.
- **Loads** are *PQ buses*: fixed P/Q draw, voltage solved.
- **Solar units** are *negative PQ injections* (P only, Q = 0).
- Solution must **converge**; divergence (islanding extremes, absurd setpoints) is reported as a P1
  `non_convergence` alarm, not silently hidden.

### 4.2 Per-unit system

All voltages are normalized: `Vpu = Vactual / Vbase` (11 kV feeders, 33 kV grid). Per-unit lets one
limit band (0.95–1.05) apply at every voltage level and matches utility practice (EN 50160 allows ±10%
for 95% of the week; we use the tighter ±5% planning band as the demo default).

### 4.3 Why voltage sags along a feeder

Current through series impedance `Z = R + jX` causes drop `ΔV ≈ (P·R + Q·X) / V`. So voltage falls
with distance from the substation, faster under heavy P/Q load — exactly why Feeder B2 (far end,
0.8 MW head-end load) is always the lowest bus, and why PV injection (negative P) *raises* local voltage.

### 4.4 Thermal loading

Each asset has a continuous current rating (feeders 200 A from `max_i_ka`; transformer 5 MVA).
Loading % = actual ÷ rated × 100. Sustained >100% overheats conductors/transformers (insulation aging,
sag, protection trip) — hence P1. The 90% (P2) and 75% (P3) bands are standard early-warning practice.

### 4.5 Losses

`Ploss = I²R` per line plus transformer copper (`I²·vkr`) and iron (`pfe`) losses. Losses grow with the
*square* of current — doubling load roughly quadruples line losses, which the loss KPI and compare view show.

### 4.6 Radial topology & islanding

The network is **radial** (one path from source to each load, no loops or tie-switches). Opening any
head-end breaker leaves downstream buses with **no source**: pandapower returns NaN voltages, which
GridOS reports as 0.0 pu + `DE-ENERGIZED` P1 alarms. This is physically correct for a radial feeder —
real DNOs restore such outages by mobile generation or normally-open tie points (a possible extension:
an A2–B2 tie-switch would turn N-1 into a *restoration* study instead of a guaranteed blackout).

### 4.7 N-1 security criterion

Transmission/distribution planners require the system to survive **any single credible outage** (N-1)
without violating limits. `/contingency` automates this screen: intact case + each line opened in turn.
Here every feeder-head outage fails (by design — radial), which itself demonstrates *why* utilities add
interconnection.

### 4.8 Alarm management (ISA-18.2 inspired)

Alarms carry **priority, dead-simple text, observed-vs-limit values and recommended action**:

| Priority | Trigger | Example |
|---|---|---|
| **P1 critical** | V outside [0.95, 1.05], loading >100%, de-energized, non-convergence | `L1-4: 112% above 100% — shed/transfer load` |
| **P2 high** | loading >90% | `T1: 94% — prepare contingency` |
| **P3 advisory** | loading >75%, V within 0.01 pu of a limit | `Feeder B2: 0.952 pu near limit — monitor` |

ACK writes to the SOE log, mimicking control-room acknowledge workflows.

### 4.9 What is *not* modelled (honest limits)

Balanced phases only (no unbalance/harmonics); steady-state (no transients, faults, protection timing);
constant-PQ loads (no voltage/thermal dependence); unity-pf PV (no inverter Q(V)/curtailment yet);
no tap-changers, capacitors, batteries, or state estimation. See §7.

---

## 5. Network model (as built)

```
                    GRID 33kV (slack, 1.02 pu)
                          │
                    T1 33/11kV · 5 MVA · uk 10% · ONAN
                          │
                    LV Main (11 kV busbar)
                    ┌─────┴─────┐
              L1-2 (1.5 km)   L1-4 (1.8 km)   ← 11 kV, R 0.161 / X 0.190 Ω/km, 200 A rated
                    │               │
              Feeder A1         Feeder B1
              0.6 MW + PV?      0.8 MW
                    │               │
              L2-3 (1.2 km)   L4-5 (1.0 km)
                    │               │
              Feeder A2         Feeder B2
              0.5 MW + 0.4 PV   0.6 MW + 0.3 PV
```

Baseline totals: demand **2.50 MW / 0.81 Mvar** (pf ≈ 0.95), PV **0.70 MW** → grid import ≈ 1.82 MW,
T1 ≈ 39%, losses ≈ 0.017 MW, all voltages 0.997–1.02 pu (clean). Defined in
`backend/app/grid/model.py` (`build_default_grid()`); limits in the same file
(`VMIN_PU=0.95, VMAX_PU=1.05, LOADING_MAX_PCT=100`).

---

## 6. API reference

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/` | the console UI |
| GET | `/health` | liveness (`{status, service, version}`) |
| GET | `/grid` | topology: substation, buses+zones, lines+ratings, transformer, loads, PV, limits |
| POST | `/simulate` | load flow: `{load_multiplier (0–5), solar_multiplier (0–3), open_lines[], include_alarms}` |
| GET | `/alarms?load_multiplier=&solar_multiplier=&open_lines=L1-4` | alarm list + P1/P2/P3 counts |
| GET | `/contingency?load_multiplier=&solar_multiplier=` | N-1 screen (intact + 4 outages) |
| POST | `/scenarios` | save study case `{name, …simulate fields}` |
| GET | `/scenarios` / `/scenarios/{id}` | list / fetch saved cases |
| POST | `/compare` | `{baseline, scenario}` → both results + Δlosses, ΔT1, ΔP1 |
| GET/POST | `/events?limit=` | SOE log list / append `{type, asset, message, actor}` |
| GET | `/export/{buses,lines,alarms}` | CSV downloads for the current operating point |

Example:

```bash
# evening peak with Feeder B tripped
curl -X POST localhost:8000/simulate -H 'Content-Type: application/json' \
  -d '{"load_multiplier":1.5,"solar_multiplier":0.15,"open_lines":["L1-4"]}'
```

---

## 7. Tech stack, repo map, tests, deploy

| Layer | Tech |
|---|---|
| Simulation | Python + pandapower (+ numpy/scipy) |
| API | FastAPI + Uvicorn |
| UI | Zero-build HTML/JS/CSS served by FastAPI (`/static`); SVG single-line, Chart.js |
| Tests | pytest + httpx (10 tests) |
| Deploy | Vercel (`vercel.json` + `api/index.py`) or any Python host |

```
power_system/
├── README.md
├── vercel.json · requirements.txt · api/index.py
├── backend/
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py            # FastAPI + all endpoints
│   │   ├── schemas.py         # Pydantic I/O models
│   │   ├── scenarios.py       # in-memory case store
│   │   ├── events.py          # SOE log
│   │   ├── exports.py         # CSV builders
│   │   ├── grid/model.py      # network builder (+ N-1 switching)
│   │   ├── grid/power_flow.py # run_simulation() → SCADA-style telemetry
│   │   ├── analysis/violations.py  # P1/P2/P3 alarm engine
│   │   └── static/            # console UI (index.html, app.js, style.css)
│   └── tests/                 # test_power_flow.py, test_api.py
└── data/                      # load_profile.csv, solar_profile.csv (future time-series)
```

```bash
pytest backend/tests -v   # 10 passed: build, convergence, bands, overload, N-1 islanding, API, exports
```

**Deploy (Vercel):** push to GitHub → Vercel → New Project → import (framework *Other*, no build
command). `vercel.json` routes everything to the FastAPI app; UI at `/`, API at `/docs`.
Note: pandapower+scipy ≈ 100 MB — fine on Python 3.12 serverless in practice; fallback one-click
hosts: Render/Railway with `uvicorn backend.app.main:app`. Cloudflare Workers can't run pandapower.

---

## 8. Safety & limitations

Simulation and decision-support only. **Not** protection, certified control, or authority to switch
real plant. Balanced-model results must be validated against utility benchmarks before any real-world
use; real deployments need engineering review, operational safeguards, cybersecurity and regulatory
controls. Demo limits (0.95–1.05 pu, 90/75% bands) are illustrative defaults.

## 9. Roadmap

- [ ] Normally-open A2–B2 tie → N-1 *restoration* study (close tie, re-energize)
- [ ] 15-min time-series playback (`data/*.csv`) with play button
- [ ] OLTC / capacitor / PV Q(V) controls + verify-by-re-run optimizer
- [ ] Battery dispatch, EV charging, Postgres persistence (only if needed)

---

## 10. Talking about GridOS in interviews

*How to frame it in one line:*
> "I built a digital twin of a distribution substation — pandapower AC load flow behind a
> FastAPI service with a control-room-style UI: live alarms, N-1 contingency screening and
> breaker switching studies." ($_10 tests green, deployable to Vercel._)

### The 60-second demo script

1. Open `/` — "This is a simulated 33/11 kV primary substation with two radial 11 kV feeders."
2. Click 🌆 *Evening peak* — "Watch the transformer climb, voltages sag. That's ΔV ≈ (PR+XQ)/V."
3. Drag demand to 2.2× — "P1 alarms fire, banner goes red — thermal and voltage limits enforced."
4. Open breaker **L1-4** — "Radial feeder islands: buses de-energize, SOE log records the switching."
5. Hit **🔀 N-1 screen** — "Automated single-outage screening, the standard planner's security check."

### Questions you'll likely get (and strong answers)

| They ask | You answer |
|---|---|
| *Why pandapower?* | Production-grade Newton–Raphson load flow, scriptable, benchmarked — let me focus on the product instead of writing a solver. |
| *Why FastAPI, not Django?* | Async API with auto-validated Pydantic schemas and free Swagger docs; UI is zero-build static so one process serves everything — ideal for a serverless demo. |
| *How do you know the physics is right?* | Regression tests: baseline voltages in band, losses non-negative and split correctly, heavy-load flags overloads, N-1 islands verified against pandapower NaN-bus behavior. Plus EN 50160 ±5% band as the limit reference. |
| *What breaks at scale?* | In-memory stores reset on redeploy (fine for demo; Postgres/Timescale next). Load flow is per-request synchronous — for large networks I'd add a task queue + caching and move time-series to a proper TSDB. |
| *Why radial? Why no loops?* | Deliberate: radial is the dominant real-world LV/MV topology, and it makes islanding honest — an outage *should* black out load without ties. A normally-open tie is the natural next feature. |
| *P1/P2/P3 — where's that from?* | ISA-18.2 alarm-management practice: prioritize by consequence, give every alarm a recommended action, support acknowledge-to-SOE workflow. |
| *What would you add with 2 more weeks?* | Tie-switch restoration study, 15-min time-series playback from `data/*.csv`, OLTC tap control with verify-by-re-run, then Postgres persistence. (Matches §9 Roadmap.) |
| *Is this safe to connect to a real grid?* | No — and I say that upfront in the UI and README. No protection modelling, no transients, no cybersecurity controls. It's study/decision-support software. |

### Skills this project demonstrates (use these keywords)

- **Power systems:** AC load flow, per-unit analysis, voltage regulation, thermal ratings,
  I²R losses, radial protection/islanding concepts, N-1 security, EN 50160.
- **Backend:** FastAPI, Pydantic validation, REST design, CSV/JSON exports, pytest (unit +
  regression + API integration), NaN-safety in numerical pipelines.
- **Frontend:** SVG single-line diagrams, Chart.js telemetry, operator-UX (alarms, ACK, SOE log),
  zero-build static serving.
- **Engineering judgment:** honest scoping (what's *not* modelled), safety disclaimers, alarm
  philosophy, tradeoff notes (serverless size limits, in-memory vs Postgres).

### If they want to dig deeper

- Point them at `backend/app/grid/power_flow.py` (telemetry pipeline + NaN handling) and
  `backend/app/analysis/violations.py` (alarm bands).
- Show `/docs` Swagger live, then `pytest backend/tests -v` in the terminal.
- Have one opinion ready: e.g. *"The most valuable next feature is the tie-switch, because it
  turns N-1 from a guaranteed-blackout demo into a real restoration study."*
