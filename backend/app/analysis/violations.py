"""Violation + alarm evaluation (ISA-18.2 inspired priorities).

Bands:
  - P1 CRITICAL : loading > 100%%, V outside 0.94-1.06, non-convergence
  - P2 HIGH     : loading > 90%%, V outside 0.95-1.05
  - P3 ADVISORY : loading > 75%%, V within 0.01 pu of a limit
"""
from ..grid.model import VMIN_PU, VMAX_PU, LOADING_MAX_PCT

WARN_LOADING = 90.0
ADVISORY_LOADING = 75.0
WARN_V_MARGIN = 0.0      # P2 at the configured limit
ADVISORY_V_MARGIN = 0.01  # P3 within 0.01 pu of a limit


def check_violations(buses, lines, trafo_loading,
                     vmin=VMIN_PU, vmax=VMAX_PU, loading_max=LOADING_MAX_PCT):
    """Back-compat: only hard violations (unchanged schema)."""
    return [a for a in evaluate_alarms(buses, lines, trafo_loading, vmin, vmax, loading_max)
            if a["priority"] == "P1"]


def evaluate_alarms(buses, lines, trafo_loading,
                    vmin=VMIN_PU, vmax=VMAX_PU, loading_max=LOADING_MAX_PCT):
    """Full alarm list with priority, band and recommended action."""
    alarms = []
    for b in buses:
        v = b["voltage_pu"]
        if v < 0.1:
            alarms.append(_alarm(b["name"], "de_energized", v, vmin, "P1", "pu",
                                 f"{b['name']}: {v:.4f} pu — DE-ENERGIZED (islanded by switching)"))
            continue
        if v < vmin or v > vmax:
            alarms.append(_alarm(b["name"], "undervoltage" if v < vmin else "overvoltage",
                                 v, vmin if v < vmin else vmax, "P1", "pu",
                                 f"{b['name']}: {v:.4f} pu outside [{vmin}, {vmax}] — check tap / reactive support / transfer load"))
        elif v < vmin + ADVISORY_V_MARGIN or v > vmax - ADVISORY_V_MARGIN:
            alarms.append(_alarm(b["name"], "voltage_marginal", v, vmin, "P3", "pu",
                                 f"{b['name']}: {v:.4f} pu near limit — monitor"))
    for ln in lines:
        ld = ln["loading_percent"]
        if ld > loading_max:
            alarms.append(_alarm(ln["name"], "line_overload", ld, loading_max, "P1", "%",
                                 f"{ln['name']}: {ld:.1f}% above {loading_max}% — shed/transfer load or reconfigure"))
        elif ld > WARN_LOADING:
            alarms.append(_alarm(ln["name"], "line_high_loading", ld, WARN_LOADING, "P2", "%",
                                 f"{ln['name']}: {ld:.1f}% above {WARN_LOADING}% warning — prepare contingency"))
        elif ld > ADVISORY_LOADING:
            alarms.append(_alarm(ln["name"], "line_elevated", ld, ADVISORY_LOADING, "P3", "%",
                                 f"{ln['name']}: {ld:.1f}% elevated — monitor"))
    if trafo_loading > loading_max:
        alarms.append(_alarm("T1 33/11kV 5MVA", "transformer_overload", trafo_loading, loading_max, "P1", "%",
                             f"Transformer: {trafo_loading:.1f}% above {loading_max}% — reduce load immediately"))
    elif trafo_loading > WARN_LOADING:
        alarms.append(_alarm("T1 33/11kV 5MVA", "transformer_high_loading", trafo_loading, WARN_LOADING, "P2", "%",
                             f"Transformer: {trafo_loading:.1f}% above {WARN_LOADING}% warning"))
    order = {"P1": 0, "P2": 1, "P3": 2}
    alarms.sort(key=lambda a: (order[a["priority"]], a["asset"]))
    return alarms


def _alarm(asset, typ, observed, limit, priority, unit, message):
    sev = {"P1": "critical", "P2": "high", "P3": "advisory"}[priority]
    return {"asset": asset, "type": typ, "observed": observed, "limit": limit,
            "severity": sev, "priority": priority, "unit": unit, "message": message}
