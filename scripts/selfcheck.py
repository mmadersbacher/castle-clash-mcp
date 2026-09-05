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
