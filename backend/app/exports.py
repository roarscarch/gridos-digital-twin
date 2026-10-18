"""CSV export helpers."""
import csv, io


def buses_csv(result) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["bus", "vn_kv", "v_pu", "v_kv", "angle_deg", "p_mw", "q_mvar"])
    for b in result.get("buses", []):
        w.writerow([b.get("name"), b.get("vn_kv"), b.get("voltage_pu"), b.get("voltage_kv"),
                    b.get("angle_deg"), b.get("p_mw"), b.get("q_mvar")])
    return buf.getvalue()


def lines_csv(result) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["line", "from", "to", "loading_pct", "i_a", "rated_a", "p_from_mw", "p_to_mw", "loss_mw", "in_service"])
    for l in result.get("lines", []):
        w.writerow([l.get("name"), l.get("from_bus"), l.get("to_bus"), l.get("loading_percent"),
                    l.get("current_a"), l.get("rated_a"), l.get("p_from_mw"), l.get("p_to_mw"),
                    l.get("loss_mw"), l.get("in_service", True)])
    return buf.getvalue()


def alarms_csv(result) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["priority", "asset", "type", "observed", "limit", "unit", "message"])
    for a in result.get("alarms", result.get("violations", [])):
        w.writerow([a.get("priority"), a.get("asset"), a.get("type"), a.get("observed"),
                    a.get("limit"), a.get("unit"), a.get("message")])
    return buf.getvalue()
