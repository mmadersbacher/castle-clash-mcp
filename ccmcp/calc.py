"""Live hero stats via casclash's hero calculator (the unofficial 'API').

There is no official IGG API. But casclash's /hero-calc/ posts to WordPress
admin-ajax.php (action=heroCalcWork, sw=getRez) and returns a fully COMPUTED
stat block for a hero at a given level / skill level / talent / crest / pet /
inscription / reincarnation. The hero id equals the handbook id.
Verified 2026-09: Serratica(70205) L1 HP 48000 -> L200 HP 108695.
"""
import re
from typing import Optional

from . import config, db

AJAX_URL = f"{config.BASE_URL}/wp-admin/admin-ajax.php"
_STATS = ["HP", "Attack", "ATK SPD", "MOV SPD", "Attack Range", "ACC",
          "Dodge", "CRIT", "CRIT DMG", "CRIT Resist"]


def _post(params: dict) -> str:
    import httpx
    headers = {"User-Agent": config.USER_AGENT,
               "Referer": f"{config.BASE_URL}/hero-calc/",
               "X-Requested-With": "XMLHttpRequest"}
    r = httpx.post(AJAX_URL, data=params, headers=headers,
                   timeout=config.REQUEST_TIMEOUT, follow_redirects=True)
    r.raise_for_status()
    return r.text


def _parse_rez(js: str) -> dict:
    from bs4 import BeautifulSoup
    m = re.search(r"\.html\('(.*)'\);", js, re.S)
    html = (m.group(1) if m else js).encode().decode("unicode_escape", "ignore")
    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    out = {}
    for lab in _STATS:
        m = re.search(re.escape(lab) + r"\s*:\s*([0-9][0-9,.]*)(?:\s*\(([0-9,.]+)\))?", text)
        if m:
            out[lab] = int(m.group(1).replace(",", ""))
            if m.group(2):
                out[f"{lab} (buffed)"] = int(m.group(2).replace(",", ""))
    return out


_TALENT_IDS: dict = {}


def talent_id(conn, talent) -> int:
    """Resolve a talent NAME (or numeric id) to its casclash id. Talent id == handbook id
    (verified: Wicked Armor 85381 -> x2.5 ATK at L10, Tenacity 85141 -> x3.3 HP)."""
    if talent in (None, "", 0, "0"):
        return 0
    if str(talent).isdigit():
        return int(talent)
    if not _TALENT_IDS:
        for r in conn.execute("SELECT name, id FROM catalog WHERE category='talent' "
                              "AND id IS NOT NULL AND id!=''").fetchall():
            _TALENT_IDS[r["name"].lower()] = str(r["id"])
        if not _TALENT_IDS:  # ids not persisted yet -> live handbook index
            from . import scrape
            for e in scrape.category_index("talents"):
                _TALENT_IDS[e["name"].lower()] = e["id"]
    tid = _TALENT_IDS.get(str(talent).strip().lower())
    if not tid:
        raise ValueError(f"unknown talent: {talent}")
    return int(tid)


def hero_stats(conn, hero, lvl: int = 200, skill_lvl: int = 10, talent=0, talent_lvl=0,
               camp=0, camp_lvl=0, pet=0, pet_lvl=0, inscription=0, reincarnation=1) -> dict:
    """Fully computed stats. `hero` = name or numeric handbook id. reincarnation=1 means the
    normal EVOLVED form real players have (0 = un-evolved base, unrealistic). Optional
    talent/crest(camp)/pet/inscription are numeric ids (0 = none)."""
    hid, name = str(hero), hero
    if not hid.isdigit():
        h = db.find_hero(conn, hero)
        if not h:
            return {"error": f"hero not found: {hero}"}
        if not str(h["id"]).isdigit():
            return {"error": f"'{h['name']}' is seed-only (no numeric casclash id); can't query the calculator."}
        hid, name = str(h["id"]), h["name"]
    try:
        tid = talent_id(conn, talent)
    except ValueError as e:
        return {"error": str(e)}
    params = {"action": "heroCalcWork", "sw": "getRez",
              "hero[hero]": hid, "hero[lvl]": lvl, "hero[skillLvl]": skill_lvl,
              "hero[talent]": tid, "hero[talentLvl]": talent_lvl,
              "hero[camp]": camp, "hero[campLvl]": camp_lvl,
              "hero[pet]": pet, "hero[petLvl]": pet_lvl,
              "hero[inscription]": inscription, "hero[reincarnation]": reincarnation}
    try:
        stats = _parse_rez(_post(params))
    except Exception as e:  # noqa: BLE001
        return {"error": f"calc request failed: {e}"}
    if not stats or stats.get("HP", 0) == 0:
        return {"error": f"calc returned no stats for hero id {hid} at level {lvl}"}
    return {"hero": name, "id": hid, "level": lvl, "skill_lvl": skill_lvl,
            "applied": {"talent": talent, "talent_id": tid, "talent_lvl": talent_lvl,
                        "camp": camp, "pet": pet, "inscription": inscription,
                        "reincarnation": reincarnation},
            "stats": stats, "source": "casclash hero-calc (live)"}
