"""Castle Clash MCP server (stdio).

Tools:
  db_status, list_heroes, get_hero, tier_list,
  get_talent/get_insignia/get_enchantment/get_equipment,
  recommend_build, check_build, refresh_data
"""
from typing import Optional

try:  # mcp >= 2 renamed FastMCP -> MCPServer (identical tool/run API)
    from mcp.server.mcpserver import MCPServer as _Server
except ModuleNotFoundError:  # mcp < 2
    from mcp.server.fastmcp import FastMCP as _Server

from . import buildscore, calc, combat, crossref, db, dossier, gamedata, refresh, rules, sim, skills, sources, statcalc, systems

mcp = _Server("castle-clash")


def _conn():
    conn = db.connect()
    db.init_db(conn)
    return conn


@mcp.tool()
def db_status() -> dict:
    """Show row counts and when the data was last refreshed."""
    conn = _conn()
    try:
        return {"counts": db.counts(conn),
                "catalog": db.catalog_counts(conn),
                "last_refresh": db.get_meta(conn, "last_refresh"),
                "scraped_heroes": db.get_meta(conn, "scraped_heroes")}
    finally:
        conn.close()


@mcp.tool()
def list_heroes(mode: str = "overall", tier: Optional[str] = None, limit: int = 30) -> list:
    """List heroes ranked by tier. `mode` e.g. overall/Guild War/Arena/Dungeons; `tier` filters (S+, S, A+...)."""
    conn = _conn()
    try:
        rows = db.heroes_with_tier(conn, mode=mode)
        if tier:
            rows = [r for r in rows if (r["tier"] or "").upper() == tier.upper()]
        return rows[:limit]
    finally:
        conn.close()


@mcp.tool()
def get_hero(name: str) -> dict:
    """Full hero record: the complete game data (combat, base per evolution, level curves,
    main skill per level, totem, icon) merged with tier + build tags."""
    rich = systems.hero(name)
    conn = _conn()
    try:
        h = db.find_hero(conn, name)
        if isinstance(rich, dict) and "error" not in rich:
            rich = dict(rich)
            if h:
                rich["tiers"] = db.hero_tiers(conn, h["name"])
                rich["build_tags"] = (h.get("tags") or {})
                rich["role"] = h.get("role")
            return rich
        if not h:
            return {"error": f"hero not found: {name}"}
        h["tiers"] = db.hero_tiers(conn, h["name"])
        return h
    finally:
        conn.close()


@mcp.tool()
def tier_list(mode: str = "overall", limit: int = 40) -> list:
    """Ranked tier list for a mode (overall/Guild War/Arena/Dungeons/HBM-LBF/Blitz)."""
    conn = _conn()
    try:
        rows = [r for r in db.heroes_with_tier(conn, mode=mode) if r["tier"]]
        return rows[:limit]
    finally:
        conn.close()


def _get(table: str, name: str) -> dict:
    conn = _conn()
    try:
        e = db.get_entity(conn, table, name)
        return e or {"error": f"not found in {table}: {name}"}
    finally:
        conn.close()


@mcp.tool()
def get_talent(name: str) -> dict:
    """Talent effect and capability tags."""
    return _get("talents", name)


@mcp.tool()
def get_insignia(name: str) -> dict:
    """Insignia/crest-item (Equipment table, 208 items): per-level Hp/Attack + effect text."""
    return gamedata.item_with_levels("Equipment", name)


@mcp.tool()
def get_crest(name: str) -> dict:
    """Career crest (Camp: Oracle/Saint/Brawler/Orderbound/Voidwalker): per-level Attack/HP/Tenacity/Crit/Dodge/Hit_DMG."""
    return gamedata.item_with_levels("Camp", name)


@mcp.tool()
def get_rune(name: str) -> dict:
    """Rune (Runes table, 101): per-level Hp/Attack + effect."""
    return gamedata.item_with_levels("Runes", name)


@mcp.tool()
def get_enchantment(name: str) -> dict:
    """Enchantment = Soul-Arms skill (e.g. 'Bold Ambition', 'Forest Ward'): per-level from game data."""
    return gamedata.flat_named("SoularmsSkill", name)


@mcp.tool()
def get_equipment(name: str) -> dict:
    """Equipment item (Equipment table): per-level Hp/Attack + effect text."""
    return gamedata.item_with_levels("Equipment", name)


@mcp.tool()
def effect_at_level(kind: str, name: str, level: str) -> dict:
    """Effect of a talent or hero skill at a specific level. kind='talent' or 'hero'.
    Returns that level's effect text (+ might/cooldown if present) and the full range."""
    conn = _conn()
    try:
        if kind == "hero":
            e = db.find_hero(conn, name)
            levels = (e or {}).get("levels") or []
        else:
            e = db.get_entity(conn, "talents", name)
            levels = (e or {}).get("levels") or []
        if not e:
            return {"error": f"not found: {kind}/{name}"}
        lv = str(level)
        match = next((L for L in levels if str(L.get("level")) == lv), None)
        return {"name": e.get("name", name), "kind": kind, "level": lv,
                "effect": match.get("effect") if match else None,
                "detail": match,
                "levels_available": [L.get("level") for L in levels],
                "max_effect": levels[-1]["effect"] if levels else None}
    finally:
        conn.close()


@mcp.tool()
def hero_stats(hero: str, level: int = 200, skill_lvl: int = 10, talent: str = "",
               talent_lvl: int = 0, camp: int = 0, camp_lvl: int = 0, pet: int = 0,
               inscription: int = 0, reincarnation: int = 1) -> dict:
    """LIVE fully-computed stats for a hero at a given level (1-200), via casclash's
    calculator (there is no official IGG API). Returns HP, Attack, ATK SPD, MOV SPD,
    Attack Range, ACC, Dodge, CRIT, CRIT DMG, CRIT Resist. `talent` = talent NAME (e.g.
    'Tenacity') or id, with `talent_lvl` 1-10; reincarnation=1 is the normal evolved form.
    camp(crest)/pet/inscription are numeric ids (0 = none)."""
    conn = _conn()
    try:
        return calc.hero_stats(conn, hero, lvl=level, skill_lvl=skill_lvl, talent=talent,
                               talent_lvl=talent_lvl, camp=camp, camp_lvl=camp_lvl,
                               pet=pet, inscription=inscription, reincarnation=reincarnation)
    finally:
        conn.close()


@mcp.tool()
def hero_stats_calc(hero: str, stars: int = 10, level: int = 200, evo: int = 0,
                    talent: str = "", talent_lvl: int = 0, inscription: int = 0,
                    soularms: int = 0, soul: int = 0, artifact: int = 0,
                    crest_name: str = "", crest_level: int = 0,
                    pet_talent: str = "", pet_talent_level: int = 0, gear_json: str = "",
                    loadout_json: str = "") -> dict:
    """TRUSTWORTHY formula-based stats (validated exactly vs the user's real game: Serratica
    10 stars/L200 = 180,695 HP). stat = perStar*Stars + inc*(Level-1); evo=1/2 uses Fandom's
    exact Legendary evolution params. Optional talent name + level applies its HP/ATK %.
    Prefer this over hero_stats (casclash caps stars at 4). inscription/soularms/artifact are
    LEVELS; gear_json is a JSON list of {type:'insignia'|'rune', name, level} — all fold into the
    returned `effective` stats (flat HP/ATK on top of the talent-% base)."""
    import json as _j
    try:
        gear = _j.loads(gear_json) if gear_json else []
    except Exception:
        gear = []
    try:
        loadout = _j.loads(loadout_json) if loadout_json else None
    except Exception:
        loadout = None
    conn = _conn()
    try:
        return statcalc.calc(conn, hero, stars=stars, level=level, evo=evo,
                             talent=talent or None, talent_lvl=talent_lvl,
                             inscription=inscription, soularms=soularms, soul=soul, artifact=artifact,
                             crest_name=crest_name or None, crest_level=crest_level,
                             pet_talent=pet_talent or None, pet_talent_level=pet_talent_level, gear=gear, loadout=loadout)
    finally:
        conn.close()


@mcp.tool()
def hero_level_stats(hero: str, level: int = 80, evo: str = "max") -> dict:
    """EXACT per-level HP/Attack/MOV/Might from casclash's tables (Lv1-80, per evolution),
    authoritative, no formula. evo = 'Ordinary'|'Evolution1'|'Evolution2'|'max'. For level>80
    or higher stars use hero_stats_calc (formula)."""
    data = sources.load("wiki_hero_levels.json", "sources")
    if not data:
        return {"error": "wiki_hero_levels.json not built yet"}
    rec = next((v for v in data.values() if v.get("name", "").lower() == hero.strip().lower()), None)
    if not rec:
        return {"error": f"hero not found in wiki level data: {hero}"}
    pl = rec.get("per_level") or {}
    stage = (sorted(pl)[-1] if pl else None) if evo == "max" else evo
    if stage not in pl:
        return {"error": f"no '{stage}' stage for {hero}; available: {list(pl)}"}
    hdr = pl[stage]["header"]
    row = next((r for r in pl[stage]["rows"] if r and r[0] == str(level)), None)
    if not row:
        return {"error": f"level {level} not in table (Lv1-80 only); use hero_stats_calc"}
    return {"hero": rec["name"], "evolution": stage, "level": level,
            "stats": dict(zip(hdr, row)), "evolutions_available": list(pl),
            "base_by_evolution": rec.get("base_by_evolution")}


@mcp.tool()
def skill_levels(skill: str) -> dict:
    """Per-level effect + English description for any of the 421 game skills (from decoded
    Skill.data). `skill` = name (e.g. 'Divine Shield') or numeric name_id."""
    return skills.skill_levels(skill)


@mcp.tool()
def hero_skills(hero: str) -> dict:
    """A hero's skills: totem skill (name + level count, from Hero.data naming scheme) and a
    pointer to the main active skill (via get_hero / hero_level_stats from the wiki)."""
    t = skills.hero_totem(hero)
    conn = _conn()
    try:
        h = db.find_hero(conn, hero)
        main = (h or {}).get("skill_base") or (h or {}).get("skill_max")
    finally:
        conn.close()
    return {"hero": (h or {}).get("name", hero) if h else hero,
            "totem_skill": ({"name": t["totem_skill"], "id": t["totem_name_id"], "levels": t["levels"]} if t else None),
            "main_skill_text": main,
            "note": "totem from hero_totem_skills.json (94 heroes); main skill text from casclash wiki."}


@mcp.tool()
def list_game_tables() -> list:
    """List all 182 game data tables extracted from the APK (buildings, dungeons, pets, soul
    arms, inscriptions, summon rates, battle pass, guild, monsters, ...)."""
    return gamedata.list_tables()


@mcp.tool()
def get_game_table(table: str, limit: int = 100) -> dict:
    """Rows of a game data table by name (see list_game_tables). Rows carry English *_en fields."""
    return gamedata.get_table(table, limit=limit)


@mcp.tool()
def search_game_data(query: str, limit: int = 40) -> list:
    """Full-text search across ALL 182 game tables. Returns matching rows with their table name."""
    return gamedata.search(query, limit=limit)


@mcp.tool()
def get_pet(name: str) -> dict:
    """Pet lookup (Pet table): id, mark, and its pet-talent. Note: pets give a team-wide %% aura,
    browsable here but not folded into hero_stats_calc's per-hero flat stats."""
    for r in gamedata.rows("Pet") or []:
        en = r.get("NameId_en") or r.get("NameID_en") or r.get("Name")
        if str(en or "").lower() == name.strip().lower():
            return {k: v for k, v in r.items() if k != "_tag" and not isinstance(v, (list, dict))}
    # fall back to a fuzzy contains
    hits = [{k: v for k, v in r.items() if k != "_tag" and not isinstance(v, (list, dict))}
            for r in gamedata.rows("Pet") or []
            if name.strip().lower() in str(r.get("NameId_en") or r.get("Name") or "").lower()]
    return hits[0] if hits else {"error": f"pet not found: {name}"}


@mcp.tool()
def get_soularm(level: int) -> dict:
    """Soul-Arms base stats at a given level (flat Attack/HP/Tenacity added to a hero)."""
    for r in gamedata.rows("Soularms") or []:
        if str(r.get("Lv")) == str(level):
            return {k: v for k, v in r.items() if k != "_tag"}
    return {"error": f"soularms level {level} not found (1..{len(gamedata.rows('Soularms') or [])})"}


@mcp.tool()
def game_systems() -> dict:
    """Every Castle Clash data system and its entry count (heroes, skills, talents, crests,
    insignias, gear, holy, traits, relics, soul, pets, magic, buildings, monsters, gacha, items...)."""
    return systems.systems()


@mcp.tool()
def get_system(system: str, limit: int = 60) -> dict:
    """Rows of a game system (see game_systems). English-annotated (name_en)."""
    rs = systems.rows(system)
    if not rs:
        return {"error": f"unknown system: {system}", "available": list(systems.REGISTRY)}
    clean = [{k: v for k, v in r.items() if not isinstance(v, (list, dict))} for r in rs[:limit]]
    return {"system": system, "count": len(rs), "rows": clean}


@mcp.tool()
def system_lookup(system: str, name: str) -> dict:
    """One entry from a system by English name, with its full per-level/per-star data
    (e.g. system_lookup('holy','Divine Roots'), ('crest','Revive Crest I'), ('gear','Dragon Ring'))."""
    return systems.lookup(system, name)


@mcp.tool()
def hero_complete(hero: str) -> dict:
    """The COMPLETE hero record: combat stats, base per evolution, full level curves (Ord/Evo1/Evo2
    1-80), main skill per level, totem skill, icon. The authoritative all-in-one hero entry."""
    return systems.hero(hero)


@mcp.tool()
def get_icon(kind: str, key: str = "") -> dict:
    """Icon path for a hero/skill/item/pet (kind from icon_maps). Omit key to list icon kinds."""
    return systems.icon(kind, key)


@mcp.tool()
def gacha_odds(pool_type: int) -> dict:
    """Drop odds for a gacha pool (by Type): each reward with its weight and probability %.
    Omit/unknown type returns the list of available pool types."""
    return systems.gacha_odds(pool_type)


@mcp.tool()
def search_all(query: str, limit: int = 40) -> list:
    """Search across ALL 28 game systems at once (heroes, skills, talents, gear, items, ...)."""
    return systems.search_all(query, limit=limit)


@mcp.tool()
def compare_heroes(hero_a: str, hero_b: str, stars: int = 10, level: int = 200) -> dict:
    """Side-by-side computed stats for two heroes at the same stars/level."""
    conn = _conn()
    try:
        a = statcalc.calc(conn, hero_a, stars=stars, level=level)
        b = statcalc.calc(conn, hero_b, stars=stars, level=level)
        if "error" in a or "error" in b:
            return {"error": a.get("error") or b.get("error")}
        keys = ["HP", "Attack", "ATK SPD", "MOV SPD", "Attack Range", "ACC"]
        return {"stars": stars, "level": level, "a": a["hero"], "b": b["hero"],
                "stats": {k: {a["hero"]: a["stats"].get(k), b["hero"]: b["stats"].get(k)} for k in keys}}
    finally:
        conn.close()


@mcp.tool()
def rank_heroes(stat: str = "HP", stars: int = 10, level: int = 200, limit: int = 15) -> list:
    """Rank heroes by a computed stat (HP/Attack) at given stars/level. Newest epics may be missing."""
    conn = _conn()
    try:
        out = []
        for name, hid in [(v.get("name"), k) for k, v in (systems.load("heroes") or {}).items()]:
            r = statcalc.calc(conn, name, stars=stars, level=level)
            v = (r.get("stats") or {}).get(stat) if "error" not in r else None
            if isinstance(v, int):
                out.append({"hero": name, stat: v})
        out.sort(key=lambda x: -x[stat])
        return out[:limit]
    finally:
        conn.close()


@mcp.tool()
def totem_skill(hero: str) -> dict:
    """A hero's Totem skill with English description per level (from totem_skills_full)."""
    return systems.totem_skill(hero)


@mcp.tool()
def hero_sheet(hero: str) -> dict:
    """EVERYTHING about a hero in one call: complete stats + main skill + totem skill summary +
    tier + a recommended build. The one-stop hero overview."""
    conn = _conn()
    try:
        h = systems.hero(hero)
        if "error" in h:
            return h
        dbh = db.find_hero(conn, hero)
        ms = h.get("main_skill") or {}
        ms_lv = ms.get("levels") if isinstance(ms, dict) else None
        tot = systems.totem_skill(hero)
        rec = rules.recommend_build(conn, hero)
        return {
            "name": h["name"], "id": h["id"], "combat": h.get("combat"),
            "base_by_evolution": h.get("base_by_evolution"),
            "main_skill": {"name": (ms.get("name") if isinstance(ms, dict) else None),
                           "max": (ms_lv[-1] if ms_lv else None)},
            "totem_skill": {"name": tot.get("skill_name"), "max": (tot.get("levels") or [{}])[-1] if "error" not in tot else None},
            "tiers": db.hero_tiers(conn, dbh["name"]) if dbh else [],
            "role": (dbh or {}).get("role"),
            "recommended_build": rec.get("build"), "build_rationale": rec.get("rationale"),
            "icon": h.get("icon"),
        }
    finally:
        conn.close()


@mcp.tool()
def recommend_build(hero: str, talent: Optional[str] = None, crest: Optional[str] = None,
                    insignia: Optional[str] = None, enchantment: Optional[str] = None,
                    pet: Optional[str] = None, mode: Optional[str] = None) -> dict:
    """Recommend a full 5-slot build (talent, crest, insignia, enchantment, pet). Pass any slot
    to fix it (e.g. talent='Wicked Armor'); the engine fills the rest without anti-synergies
    (reflection in the enchant slot, energy in talent-or-crest) and explains every pick."""
    conn = _conn()
    try:
        return rules.recommend_build(conn, hero, talent=talent, crest=crest, insignia=insignia,
                                     enchantment=enchantment, pet=pet, mode=mode)
    finally:
        conn.close()


@mcp.tool()
def check_build(hero: str, talent: Optional[str] = None, crest: Optional[str] = None,
                insignia: Optional[str] = None, enchantment: Optional[str] = None,
                pet: Optional[str] = None) -> dict:
    """Validate a 5-slot build: flags reflection redundancy (two slots), energy gaps, missing
    reflection/ATK, signature-talent HP penalties, and revive suggestions. Returns findings + ok."""
    conn = _conn()
    try:
        return rules.check_build(conn, hero, talent=talent, crest=crest, insignia=insignia,
                                 enchantment=enchantment, pet=pet)
    finally:
        conn.close()


@mcp.tool()
def list_categories() -> dict:
    """List catalog categories and how many entries each has (talent, enchantment,
    pet, crest, trait, signature, buildings, decorations, dungen, watchers, ...)."""
    conn = _conn()
    try:
        return db.catalog_counts(conn)
    finally:
        conn.close()


@mcp.tool()
def list_catalog(category: str, limit: int = 300) -> list:
    """List all entries in a catalog category (e.g. pet, crest, trait, signature,
    buildings, decorations, dungen, watchers, slime, talent, enchantment)."""
    conn = _conn()
    try:
        return db.list_catalog(conn, category, limit=limit)
    finally:
        conn.close()


@mcp.tool()
def get_catalog_entry(category: str, name: str) -> dict:
    """Get one catalog entry (effect/stats where casclash provides them)."""
    conn = _conn()
    try:
        e = db.get_catalog_entry(conn, category, name)
        return e or {"error": f"not found: {category}/{name}"}
    finally:
        conn.close()


@mcp.tool()
def refresh_data(seed_only: bool = False, limit: Optional[int] = None) -> dict:
    """Rebuild the database: load seed catalog and (unless seed_only) scrape casclash. `limit` caps heroes scraped."""
    return refresh.run(seed_only=seed_only, limit=limit)


@mcp.tool()
def combat_math(atk: float, attack_type: int = 5, armor_type: int = 5,
                skill_coeff: float = 1.0, is_crit: bool = False,
                crit_rating: int = 0, crit_dmg_rating: int = 0,
                target_reduce_rating: int = 0, target_tenacity_rating: int = 0) -> dict:
    """Explain one hit using the engine's exact formulas (recovered from
    libgame.so, see docs/GAME_MATH.md). attack_type/armor_type 1..5 (Melee,
    Pierce, Magic, Siege, Hero); player heroes attack as 5. skill_coeff=1.0 for a
    normal hit or skill%/100 for a skill. Ratings are raw Hero.data stats.
    Also returns crit chance and crit-damage that the ratings convert to."""
    res = combat.hit_damage(atk, attack_type=attack_type, armor_type=armor_type,
                            skill_coeff=skill_coeff, is_crit=is_crit,
                            crit_dmg_rating=crit_dmg_rating,
                            target_reduce_rating=target_reduce_rating)
    res["crit_chance_from_rating"] = round(combat.crit_chance(crit_rating), 4)
    res["crit_chance_vs_tenacity"] = round(combat.effective_crit_chance(crit_rating, target_tenacity_rating), 4)
    res["crit_damage_from_rating"] = round(combat.crit_damage(crit_dmg_rating), 4)
    res["target_mitigation"] = round(combat.mitigation(target_reduce_rating), 4)
    return res


@mcp.tool()
def simulate_fight(hero_a: str, hero_b: str, stars: int = 10, level: int = 200,
                   evo: int = 0, talent_a: Optional[str] = None, talent_a_lvl: int = 0,
                   talent_b: Optional[str] = None, talent_b_lvl: int = 0,
                   reduce_a: int = 0, reduce_b: int = 0) -> dict:
    """Simulate a 1v1 auto-attack duel between two hero builds using the verified
    damage formulas (see docs/GAME_MATH.md). Returns the expected winner, each
    side's DPS, crit chance (with the opponent's Tenacity), and time-to-kill.
    reduce_a/reduce_b are optional damage-reduce ratings from each build. Skills,
    energy, heals, shields and crowd control are not yet modeled."""
    conn = _conn()
    try:
        a, ea = sim.effective(conn, hero_a, stars, level, evo, talent_a, talent_a_lvl)
        b, eb = sim.effective(conn, hero_b, stars, level, evo, talent_b, talent_b_lvl)
        if ea:
            return {"error": ea}
        if eb:
            return {"error": eb}
        return sim.duel(a, b, reduce_a=reduce_a, reduce_b=reduce_b)
    finally:
        conn.close()


@mcp.tool()
def combat_effects(buffer_type: Optional[int] = None) -> dict:
    """The effect-engine taxonomy recovered from the binary (docs/GAME_MATH.md
    sec 9). With no argument: counts by handler category across the 59 in-use
    BufferTypes. With a buffer_type: that type's mechanic + state bit. Status bits
    map to crowd control (type 39 = hard CC / halt; type 3 = immunity/cleanse)."""
    rows = systems.rows("effect_types")
    if buffer_type is not None:
        r = next((x for x in rows if str(x.get("buffer_type")) == str(buffer_type)), None)
        return r or {"error": f"buffer_type {buffer_type} not in use"}
    cats: dict = {}
    for r in rows:
        h = r.get("handler", "?")
        key = ("hard-CC (halt)" if "Stop" in h else
               "status (SetObjectState)" if "SetObjectState(apply" in h else
               "immunity/cleanse" if "UnSet" in h else
               "value effect (stat/dmg/heal)" if "value" in h else h)
        cats[key] = cats.get(key, 0) + 1
    return {"in_use_buffer_types": len(rows), "by_category": cats,
            "hard_cc_type": 39, "immunity_type": 3,
            "note": "exact state-bit -> English name (e.g. 0x1000 = Stun vs Freeze) "
                    "needs a Frida trace on a live client; mechanics are resolved."}


@mcp.tool()
def hero_dossier(hero: str) -> dict:
    """Everything about one hero in a single call: base combat ratings, every
    evolution grade's exact formula params + 10*/L200 HP/ATK, main + totem skill,
    tier/role, and a recommended build. Ordinary stats are formula-verified;
    evolved grades come from live_hero_params (with a reconciliation flag when a
    multi-form hero mis-extracts its Ordinary grade)."""
    conn = _conn()
    try:
        return dossier.build(conn, hero)
    finally:
        conn.close()


@mcp.tool()
def skill_data(skill: str) -> dict:
    """Numeric per-level data for a skill (from Skill.data): damage % of ATK,
    targets, duration, effect %. 274 of 426 skills carry a real damage
    coefficient. Use skill_damage to turn a % into an actual number."""
    return skills.skill_data(skill)


@mcp.tool()
def skill_damage(skill: str, atk: float, skill_level: Optional[int] = None) -> dict:
    """Exact skill damage for a given ATK, using the verified skill primitive
    (ceil(damage% * ATK / 100), from docs/GAME_MATH.md). Defaults to the skill's
    max level. Returns per-hit damage and the target count."""
    d = skills.skill_data(skill)
    if "error" in d:
        return d
    dmg_levels = [L for L in d["levels"] if (L.get("damage_pct") or 0) > 0]
    if not dmg_levels:
        return {"skill": d["skill"], "note": "this skill has no direct damage coefficient (buff/heal/CC)"}
    row = None
    if skill_level is not None:
        row = next((L for L in dmg_levels if L["lvl"] == skill_level), None)
    row = row or dmg_levels[-1]
    per_hit = combat.skill_value(row["damage_pct"], atk)
    return {
        "skill": d["skill"], "skill_level": row["lvl"], "atk": atk,
        "damage_pct": row["damage_pct"], "per_hit_damage": per_hit,
        "targets": row["targets"],
        "formula": "ceil(damage_pct * ATK / 100)",
    }


@mcp.tool()
def build_score(hero: str, stars: int = 10, level: int = 200, evo: int = 0,
                talent: Optional[str] = None, talent_lvl: int = 0,
                loadout_json: str = "") -> dict:
    """Grade a build by numbers without a fight: effective stats plus EHP
    (tankiness) and an offense score (ATK x attacks/sec x average crit factor),
    all from the verified combat math. loadout_json is the same shape
    hero_stats_calc takes. Use it to compare builds on one hero."""
    import json as _json
    loadout = None
    if loadout_json:
        try:
            loadout = _json.loads(loadout_json)
        except ValueError:
            return {"error": "loadout_json is not valid JSON"}
    conn = _conn()
    try:
        return buildscore.score(conn, hero, stars=stars, level=level, evo=evo,
                                talent=talent, talent_lvl=talent_lvl, loadout=loadout)
    finally:
        conn.close()


@mcp.tool()
def related(query: str) -> dict:
    """Cross-reference any name: resolve whether it is a hero, a skill, or a
    catalog item, and return what connects to it (a skill points to the heroes
    that use it, a hero points to its skill, an item points to its system)."""
    conn = _conn()
    try:
        return crossref.related(conn, query)
    finally:
        conn.close()


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
