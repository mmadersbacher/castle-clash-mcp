"""Stat-based build generator: rank the stat levers (talent slot, crest slot) by
build_score for a chosen objective, and combine the best of each into a full
build. Pure numbers — it does not model conditional mechanics (a talent that
trades HP for ATK on the wrong hero still scores high on ATK), so it pairs with
recommend_build, which knows the capability caveats.
"""
import html
from functools import lru_cache

from . import buildscore, statcalc, systems


def _disp(name):
    return html.unescape(name) if isinstance(name, str) else name

OBJECTIVES = ("offense", "ehp", "balanced")


def _catalog(category):
    from . import db
    conn = db.connect()
    try:
        cur = conn.cursor()
        cur.execute("select name from catalog where category=?", (category,))
        return [r[0] for r in cur.fetchall()]
    except Exception:
        return []


@lru_cache(maxsize=2)
def _stat_talents():
    """Talent names that apply an ATK or HP % (the levers worth ranking)."""
    from . import db
    conn = db.connect()
    out = []
    for t in _catalog("talent"):
        m = statcalc.talent_multipliers(conn, t, 10)
        if m["ATK"] or m["HP"]:
            out.append(t)
    return tuple(out)


@lru_cache(maxsize=2)
def _crests():
    return tuple(_catalog("crest"))


@lru_cache(maxsize=2)
def _insignias():
    names = []
    for r in systems.rows("insignia"):
        nm = r.get("name_en") or r.get("NameID_en") or r.get("Name")
        if nm and nm not in names:
            names.append(nm)  # kept as-is so the loadout lookup matches
    return tuple(names)


def _rank_key(m, objective):
    if objective == "offense":
        return m["offense"]
    if objective == "ehp":
        return m["ehp"]
    return m["offense"] * m["ehp"]  # balanced = product


def _metrics(conn, hero, talent=None, talent_lvl=10, loadout=None):
    g = buildscore.score(conn, hero, talent=talent, talent_lvl=talent_lvl, loadout=loadout)
    if "metrics" not in g:
        return None
    return {"atk": g["effective"]["ATK"],
            "offense": g["metrics"]["offense_score"], "ehp": g["metrics"]["EHP"]}


def generate(conn, hero, objective="balanced", top=5, talent_lvl=10, crest_level=10):
    if objective not in OBJECTIVES:
        return {"error": f"objective must be one of {OBJECTIVES}"}
    base = _metrics(conn, hero)
    if base is None:
        return {"error": f"no stats for '{hero}'"}

    talents = [{"talent": None, **base}]
    for t in _stat_talents():
        m = _metrics(conn, hero, talent=t, talent_lvl=talent_lvl)
        if m:
            talents.append({"talent": t, **m})
    talents.sort(key=lambda m: _rank_key(m, objective), reverse=True)

    crests = [{"crest": None, **base}]
    for c in _crests():
        m = _metrics(conn, hero, loadout={"crest": c, "crest_level": crest_level})
        if m and (m["offense"] != base["offense"] or m["ehp"] != base["ehp"]):
            crests.append({"crest": c, **m})
    crests.sort(key=lambda m: _rank_key(m, objective), reverse=True)

    insignias = [{"insignia": None, **base}]
    for i in _insignias():
        m = _metrics(conn, hero, loadout={"insignias": [{"name": i, "level": 10}]})
        if m and (m["offense"] != base["offense"] or m["ehp"] != base["ehp"]):
            insignias.append({"insignia": i, **m})
    insignias.sort(key=lambda m: _rank_key(m, objective), reverse=True)

    # best full build = best talent + crest + insignia, scored together (interactions counted)
    bt, bc, bi = talents[0]["talent"], crests[0]["crest"], insignias[0]["insignia"]
    lo = {}
    if bc:
        lo.update({"crest": bc, "crest_level": crest_level})
    if bi:
        lo["insignias"] = [{"name": bi, "level": 10}]
    combo = _metrics(conn, hero, talent=bt, talent_lvl=talent_lvl, loadout=lo or None) or base

    # the enchantment slot is effect-based (not flat stats) -> take the capability pick
    ench = None
    try:
        from . import rules
        ench = (rules.recommend_build(conn, hero) or {}).get("build", {}).get("enchantment")
    except Exception:
        pass

    def _slim(rows, slot):
        return [{slot: _disp(r[slot]), "offense": r["offense"], "ehp": r["ehp"]} for r in rows[:top]]

    return {
        "hero": hero, "objective": objective,
        "naked_baseline": {"offense": base["offense"], "ehp": base["ehp"], "atk": base["atk"]},
        "best_full_build": {"talent": bt, "crest": bc, "insignia": _disp(bi), "enchantment": ench,
                            "atk": combo["atk"], "offense": combo["offense"], "ehp": combo["ehp"]},
        "top_talents": _slim(talents, "talent"),
        "top_crests": _slim(crests, "crest"),
        "top_insignias": _slim(insignias, "insignia"),
        "ranked": _slim(talents, "talent"),  # back-compat alias
        "note": "talent/crest/insignia ranked by raw stat contribution; the enchantment "
                "slot is effect-based (from recommend_build's capability logic, not "
                "stat-scored). Conditional mechanics are not modeled — cross-check "
                "recommend_build for anti-synergies.",
    }
