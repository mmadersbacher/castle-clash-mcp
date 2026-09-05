"""Canonical game-system registry — every Castle Clash data system, queryable.

Backed by the user's clean parsed dataset (data/sources/game/*.json), mapped in SYSTEMS.md.
Generic access: systems() lists them, rows(system) returns records, lookup(system, name)
finds one by English name. Stat-bearing systems also feed the calculator (see loadout.py).
"""
import json
from functools import lru_cache
from . import sources

REGISTRY = {
    "heroes": "heroes_complete.json", "skills": "skills_catalog.json",
    "talents": "sys_talents_complete.json", "talent_manual": "sys_talent_manual.json",
    "breakthrough": "sys_breakthrough.json", "insignia": "sys_runes.json",
    "crest": "sys_insignia.json", "destiny": "sys_destiny.json",
    "gear": "sys_equipment_gear.json", "enchantment": "sys_enchantments.json",
    "traits": "sys_traits.json", "relics": "sys_relics.json", "soul": "sys_soul.json",
    "holy": "sys_holy.json", "inscription": "sys_inscription.json", "endow": "sys_endow.json",
    "pets": "pets_full.json", "totem_skills": "totem_skills_full.json",
    "magic": "magic_named.json", "buildings": "buildings_full.json",
    "monsters": "monsters.json", "gacha": "gacha_pools.json", "items": "items_icons.json",
    "icons": "icon_maps.json", "buffers": "buffers.json", "summons": "summons.json",
    "runes_named": "runes_named.json", "sentinels": "sentinels.json",
    "effect_types": "effect_types.json", "effect_subtypes": "effect_subtypes.json",
}


def load(system: str):
    f = REGISTRY.get(system, system if system.endswith(".json") else system + ".json")
    if not f.endswith(".json"):
        f += ".json"
    return sources.load(f, "game")


def _flatten(d) -> list:
    if isinstance(d, list):
        return d
    if isinstance(d, dict):
        # dict of records, or dict of sub-lists (e.g. breakthrough/destiny/soul)
        vals = list(d.values())
        if vals and all(isinstance(v, dict) for v in vals):
            return vals
        rows = []
        for k, v in d.items():
            if isinstance(v, list):
                for r in v:
                    rows.append({"_group": k, **(r if isinstance(r, dict) else {"value": r})})
            elif isinstance(v, dict):
                rows.append({"_group": k, **v})
        return rows or vals
    return []


def systems() -> dict:
    out = {}
    for name in REGISTRY:
        d = load(name)
        out[name] = len(_flatten(d)) if d is not None else 0
    return out


def rows(system: str) -> list:
    d = load(system)
    return _flatten(d) if d is not None else []


def _name(r: dict) -> str:
    for k in ("name_en", "NameID_en", "NameId_en", "name", "Name", "EquipName"):
        if r.get(k):
            return str(r[k])
    return ""


def lookup(system: str, name: str) -> dict:
    q = str(name).strip().lower()
    exact = [r for r in rows(system) if _name(r).lower() == q]
    part = exact or [r for r in rows(system) if q and q in _name(r).lower()]
    if not part:
        return {"error": f"'{name}' not in system '{system}'"}
    return part[0]


@lru_cache(maxsize=2)
def _hero_name_index():
    d = load("heroes") or {}
    return {v.get("name", "").lower(): k for k, v in d.items()}


def hero(name_or_id: str) -> dict:
    d = load("heroes") or {}
    q = str(name_or_id).strip()
    if q in d:
        return d[q]
    hid = _hero_name_index().get(q.lower())
    if hid:
        return d[hid]
    # fuzzy
    for k, v in d.items():
        if q.lower() in v.get("name", "").lower():
            return v
    return {"error": f"hero not found: {name_or_id}"}


def icon(kind: str, key: str) -> dict:
    im = load("icons") or {}
    m = im.get(kind) or im.get(kind + "s") or {}
    if isinstance(m, dict):
        return {"kind": kind, "key": key, "path": m.get(str(key))}
    return {"kinds_available": list(im.keys())}


import re as _re

TRAIT_MARK = {"1": "HP", "2": "Attack", "3": "CRIT Resist", "4": "CRIT DMG",
              "5": "Dodge", "6": "ACC", "7": "CRIT"}


def trait_name(r: dict) -> str:
    m = _re.search(r"(\d+)\s*星", r.get("Text", ""))
    star = m.group(1) if m else "?"
    return f"{TRAIT_MARK.get(r.get('Mark'), 'Bonus')} {star}-star"


@lru_cache(maxsize=2)
def traits_named() -> tuple:
    out = []
    for r in rows("traits"):
        out.append({"name": trait_name(r), "stat": TRAIT_MARK.get(r.get("Mark"), "Bonus"),
                    "Attack": r.get("Attack"), "HP": r.get("HP"), "id": r.get("ID")})
    return tuple(out)


def gacha_odds(pool) -> dict:
    """Drop odds for a gacha pool (grouped by Type). weight -> probability, reward resolved."""
    tf = load("text_en_flat") or {}
    idx = {}
    for it in rows("items"):
        k = str(it.get("ID") or it.get("id") or it.get("Mark") or "")
        nm = it.get("name_en") or it.get("Name")
        if k and nm:
            idx[k] = nm
    grp = [r for r in rows("gacha") if str(r.get("Type")) == str(pool)]
    if not grp:
        types = sorted({r.get("Type") for r in rows("gacha")})
        return {"error": f"pool Type {pool} not found", "pool_types": types[:40]}
    total = sum(_i_(r.get("RuleWeight")) for r in grp) or 1
    out = []
    for r in grp:
        rid = str(r.get("RewardID"))
        name = idx.get(rid) or tf.get(rid)
        if name and len(name) > 40:
            name = None  # long sentence = not an item name
        out.append({"reward": name or rid, "reward_id": rid, "reward_type": r.get("RewardType"),
                    "num": r.get("Num"), "weight": _i_(r.get("RuleWeight")),
                    "pct": round(100 * _i_(r.get("RuleWeight")) / total, 3)})
    out.sort(key=lambda x: -x["weight"])
    return {"pool_type": pool, "entries": len(out), "total_weight": total, "drops": out}


def _i_(x):
    try:
        return int(x)
    except (TypeError, ValueError):
        return 0


def search_all(query: str, limit: int = 40) -> list:
    """Search across ALL 28 canonical systems by English name / any field."""
    q = str(query).lower()
    hits = []
    for sysname in REGISTRY:
        for r in rows(sysname):
            if q in _name(r).lower() or q in json.dumps(r, ensure_ascii=False).lower():
                hits.append({"system": sysname, "name": _name(r),
                             **{k: v for k, v in r.items() if not isinstance(v, (list, dict)) and k != "_group"}})
                if len(hits) >= limit:
                    return hits
    return hits


def totem_skill(hero: str) -> dict:
    q = str(hero).strip().lower()
    lv = [{"lvl": r.get("lvl"), "desc": r.get("desc_en")}
          for r in rows("totem_skills") if str(r.get("hero", "")).lower() == q]
    if not lv:
        return {"error": f"no totem skill for {hero}"}
    nm = next((r.get("skill_name") for r in rows("totem_skills") if str(r.get("hero", "")).lower() == q), None)
    return {"hero": hero, "skill_name": nm, "level_count": len(lv), "levels": lv}
