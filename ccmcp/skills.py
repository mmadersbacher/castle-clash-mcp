"""Skill catalog + hero totem-skill lookup (from the user's full client RE).

skills_catalog.json: 421 skills, each {name_id, name_en, levels:[{lvl,effect,desc}]}.
hero_totem_skills.json: 94 heroes -> totem skill (naming: totem_name_id = 75000+short_hero_id).
Main active skill per hero: from the wiki (hero_level_stats / get_hero skill_base).
"""
from typing import Optional
from . import sources


def _load(name):
    return sources.load(name, "sources")


def skill_levels(query) -> dict:
    cat = _load("skills_catalog.json") or []
    q = str(query).strip().lower()
    exact = [s for s in cat if str(s.get("name_id")) == q or (s.get("name_en", "").lower() == q)]
    part = exact or [s for s in cat if q in s.get("name_en", "").lower()]
    if not part:
        return {"error": f"skill not found: {query}"}
    s = part[0]
    lv = s.get("levels", [])
    return {"skill": s.get("name_en"), "id": s.get("name_id"), "level_count": len(lv),
            "levels": lv, "matches": [x["name_en"] for x in part[:5]] if len(part) > 1 else None}


def skill_data(query) -> dict:
    """Numeric per-level skill data from live_skill_data.json (426 skills, the
    coefficients recovered from Skill.data): damage % of ATK, targets, duration,
    effect %. Match by skill name or id."""
    d = _load("live_skill_data.json") or {}
    q = str(query).strip().lower()
    hit = next((v for v in d.values()
                if str(v.get("skill_id")) == q or str(v.get("name", "")).lower() == q), None)
    if not hit and q:
        hit = next((v for v in d.values() if q in str(v.get("name", "")).lower()), None)
    if not hit:
        return {"error": f"skill not found: {query}"}
    lv = [{"lvl": L["lvl"], "damage_pct": L.get("damage_pct"), "targets": L.get("targets"),
           "duration_s": L.get("duration_s"), "effect_pct": L.get("effect")}
          for L in hit.get("levels", [])]
    return {"skill": hit.get("name"), "id": hit.get("skill_id"), "max_lvl": hit.get("max_lvl"),
            "level_count": len(lv), "levels": lv}


def hero_totem(hero) -> Optional[dict]:
    tot = _load("hero_totem_skills.json") or []
    q = str(hero).strip().lower()
    return next((h for h in tot if h.get("hero", "").lower() == q or str(h.get("hero_full")) == q), None)
