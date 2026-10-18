"""Operator event / SOE log (in-memory, newest first cap 200)."""
from datetime import datetime, timezone
from itertools import count

_events: list = []
_ids = count(1)


def log_event(type: str, asset: str = "", message: str = "", actor: str = "operator"):
    rec = {"id": next(_ids), "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "type": type, "asset": asset, "message": message, "actor": actor}
    _events.insert(0, rec)
    del _events[200:]
    return rec


def list_events(limit: int = 50):
    return _events[:limit]
