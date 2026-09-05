"""Flat HP/ATK contributions from gear, inscription, soul arms (from enriched game tables).

Global level->stat tables: Inscription, Soularms, Artifact ({Lvl|Lv, Hp, Attack}).
Named item + level tables: Equipment (insignias/crests/emblems), Runes ({NameID_en, _children:[{Lvl,Hp,Attack}]}).
Contributions are FLAT additions on top of the star/level/talent-% base stats.
"""
from . import gamedata


def _i(x):
    try:
        return int(x)
    except (TypeError, ValueError):
        return 0


def flat_level(table: str, level: int) -> dict:
    """{Hp, Attack} for a global level->stat table (Inscription/Soularms/Artifact) at `level`."""
    if not level:
        return {"Hp": 0, "Attack": 0}
    for r in gamedata.rows(table) or []:
        lv = r.get("Lvl") or r.get("Lv") or r.get("Level")
        if str(lv) == str(level):
            return {"Hp": _i(r.get("Hp")), "Attack": _i(r.get("Attack"))}
    return {"Hp": 0, "Attack": 0}


def item(table: str, name: str, level: int) -> dict:
    """{Hp, Attack, item, effect} for a named item (Equipment/Runes) at `level`."""
    for r in gamedata.rows(table) or []:
        if str(r.get("NameID_en", "")).lower() == str(name).lower():
            row = next((c for c in (r.get("_children") or []) if str(c.get("Lvl")) == str(level)), None)
            if row:
                return {"Hp": _i(row.get("Hp")), "Attack": _i(row.get("Attack")),
                        "item": r.get("NameID_en"), "effect": row.get("TxtID_en")}
            return {"Hp": 0, "Attack": 0, "item": r.get("NameID_en"), "effect": None}
    return {"error": f"item not found in {table}: {name}"}


_TYPE_TABLE = {"insignia": "Equipment", "equipment": "Equipment", "emblem": "Equipment",
               "crest": "Equipment", "rune": "Runes"}


def total_flat(inscription: int = 0, soularms: int = 0, artifact: int = 0, gear: list = None) -> dict:
    """Sum flat Hp/Attack from inscription+soularms+artifact levels and a gear list
    [{type, name, level}] (insignia/rune)."""
    hp = atk = 0
    parts = []
    for tbl, lvl in (("Inscription", inscription), ("Soularms", soularms), ("Artifact", artifact)):
        if lvl:
            c = flat_level(tbl, lvl)
            hp += c["Hp"]; atk += c["Attack"]
            parts.append({tbl.lower(): lvl, **c})
    for g in gear or []:
        tbl = _TYPE_TABLE.get(str(g.get("type", "")).lower())
        if tbl and g.get("name"):
            c = item(tbl, g["name"], g.get("level", 1))
            if "error" not in c:
                hp += c["Hp"]; atk += c["Attack"]
                parts.append({"type": g["type"], **c})
    return {"Hp": hp, "Attack": atk, "parts": parts}
