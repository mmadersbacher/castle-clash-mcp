"""SQLite storage layer for Castle Clash data."""
import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS heroes (
    id            TEXT PRIMARY KEY,
    name          TEXT UNIQUE NOT NULL,
    slug          TEXT,
    role          TEXT,
    icon          TEXT,
    stats_json    TEXT,
    skill_base    TEXT,
    skill_max     TEXT,
    tags_json     TEXT,
    rec_talents_json    TEXT,
    rec_equipment_json  TEXT,
    rec_enchant_json    TEXT,
    levels_json   TEXT,
    source        TEXT,
    updated_at    TEXT
);
CREATE TABLE IF NOT EXISTS talents (
    name TEXT PRIMARY KEY, effect TEXT, tags_json TEXT, levels_json TEXT, source TEXT, updated_at TEXT
);
CREATE TABLE IF NOT EXISTS insignias (
    name TEXT PRIMARY KEY, effect TEXT, tags_json TEXT, source TEXT, updated_at TEXT
);
CREATE TABLE IF NOT EXISTS enchantments (
    name TEXT PRIMARY KEY, effect TEXT, tags_json TEXT, source TEXT, updated_at TEXT
);
CREATE TABLE IF NOT EXISTS equipment (
    name TEXT PRIMARY KEY, effect TEXT, tags_json TEXT, source TEXT, updated_at TEXT
);
CREATE TABLE IF NOT EXISTS tiers (
    hero TEXT, mode TEXT, tier TEXT, source TEXT, updated_at TEXT,
    PRIMARY KEY (hero, mode, source)
);
CREATE TABLE IF NOT EXISTS catalog (
    category TEXT, name TEXT, id TEXT, effect TEXT, effect_max TEXT,
    stats_json TEXT, icon TEXT, extra_json TEXT, levels_json TEXT, source TEXT, updated_at TEXT,
    PRIMARY KEY (category, name)
);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
"""

_JSON_COLS = {
    "heroes": {"stats_json", "tags_json", "rec_talents_json", "rec_equipment_json", "rec_enchant_json", "levels_json"},
    "talents": {"tags_json", "levels_json"}, "insignias": {"tags_json"},
    "enchantments": {"tags_json"}, "equipment": {"tags_json"},
    "catalog": {"stats_json", "extra_json", "levels_json"},
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect() -> sqlite3.Connection:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _migrate(c: sqlite3.Connection) -> None:
    for table in ("heroes", "talents", "catalog"):
        try:
            c.execute(f"ALTER TABLE {table} ADD COLUMN levels_json TEXT")
        except sqlite3.OperationalError:
            pass  # column already exists


def init_db(conn: Optional[sqlite3.Connection] = None) -> None:
    c = conn or connect()
    c.executescript(SCHEMA)
    _migrate(c)
    c.commit()
    if conn is None:
        c.close()


def upsert(conn: sqlite3.Connection, table: str, row: dict, pk) -> None:
    pks = [pk] if isinstance(pk, str) else list(pk)
    row = dict(row)
    for col in _JSON_COLS.get(table, set()):
        if col in row and not isinstance(row[col], (str, type(None))):
            row[col] = json.dumps(row[col], ensure_ascii=False)
    row.setdefault("updated_at", now())
    cols = list(row.keys())
    placeholders = ",".join("?" for _ in cols)
    updates = ",".join(f"{c}=excluded.{c}" for c in cols if c not in pks)
    action = f"DO UPDATE SET {updates}" if updates else "DO NOTHING"
    sql = (
        f"INSERT INTO {table} ({','.join(cols)}) VALUES ({placeholders}) "
        f"ON CONFLICT({','.join(pks)}) {action}"
    )
    conn.execute(sql, [row[c] for c in cols])


def set_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )


def get_meta(conn: sqlite3.Connection, key: str, default: Any = None) -> Any:
    r = conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return r["value"] if r else default


def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    for k, v in list(d.items()):
        if k.endswith("_json") and isinstance(v, str):
            try:
                d[k[:-5]] = json.loads(v)
            except json.JSONDecodeError:
                d[k[:-5]] = None
            del d[k]
    return d


def get_entity(conn: sqlite3.Connection, table: str, name: str) -> Optional[dict]:
    r = conn.execute(
        f"SELECT * FROM {table} WHERE name=? COLLATE NOCASE", (name,)
    ).fetchone()
    return _row_to_dict(r) if r else None


def find_hero(conn: sqlite3.Connection, name: str) -> Optional[dict]:
    r = conn.execute("SELECT * FROM heroes WHERE name=? COLLATE NOCASE", (name,)).fetchone()
    if not r:
        r = conn.execute(
            "SELECT * FROM heroes WHERE name LIKE ? COLLATE NOCASE ORDER BY length(name) LIMIT 1",
            (f"%{name}%",),
        ).fetchone()
    return _row_to_dict(r) if r else None


def hero_tiers(conn: sqlite3.Connection, hero: str) -> list[dict]:
    rows = conn.execute(
        "SELECT mode,tier,source FROM tiers WHERE hero=? COLLATE NOCASE", (hero,)
    ).fetchall()
    return [dict(r) for r in rows]


def counts(conn: sqlite3.Connection) -> dict:
    out = {}
    for t in ("heroes", "talents", "insignias", "enchantments", "equipment", "tiers"):
        out[t] = conn.execute(f"SELECT COUNT(*) n FROM {t}").fetchone()["n"]
    return out


TIER_ORDER = {"S+": 0, "S": 1, "A+": 2, "A": 3, "B+": 4, "B": 5, "C": 6, "D": 7, "E": 8}


def tier_rank(t: Optional[str]) -> int:
    return TIER_ORDER.get((t or "").upper().replace(" ", ""), 99)


def heroes_with_tier(conn: sqlite3.Connection, mode: str = "overall") -> list[dict]:
    out = []
    for r in conn.execute("SELECT name, role FROM heroes").fetchall():
        trows = conn.execute(
            "SELECT tier FROM tiers WHERE hero=? COLLATE NOCASE AND mode=?", (r["name"], mode)
        ).fetchall()
        best = min((t["tier"] for t in trows), key=tier_rank, default=None)
        out.append({"name": r["name"], "role": r["role"], "tier": best})
    out.sort(key=lambda x: (tier_rank(x["tier"]), x["name"]))
    return out


def catalog_counts(conn: sqlite3.Connection) -> dict:
    rows = conn.execute(
        "SELECT category, COUNT(*) n FROM catalog GROUP BY category ORDER BY category"
    ).fetchall()
    return {r["category"]: r["n"] for r in rows}


def list_catalog(conn: sqlite3.Connection, category: str, limit: int = 300) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM catalog WHERE category=? COLLATE NOCASE ORDER BY name LIMIT ?",
        (category, limit),
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_catalog_entry(conn: sqlite3.Connection, category: str, name: str) -> Optional[dict]:
    r = conn.execute(
        "SELECT * FROM catalog WHERE category=? COLLATE NOCASE AND name=? COLLATE NOCASE",
        (category, name),
    ).fetchone()
    return _row_to_dict(r) if r else None
