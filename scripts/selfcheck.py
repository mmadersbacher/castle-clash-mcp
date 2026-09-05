#!/usr/bin/env python3
"""Regression self-check for the Castle Clash MCP.

Asserts the validated in-game exacts and a sane dataset shape still hold. Run it
after ANY change, and especially after integrating the live post-4.5.7 sweep
(see data/sources/MANIFEST.md). Exits nonzero on drift.

    .venv/bin/python scripts/selfcheck.py

The two hero stat lines are hard invariants: the user confirmed them against the
real game, so the formula must always reproduce them. If the sweep changes a
base stat and the number moves, that is a signal to review — not to edit here
blindly. The dataset counts are floors (data only ever grows), guarding against
a load path silently returning empty.
"""
import sys

from ccmcp import combat as cb, db, gamedata as gd, skills as sk, statcalc as sc, systems as sy

EXACT = {
    "Serratica": (180695, 7881),  # 10*/L200/evo0, user-confirmed in-game
    "Dynamica": (157700, 9279),   # 10*/L200/evo0, calibration-confirmed
}
MIN_SYSTEMS = 28
MIN_ENRICHED = 180


def main() -> int:
    conn = db.connect()
    fails = []

    for hero, (hp, atk) in EXACT.items():
        eff = sc.calc(conn, hero, 10, 200, 0)["effective"]
        if (eff["HP"], eff["Attack"]) != (hp, atk):
            fails.append(f"{hero}: got {eff['HP']}/{eff['Attack']}, expected {hp}/{atk}")

    n_sys = len(sy.systems())
    if n_sys < MIN_SYSTEMS:
        fails.append(f"systems: {n_sys} < {MIN_SYSTEMS}")

    n_enr = len(gd.list_tables())
    if 0 < n_enr < MIN_ENRICHED:  # enriched dump is bundled-optional
        fails.append(f"enriched tables: {n_enr} < {MIN_ENRICHED}")

    if "levels" not in sk.skill_levels("Divine Shield"):
        fails.append("skills: skill_levels('Divine Shield') returned no levels")

    # Combat formulas recovered from libgame.so (docs/GAME_MATH.md §6).
    combat_anchors = [
        ("crit_chance(250)", round(cb.crit_chance(250), 2), 0.20),
        ("crit_chance(1000)", round(cb.crit_chance(1000), 2), 0.50),
        ("crit_chance(3000)", round(cb.crit_chance(3000), 2), 0.75),
        ("crit_damage(10000)", round(cb.crit_damage(10000), 2), 2.50),
        ("attack_ratio(4,4)", cb.attack_ratio(4, 4), 2.50),
        ("attack_ratio(5,5)", cb.attack_ratio(5, 5), 1.00),
        ("damage_taken_multiplier(5000)", cb.damage_taken_multiplier(5000), 0.50),
        ("damage_taken_multiplier(10000)", cb.damage_taken_multiplier(10000), 0.00),
        ("skill_value(200,1000)", cb.skill_value(200, 1000), 2000),
    ]
    for label, got, want in combat_anchors:
        if got != want:
            fails.append(f"{label}: got {got}, expected {want}")

    # full-build stacking, validated against the real game (RE report sec 7)
    FULL = {"Serratica": (603404, 8574, 597), "Michael": (359352, 4633, 597)}
    for hero, want in FULL.items():
        e = sc.calc(conn, hero, 10, 200, 0, talent="Tenacity", talent_lvl=10,
                    inscription=10, soularms=10, soul=10)["effective"]
        got = (e["HP"], e["Attack"], e["Dodge"])
        if got != want:
            fails.append(f"full-build {hero}: got {got}, expected {want}")

    # documented-system fold: breakthrough L45 = +213,300 HP (RE curve)
    base_hp = sc.calc(conn, "Serratica", 10, 200, 0)["effective"]["HP"]
    bt_hp = sc.calc(conn, "Serratica", 10, 200, 0, loadout={"breakthrough": 45})["effective"]["HP"]
    if bt_hp - base_hp != 213300:
        fails.append(f"breakthrough L45 fold: +{bt_hp - base_hp} HP, expected +213300")

    from ccmcp import stacking
    f = stacking.faction("Oracle", 48)
    if (f.get("Attack"), f.get("HP"), f.get("Dodge")) != (1080, 27000, 280):
        fails.append(f"faction Oracle L48: {f}, expected 1080/27000/280")

    # smoke-test the higher-level modules so a regression in them fails the gate
    try:
        from ccmcp import buildscore, crossref, dossier, generator
        if "grades" not in dossier.build(conn, "Serratica"):
            fails.append("dossier.build('Serratica') returned no grades")
        if buildscore.score(conn, "Serratica").get("metrics", {}).get("offense_score") != 4776:
            fails.append("buildscore.score('Serratica') offense_score drifted from 4776")
        if not generator.generate(conn, "Serratica", "offense").get("ranked"):
            fails.append("generator.generate('Serratica') returned no ranking")
        if crossref.related(conn, "Serratica").get("resolved_as") != "hero":
            fails.append("crossref.related('Serratica') did not resolve as hero")
        if "levels" not in sk.skill_data("Magic Missile"):
            fails.append("skills.skill_data('Magic Missile') returned no levels")
    except Exception as e:
        fails.append(f"module smoke raised: {e}")

    if fails:
        print("SELF-CHECK FAILED:")
        for f in fails:
            print("  -", f)
        return 1

    print(f"self-check OK: Serratica 180695/7881, Dynamica 157700/9279, "
          f"systems={n_sys}, enriched={n_enr}, skills ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
