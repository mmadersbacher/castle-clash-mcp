"""Generic access to the 182 enriched cc_data game tables (from the user's client RE).

Each table JSON is {_root, Name, ..., _children:[{_tag:'List', ...fields}]}. Rows carry
Chinese Name + English *_en fields (NameID_en, TxtID_en). This exposes them for browse/search.
"""
import json
import os
from . import config, sources

SRC = str(config.ENRICHED_DIR)


def list_tables() -> list:
    if not os.path.isdir(SRC):
        return []
    return sorted(f[:-5] for f in os.listdir(SRC) if f.endswith(".json"))


def _raw(table: str):
    return sources.load(table + ".json", "enriched")


def rows(table: str):
    d = _raw(table)
    if d is None:
        return None

    def find(x):
        if isinstance(x, dict):
            ch = x.get("_children")
            if isinstance(ch, list) and ch and isinstance(ch[0], dict):
                return ch
            for v in x.values():
                r = find(v)
                if r:
                    return r
        elif isinstance(x, list) and x and isinstance(x[0], dict) and x[0].get("_tag"):
            return x
        return None

    return find(d) or []


def _clean(r: dict) -> dict:
    return {k: v for k, v in r.items() if k != "_tag" and not isinstance(v, (list, dict))}


def get_table(table: str, limit: int = 100) -> dict:
    rs = rows(table)
    if rs is None:
        return {"error": f"table not found: {table}. Use list_game_tables."}
    return {"table": table, "row_count": len(rs), "fields": [k for k in rs[0].keys() if k != "_tag"] if rs else [],
            "rows": [_clean(r) for r in rs[:limit]]}


def search(query: str, limit: int = 40) -> list:
    q = str(query).lower()
    hits = []
    for t in list_tables():
        for r in rows(t) or []:
            if q in json.dumps(r, ensure_ascii=False).lower():
                hits.append({"table": t, **_clean(r)})
                if len(hits) >= limit:
                    return hits
    return hits


def _en(r):
    return r.get("NameID_en") or r.get("NameId_en") or r.get("Name") or ""


def item_with_levels(table: str, name: str) -> dict:
    """A named item (Equipment/Runes/Camp) with its per-level _children rows."""
    for r in rows(table) or []:
        if _en(r).lower() == str(name).lower():
            lv = [_clean(c) for c in (r.get("_children") or [])]
            return {"name": _en(r), "id": r.get("NameID") or r.get("NameId"), "table": table,
                    "levels": lv, "level_count": len(lv)}
    return {"error": f"'{name}' not in {table}"}


def flat_named(table: str, name: str, name_field: str = "NameId_en") -> dict:
    """A named entry whose per-level rows are FLAT (one row per level, e.g. SoularmsSkill)."""
    lv = [_clean(r) for r in (rows(table) or []) if (r.get(name_field) or r.get("NameID_en") or "").lower() == str(name).lower()]
    if not lv:
        return {"error": f"'{name}' not in {table}"}
    return {"name": name, "table": table, "levels": lv, "level_count": len(lv)}
