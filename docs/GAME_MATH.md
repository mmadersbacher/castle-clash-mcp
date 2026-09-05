# The mathematics of Castle Clash — derived and verified

Goal: every number the game computes is explainable by us from a formula, each
either **verified** (real reading / the engine binary, cross-checked against our
data) or honestly marked not yet closed. Built from our data (APK `Hero.data`,
enriched `cc_data`, the live post-4.5.7 capture) and a static reverse-engineering
of the native engine `libgame.so` (aarch64, 60,849 symbols, 1,319 classes). The
verified combat conversions are implemented in `ccmcp/combat.py` (tool
`combat_math`) and locked in `scripts/selfcheck.py`.

## Confidence tags

**VERIFIED** — real reading to the unit, ground truth across many heroes, or read
from the binary and cross-checked. **DERIVED** — mechanism known from the binary
but an exact constant/space not yet pinned. **HYPOTHESIS** — plausible, unproven.
**OPEN** — not known; the experiment to close it is stated.

## Sources

- `game_hero_stats.json` — APK `Hero.data`, 176 heroes, validated 167/167.
- `live_hero_params.json` — 203 heroes, separate `perStar`+`inc` per evolution
  grade.
- Engine RE (the RE workspace): `GAME_MECHANICS_MAP.md` (§A–Q),
  `GAME_MATH_FORMULAS.md`, `gamedata/re/` (`math_functions_catalog.txt`,
  `battle_engine_api.txt`, `staticdb_api.txt`, `player_api.txt`,
  `class_index.json`, `symbols_demangled.txt`), `live_buffer_types.json`.

---

## 1. Base primary stats — the two-term law — VERIFIED

    stat(stars, level) = perStar * stars + inc * (level - 1)      (stars 1..10, level 1..200)

`Hero.data` fields: f21 HP/star, f19 ATK/star, f25 HPinc, f23 ATKinc, f16 range,
f17 atkspd, f18 mov, f27 ACC (Roquet), f26 CRIT DMG, f28 Dodge, f29 CRIT, f30
CRIT Resist, f2 evolution form.

- Serratica 10★/L200 = `12000*10+305*199 = 180,695` HP, `410*10+19*199 = 7,881`
  ATK — confirmed in-game.
- Live per-star ladder vs our `perStar`: HP 182/183, ATK 182/183.
- `live_hero_params` Ordinary vs APK: 169/176; the 7 misses (Paladin, Druid,
  Moltanica, Grizzly Reaper, Death Knight, Destroyer, Juggernaut) are wrong-form
  extractions — APK is right there, reconcile before trusting the file.

## 2. The attribute set — VERIFIED (`Hero_Attr` enum)

HP, Attack, Attack Range, ATK SPD, MOV SPD, **ACC (internally "Roquet")**, Dodge,
CRIT, CRIT DMG, CRIT Resist, **Tenacity (crowd-control + crit resist)**, **Life
Drain (lifesteal)**. ATK SPD / Range / ACC are constant per hero; ACC changes per
evolution form. CRIT/CRIT DMG/Dodge/CRIT Resist are integer ratings, 0 for most
heroes (cross-checked: Heartbreaker CRIT 250, Phantom King Dodge 2500, Alphamech
CRIT DMG 1500).

## 3. Evolution / grades — DERIVED

`live_hero_params.json` stores `perStar_HP, HPinc, perStar_ATK, ATKinc` **per
grade** (Ordinary, Evo1…Evo4), each obeying §1 — this resolves the perStar-vs-inc
split that the entangled live curve alone could not. Internal check: Moltanica
Ordinary `160*10 + 158*199 = 33,042` = its stored `HP_10s_L200`. `evo_group`
bundles forms and skins (Moltanica: 21 forms / 27 grades); pick by the `grade`
label. DERIVED because the Ordinary grade is only 169/176 vs APK and no evolved
in-game reading is checked yet.

## 4. Stat stacking — VERIFIED (model, `Hero::GetAttr`)

    effective_X = baseX + Σ FLAT sources + Σ PERCENT sources
    (Attack cached at CBaseObject+0x150, MaxHP at +0x154)

FLAT sources, each a summed `Hero::` getter: gear (`GetEquipBaseAttrAll`),
equipment level (`GetEquipmentLvlInfoAdd`), equip refine (`GetEquipRefineSame`),
equip set bonus (`GetEquipSuitItems`), awaken/red-hero (`GetRedHeroAttrAll`),
super-pet (`GetSuperPetAttrAdd`), skin (`SetHeroSkinAttrAdd`), nobility/rank
(`SetNobilityAttr`), soul-arms (`SetSoulArmsWithRefineData`), guild tech
(`GetConsortiaTechPersonSkillAdd`), insignia / crest / inscription / soul / holy /
artifact, Posy inlay. PERCENT sources: talents/traits multiply a component by a
float ratio; star bonus % via `getAttStarAddtionPercentage`. General percent op
everywhere: `value * percent / 100`.

System → data table (for the calculator): base `Hero.data`, gear `EquipBase.xml`,
crest `Equipment.xml` (铭牌), insignia `Runes.xml`, inscription `Inscription.xml`,
breakthrough `HeroAwake.xml`+`TopLevel.xml`, destiny `FateCalculate.xml`+
`HeroFate.xml`, relic `Artifact.xml`, soul `Soul/Soularms.xml`, holy
`HeroHoly.xml`, talent `Talent.xml`+`TalentManual.xml`, totem `Herototem.xml`,
pet `Pet*.xml`, enchant `live_enchantments.json`, traits Type35/36, skill
`Skill.data`.

## 5. The full damage formula — VERIFIED (structure), `BearAttackDamage`

    power     = GetAttack (final ATK, cached +0x150) * FormulaManager pet scaling
    rawDmg    = power
              * AttackRatio[attackType][armorType] / 100        (§6)
              * defender.getDamage_Reduce()  (= 1 - reduceStat*0.0001, a damage-taken multiplier)   (§7)
              * randomVariance   (rand within [min,max] at def+0xd8/0xda/0xde)
              * critMultiplier   (isCrit ? GetCritDamage() : 1.0)        (§7)
    final     = LessenFinal(rawDmg)   (clamp to a minimum floor)
    penetration: GetIgnoreAttribute(0x20/0x40) can bypass defense
    apply: Shield first (DamageShield / +0x15c, capped at MaxHP), then HP (+0x158)

There is a genuine **random variance** on every hit, and hits deplete Shield
before HP. `damage_reduce` itself grows with armor tier:
`GetHeroDamageReduce = base[+0x50] + grow[+0x60]*(armorType-1)`.

## 6. Attack-type vs armor matrix — VERIFIED (`ParaManager::GetAttackRatio`)

Percent multiplier, row = attack type, col = armor 1..5. `damage *= Ratio/100`.

| atk ↓ / armor → | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| Melee  | 100 | 150 | 75 | 70 | 65 |
| Pierce | 150 | 75 | 100 | 70 | 65 |
| Magic  | 75 | 100 | 150 | 70 | 65 |
| Siege  | 50 | 50 | 50 | 250 | 65 |
| Hero   | 125 | 125 | 125 | 100 | 100 |

Heroes attack as type Hero, so hero-vs-hero = 1.0. Matches `AttackRatio.xml`.

## 7. Crit, hit/dodge, defense, tenacity — VERIFIED conversions + DERIVED rolls

Rating→effect conversions (constant `0.0001`), VERIFIED by **executing** the
native code under Unicorn emulation and in `combat.py`:

    crit_chance   = crit * 10000 / (crit + 1000) / 10000     (250→.20, 1000→.50, 3000→.75)
    crit_damage   = 1.5 + critDmgStat * 0.0001               (5000→2.0x, 10000→2.5x)
    dmg_taken     = 1 - reduceStat * 0.0001                  (MULTIPLY; 5000→x0.5, 10000→x0)

The damage-taken factor was **corrected** by execution: it multiplies incoming
damage and reduces it (an earlier static reading had `1 +` / divide — wrong sign).
Skill scaling is likewise executed: a skill's numeric effect =
`ceil(coeff% * base_stat / 100)` (`combat.skill_value`; FormulaManager
`_function_001..005`).

The rolls (mechanism VERIFIED, exact `ratio` constant DERIVED):

- **Crit roll** (`JudgeAttackState`): `rand(1000) < (attackerCritChance −
  defenderTenacity) * ratio`. **Tenacity directly subtracts from crit chance** —
  it is anti-crit as well as crowd-control resist. `combat.effective_crit_chance`
  models this (subtracting Tenacity through the same curve — DERIVED).
- **Hit vs dodge**: `Roquet` (accuracy) vs `Dodge`, both raw ratings, resolved by
  the same `rand(1000)` roll.

The exact `ratio` scaling and Tenacity's rating space still need one extraction
or reading (the mechanism is certain, the constant is not).

## 8. Energy / skill trigger — DERIVED

Skills charge on an MP/energy gauge: `AddMP` / `GetMaxMP` / `getMPFull` → cast.
`SweepBattleProcessor::GetEnergyPoint` = energy gained per action.
`SceneMagicManager::CheckSkillMark` selects the skill; on cast, `MagicBuffer`
pushes the buff (§9) and `FormulaManager::CallFunction` computes the numeric
effect from `Skill.data`. Exact energy-per-hit / per-second and the ATK-SPD→
interval mapping (`getAttackSpeed`) are the remaining constants.

## 9. Effects & buffs — VERIFIED mechanics, per-type numbers partly OPEN

Effects are **data-driven**: `Buffer.xml` maps a buffer id → one or more
`BufferType`s (combinable, e.g. "19,28"). The engine applies them generically —
`SceneMagicManager::_affectBuffer` (a 6,320-byte switch on `BufferType`) calls:

- **HP**: `SetCurrHP`, `DamageHP`, `ModifyHp`, `ModifyEnhanceHP`, `InitHp`.
- **Speed**: `ModifyMoveSpeed`, `ModifyAttackSpeed`.
- **Status (crowd control)**: `SetObjectState` / `UnSetObjectState` set object
  **state bits** — this is how Stun, Silence, Freeze, Entangle, Inhibit work.
- **Cooldown**: `ModifyCDTime`. **Lifesteal**: `GetSuckToDamage`.
- **Transform**: `Transformer`, `HeroShapeshift`. **Skill grant/remove**:
  `SetSecondarySkillID` / `DelSecondarySkillID`.

Companion dispatchers: `_affectSpell` (direct damage), `_affectHeartbeat` /
`DealHeartbeat` (damage-over-time tick), `DealRevivalNode` (revive),
`DisperseBuffer` (dispel). `MagicBuffer` holds the live state: LifeLine (revive),
HealthShield (absorb), IgnoreAttribute (penetration), Deadliness (lethal DoT
stacks), Redirection, Lightning (chain), DamageTop (cap), Endow buffs.

**Damage modifiers layered on §5** (`T_ObjectSpellInfo`, each Get+Modify):
DamageTurbo (amplify %), LessenDamage (flat reduce), RealDamagePer (% max-HP true
damage), ReboundDamage (reflect/thorns), SkillSuckHP (lifesteal), TargetRaceDMG /
TargetTypeDMG (bonus vs race/unit-type), CritLevel / CritDamageLevel,
IgnoreMaxDamage.

There are **59 distinct `BufferType`s across 1,308 buffers**
(`live_buffer_types.json`; commonest: type 8 ×178, 92 ×156, 20 ×145, 91 ×125).
Effect vocabulary (Text_EN): Stun, Silence, Freeze (3s / CD 20s), Entangle,
Inhibit, Curse, Berserk, Fearless (immune). Deployable spells = `Magic.xml`;
tower-defense passives = `TD_Effect.xml`.

**RESOLVED (statically): every in-use BufferType → mechanic.** The dispatch is a
jump table at `0x2049200` (98 subtypes), and `BufferType == subtype`, so all 59
in-use types are classified (`effect_types.json` / `effect_subtypes.json`,
browsable via the `combat_effects` and `game_systems` tools):

- **38** value effects (stat mod / damage / heal).
- **12** status effects (`SetObjectState`, each a unique `eObjectState` bit).
- **1** hard crowd control that halts the unit — **type 39** (bit `0x1000`,
  Stun/Freeze class, 11 buffers).
- **1** immunity / cleanse — **type 3** (`UnSetObjectState`, bit `0x4`).
- **7** secondary-dispatch types (99–114) beyond the main jump table.

**The only remaining gap:** the `eObjectState` bit → exact English name
(is `0x1000` Stun or Freeze?). That label is not a string in the binary; it lives
in the runtime enum and needs a **Frida trace on a live client** (hook
`_affectBuffer` + `SetObjectState`, log the bit↔skill-name pair). The mechanics,
the primitives, and the vocabulary are complete; only the human-readable status
names are missing.

## 10. Skill coefficients — VERIFIED encoding

`Skill.data` per skill: **f8 = % effect, f16 = damage coefficient (16.16
fixed-point = damage %), f7 = targets, f2 = duration ms** (see
`live_skill_data.json`). The "N% ATK" coefficients also appear in the skill effect
text (3,939 instances), scaling with skill level. `FormulaManager::_function_000
..005` are the arithmetic primitives the coefficients feed (`_000` = no-op;
others = value×param/divisor); e.g. pet-scaling type3 = `(petLow%*A +
petHigh%*B)/100`.

## 11. Open problems (all that remains)

Only these; each needs a running client (Frida) or one in-game reading — the
static RE is essentially complete.

1. **Status bit → English name** (§9) — Frida trace: hook `SetObjectState`, log
   bit↔skill-name.
2. **Exact crit/hit `ratio` + Tenacity space** (§7).
3. **Energy + ATK-SPD interval constants** (§8).
4. **Evolution validation** (§3) — one evolved reading + reconcile the 7 rows.
5. **Destiny/Fate** — decode `FateCalculate.QualityFactor` to HP/ATK.

## 12. What is solid today, and what runs

Verified and runnable in the MCP:

- **Stats** — `hero_stats_calc` (two-term law, all grades) and the full attribute
  set + stacking model with every named source.
- **Combat** — `combat_math` explains one hit; `combat.py` holds the executed
  conversions (crit chance, crit damage, the corrected damage-taken multiplier,
  skill scaling), the attack-type matrix, and Tenacity's crit subtraction.
- **Effects** — `combat_effects` and `game_systems` browse the resolved 59-type
  effect taxonomy.
- **Simulation** — `simulate_fight` runs an expected-value auto-attack duel
  between two builds (winner, DPS, crit-with-tenacity, time-to-kill). Skills,
  energy, heals/shields and crowd control are the next layer to add, once their
  constants (§11) are closed.

The frontier is now **dynamic tracing** for the last constants, and building the
simulator up from auto-attacks to full skill/effect battles.
