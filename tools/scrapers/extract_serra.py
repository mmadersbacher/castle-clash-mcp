import json, re
from bs4 import BeautifulSoup
try:
    html = json.load(open("serra_parse.json"))["parse"]["text"]
    t = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    print("rendered chars:", len(t))
    seen = 0
    for m in re.finditer(r"(?i)(hp|health|attack|atk|dmg|evo\w*|star\w*|base)[^.\n]{0,60}?([0-9][0-9,]{2,})", t):
        print("  ", t[max(0, m.start()-25):m.end()+15])
        seen += 1
        if seen >= 30:
            break
except Exception as e:
    print("parse failed:", e, open("serra_parse.json").read()[:200])
print("=== raw wikitext infobox-ish lines ===")
for line in open("serra_raw.wiki", encoding="utf-8", errors="replace"):
    if re.search(r"(?i)hp|attack|atk|dmg|evo|star|base|^\|", line):
        print("  ", line.rstrip()[:140])
