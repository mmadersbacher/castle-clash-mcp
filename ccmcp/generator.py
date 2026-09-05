"""Stat-based build generator: rank the stat levers (talent slot, crest slot) by
build_score for a chosen objective, and combine the best of each into a full
build. Pure numbers — it does not model conditional mechanics (a talent that
trades HP for ATK on the wrong hero still scores high on ATK), so it pairs with
recommend_build, which knows the capability caveats.
"""
from functools import lru_cache

from . import buildscore, statcalc

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

    # best full build = best talent + best crest, scored together (interactions counted)
    bt, bc = talents[0]["talent"], crests[0]["crest"]
    combo = _metrics(conn, hero, talent=bt, talent_lvl=talent_lvl,
                     loadout={"crest": bc, "crest_level": crest_level} if bc else None) or base

    def _slim(rows, slot):
        return [{slot: r[slot], "offense": r["offense"], "ehp": r["ehp"]} for r in rows[:top]]

    return {
        "hero": hero, "objective": objective,
        "naked_baseline": {"offense": base["offense"], "ehp": base["ehp"], "atk": base["atk"]},
        "best_full_build": {"talent": bt, "crest": bc, "atk": combo["atk"],
                            "offense": combo["offense"], "ehp": combo["ehp"]},
        "top_talents": _slim(talents, "talent"),
        "top_crests": _slim(crests, "crest"),
        "ranked": _slim(talents, "talent"),  # back-compat alias
        "note": "ranked by raw stat contribution only. It does not model conditional "
                "mechanics (a talent that penalizes HP on the wrong hero, an anti-synergy) "
                "— cross-check recommend_build for the capability-aware pick.",
    }
