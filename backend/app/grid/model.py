"""GridOS default radial distribution network (pandapower)."""
import pandapower as pp

VMIN_PU = 0.95
VMAX_PU = 1.05
LOADING_MAX_PCT = 100.0

# Baseline injections (used for multiplier scaling + /grid metadata)
BASE_LOADS = [
    {"bus_name": "Feeder A1", "p_mw": 0.6, "q_mvar": 0.20},
    {"bus_name": "Feeder A2", "p_mw": 0.5, "q_mvar": 0.16},
    {"bus_name": "Feeder B1", "p_mw": 0.8, "q_mvar": 0.26},
    {"bus_name": "Feeder B2", "p_mw": 0.6, "q_mvar": 0.19},
]
BASE_SGEN = [
    {"bus_name": "Feeder A2", "p_mw": 0.40},
    {"bus_name": "Feeder B2", "p_mw": 0.30},
]


LINE_NAMES = ["L1-2", "L2-3", "L1-4", "L4-5"]


def build_default_grid(open_lines=()):
    """Build a small radial 33/11 kV network. Returns fresh pp net.

    open_lines: names of lines to take out of service (N-1 switching study).
    """
    net = pp.create_empty_network(name="GridOS demo feeder")

    b0 = pp.create_bus(net, vn_kv=33.0, name="Grid Supply")
    b1 = pp.create_bus(net, vn_kv=11.0, name="LV Main")
    b2 = pp.create_bus(net, vn_kv=11.0, name="Feeder A1")
    b3 = pp.create_bus(net, vn_kv=11.0, name="Feeder A2")
    b4 = pp.create_bus(net, vn_kv=11.0, name="Feeder B1")
    b5 = pp.create_bus(net, vn_kv=11.0, name="Feeder B2")

    pp.create_ext_grid(net, bus=b0, vm_pu=1.02, name="Upstream grid")

    pp.create_transformer_from_parameters(
        net, hv_bus=b0, lv_bus=b1, sn_mva=5.0,
        vn_hv_kv=33.0, vn_lv_kv=11.0,
        vkr_percent=0.5, vk_percent=10.0,
        pfe_kw=8.0, i0_percent=0.1, name="T1 33/11kV 5MVA",
    )

    def _line(f, t, length, name):
        return pp.create_line_from_parameters(
            net, from_bus=f, to_bus=t, length_km=length,
            r_ohm_per_km=0.161, x_ohm_per_km=0.190,
            c_nf_per_km=170.0, max_i_ka=0.20, name=name,
        )

    _line(b1, b2, 1.5, "L1-2")
    _line(b2, b3, 1.2, "L2-3")
    _line(b1, b4, 1.8, "L1-4")
    _line(b4, b5, 1.0, "L4-5")

    bus_by_name = {net.bus.name[i]: i for i in net.bus.index}
    for i, ld in enumerate(BASE_LOADS):
        pp.create_load(net, bus=bus_by_name[ld["bus_name"]],
                       p_mw=ld["p_mw"], q_mvar=ld["q_mvar"],
                       name=f"Load {ld['bus_name']}")
    for i, sg in enumerate(BASE_SGEN):
        pp.create_sgen(net, bus=bus_by_name[sg["bus_name"]],
                       p_mw=sg["p_mw"], q_mvar=0.0,
                       name=f"Solar {sg['bus_name']}")

    for ln in (open_lines or []):
        idx = net.line[net.line.name == ln].index
        if len(idx):
            net.line.loc[idx, "in_service"] = False

    # stash base values for scaling
    net["_base_load_p"] = net.load.p_mw.copy()
    net["_base_load_q"] = net.load.q_mvar.copy()
    net["_base_sgen_p"] = net.sgen.p_mw.copy()
    return net
