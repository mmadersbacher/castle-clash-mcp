"""Real item catalogs (talents, enchantments, insignias, crests) with capabilities
auto-derived from their effect text — so the build engine works off the full game data,
not the thin seed. Seed tags (nuanced, e.g. Wicked Armor reflect_cap) still win when present.
"""
import re
from functools import lru_cache
from . import gamedata, db

_RULES = [
    (r"ignore[s]?.{0,20}reflection", "reflect_ignore"),
    (r"reflect[s]?\s+\d+%?.{0,10}(incoming )?damage", "reflect"),
    (r"limits reflected", "reflect_cap"),
    (r"\brevive", "revive"),
    (r"instant.{0,20}energy|energy at the start", "energy_burst"),
    (r"\benergy (regen|regain|recover)|per second.{0,10}energy|gains?\s+\d+\s*energy", "energy_regen"),
    (r"increases? (atk|attack)\b|raises? atk|\+\d+%?\s*atk", "atk"),
    (r"crit(ical)?\s*(rate|dmg|damage)?", "crit"),
    (r"increases? (hp|max hp)|raises? .{0,6}hp", "hp"),
    (r"(reduce|reduces|reducing).{0,20}(damage taken|dmg taken)|damage taken by", "dmg_reduction"),
    (r"(restore|restores|recover).{0,10}hp|heal", "heal"),
    (r"reduce[s]?.{0,20}healing|less healing", "anti_heal"),
    (r"coma|stun|freeze|silence|fear", "control"),
    (r"dodge", "dodge"),
    (r"deal[s]?\s+\d+%?\s*atk\s*dmg|deals?\s+\d+%", "skill_dmg"),
]


def derive_caps(text: str) -> list:
    t = (text or "").lower()
    caps = []
    for rx, cap in _RULES:
        if re.search(rx, t) and cap not in caps:
            caps.append(cap)
    return caps


@lru_cache(maxsize=8)
def enchantments() -> tuple:
    """SoularmsSkill grouped by name -> {name, caps, effect(max lvl)}."""
    from collections import defaultdict
    byn = defaultdict(list)
    for r in gamedata.rows("SoularmsSkill") or []:
        if r.get("NameId_en"):
            byn[r["NameId_en"]].append(r)
    out = []
    for nm, rows in byn.items():
        eff = rows[-1].get("TextId_en", "")
        out.append({"name": nm, "caps": derive_caps(eff), "effect": eff, "levels": len(rows)})
    return tuple(out)


@lru_cache(maxsize=8)
def insignias() -> tuple:
    out = []
    for r in gamedata.rows("Equipment") or []:
        ch = r.get("_children") or []
        eff = ch[-1].get("TxtID_en", "") if ch else ""
        out.append({"name": r.get("NameID_en"), "caps": derive_caps(eff), "effect": eff, "levels": len(ch)})
    return tuple(out)


def talent_caps(conn, name: str) -> list:
    """Caps for a talent: seed tags first, else derive from casclash effect text."""
    t = db.get_entity(conn, "talents", name)
    if not t:
        return []
    tags = (t.get("tags") or {}).get("provides")
    if tags:
        return list(tags)
    return derive_caps(t.get("effect") or "")


def find(catalog_fn, name: str):
    q = str(name).strip().lower()
    for it in catalog_fn():
        if (it.get("name") or "").lower() == q:
            return it
    return None
