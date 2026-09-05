"""casclash handbook scraper. Structure verified against live HTML 2026-09.

Categories that exist: heroes, talents, buildings, guildbuildings, decorations,
dungen, watchers, slime. There are NO standalone pet/insignia/enchantment/crest
pages on casclash -- those appear only as full dropdown catalogs inside every
hero page (extract_catalogs), and each hero's own signature item sits in its
'Equipment' section.
"""
import re
import time
from typing import Iterator, Optional

from bs4 import BeautifulSoup

from . import config

_ID_RE = {c: re.compile(rf"/handbook/{c}/(\d+)/")
          for c in ("heroes", "talents", "buildings", "guildbuildings",
                    "decorations", "dungen", "watchers", "slime")}
_ICON_RE = re.compile(r"/icon/[a-z]+/\d+\.png")
_INT_RE = re.compile(r"^-?\d[\d,]*$")
_STAT_LABELS = {"HP", "Attack", "ATK SPD", "MOV SPD", "Attack Range", "ACC",
                "Dodge", "CRIT", "CRIT DMG", "CRIT Resist", "DEF", "Defense"}
_EFFECT_KW = ("%", "ATK", "DMG", "Raise", "Increase", "Reduce", "Deals", "Deal ",
              "Recover", "Grant", "Heal", "Summon", "When ", "Energy", "energy",
              "damage", "Damage", "chance", "second")
_NOISE = {"Notice", "Pet", "Enchantments", "Traits", "Crests", "Equipment",
          "Hero Talents", "Skins", "Destiny"}


def fetch(url: str, retries: int = 3) -> Optional[str]:
    import httpx  # lazy: only needed when scraping
    headers = {"User-Agent": config.USER_AGENT, "Accept-Language": "en-US,en;q=0.9"}
    last = None
    for attempt in range(retries):
        try:
            r = httpx.get(url, headers=headers, timeout=config.REQUEST_TIMEOUT,
                          follow_redirects=True)
            if r.status_code == 200 and len(r.text) > 500:
                return r.text
            last = f"HTTP {r.status_code}"
        except Exception as e:  # noqa: BLE001
            last = str(e)
        time.sleep(0.8 * (attempt + 1))
    print(f"  ! fetch failed {url}: {last}")
    return None


def _soup(html: str):
    return BeautifulSoup(html, "html.parser")


def _content(soup):
    return soup.select_one(".entry-content") or soup


def _title_name(soup) -> str:
    t = soup.select_one("h1.entry-title")
    txt = t.get_text(strip=True) if t else ""
    return txt.split(":", 1)[1].strip() if ":" in txt else txt


def _icon(content) -> Optional[str]:
    for img in content.find_all("img"):
        if _ICON_RE.search(img.get("src", "")):
            return config.BASE_URL + img["src"]
    return None


def _parse_stats(content) -> dict:
    for table in content.find_all("table"):
        rows = [[c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
                for tr in table.find_all("tr")]
        if not any(cells and cells[0].rstrip(":") in _STAT_LABELS for cells in rows):
            continue
        stats = {}
        for cells in rows:
            if len(cells) >= 2 and cells[0].endswith(":") and cells[0].strip(":"):
                key = cells[0].rstrip(":").strip()
                val = cells[1].strip()
                stats[key] = int(val.replace(",", "")) if _INT_RE.match(val) else val
        if stats:
            return stats
    return {}


def _effects(content, prefer_deals: bool = False) -> tuple:
    lines = [t.strip() for t in content.stripped_strings]
    desc = [t for t in lines if len(t) > 14 and " " in t and any(k in t for k in _EFFECT_KW)]
    if prefer_deals:
        deals = [t for t in desc if t.startswith("Deal")]
        if deals:
            return deals[0], deals[-1]
    return (desc[0], desc[-1]) if desc else (None, None)


_ROOT_CACHE: dict = {}


def _extract_links(html: str, cat: str) -> list[dict]:
    rx = _ID_RE[cat]
    seen, out = set(), []
    for a in _soup(html).select(f'a[href*="/handbook/{cat}/"]'):
        m = rx.search(a.get("href", ""))
        if not m or m.group(1) in seen:
            continue
        seen.add(m.group(1))
        out.append({"id": m.group(1), "name": a.get_text(strip=True),
                    "url": f"{config.BASE_URL}/handbook/{cat}/{m.group(1)}/"})
    return out


def _root_html() -> Optional[str]:
    if "html" not in _ROOT_CACHE:
        _ROOT_CACHE["html"] = fetch(f"{config.BASE_URL}/handbook/", retries=6)
    return _ROOT_CACHE.get("html")


def category_index(cat: str, html: Optional[str] = None) -> list[dict]:
    # explicit html (tests) wins
    if html is not None:
        return _extract_links(html, cat)
    # try the category's own index; some small index pages 404 intermittently
    page = fetch(f"{config.BASE_URL}/handbook/{cat}/", retries=3)
    out = _extract_links(page, cat) if page else []
    if not out:  # fall back to the reliable handbook root, which links every entity
        root = _root_html()
        if root:
            out = _extract_links(root, cat)
    return out


def hero_index(html: Optional[str] = None) -> list[dict]:
    return category_index("heroes", html)


def _clean_names(names: list[str]) -> list[str]:
    out, seen = [], set()
    for n in names:
        n = n.strip()
        if not n or n.lower() in seen or _INT_RE.match(n) or len(n) > 40 or n in _NOISE:
            continue
        seen.add(n.lower())
        out.append(n)
    return out


def extract_catalogs(html: str) -> dict:
    """Full dropdown catalogs + signature, sliced by <h2> position on a hero page."""
    content = _content(_soup(html))
    head_map = {"hero talents": "talents", "equipment": "signature",
                "enchantments": "enchantments", "crests": "crests",
                "pet": "pets", "traits": "traits"}
    stop = ("skins", "destiny", "additionally", "features", "select the best", "claim")
    sections: dict = {}
    current = None
    for el in content.find_all(True):
        if el.name in ("h1", "h2", "h3"):
            t = el.get_text(" ", strip=True).lower().rstrip(":")
            key = next((v for k, v in head_map.items() if t.startswith(k)), None)
            current = None if (key is None and any(t.startswith(s) for s in stop)) else key
            continue
        if current is None:
            continue
        if el.name == "img":
            v = (el.get("title") or el.get("alt") or "").strip()
        elif el.name == "a":
            v = el.get_text(strip=True)
        else:
            continue
        if v:
            sections.setdefault(current, []).append(v)
    return {k: _clean_names(v) for k, v in sections.items()}


def parse_levels(content) -> list[dict]:
    """Per-level progression from the 'Level | Notice' table (talents & hero skills).
    Returns [{level, effect, might?, cooldown?, magic_duration?}] in level order."""
    for table in content.find_all("table"):
        rows = [[c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
                for tr in table.find_all("tr")]
        rows = [r for r in rows if any(r)]
        if not rows:
            continue
        header = [h.strip().lower() for h in rows[0]]
        if "level" not in header or "notice" not in header:
            continue
        li, ni = header.index("level"), header.index("notice")
        extra = {h: header.index(h) for h in ("might", "cooldown", "magic duration")
                 if h in header}
        out = []
        for r in rows[1:]:
            if len(r) <= max(li, ni):
                continue
            lvl, eff = r[li].strip(), r[ni].strip()
            if not lvl or not eff:
                continue
            entry = {"level": lvl, "effect": eff}
            for h, i in extra.items():
                if i < len(r) and r[i].strip():
                    entry[h.replace(" ", "_")] = r[i].strip()
            out.append(entry)
        if out:
            return out
    return []


def parse_hero(html: str, hid: str = "", url: str = "") -> dict:
    soup = _soup(html)
    content = _content(soup)
    name = _title_name(soup)
    levels = parse_levels(content)
    if levels:
        base, mx = levels[0]["effect"], levels[-1]["effect"]
    else:
        base, mx = _effects(content, prefer_deals=True)
    cats = extract_catalogs(html)
    sig = cats.get("signature") or []
    return {
        "id": hid or (_ID_RE["heroes"].search(url).group(1)
                      if _ID_RE["heroes"].search(url or "") else name),
        "name": name, "icon": _icon(content), "stats": _parse_stats(content),
        "skill_base": base, "skill_max": mx, "levels": levels,
        "signature": sig[0] if sig else None,
        "catalogs": {k: cats.get(k, []) for k in ("enchantments", "pets", "crests", "traits")},
        "source": "casclash",
    }


def parse_entity(html: str, cat: str, eid: str = "", url: str = "") -> dict:
    soup = _soup(html)
    content = _content(soup)
    levels = parse_levels(content)
    if levels:
        base, mx = levels[0]["effect"], levels[-1]["effect"]
    else:
        base, mx = _effects(content)
    return {"category": cat, "id": eid, "name": _title_name(soup),
            "icon": _icon(content), "stats": _parse_stats(content),
            "effect_base": base, "effect_max": mx, "levels": levels,
            "source": "casclash"}


def crawl_heroes(limit: Optional[int] = None, delay: Optional[float] = None) -> Iterator[dict]:
    idx = hero_index()
    if limit:
        idx = idx[:limit]
    delay = config.CRAWL_DELAY if delay is None else delay
    for i, h in enumerate(idx, 1):
        html = fetch(h["url"])
        if not html:
            continue
        try:
            d = parse_hero(html, hid=h["id"], url=h["url"])
            if not d.get("name"):
                d["name"] = h["name"]
            print(f"  [heroes {i}/{len(idx)}] {d['name']}  stats={len(d['stats'])} sig={d['signature']}")
            yield d
        except Exception as e:  # noqa: BLE001
            print(f"  ! parse failed {h['url']}: {e}")
        time.sleep(delay)


def crawl_category(cat: str, limit: Optional[int] = None,
                   delay: Optional[float] = None) -> Iterator[dict]:
    idx = category_index(cat)
    if limit:
        idx = idx[:limit]
    delay = config.CRAWL_DELAY if delay is None else delay
    for i, e in enumerate(idx, 1):
        html = fetch(e["url"])
        if not html:
            continue
        try:
            d = parse_entity(html, cat, eid=e["id"], url=e["url"])
            # some category pages title as a generic template ("Reference"); the
            # index/root anchor carries the real name -> prefer it when title is bad
            if not d.get("name") or d["name"].strip().lower() in ("reference", "notice"):
                d["name"] = e["name"] or d.get("name")
            print(f"  [{cat} {i}/{len(idx)}] {d['name']}  stats={len(d['stats'])}")
            yield d
        except Exception as ex:  # noqa: BLE001
            print(f"  ! parse failed {e['url']}: {ex}")
        time.sleep(delay)
