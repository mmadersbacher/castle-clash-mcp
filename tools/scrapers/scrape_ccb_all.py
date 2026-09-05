import re, json, time, httpx
from bs4 import BeautifulSoup
UA="Mozilla/5.0 (X11; Linux x86_64; rv:129.0) Gecko/20100101 Firefox/129.0"
slugs=[l.strip() for l in open("ccb_slugs.txt") if l.strip()]
print("hero slugs on castleclashbuilds:", len(slugs), flush=True)
line=re.compile(r"ATK\s+([\d,]+)\s+HP\s+([\d,]+)\s+ATK SPD\s+([\d,]+)\s+Move SPD\s+([\d,]+)\s+Range\s+(\d+)\s+ATK/Lv\s+\+?([\d,]+)\s+HP/Lv\s+\+?([\d,]+)")
namerx=re.compile(r"← Back\s+(.+?)\s+(Epic|Legend(?:ary)?|Elite|Ordinary)\b")
n=lambda s:int(s.replace(",",""))
out={}
for i,s in enumerate(slugs,1):
    try:
        r=httpx.get(f"https://castleclashbuilds.com/heroes/{s}",headers={"User-Agent":UA},timeout=25,follow_redirects=True)
        t=BeautifulSoup(r.text,"html.parser").get_text(" ",strip=True)
        m=line.search(t); nm=namerx.search(t)
        name=(nm.group(1).strip() if nm else s.replace("-"," ").title())
        typ=(nm.group(2) if nm else None)
        if m:
            out[name]={"slug":s,"type":typ,"ATK":n(m.group(1)),"HP":n(m.group(2)),"ATKSPD":n(m.group(3)),"MOV":n(m.group(4)),"Range":int(m.group(5)),"ATKinc":n(m.group(6)),"HPinc":n(m.group(7))}
            print(f"[{i}/{len(slugs)}] {name}: HP {out[name]['HP']} +{out[name]['HPinc']} | ATK {out[name]['ATK']} +{out[name]['ATKinc']}",flush=True)
        else:
            print(f"[{i}/{len(slugs)}] {s}: no stat line",flush=True)
    except Exception as e:
        print(f"[{i}/{len(slugs)}] {s}: ERROR {e}",flush=True)
    time.sleep(0.3)
json.dump(out,open("/home/titan/castle-clash-mcp/data/sources/ccb_all_base_stats.json","w"),indent=1)
print(f"\nDONE {len(out)} heroes with base stats -> data/sources/ccb_all_base_stats.json",flush=True)
