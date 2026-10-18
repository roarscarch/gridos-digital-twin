"""GridOS FastAPI app — also serves the static UI (no separate frontend build)."""
import os
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from .schemas import SimulateRequest, SimulateResponse, ScenarioCreate, CompareRequest, EventIn
from .grid.model import build_default_grid, BASE_LOADS, BASE_SGEN, VMIN_PU, VMAX_PU, LOADING_MAX_PCT, LINE_NAMES
from .grid.power_flow import run_simulation
from . import scenarios, events
from .exports import buses_csv, lines_csv, alarms_csv

app = FastAPI(title="GridOS Digital Twin", version="0.2.0",
              description="Simulated distribution-grid digital twin — control-room prototype")

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def root():
    idx = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(idx):
        return FileResponse(idx)
    return {"name": "GridOS", "docs": "/docs", "health": "/health"}


@app.get("/health")
def health():
    return {"status": "ok", "service": "gridos", "version": "0.2.0"}


@app.get("/grid")
def get_grid():
    net = build_default_grid()
    buses = [{"id": int(i), "name": net.bus.name[i], "vn_kv": float(net.bus.vn_kv[i]),
               "zone": ("33kV grid" if float(net.bus.vn_kv[i]) > 20 else ("Nodal substation" if net.bus.name[i] == "LV Main" else ("Feeder A" if "A" in net.bus.name[i] else ("Feeder B" if "B" in net.bus.name[i] else "LV"))))}
             for i in net.bus.index]
    lines = [{"id": int(i), "name": net.line.name[i],
              "from_bus": net.bus.name[net.line.from_bus[i]],
              "to_bus": net.bus.name[net.line.to_bus[i]],
              "length_km": float(net.line.length_km[i]),
              "rated_a": round(float(net.line.max_i_ka[i]) * 1000, 1),
              "feeder": ("A" if net.line.name[i] in ("L1-2", "L2-3") else "B")}
             for i in net.line.index]
    trafos = [{"name": net.trafo.name[i], "hv_bus": net.bus.name[net.trafo.hv_bus[i]],
               "lv_bus": net.bus.name[net.trafo.lv_bus[i]],
               "sn_mva": float(net.trafo.sn_mva[i]), "vk_pct": float(net.trafo.vk_percent[i])} for i in net.trafo.index]
    return {"substation": "GRIDOS 33/11kV PRIMARY SUBSTATION", "feeders": ["Feeder A", "Feeder B"],
            "buses": buses, "lines": lines, "transformers": trafos,
            "loads": BASE_LOADS, "solar": BASE_SGEN,
            "limits": {"vmin": VMIN_PU, "vmax": VMAX_PU, "loading_max": LOADING_MAX_PCT,
                         "warn_loading": 90.0, "advisory_loading": 75.0}}


@app.post("/simulate", response_model=SimulateResponse)
def simulate(req: SimulateRequest):
    for ln in req.open_lines:
        if ln not in LINE_NAMES:
            raise HTTPException(400, f"unknown line '{ln}'. Valid: {LINE_NAMES}")
    return run_simulation(req.load_multiplier, req.solar_multiplier,
                          open_lines=req.open_lines, include_alarms=req.include_alarms)


@app.get("/alarms")
def get_alarms(load_multiplier: float = 1.0, solar_multiplier: float = 0.8,
               open_lines: str = Query("", description="comma-separated line names")):
    opened = [x.strip() for x in open_lines.split(",") if x.strip()] if open_lines else []
    r = run_simulation(load_multiplier, solar_multiplier, open_lines=opened)
    return {"alarms": r["alarms"], "violations": r["violations"],
            "counts": {"P1": sum(1 for a in r["alarms"] if a.get("priority") == "P1"),
                         "P2": sum(1 for a in r["alarms"] if a.get("priority") == "P2"),
                         "P3": sum(1 for a in r["alarms"] if a.get("priority") == "P3")}}


@app.get("/contingency")
def contingency(load_multiplier: float = 1.0, solar_multiplier: float = 1.0):
    """N-1 screening: open each line in turn, report worst alarms."""
    import math as _m
    def _num(x):
        return 0.0 if x is None or (isinstance(x, float) and _m.isnan(x)) else round(float(x), 2)
    base = run_simulation(load_multiplier, solar_multiplier)
    rows = [{"outage": "(none — intact)", "converged": base["converged"],
             "p1": sum(1 for a in base["alarms"] if a.get("priority") == "P1"),
             "worst_loading": _num(max([l["loading_percent"] for l in base["lines"]] + [base["transformer_loading_percent"]])),
             "min_v": _num(min([b["voltage_pu"] for b in base["buses"]]) if base["buses"] else 0.0)}]
    for ln in LINE_NAMES:
        r = run_simulation(load_multiplier, solar_multiplier, open_lines=[ln])
        rows.append({"outage": ln, "converged": r["converged"],
                     "p1": sum(1 for a in r["alarms"] if a.get("priority") == "P1"),
                     "alarms": [a["message"] for a in r["alarms"] if a.get("priority") == "P1"][:4],
                     "worst_loading": _num(max([l["loading_percent"] for l in r["lines"] if l.get("in_service", True)] + [r["transformer_loading_percent"]])) if r["converged"] else 0.0,
                     "min_v": _num(min([b["voltage_pu"] for b in r["buses"] if b.get("energized", True)] or [0.0]))})
    return {"results": rows}


@app.post("/scenarios")
def create_scenario(req: ScenarioCreate):
    result = run_simulation(req.load_multiplier, req.solar_multiplier, open_lines=req.open_lines)
    rec = scenarios.save_scenario(req.name, req.load_multiplier, req.solar_multiplier, result,
                                  open_lines=req.open_lines)
    events.log_event("scenario", "", f"Saved scenario #{rec['id']} '{req.name}'", "operator")
    return rec


@app.get("/scenarios")
def list_scenarios():
    return scenarios.list_scenarios()


@app.get("/scenarios/{sid}")
def get_scenario(sid: int):
    rec = scenarios.get_scenario(sid)
    if rec is None:
        raise HTTPException(404, "scenario not found")
    return rec


@app.post("/compare")
def compare(req: CompareRequest):
    ra = run_simulation(req.baseline.load_multiplier, req.baseline.solar_multiplier,
                        open_lines=req.baseline.open_lines)
    rb = run_simulation(req.scenario.load_multiplier, req.scenario.solar_multiplier,
                        open_lines=req.scenario.open_lines)
    return {"baseline": ra, "scenario": rb,
            "delta_losses_mw": round(rb["total_losses_mw"] - ra["total_losses_mw"], 5),
            "delta_trafo_loading": round(rb["transformer_loading_percent"] - ra["transformer_loading_percent"], 2),
            "delta_p1": sum(1 for a in rb["alarms"] if a.get("priority") == "P1") - sum(1 for a in rb["alarms"] if False) - (sum(1 for a in ra["alarms"] if a.get("priority") == "P1"))}


@app.get("/events")
def get_events(limit: int = 50):
    return events.list_events(limit)


@app.post("/events")
def post_event(ev: EventIn):
    return events.log_event(ev.type, ev.asset, ev.message, ev.actor)


@app.get("/export/buses")
def export_buses(load_multiplier: float = 1.0, solar_multiplier: float = 1.0):
    r = run_simulation(load_multiplier, solar_multiplier)
    return PlainTextResponse(buses_csv(r), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=gridos_buses.csv"})


@app.get("/export/lines")
def export_lines(load_multiplier: float = 1.0, solar_multiplier: float = 1.0):
    r = run_simulation(load_multiplier, solar_multiplier)
    return PlainTextResponse(lines_csv(r), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=gridos_lines.csv"})


@app.get("/export/alarms")
def export_alarms(load_multiplier: float = 1.0, solar_multiplier: float = 1.0):
    r = run_simulation(load_multiplier, solar_multiplier)
    return PlainTextResponse(alarms_csv(r), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=gridos_alarms.csv"})
