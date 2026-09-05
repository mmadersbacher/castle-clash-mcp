"""Parse casclash hero pages for per-evolution base stats + per-level curves.

Each /handbook/heroes/<id>/ page has a 'Features:' table (each stat has up to 3
columns = Ordinary/Evo1/Evo2 base) and up to 3 per-level tables with header
[Level, HP, Attack, MOV SPD, Might] (Lv1..80). Structure matches the user's
paladin_stats_reference.json. Authoritative per-level HP/ATK curve, no formula.
"""
import re
from typing import Optional
from bs4 import BeautifulSoup

_STAT_ROW = re.compile(r"^(HP|Attack|ATK SPD|MOV SPD|Attack Range|ACC|Dodge|CRIT|CRIT DMG|CRIT Resist):$")
_PL_HEADER = ["Level", "HP", "Attack", "MOV SPD", "Might"]
_STAGES = ["Ordinary", "Evolution1", "Evolution2"]


def _rows(table):
    out = []
    for tr in table.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
        if any(cells):
            out.append(cells)
    return out


def parse(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    content = soup.select_one(".entry-content") or soup
    base, per_level = [], {}
    stage_i = 0
    for table in content.find_all("table"):
        rows = _rows(table)
        if not rows:
            continue
        # base_by_evolution: the table whose rows are 'HP:', 'Attack:' ...
        if not base and any(r and _STAT_ROW.match(r[0]) for r in rows):
            base = [r for r in rows if r and (r[0] == "Features:" or _STAT_ROW.match(r[0]))]
            continue
        # per-level tables: header starts Level/HP/Attack
        hdr = rows[0]
        if len(hdr) >= 5 and hdr[0] == "Level" and hdr[1] == "HP" and hdr[2] == "Attack":
            data = [r for r in rows[1:] if len(r) >= 5 and r[0].isdigit()]
            if data and stage_i < len(_STAGES):
                per_level[_STAGES[stage_i]] = {"header": _PL_HEADER, "rows": data}
                stage_i += 1
    return {"base_by_evolution": base, "per_level": per_level}
