"""API tests via FastAPI TestClient."""
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)


def test_health():
    assert client.get("/health").json()["status"] == "ok"


def test_grid_topology():
    g = client.get("/grid").json()
    assert len(g["buses"]) == 6 and len(g["lines"]) == 4
    assert g["substation"].startswith("GRIDOS")


def test_simulate_ok_and_validation():
    r = client.post("/simulate", json={"load_multiplier": 1.2, "solar_multiplier": 0.8})
    assert r.status_code == 200
    body = r.json()
    assert body["converged"] is True
    assert "transformer_loading_percent" in body
    assert "alarms" in body and "pf" in body
    bad = client.post("/simulate", json={"load_multiplier": 99})
    assert bad.status_code == 422
    badline = client.post("/simulate", json={"open_lines": ["NOPE"]})
    assert badline.status_code == 400


def test_n1_switching_flags_deenergized():
    r = client.post("/simulate", json={"open_lines": ["L1-4"]})
    assert r.status_code == 200
    types = {v["type"] for v in r.json()["violations"]}
    assert "de_energized" in types


def test_alarms_and_contingency():
    a = client.get("/alarms").json()
    assert "counts" in a
    c = client.get("/contingency").json()
    assert len(c["results"]) == 5  # intact + 4 lines


def test_scenario_roundtrip():
    c = client.post("/scenarios", json={"name": "t", "load_multiplier": 1.5, "solar_multiplier": 0.5})
    assert c.status_code == 200
    sid = c.json()["id"]
    assert client.get(f"/scenarios/{sid}").status_code == 200
    assert len(client.get("/scenarios").json()) >= 1


def test_events_and_exports():
    e = client.post("/events", json={"type": "note", "message": "test"})
    assert e.status_code == 200
    assert len(client.get("/events").json()) >= 1
    assert "bus,vn_kv" in client.get("/export/buses").text
    assert "loading_pct" in client.get("/export/lines").text
