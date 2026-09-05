"""Central, cached loader for every JSON data source.

One place resolves + reads + caches source files, so no module hardcodes a path
or re-parses a file per call. Roots map to config.*_DIR (see data/sources/MANIFEST.md):

    load("game_hero_stats.json")            -> data/sources/
    load("heroes_complete.json", "game")    -> data/sources/game/
    load("Achievement.json", "enriched")    -> data/sources/enriched/

Returned objects are cached and SHARED across callers — treat them as read-only.
Call clear_cache() after regenerating any source file (e.g. a live-data refresh).
"""
import json
from functools import lru_cache

from . import config

_ROOTS = {
    "sources": config.SOURCES_DIR,
    "game": config.GAME_DIR,
    "enriched": config.ENRICHED_DIR,
}


@lru_cache(maxsize=512)
def load(name: str, root: str = "sources"):
    """Load and cache a JSON source. Returns the parsed object, or None if the
    file is absent. The result is shared — do not mutate it in place."""
    base = _ROOTS.get(root)
    if base is None:
        raise ValueError(f"unknown source root: {root!r} (expected one of {sorted(_ROOTS)})")
    p = base / name
    if not p.exists():
        return None
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def path(name: str, root: str = "sources"):
    """Resolve a source file to its Path without loading it."""
    return _ROOTS[root] / name


def clear_cache() -> None:
    """Drop the in-memory source cache (call after refreshing data on disk)."""
    load.cache_clear()
