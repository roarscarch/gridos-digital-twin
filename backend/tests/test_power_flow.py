"""Power-flow / violation tests (no server needed)."""
from backend.app.grid.model import build_default_grid, VMIN_PU, VMAX_PU
from backend.app.grid.power_flow import run_simulation


def test_grid_builds():
    net = build_default_grid()
    assert len(net.bus) == 6
    assert len(net.line) == 4
    assert len(net.trafo) == 1
    assert len(net.load) == 4
    assert len(net.sgen) == 2


def test_baseline_converges_and_in_band():
    r = run_simulation(1.0, 1.0)
    assert r["converged"] is True
    for b in r["buses"]:
        assert VMIN_PU - 0.02 <= b["voltage_pu"] <= VMAX_PU + 0.05, b
    assert r["total_losses_mw"] >= 0
    assert abs((r["line_losses_mw"] + r["trafo_losses_mw"]) - r["total_losses_mw"]) < 1e-6


def test_heavy_load_flags_violation():
    r = run_simulation(2.5, 0.0)
    assert r["converged"] is True
    assert len(r["violations"]) > 0
    types = {v["type"] for v in r["violations"]}
    assert types & {"undervoltage", "line_overload", "transformer_overload"}
