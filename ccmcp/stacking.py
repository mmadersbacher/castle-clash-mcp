"""Fold the documented stat systems into effective stats, from the RE stacking
chain (data/sources/live_stacking_chain.json + data/sources/curated/). These are
flat-add systems the core calculator did not fold before: their per-level HP /
Attack / Tenacity add on top of the base, after the talent %.

Validated where a curve is published (breakthrough L45 = +213,300 HP). Systems
with a percent-of-HP skill bucket (crest, insignia) are folded for their flat
part only and flagged, since there is no in-game oracle for the % yet.
"""
from . import sources


def _i(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def _curated(name):
    return sources.load("curated/" + name, "sources") or {}


def _entries(d):
    if isinstance(d, dict):
        return d.get("entries") or []
    return d if isinstance(d, list) else []


def breakthrough(level: int) -> dict:
    """Pinnacle (TopLevel.xml) cumulative flat bonus at a breakthrough level.
    Validated: L1 +180 HP/+6 ATK, L10 +12,150 HP/+30 Tenacity, L45 +213,300 HP."""
    rows = _entries(_curated("breakthrough_pinnacle.json"))
    r = next((x for x in rows if str(x.get("Lv")) == str(level)), None)
    if not r:
        return {}
    return {"Attack": _i(r.get("Attack")), "HP": _i(r.get("HP")), "Tenacity": _i(r.get("Tenacity"))}


# system name -> (loadout key, folding function taking the loadout value)
_SYSTEMS = {
    "breakthrough": lambda v: breakthrough(v),
}


def documented(loadout: dict) -> list:
    """Flat-delta parts from every documented system present in the loadout.
    Returns a list of {"source": name, <stat>: value} to add on top of the base."""
    lo = loadout or {}
    parts = []
    for name, fn in _SYSTEMS.items():
        v = lo.get(name)
        if v:
            delta = {k: val for k, val in fn(v).items() if val}
            if delta:
                parts.append({"source": name, **delta})
    return parts
