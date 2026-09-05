"""Full refresh pipeline: seed -> heroes -> talents -> every other casclash
category -> derived catalogs (signatures, enchantments, pets, crests, traits).

Curated seed tags/roles are preserved; scraping only fills factual data
(stats, skills, effects, catalog names). Run from cron for auto-refresh.
"""
import argparse
import sys

from . import db, scrape, seed, tiers

# casclash categories that have their own entity pages (besides heroes/talents)
OTHER_CATS = ["buildings", "guildbuildings", "decorations", "dungen", "watchers", "slime"]


def load_seed(conn) -> None:
    for tbl, rows in (("talents", seed.TALENTS), ("insignias", seed.INSIGNIAS),
                      ("enchantments", seed.ENCHANTMENTS), ("equipment", seed.EQUIPMENT)):
        for r in rows:
            db.upsert(conn, tbl, {"name": r["name"], "effect": r["effect"],
                                  "tags_json": r["tags"], "source": r["source"]}, "name")
    for h in seed.HEROES:
        db.upsert(conn, "heroes", {
            "id": h["id"], "name": h["name"], "role": h.get("role"),
            "tags_json": h.get("tags"), "skill_base": h.get("skill_base"),
            "rec_talents_json": h.get("rec_talents"),
            "rec_equipment_json": h.get("rec_equipment"),
            "rec_enchant_json": h.get("rec_enchant"), "source": h["source"],
        }, "id")
    for t in tiers.seed_tiers():
        db.upsert(conn, "tiers", t, ["hero", "mode", "source"])
    conn.commit()


def _cat(conn, category, name, effect=None, effect_max=None, stats=None,
         icon=None, extra=None, levels=None, entity_id=None) -> None:
    if not name:
        return
    db.upsert(conn, "catalog", {"category": category, "name": name, "id": entity_id,
                                "effect": effect,
                                "effect_max": effect_max, "stats_json": stats or {},
                                "icon": icon, "extra_json": extra or {},
                                "levels_json": levels or [], "source": "casclash"},
              ["category", "name"])


def scrape_heroes(conn, limit=None, delay=None) -> dict:
    n_h = n_sig = 0
    catalogs_done = False
    for d in scrape.crawl_heroes(limit=limit, delay=delay):
        name = d["name"]
        ex = conn.execute("SELECT id, source FROM heroes WHERE name=? COLLATE NOCASE",
                          (name,)).fetchone()
        hid = ex["id"] if ex else d["id"]
        source = "casclash+seed" if (ex and ex["source"] and "seed" in ex["source"]) else "casclash"
        db.upsert(conn, "heroes", {"id": hid, "name": name, "icon": d["icon"],
                  "stats_json": d["stats"], "skill_base": d["skill_base"],
                  "skill_max": d["skill_max"], "levels_json": d.get("levels") or [],
               "source": source}, "id")
        n_h += 1
        if d.get("signature"):
            _cat(conn, "signature", d["signature"], extra={"hero": name})
            n_sig += 1
        if not catalogs_done and any(d["catalogs"].values()):
            cmap = {"enchantments": "enchantment", "pets": "pet",
                    "crests": "crest", "traits": "trait"}
            for src_key, cat in cmap.items():
                for nm in d["catalogs"].get(src_key, []):
                    _cat(conn, cat, nm)
                    if cat == "enchantment":
                        db.upsert(conn, "enchantments", {"name": nm, "source": "casclash"}, "name")
            catalogs_done = True
        if n_h % 15 == 0:
            conn.commit()
    conn.commit()
    return {"heroes": n_h, "signatures": n_sig}


def scrape_talents(conn, limit=None, delay=None) -> int:
    n = 0
    for d in scrape.crawl_category("talents", limit=limit, delay=delay):
        db.upsert(conn, "talents", {"name": d["name"], "effect": d["effect_base"],
                                    "levels_json": d.get("levels") or [],
                                    "source": "casclash"}, "name")  # seed tags preserved
        _cat(conn, "talent", d["name"], effect=d["effect_base"],
             effect_max=d["effect_max"], icon=d["icon"], levels=d.get("levels") or [],
             entity_id=d["id"])
        n += 1
        if n % 15 == 0:
            conn.commit()
    conn.commit()
    return n


def scrape_categories(conn, cats, limit=None, delay=None) -> dict:
    out = {}
    for cat in cats:
        n = 0
        for d in scrape.crawl_category(cat, limit=limit, delay=delay):
            _cat(conn, cat, d["name"], effect=d["effect_base"], effect_max=d["effect_max"],
                 stats=d["stats"], icon=d["icon"], levels=d.get("levels") or [],
                 entity_id=d["id"])
            n += 1
            if n % 15 == 0:
                conn.commit()
        conn.commit()
        out[cat] = n
    return out


def run(seed_only=False, limit=None, delay=None, categories=None) -> dict:
    conn = db.connect()
    db.init_db(conn)
    load_seed(conn)
    result = {"heroes": 0, "signatures": 0, "talents": 0, "categories": {}}
    if not seed_only:
        try:
            result.update(scrape_heroes(conn, limit=limit, delay=delay))
            result["talents"] = scrape_talents(conn, limit=limit, delay=delay)
            result["categories"] = scrape_categories(
                conn, categories or OTHER_CATS, limit=limit, delay=delay)
        except Exception as e:  # noqa: BLE001
            print(f"! scrape stage failed ({e}); seed data is still loaded.")
    db.set_meta(conn, "last_refresh", db.now())
    db.set_meta(conn, "scraped_heroes", str(result["heroes"]))
    conn.commit()
    result["counts"] = db.counts(conn)
    result["catalog_counts"] = db.catalog_counts(conn)
    conn.close()
    return result


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Refresh ALL Castle Clash data")
    ap.add_argument("--seed-only", action="store_true")
    ap.add_argument("--limit", type=int, default=None, help="cap entities per category (testing)")
    ap.add_argument("--delay", type=float, default=None, help="seconds between requests")
    ap.add_argument("--categories", nargs="*", default=None,
                    help=f"subset of {OTHER_CATS} (default all)")
    a = ap.parse_args(argv)
    res = run(seed_only=a.seed_only, limit=a.limit, delay=a.delay, categories=a.categories)
    print(f"\nrefresh done. heroes={res['heroes']} signatures={res['signatures']} "
          f"talents={res['talents']} categories={res['categories']}")
    print(f"counts={res['counts']}")
    print(f"catalog={res['catalog_counts']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
