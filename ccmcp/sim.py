"""Expected-value combat simulator — a duel between two hero builds using the
VERIFIED stat + damage formulas (statcalc + combat). Auto-attack model: each side
computes its expected DPS and time-to-kill; the faster kill wins.

Modeled (verified): effective HP/ATK/crit/crit-dmg/tenacity, the type matrix,
crit with Tenacity subtraction, damage-taken multiplier, ATK-SPD -> attacks/sec.
NOT yet modeled (constants still OPEN): skills + energy, heals/shields, crowd
control, dodge/accuracy rolls. So this is the honest auto-attack baseline the
"build tester" grows from, not a full battle. Flags say what is approximate.
"""
from . import combat, statcalc


def effective(conn, hero, stars=10, level=200, evo=0, talent=None, talent_lvl=0,
              loadout=None):
    """Effective combat stats for one build, via the verified calculator."""
    r = statcalc.calc(conn, hero, stars=stars, level=level, evo=evo,
                      talent=talent, talent_lvl=talent_lvl, loadout=loadout)
    if "error" in r:
        return None, r["error"]
    e = r["effective"]
    return {
        "hero": r["hero"], "HP": e["HP"], "ATK": e["Attack"],
        "atkspd": e.get("ATK SPD") or 1500,
        "crit": e.get("CRIT") or 0, "crit_dmg": e.get("CRIT DMG") or 0,
        "dodge": e.get("Dodge") or 0, "tenacity": e.get("Tenacity") or 0,
        "acc": e.get("ACC") or 0,
    }, None


def _offense(attacker, defender, reduce_rating=0):
    """Expected DPS of attacker onto defender (hero-vs-hero, auto-attacks)."""
    om = combat.offense_metrics(
        attacker["ATK"], attacker["atkspd"], attacker["crit"], attacker["crit_dmg"],
        defender_tenacity=defender["tenacity"], ratio=combat.attack_ratio(5, 5),
        target_reduce=reduce_rating)
    return om["dps"], {
        "crit_chance": round(om["crit_chance"], 3),
        "crit_multiplier": round(combat.crit_damage(attacker["crit_dmg"]), 3),
        "avg_hit": round(om["avg_hit"]), "attacks_per_sec": round(om["attacks_per_sec"], 3),
        "dps": round(om["dps"]),
    }


def duel(a, b, reduce_a=0, reduce_b=0):
    """a, b are effective-stat dicts. Returns the expected outcome."""
    dps_a, oa = _offense(a, b, reduce_b)   # a attacking b
    dps_b, ob = _offense(b, a, reduce_a)   # b attacking a
    ttk_a = (b["HP"] / dps_a) if dps_a else float("inf")   # a kills b in ttk_a s
    ttk_b = (a["HP"] / dps_b) if dps_b else float("inf")
    if ttk_a == ttk_b:
        winner, margin = "draw", 0.0
    else:
        winner = a["hero"] if ttk_a < ttk_b else b["hero"]
        margin = round(abs(ttk_a - ttk_b), 2)
    return {
        "winner": winner,
        "margin_seconds": margin,
        "a": {"hero": a["hero"], "HP": a["HP"], "ATK": a["ATK"],
              "time_to_kill_opponent_s": round(ttk_a, 2), **oa},
        "b": {"hero": b["hero"], "HP": b["HP"], "ATK": b["ATK"],
              "time_to_kill_opponent_s": round(ttk_b, 2), **ob},
        "model": "expected-value auto-attack (hero-vs-hero, ratio 1.0)",
        "not_modeled": ["skills+energy", "heals/shields", "crowd control",
                        "dodge/accuracy rolls"],
    }
