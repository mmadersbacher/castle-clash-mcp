"""Combat math — the engine's exact formulas, recovered from libgame.so (aarch64)
by static RE and, where marked, executed/corrected under Unicorn emulation
(gamedata/re/emu.py). Cross-checked against our own Hero.data. See
docs/GAME_MATH.md and the engagement's GAME_MATH_FORMULAS.md.

Ratings (crit, crit-dmg, dodge, crit-resist, damage-reduce, tenacity) are the raw
integer stats stored per hero in Hero.data; these functions convert them the way
the client does. Constants tagged VERIFIED were confirmed by executing the native
code, not just reading it.
"""
import math

# The single scaling constant the binary uses for crit-dmg and damage-reduce
# ratings (float 0.0001, 0x3F1A36E2EB1C432D).
_RATING = 0.0001

# AttackRatio.xml via ParaManager::GetAttackRatio(attackType, armorType).
# Percent multiplier; row = attackType 1..5, col = armorType 0..5 (col 0 unused).
ATTACK_RATIO = {
    1: [0, 100, 150, 75, 70, 65],   # Melee
    2: [0, 150, 75, 100, 70, 65],   # Pierce
    3: [0, 75, 100, 150, 70, 65],   # Magic
    4: [0, 50, 50, 50, 250, 65],    # Siege
    5: [0, 125, 125, 125, 100, 100],  # Hero (player heroes attack as this)
}
ATTACK_TYPES = {1: "Melee", 2: "Pierce", 3: "Magic", 4: "Siege", 5: "Hero"}


def crit_chance(crit_rating: int) -> float:
    """Crit chance as a fraction 0..1. crit*10000/(crit+1000), /10000.
    VERIFIED (executed): 250->0.20, 1000->0.50, 3000->0.75. Diminishing."""
    c = max(int(crit_rating), 0)
    if c == 0:
        return 0.0
    return (c * 10000 / (c + 1000)) / 10000.0


def crit_damage(crit_dmg_rating: int) -> float:
    """Crit damage multiplier. 1.5 + stat*0.0001. Base 150%.
    VERIFIED (executed): 0->1.5x, 5000->2.0x, 10000->2.5x, 20000->3.5x."""
    return 1.5 + max(int(crit_dmg_rating), 0) * _RATING


def damage_taken_multiplier(reduce_rating: int) -> float:
    """Damage-taken multiplier: 1 - reduceStat*0.0001, clamped to [0,1].
    VERIFIED (Unicorn execution): 1000->x0.9, 5000->x0.5, 10000->x0 (immune).
    Incoming damage is MULTIPLIED by this. (An earlier static reading had the
    sign inverted; execution corrected it.)"""
    return max(0.0, min(1.0, 1.0 - max(int(reduce_rating), 0) * _RATING))


def mitigation(reduce_rating: int) -> float:
    """Fraction of damage removed = reduceStat*0.0001, clamped to [0,1]."""
    return 1.0 - damage_taken_multiplier(reduce_rating)


def effective_crit_chance(attacker_crit_rating: int, defender_tenacity_rating: int = 0) -> float:
    """Crit chance after the defender's Tenacity. DERIVED: the engine rolls
    rand(1000) < (attackerCritChance - defenderTenacity) * ratio — Tenacity
    subtracts from crit chance (JudgeAttackState). We pass Tenacity through the
    same diminishing curve and subtract; Tenacity's exact rating space is not yet
    confirmed, so this is DERIVED, not VERIFIED."""
    return max(0.0, crit_chance(attacker_crit_rating) - crit_chance(defender_tenacity_rating))


def attack_ratio(attack_type: int, armor_type: int) -> float:
    """Type-vs-armor multiplier as a fraction. VERIFIED from AttackRatio.xml."""
    row = ATTACK_RATIO.get(int(attack_type))
    if not row or not (0 <= int(armor_type) <= 5):
        return 1.0
    return row[int(armor_type)] / 100.0


def skill_value(coeff_pct: float, base_stat: float) -> int:
    """A skill's numeric effect. VERIFIED (Unicorn-traced FormulaManager
    _function_001..005): ceil(coeff% * base_stat / 100). base_stat is whichever
    combat value the skill scales on (ATK, Max HP, level, target-count)."""
    return math.ceil(coeff_pct * base_stat / 100.0)


def hit_damage(atk: float, *, attack_type: int = 5, armor_type: int = 5,
               skill_coeff: float = 1.0, is_crit: bool = False,
               crit_dmg_rating: int = 0, target_reduce_rating: int = 0) -> dict:
    """One hit, assembled the way CBaseObject::Attack -> BearAttackDamage does:
        base = ATK * skill_coeff * AttackRatio[atk][armor]
        if crit: * crit_damage
        * damage_taken_multiplier(target)      (VERIFIED: multiply, not divide)
    skill_coeff = 1.0 for a normal hit, or (skill % / 100) for a skill.
    Returns the value plus every factor, so any number is explainable."""
    ratio = attack_ratio(attack_type, armor_type)
    base = atk * skill_coeff * ratio
    crit_mult = crit_damage(crit_dmg_rating) if is_crit else 1.0
    dtm = damage_taken_multiplier(target_reduce_rating)
    final = base * crit_mult * dtm
    return {
        "final_damage": round(final),
        "factors": {
            "ATK": atk, "skill_coeff": skill_coeff,
            "attack_type": ATTACK_TYPES.get(attack_type, attack_type),
            "armor_type": armor_type, "attack_ratio": ratio,
            "is_crit": is_crit, "crit_multiplier": crit_mult,
            "target_damage_taken_multiplier": dtm,
        },
        "steps": [
            f"ATK {atk} x coeff {skill_coeff} x ratio {ratio} = {round(base)}",
            (f"x crit {crit_mult} " if is_crit else "x crit 1.0 (no crit) ")
            + f"x dmg_taken {dtm} = {round(final)}",
        ],
        "note": "point estimate; the engine also applies a random +/- variance and "
                "hits Shield before HP (see docs/GAME_MATH.md sec 5).",
    }
