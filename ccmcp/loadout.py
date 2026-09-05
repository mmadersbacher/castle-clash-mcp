"""Full loadout stat contributions from the real game tables.

Flat global-level tables (Attack/HP + secondary): Inscription, Soularms, Soul, Artifact.
Crests (Camp): per type+level Attack/HP/Tenacity/Crit/Dodge/Hit_DMG.
Named items (Equipment=insignias, Runes): per level Hp/Attack.
Returns the summed delta over the full stat set; folds into statcalc's effective block.
"""
from . import gamedata

STATS = ["Attack", "HP", "Tenacity", "Crit", "Dodge", "Hit_DMG"]
# pet talent (team-wide aura) -> (stat, kind). kind 'pct' multiplies, 'raw' adds.
PET_TALENT = {
    "bloodlust hunt": ("Attack", "pct"), "pursuit strike": ("ATK SPD", "pct"),
    "beastly instinct": ("Dodge", "raw"), "savage stomp": ("Crit", "raw"),
    "law of survival": ("dmg_reduction", "pct"),
}
FLAT_TABLES = {"inscription": "Inscription", "soularms": "Soularms", "soul": "Soul", "artifact": "Artifact"}
ITEM_TABLES = {"insignia": "Equipment", "equipment": "Equipment", "emblem": "Equipment",
               "crest_item": "Equipment", "rune": "Runes"}


def _i(x):
    try:
        return int(float(x))
    except (TypeError, ValueError):
        return 0


def _lv(r):
    return r.get("Lvl") or r.get("Lv") or r.get("Level")


def _flat(table, level):
    if not level:
        return {s: 0 for s in STATS}
    for r in gamedata.rows(table) or []:
        if str(_lv(r)) == str(level):
            return {s: _i(r.get(s)) for s in STATS}
    return {s: 0 for s in STATS}


def crest(name, level):
    if not name or not level:
        return None
    for c in gamedata.rows("Camp") or []:
        if str(c.get("NameID_en", "")).lower() == str(name).lower():
            row = next((x for x in (c.get("_children") or []) if str(x.get("Lvl")) == str(level)), None)
            return {s: _i((row or {}).get(s)) for s in STATS} if row is not None else {s: 0 for s in STATS}
    return None


def item(table, name, level):
    for r in gamedata.rows(table) or []:
        if str(r.get("NameID_en", "")).lower() == str(name).lower():
            row = next((c for c in (r.get("_children") or []) if str(c.get("Lvl")) == str(level)), None)
            out = {s: 0 for s in STATS}
            if row:
                out["HP"] = _i(row.get("Hp"))
                out["Attack"] = _i(row.get("Attack"))
            return out
    return None


def pet(talent_name, level):
    """Pet talent aura at a level -> {stat, kind, value}. Value = the % / raw at that talent level."""
    if not talent_name or not level:
        return None
    key = str(talent_name).strip().lower()
    stat_kind = PET_TALENT.get(key)
    for r in gamedata.rows("PetTalent") or []:
        en = (r.get("NameID_en") or r.get("Name") or "").lower()
        if en == key:
            row = next((c for c in (r.get("_children") or []) if str(c.get("Lv")) == str(level)), None)
            val = _i((row or {}).get("Value"))
            stat, kind = stat_kind or ("Attack", "pct")
            return {"talent": r.get("NameID_en") or talent_name, "stat": stat, "kind": kind, "value": val}
    return None


def total(inscription=0, soularms=0, soul=0, artifact=0, crest_name=None, crest_level=0,
          pet_talent=None, pet_talent_level=0, gear=None):
    tot = {s: 0 for s in STATS}
    pct = {"Attack": 0.0, "HP": 0.0, "ATK SPD": 0.0, "dmg_reduction": 0.0}
    parts = []
    for key, tbl in FLAT_TABLES.items():
        lvl = {"inscription": inscription, "soularms": soularms, "soul": soul, "artifact": artifact}[key]
        if lvl:
            c = _flat(tbl, lvl)
            for s in STATS:
                tot[s] += c[s]
            parts.append({"source": key, "level": lvl, **{s: c[s] for s in STATS if c[s]}})
    if crest_name and crest_level:
        c = crest(crest_name, crest_level)
        if c:
            for s in STATS:
                tot[s] += c[s]
            parts.append({"source": "crest", "name": crest_name, "level": crest_level,
                          **{s: c[s] for s in STATS if c[s]}})
    if pet_talent and pet_talent_level:
        pt = pet(pet_talent, pet_talent_level)
        if pt:
            if pt["kind"] == "pct" and pt["stat"] in pct:
                pct[pt["stat"]] += pt["value"]
            elif pt["stat"] in tot:
                tot[pt["stat"]] += pt["value"]
            parts.append({"source": "pet", **pt})
    for g in gear or []:
        tbl = ITEM_TABLES.get(str(g.get("type", "")).lower())
        if tbl and g.get("name"):
            c = item(tbl, g["name"], g.get("level", 1))
            if c:
                for s in STATS:
                    tot[s] += c[s]
                parts.append({"source": g["type"], "name": g["name"], "level": g.get("level", 1),
                              **{s: c[s] for s in STATS if c[s]}})
    return {"delta": tot, "pct": pct, "parts": parts}


# ---- comprehensive loadout over the canonical sys_* systems ----
from . import systems as _sys


def _rows(system):
    return _sys.rows(system)


def _flat_lookup(system, level, lv_keys=("Lvl", "Lv", "level"), stat_keys=None):
    stat_keys = stat_keys or {"Attack": ("Attack", "atk"), "HP": ("HP", "Hp", "hp"),
                              "Tenacity": ("Tenacity",)}
    for r in _rows(system):
        lv = next((r.get(k) for k in lv_keys if r.get(k) is not None), None)
        if str(lv) == str(level):
            out = {}
            for stat, keys in stat_keys.items():
                out[stat] = _i(next((r.get(k) for k in keys if r.get(k) not in (None, "")), 0))
            return out
    return {}


def _named_level(system, name, level):
    it = _sys.lookup(system, name)
    if "error" in it:
        return {}
    row = next((c for c in (it.get("levels") or []) if str(c.get("lvl") or c.get("Lvl")) == str(level)), None)
    if not row:
        return {}
    return {"Attack": _i(row.get("atk") or row.get("Attack")), "HP": _i(row.get("hp") or row.get("HP"))}


def _holy(name, star):
    it = _sys.lookup("holy", name)
    if "error" in it:
        return {}
    row = next((s for s in (it.get("stars") or []) if str(s.get("Star")) == str(star)), None)
    if not row:
        return {}
    return {"Attack": _i(row.get("Attack")) + _i(row.get("PassiveAttack")), "HP": _i(row.get("HP"))}


def compute(loadout: dict) -> dict:
    """Full effective delta+pct from a loadout dict over all stat systems."""
    lo = loadout or {}
    tot = {s: 0 for s in STATS}
    pct = {"Attack": 0.0, "HP": 0.0, "ATK SPD": 0.0, "dmg_reduction": 0.0}
    parts = []

    def add(label, c):
        if c:
            for s in STATS:
                if s in c:
                    tot[s] += c[s]
            parts.append({"source": label, **{k: v for k, v in c.items() if v}})

    # global-level flat systems
    if lo.get("inscription"):
        add("inscription", _flat_lookup("inscription", lo["inscription"]))
    def _grouped(system, group, level, lv_key="Lv"):
        for r in _rows(system):
            if r.get("_group") == group and str(r.get(lv_key)) == str(level):
                return {"Attack": _i(r.get("Attack")), "HP": _i(r.get("HP") or r.get("Hp")),
                        "Tenacity": _i(r.get("Tenacity"))}
        return {}
    if lo.get("soularms"):
        add("soularms", _grouped("soul", "soularms_levels", lo["soularms"]))
    if lo.get("soul"):
        add("soul", _grouped("soul", "soul_levels", lo["soul"]))
    if lo.get("pinnacle"):
        add("pinnacle", _grouped("breakthrough", "pinnacle_TopLevel", lo["pinnacle"]))
    if lo.get("relics"):
        for r in _rows("relics"):
            for c in (r.get("levels") or []):
                if str(c.get("Lv")) == str(lo["relics"]):
                    add("relics", {"Attack": _i(c.get("Attack")), "HP": _i(c.get("Hp"))}); break
    # named + level
    for key, system in (("insignia", "insignia"), ("crest_item", "crest")):
        for g in lo.get(key + "s", []) if isinstance(lo.get(key + "s"), list) else ([lo[key]] if lo.get(key) else []):
            if isinstance(g, dict):
                add(key, _named_level(system, g.get("name"), g.get("level", 1)))
    # career crest (Camp), rich stats
    if lo.get("crest") and lo.get("crest_level"):
        add("career_crest", crest(lo["crest"], lo["crest_level"]) or {})
    # holy per star
    if lo.get("holy"):
        h = lo["holy"]
        add("holy", _holy(h.get("name"), h.get("star", 0)))
    # traits (Attack/HP flat, resolved by generated English name)
    tmap = {t["name"].lower(): t for t in _sys.traits_named()}
    for tname in lo.get("traits", []) or []:
        t = tmap.get(str(tname).strip().lower())
        if t:
            add("trait", {"Attack": _i(t.get("Attack")), "HP": _i(t.get("HP"))})
    # gear pieces (Attack)
    for g in lo.get("gear", []) or []:
        it = _sys.lookup("gear", g.get("name") if isinstance(g, dict) else g)
        if "error" not in it:
            add("gear", {"Attack": _i(it.get("Attack"))})
    # raw explicit bonuses (in-game system totals the user reads directly)
    bons = lo.get("bonuses") or {}
    _K = {"ATK": "Attack", "Attack": "Attack", "HP": "HP", "Crit": "Crit", "CRIT": "Crit",
          "Dodge": "Dodge", "Tenacity": "Tenacity", "Hit_DMG": "Hit_DMG", "CRIT DMG": "Hit_DMG"}
    for k, v in bons.items():
        stat = _K.get(k)
        if stat in tot:
            tot[stat] += _i(v)
            parts.append({"source": "bonus:" + k, stat: _i(v)})
    # pet aura (% / raw)
    if lo.get("pet_talent") and lo.get("pet_talent_level"):
        pt = pet(lo["pet_talent"], lo["pet_talent_level"])
        if pt:
            if pt["kind"] == "pct" and pt["stat"] in pct:
                pct[pt["stat"]] += pt["value"]
            elif pt["stat"] in tot:
                tot[pt["stat"]] += pt["value"]
            parts.append({"source": "pet", **pt})
    return {"delta": tot, "pct": pct, "parts": parts}
