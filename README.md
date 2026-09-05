# castle-clash-mcp

An MCP server that answers Castle Clash from real game data and the engine's own
formulas, not from a model's guess.

Ask an LLM how much HP Serratica has at 10 stars level 200 and it guesses. This
server computes it: `12000*10 + 305*199 = 180,695`, the exact in-game number.
Every stat and every combat number comes from the game's data plus formulas
recovered from the client → the answer is derived, not remembered.

## What it knows

- 203 heroes, exact base stats per evolution grade → `hero_stats_calc`, `hero_dossier`
- The full stacking model (gear, crest, insignia, talent, soul, holy, runes, ...) folded into effective stats
- The real damage math, recovered from `libgame.so` → `combat_math`
- 200+ game tables, 426 skills, items, gacha drop odds → `game_systems`, `search_all`
- The effect engine: 59 buffer types resolved to their mechanic → `combat_effects`
- Exact skill damage from the numeric coefficients → `skill_data`, `skill_damage`
- A stat-based build generator and scorer → `generate_build`, `build_score`
- A 1v1 fight simulator built on the verified formulas → `simulate_fight`

The math is written up in [docs/GAME_MATH.md](docs/GAME_MATH.md): stat scaling,
the crit / damage / defense formulas, the attack-type matrix, the effect engine.
Each formula is tagged verified or open, with the experiment that closes it.

## Install

```bash
git clone https://github.com/mmadersbacher/castle-clash-mcp
cd castle-clash-mcp
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/python scripts/selfcheck.py   # asserts the verified anchors
```

## Wire into an MCP client

```bash
claude mcp add castle-clash -- /path/to/castle-clash-mcp/.venv/bin/ccmcp-server
```

Or in a client config:

```json
{ "mcpServers": {
    "castle-clash": { "command": "/path/to/castle-clash-mcp/.venv/bin/ccmcp-server" }
} }
```

## Tools

Heroes and stats: `hero_dossier` (one-call hub: stats, every grade, skill damage
at the hero's own ATK, recommended build and its grade), `hero_stats_calc`,
`hero_sheet`, `get_hero`, `hero_level_stats`, `rank_heroes`, `compare_heroes`,
`list_heroes`, `tier_list`.

Skills: `skill_data` (numeric per-level coefficients), `skill_damage` (exact
damage at a given ATK), `skill_levels`, `hero_skills`, `totem_skill`.

Combat: `combat_math` explains one hit, `combat_effects` browses the effect
taxonomy, `simulate_fight` runs a duel.

Builds: `generate_build` ranks talents by the numbers for offense / ehp /
balanced, `build_score` grades one build, `recommend_build` fills a build with
capability-aware picks, `check_build` flags redundancies and gaps.

Cross-reference: `related` resolves any name to what connects to it (a skill to
the heroes that use it, a hero to its skill, an item to its system).

Game data: `game_systems`, `get_system`, `system_lookup`, `search_all`,
`gacha_odds`, plus per-catalog lookups (`get_crest`, `get_insignia`, `get_pet`,
`get_soularm`, ...).

## The math is checked, not asserted

`scripts/selfcheck.py` locks the anchors and fails on drift: Serratica
180,695/7,881 and Dynamica 157,700/9,279 (both confirmed against a real account
to the unit), plus the crit, crit-damage, damage-reduce and skill-scaling
constants. Those combat constants were confirmed by executing the native code,
so a wrong sign or a bad edit gets caught immediately.

What is not yet pinned (a few status labels, the energy and attack-speed
constants) is listed in the doc, each with the reading or trace that closes it.

## Data

Hero stats and the game tables are extracted from the client and the community
handbook `en.casclash.com`. `data/sources/MANIFEST.md` maps every file to what it
is and where it came from. The raw cc_data dump and local scratch are not
bundled → the core (stats, combat, sim, builds, dossier) runs without them.

Castle Clash is IGG's game. This is an unofficial fan project, not affiliated
with or endorsed by IGG, and the game data belongs to IGG. The code is MIT.
