import json, re, time, urllib.parse, sys
import httpx
from bs4 import BeautifulSoup
UA = "Mozilla/5.0 (X11; Linux x86_64; rv:129.0) Gecko/20100101 Firefox/129.0"
API = "https://castle-clash.fandom.com/api.php"
hv = json.load(open("hero_variables.json"))
heroes = sorted(n for n, d in hv.items() if d.get("HP") and d.get("DMG") and str(d["HP"]).isdigit())
trip = re.compile(r"\[\s*([\d,]+)\s*\+\]\s*([\d,]+)\s*\(\+\s*([\d,]+)\)")
base = re.compile(r"([\d,]+)\s*\(\+\s*([\d,]+)\)")
def num(s): return int(s.replace(",", ""))
out = {}
for i, name in enumerate(heroes, 1):
    try:
        r = httpx.get(API, params={"action":"parse","page":name,"prop":"text","format":"json","formatversion":2},
                      headers={"User-Agent": UA}, timeout=30)
        html = r.json()["parse"]["text"]
        t = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
        rec = {}
        for lab, key in (("Damage :", "dmg"), ("Hitpoints :", "hp")):
            m = re.search(re.escape(lab) + r"\s*" + base.pattern, t)
            if m: rec[key] = {"base": num(m.group(1)), "inc": num(m.group(2))}
        for lab, key in (("Evo1 DMG :", "e1dmg"), ("Evo1 HP :", "e1hp"), ("Evo2 DMG :", "e2dmg"), ("Evo2 HP :", "e2hp")):
            m = re.search(re.escape(lab) + r"\s*" + trip.pattern, t)
            if m: rec[key] = {"base": num(m.group(1)), "perStar": num(m.group(2)), "perLevel": num(m.group(3))}
        # L1 table anchors for cross-check
        for star, key in ((1, "std_L1"), (4, "e1_L1"), (5, "e2_L1")):
            m = re.search(r"\(%d star\)\s*1\s+([\d,]+)\s+([\d,]+)" % star, t)
            if m: rec[key] = {"dmg": num(m.group(1)), "hp": num(m.group(2))}
        out[name] = rec
        print(f"[{i}/{len(heroes)}] {name}: keys={sorted(rec)}", flush=True)
    except Exception as e:
        print(f"[{i}/{len(heroes)}] {name}: ERROR {e}", flush=True)
    time.sleep(0.35)
json.dump(out, open("fandom_evo_params.json", "w"), indent=1)
have = sum(1 for r in out.values() if "e1hp" in r)
print(f"\nDONE heroes={len(out)} with_evo1={have} with_evo2={sum(1 for r in out.values() if 'e2hp' in r)}", flush=True)
