import json, sys, re
from bs4 import BeautifulSoup
hero = sys.argv[1]
html = json.load(open(f"val_{hero}.json"))["parse"]["text"]
soup = BeautifulSoup(html, "html.parser")
print(f"##### {hero} #####")
# infobox lines: base + evo per-star/per-level
t = soup.get_text(" ", strip=True)
for lab in ("Damage :", "Hitpoints :", "Evo1 DMG :", "Evo1 HP :", "Evo2 DMG :", "Evo2 HP :"):
    m = re.search(re.escape(lab) + r"\s*([^A-Z]{0,40})", t)
    if m: print("  ", lab, m.group(1).strip()[:40])
# every table that has a 'star' cell: dump rows as cells
for ti, table in enumerate(soup.find_all("table")):
    txt = table.get_text(" ", strip=True)
    if "star" not in txt.lower():
        continue
    rows = []
    for tr in table.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
        if cells: rows.append(cells)
    print(f"  --- table{ti}: {len(rows)} rows; header: {rows[0] if rows else None}")
    for r in rows[1:12]:
        print("     ", r)
