#!/usr/bin/env python3
"""Scrape casclash per-evolution base + per-level (Lv1-80) tables for every hero.
Output: data/sources/wiki_hero_levels.json  keyed by hero id."""
import json, time, sys, os
sys.path.insert(0, "/home/titan/castle-clash-mcp")
from ccmcp import scrape, wikilevels

SRC = "/home/titan/castle-clash-mcp/data/sources"
ids = {}
game = json.load(open(f"{SRC}/game_hero_stats.json"))
for nm, d in game.items():
    ids[str(d["id"])] = nm
hin = json.load(open("/home/titan/engagements/castle-clash/gamedata/parsed/hero_id_name.json"))
for grp, m in hin.items():
    if isinstance(m, dict):
        for hid, nm in m.items():
            ids.setdefault(str(hid), nm)
# known epics not in either
for hid, nm in {"70205": "Serratica", "70223": "Celestica", "70242": "Malefica",
                "70248": "Dreadshade"}.items():
    ids.setdefault(hid, nm)
print(f"hero ids to scrape: {len(ids)}", flush=True)
out = {}
for i, (hid, nm) in enumerate(sorted(ids.items(), key=lambda x: int(x[0])), 1):
    html = scrape.fetch(f"https://en.casclash.com/handbook/heroes/{hid}/", retries=3)
    if not html:
        print(f"[{i}/{len(ids)}] {nm}({hid}) FETCH FAIL", flush=True); continue
    d = wikilevels.parse(html)
    # drop empty/zero stages
    pl = {}
    for st, t in d["per_level"].items():
        if any(r[1] not in ("0", "", None) for r in t["rows"]):
            pl[st] = t
    out[hid] = {"name": nm, "base_by_evolution": d["base_by_evolution"], "per_level": pl}
    if i % 20 == 0:
        print(f"[{i}/{len(ids)}] {nm}: stages={list(pl)}", flush=True)
        json.dump(out, open(f"{SRC}/wiki_hero_levels.json", "w"), ensure_ascii=False)
    time.sleep(0.4)
json.dump(out, open(f"{SRC}/wiki_hero_levels.json", "w"), ensure_ascii=False, indent=0)
print(f"\nDONE {len(out)} heroes -> wiki_hero_levels.json", flush=True)
