"""Grade a build by numbers, without a fight. Computes effective stats and two
single-build metrics from the verified combat math: effective HP (tankiness) and
an offense score (ATK x attacks/sec x average crit factor). No opponent, no
simulation. This is the stat-based grade the build generator ranks on.
"""
from . import combat, statcalc


def score(conn, hero, stars=10, level=200, evo=0, talent=None, talent_lvl=0, loadout=None):
    r = statcalc.calc(conn, hero, stars=stars, level=level, evo=evo,
                      talent=talent, talent_lvl=talent_lvl, loadout=loadout)
    if "error" in r:
        return r
    e = r["effective"]
    om = combat.offense_metrics(e["Attack"], e.get("ATK SPD") or 1500,
                                e.get("CRIT") or 0, e.get("CRIT DMG") or 0)
    return {
        "hero": r["hero"],
        "effective": {
            "HP": e["HP"], "ATK": e["Attack"], "ATK SPD": e.get("ATK SPD"),
            "CRIT": e.get("CRIT"), "CRIT DMG": e.get("CRIT DMG"),
            "Dodge": e.get("Dodge"), "Tenacity": e.get("Tenacity"),
        },
        "metrics": {
            "EHP": e["HP"],
            "crit_chance": round(om["crit_chance"], 3),
            "avg_crit_factor": round(om["avg_crit_factor"], 3),
            "attacks_per_sec": round(om["attacks_per_sec"], 3),
            "offense_score": round(om["dps"]),
        },
        "loadout_sources": r.get("loadout_sources"),
        "note": "single-build stat grade (no opponent). EHP = effective HP; "
                "offense = ATK x attacks/sec x average crit factor.",
    }
