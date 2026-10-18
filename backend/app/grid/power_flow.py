"""Run AC power flow and serialize results (SCADA-style telemetry)."""
import math
import pandapower as pp
from .model import build_default_grid, VMIN_PU, VMAX_PU, LOADING_MAX_PCT
from ..analysis.violations import check_violations, evaluate_alarms


def run_simulation(load_multiplier: float = 1.0, solar_multiplier: float = 1.0,
                   open_lines=(), include_alarms: bool = True):
    net = build_default_grid(open_lines=open_lines)
    net.load.p_mw = net["_base_load_p"] * load_multiplier
    net.load.q_mvar = net["_base_load_q"] * load_multiplier
    net.sgen.p_mw = net["_base_sgen_p"] * solar_multiplier

    converged = True
    try:
        pp.runpp(net, numba=False)
    except Exception:
        converged = False

    total_load = round(float(net.load.p_mw.sum() * load_multiplier) if False else float((net["_base_load_p"] * load_multiplier).sum()), 4)
    total_solar = round(float((net["_base_sgen_p"] * solar_multiplier).sum()), 4)

    if not converged or net.get("converged", True) is False:
        viol = [{"asset": "solver", "type": "non_convergence", "observed": 0.0,
                 "limit": 0.0, "severity": "critical", "priority": "P1", "unit": "-",
                 "message": "Power flow did not converge. Check islanding / extreme setpoints."}]
        return {
            "converged": False, "buses": [], "lines": [], "transformer": {},
            "transformer_loading_percent": 0.0,
            "line_losses_mw": 0.0, "trafo_losses_mw": 0.0, "total_losses_mw": 0.0,
            "total_load_mw": total_load, "total_solar_mw": total_solar,
            "total_q_mvar": 0.0, "pf": 0.0, "violations": viol, "alarms": viol if include_alarms else [],
            "limits": {"vmin": VMIN_PU, "vmax": VMAX_PU, "loading_max": LOADING_MAX_PCT},
        }

    import math as _m
    buses, bus_p, bus_q = [], {}, {}
    for i in net.bus.index:
        vm = float(net.res_bus.vm_pu[i])
        va = float(net.res_bus.va_degree[i])
        islanded = _m.isnan(vm)
        p = 0.0 if islanded else float(net.res_bus.p_mw[i])
        q = 0.0 if islanded else float(net.res_bus.q_mvar[i])
        bus_p[net.bus.name[i]] = p; bus_q[net.bus.name[i]] = q
        buses.append({
            "name": net.bus.name[i], "vn_kv": float(net.bus.vn_kv[i]),
            "voltage_pu": 0.0 if islanded else round(vm, 4),
            "voltage_kv": 0.0 if islanded else round(vm * float(net.bus.vn_kv[i]), 3),
            "angle_deg": 0.0 if islanded else round(va, 3),
            "p_mw": round(p, 4), "q_mvar": round(q, 4),
            "energized": not islanded,
        })
    lines = []
    import math as _m2
    def _f(x, nd=2):
        try:
            f = float(x)
        except (TypeError, ValueError):
            return 0.0
        return 0.0 if _m2.isnan(f) else round(f, nd)
    for i in net.line.index:
        from_b = net.bus.name[net.line.from_bus[i]]
        to_b = net.bus.name[net.line.to_bus[i]]
        ins = bool(net.line.in_service[i])
        p_from = _f(net.res_line.p_from_mw[i], 4) if ins else 0.0
        p_to = _f(net.res_line.p_to_mw[i], 4) if ins else 0.0
        ld = _f(net.res_line.loading_percent[i]) if ins else 0.0
        ika = _f(net.res_line.i_ka[i], 4) if ins else 0.0
        qf = _f(net.res_line.q_from_mvar[i], 4) if ins else 0.0
        lines.append({
            "name": net.line.name[i],
            "from_bus": from_b, "to_bus": to_b,
            "loading_percent": ld,
            "current_ka": ika,
            "current_a": round(ika * 1000, 1),
            "rated_a": round(float(net.line.max_i_ka[i]) * 1000, 1),
            "p_from_mw": p_from, "p_to_mw": p_to,
            "loss_mw": round(p_from + p_to, 5),
            "q_from_mvar": qf,
            "in_service": ins,
        })
    tr = net.res_trafo
    trafo = {
        "name": net.trafo.name[0], "hv_bus": net.bus.name[net.trafo.hv_bus[0]],
        "lv_bus": net.bus.name[net.trafo.lv_bus[0]],
        "sn_mva": float(net.trafo.sn_mva[0]),
        "loading_percent": round(float(tr.loading_percent[0]), 2),
        "p_hv_mw": round(float(tr.p_hv_mw[0]), 4),
        "q_hv_mvar": round(float(tr.q_hv_mvar[0]), 4),
        "loss_mw": round(float(tr.pl_mw[0] + tr.pfe_kw[0] / 1000.0) if "pfe_kw" in tr else float(tr.pl_mw[0]), 5),
    }
    trafo_loading = trafo["loading_percent"]
    line_losses = round(float(net.res_line.pl_mw.sum()), 5)
    trafo_losses = round(float(net.res_trafo.pl_mw.sum()), 5)
    total_losses = round(line_losses + trafo_losses, 5)
    total_q = round(float(net.load.q_mvar.sum()), 4)
    p_grid = round(float(net.res_ext_grid.p_mw.sum()), 4)
    q_grid = round(float(net.res_ext_grid.q_mvar.sum()), 4)
    pf = round(abs(p_grid) / math.sqrt(p_grid ** 2 + q_grid ** 2), 4) if (p_grid or q_grid) else 0.0
    violations = check_violations(buses, lines, trafo_loading)
    alarms = evaluate_alarms(buses, lines, trafo_loading) if include_alarms else []

    return {
        "converged": True, "buses": buses, "lines": lines, "transformer": trafo,
        "transformer_loading_percent": trafo_loading,
        "line_losses_mw": line_losses, "trafo_losses_mw": trafo_losses,
        "total_losses_mw": total_losses,
        "total_load_mw": round(float(net.load.p_mw.sum()), 4),
        "total_solar_mw": round(float(net.sgen.p_mw.sum()), 4),
        "total_q_mvar": total_q, "grid_import_mw": p_grid, "grid_import_mvar": q_grid,
        "pf": pf, "violations": violations, "alarms": alarms,
        "limits": {"vmin": VMIN_PU, "vmax": VMAX_PU, "loading_max": LOADING_MAX_PCT},
    }
