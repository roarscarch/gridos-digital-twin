"""In-memory scenario store (resets on restart — fine for Vercel demo)."""
from itertools import count

_store: dict = {}
_ids = count(1)


def save_scenario(name, load_multiplier, solar_multiplier, result, open_lines=()):
    sid = next(_ids)
    rec = {"id": sid, "name": name, "load_multiplier": load_multiplier,
           "solar_multiplier": solar_multiplier, "open_lines": list(open_lines or []),
           "result": result}
    _store[sid] = rec
    return rec


def list_scenarios():
    return list(_store.values())


def get_scenario(sid: int):
    return _store.get(sid)
