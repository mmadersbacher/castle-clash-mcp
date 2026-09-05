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
    crit_p = combat.crit_chance(e.get("CRIT") or 0)
    crit_mult = combat.crit_damage(e.get("CRIT DMG") or 0)
    avg_crit = (1 - crit_p) + crit_p * crit_mult
    aps = 1000.0 / (e.get("ATK SPD") or 1500)
    offense = e["Attack"] * aps * avg_crit
    return {
        "hero": r["hero"],
        "effective": {
            "HP": e["HP"], "ATK": e["Attack"], "ATK SPD": e.get("ATK SPD"),
            "CRIT": e.get("CRIT"), "CRIT DMG": e.get("CRIT DMG"),
            "Dodge": e.get("Dodge"), "Tenacity": e.get("Tenacity"),
        },
        "metrics": {
            "EHP": e["HP"],
            "crit_chance": round(crit_p, 3),
            "avg_crit_factor": round(avg_crit, 3),
            "attacks_per_sec": round(aps, 3),
            "offense_score": round(offense),
        },
        "loadout_sources": r.get("loadout_sources"),
        "note": "single-build stat grade (no opponent). EHP = effective HP; "
                "offense = ATK x attacks/sec x average crit factor.",
    }
