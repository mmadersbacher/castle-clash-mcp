# Data sources — manifest

Single source of truth for what every data file is, which code loads it, and
where it came from. All paths resolve through `ccmcp/config.py` (no module
hardcodes a data path any more), and every file is read through one cached
loader, `ccmcp/sources.py` — `sources.load(name, root)` where `root` is
`sources` / `game` / `enriched`. After regenerating any file on disk (e.g. the
live sweep), call `sources.clear_cache()`.

| config constant | default location | override env |
|---|---|---|
| `DATA_DIR`     | `data/`                 | `CCMCP_DATA` |
| `DB_PATH`      | `data/ccmcp.sqlite`     | `CCMCP_DB` |
| `SOURCES_DIR`  | `data/sources/`         | `CCMCP_SOURCES` |
| `GAME_DIR`     | `data/sources/game/`    | `CCMCP_GAME_DIR` |
| `ENRICHED_DIR` | `data/sources/enriched/`| `CCMCP_ENRICHED_DIR` |
| `RAW_DIR`      | `data/sources/raw/`     | (none — not loaded) |

## Layout

    data/
      ccmcp.sqlite         legacy casclash DB (db.py) — catalog + tier + seed tools
      sources/
        <calc + wiki + skills loose files>   loaded by statcalc/skills/server
        game/              28-system registry (systems.py REGISTRY -> loadout)
        enriched/          182 cc_data tables (gamedata.py)
        raw/               unused-by-code raw client dumps (provenance only)
      scratch/             raw scrape intermediates (gitignored, not shipped)

## Runtime sources (loaded by code)

### `SOURCES_DIR` (loose) — the formula calculator + skills

| file | purpose | loaded by | tools |
|---|---|---|---|
| `game_hero_stats.json`      | base HP/ATK/growth, APK Hero.data (authoritative, 167/167 vs casclash) | statcalc.base_stats (1st) | hero_stats_calc, hero_sheet, rank_heroes, compare_heroes |
| `ccb_all_base_stats.json`   | castleclashbuilds base stats (fallback + newest heroes) | statcalc.base_stats (2nd) | " |
| `new_epic_base_stats.json`  | newest epics Fandom/APK lack | statcalc.base_stats (3rd) | " |
| `fandom_hero_variables.json`| legacy-hero base stats | statcalc.base_stats (4th) | " |
| `fandom_evo_params.json`    | exact EVO1/EVO2 per-star/per-level params (58 Legendaries) | statcalc.evo_params | hero_stats_calc evo=1/2 |
| `movinc.json`               | derived MOV-per-star | statcalc.movinc | " |
| `secondary_overrides.json`  | manual ACC/range fixes for heroes missing from APK | statcalc.secondary | " |
| `wiki_hero_levels.json`     | authoritative per-level tables L1-80 (Ord/Evo1/Evo2) | server.hero_level_stats | hero_level_stats |
| `skills_catalog.json`       | 421 skills w/ per-level effects (symlink -> game/) | skills.py, systems.py | skill_levels, hero_skills |
| `hero_totem_skills.json`    | hero -> totem skill map | skills.py | totem_skill, hero_sheet |

statcalc.base_stats precedence: game_hero_stats -> ccb_all_base_stats ->
new_epic_base_stats -> fandom_hero_variables (first hit wins).

### `GAME_DIR` — the 28-system registry
`systems.py` REGISTRY maps a logical system name to one JSON file here
(heroes_complete, skills_catalog, sys_talents_complete, sys_breakthrough,
sys_runes=insignia, sys_insignia=crest, sys_destiny, sys_equipment_gear,
sys_enchantments, sys_traits, sys_relics, sys_soul, sys_holy, sys_inscription,
sys_endow, pets_full, totem_skills_full, magic_named, buildings_full, monsters,
gacha_pools, items_icons, icon_maps, buffers, summons, runes_named, sentinels).
Tools: game_systems, get_system, system_lookup, search_all; stat-bearing systems
feed loadout.compute (get_hero, hero_sheet, hero_stats_calc `effective`).
See `game/SYSTEMS.md` + `game/INDEX.md` for the field-level mapping.

### `ENRICHED_DIR` — 182 cc_data tables
`gamedata.py` browses every enriched cc_data table (Chinese Name + English
*_en fields). Tools: list_game_tables, get_game_table, search_game_data.

### `DB_PATH` — legacy casclash SQLite
`db.py`. Tools: db_status, list_heroes, get_hero (legacy fields), tier_list,
get_talent/get_insignia/get_enchantment/get_equipment/get_crest/get_pet, and
the rules engine (recommend_build, check_build).

## `RAW_DIR` — provenance only (NOT loaded)
Raw client-RE dumps kept for traceability; no module reads them. The runtime
equivalents live under `game/` (sys_*.json) / `enriched/`:
game_hero_records.json, cc_data_catalog.json, Equipment.json, Magic.json,
Artifact.json, Runes.json, HeroHoly.json, text_en_flat.json, hero_id_name.json.

---

## PENDING — live post-4.5.7 sweep integration

The user's Waydroid capture of the live client lands in
the extraction workspace (`live_*` + `live_curated/`).
The sweep is still in progress; do NOT hard-wire it until the user says it is
complete. Planned landing + wiring (paths are centralized, so this is mostly a
config/loader repoint, no path surgery):

1. `data/sources/live/live_hero_data.json` — 203 heroes, full per-level curves
   for every evolution stage + range/atkspd/ACC/mov. Becomes the PRIMARY source
   in `statcalc.base_stats` (ahead of game_hero_stats.json), and gives evo
   stages straight from the game instead of `fandom_evo_params.json`. Fixes the
   35 new heroes now on ccb fallback (e.g. Tai Lung ACC=null, guessed growth).
2. `live_new_hero_names.json` / `live_new_heroes.json` — id->name for the 35 new
   heroes (70244-70269 + slimes/juggernaut).
3. `live_curated/*.json` (27 tables) — refresh the `GAME_DIR` REGISTRY. Quick
   swap: point `CCMCP_GAME_DIR` at the live dir; permanent: replace game/ files.
4. `live_skills.json` — refresh skills_catalog; `live_table_diff.json` shows
   what changed vs the bundled tables.
5. new gear (161007-10) + insignia (44502 Warring Drum) -> loadout catalogs.

Regression gate to hold across integration — run `.venv/bin/python
scripts/selfcheck.py` (exits nonzero on drift). It asserts the exacts
Serratica 10*/L200/evo0 = 180,695 HP / 7,881 ATK and Dynamica = 157,700 /
9,279, plus dataset floors. The exacts are user-confirmed in-game: if the sweep
moves a base stat and a number changes, review it, don't just edit the gate.
