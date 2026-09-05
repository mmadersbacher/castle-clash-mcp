"""Stat-based build generator: rank the stat levers (talents) by build_score for
a chosen objective. Pure numbers — it does not model conditional mechanics (a
talent that trades HP for ATK on the wrong hero still scores high on ATK), so it
pairs with recommend_build, which knows the capability caveats.
"""
from functools import lru_cache

from . import buildscore, statcalc

OBJECTIVES = ("offense", "ehp", "balanced")


@lru_cache(maxsize=2)
def _stat_talents():
    """Talent names that apply an ATK or HP % (the levers worth ranking)."""
    from . import db
    conn = db.connect()
    try:
        cur = conn.cursor()
        cur.execute("select name from catalog where category='talent'")
        names = [r[0] for r in cur.fetchall()]
    except Exception:
        names = []
    out = []
    for t in names:
        m = statcalc.talent_multipliers(conn, t, 10)
        if m["ATK"] or m["HP"]:
            out.append(t)
    return tuple(out)


def _metrics(conn, hero, talent, talent_lvl):
    g = buildscore.score(conn, hero, talent=talent, talent_lvl=talent_lvl)
    if "metrics" not in g:
        return None
    return {"talent": talent, "atk": g["effective"]["ATK"],
            "offense": g["metrics"]["offense_score"], "ehp": g["metrics"]["EHP"]}


def generate(conn, hero, objective="balanced", top=5, talent_lvl=10):
    if objective not in OBJECTIVES:
        return {"error": f"objective must be one of {OBJECTIVES}"}
    base = _metrics(conn, hero, None, 0)
    if base is None:
        return {"error": f"no stats for '{hero}'"}
    cands = [base] + [m for t in _stat_talents()
                      if (m := _metrics(conn, hero, t, talent_lvl))]

    def rank_key(c):
        if objective == "offense":
            return c["offense"]
        if objective == "ehp":
            return c["ehp"]
        return c["offense"] * c["ehp"]  # balanced = product

    ranked = sorted(cands, key=rank_key, reverse=True)[:top]
    return {
        "hero": base and hero,
        "objective": objective,
        "naked_baseline": {"offense": base["offense"], "ehp": base["ehp"], "atk": base["atk"]},
        "ranked": ranked,
        "note": "ranked by raw stat contribution only. It does not model conditional "
                "mechanics (e.g. a talent that penalizes HP on the wrong hero) — cross-check "
                "recommend_build for the capability-aware pick.",
    }
