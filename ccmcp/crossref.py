"""Cross-reference: given any name, resolve what it is and what connects to it.
Ties the siloed lookups together — a skill points to the heroes that use it, a
hero points to its skill and build, a catalog item points to its system.
"""
from functools import lru_cache

from . import skills as skillmod, statcalc, systems


@lru_cache(maxsize=2)
def _skill_to_heroes():
    """skill name (lower) -> [hero names], from each hero's main skill."""
    idx: dict = {}
    d = systems.load("heroes") or {}
    for v in d.values():
        ms = v.get("main_skill") or {}
        nm = ms.get("name") if isinstance(ms, dict) else None
        if nm and v.get("name"):
            idx.setdefault(nm.lower(), []).append(v["name"])
    return idx


def related(conn, query: str) -> dict:
    q = str(query).strip()
    ql = q.lower()
    out = {"query": q, "resolved_as": None, "connections": {}}

    # hero?
    base = statcalc.base_stats(q)
    if base:
        hrec = systems.hero(base["name"])
        hrec = hrec if isinstance(hrec, dict) and "error" not in hrec else {}
        ms = hrec.get("main_skill") or {}
        out["resolved_as"] = "hero"
        out["connections"] = {
            "main_skill": ms.get("name") if isinstance(ms, dict) else ms,
            "totem_skill": (hrec.get("totem_skill") or {}).get("name")
            if isinstance(hrec.get("totem_skill"), dict) else hrec.get("totem_skill"),
            "full_view": "call hero_dossier for stats, grades, build",
        }
        return out

    # skill?
    sd = skillmod.skill_data(q)
    if "levels" in sd:
        dmg = [L["damage_pct"] for L in sd["levels"] if (L.get("damage_pct") or 0) > 0]
        out["resolved_as"] = "skill"
        out["connections"] = {
            "used_by_heroes": _skill_to_heroes().get(sd["skill"].lower(), []),
            "max_damage_pct": max(dmg) if dmg else None,
            "detail": "call skill_data / skill_damage",
        }
        return out

    # catalog item across all systems?
    hits = systems.search_all(q, limit=5)
    if hits:
        top = hits[0]
        out["resolved_as"] = f"item in system '{top.get('system')}'"
        out["connections"] = {
            "system": top.get("system"), "name": top.get("name"),
            "also_in": sorted({h.get("system") for h in hits}),
            "detail": f"call get_system('{top.get('system')}') or system_lookup",
        }
        return out

    out["resolved_as"] = "not found"
    return out
