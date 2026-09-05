#!/usr/bin/env python3
"""Extract the AUTHORITATIVE hero stat table from the Castle Clash APK.

Source: assets/cc_data/Hero.data (little-endian int32 records, UNENCRYPTED) +
assets/lan/Text_EN.xml (<List Id=".." Txt=".."/> id->name). Validated 167/167
against casclash. Record layout, relative to the HP field index i:
  Range=i-5, ATKSPD=i-4, MOV=i-3, ATK=i-2, HP=i, [i+1]==100 (marker),
  ATKinc=i+2, HPinc=i+4, ACC=i+6, Dodge=i+7, CRIT=i+8, CRITDMG=i+9,
  CRITResist=i+10, hero_id=i+22.  Base = record matching ccb HP/ATK else min-HP.
Usage: python extract_game_stats.py <Hero.data> <Text_EN.xml> [ccb_all_base_stats.json] > game_hero_stats.json
"""
import struct, re, json, sys
from collections import defaultdict

hero_data, text_xml = sys.argv[1], sys.argv[2]
ccb = {k.lower(): x for k, x in json.load(open(sys.argv[3])).items() if not k.startswith("_")} if len(sys.argv) > 3 else {}
b = open(hero_data, "rb").read(); n = len(b) // 4
v = struct.unpack("<%di" % n, b[:n * 4])
per = defaultdict(list)
for i in range(6, n - 25):
    if (v[i + 1] == 100 and 1 <= v[i - 5] <= 20 and 300 <= v[i - 4] <= 2600 and 60 <= v[i - 3] <= 700
            and v[i - 2] > 0 and v[i] > 0 and v[i + 2] > 0 and v[i + 4] > 0 and v[i + 6] >= 0
            and 10000 <= v[i + 22] < 1000000):
        per[v[i + 22]].append({"HP": v[i], "ATK": v[i - 2], "ATKSPD": v[i - 4], "MOV": v[i - 3],
            "Range": v[i - 5], "ATKinc": v[i + 2], "HPinc": v[i + 4], "ACC": v[i + 6],
            "Dodge": v[i + 7], "CRIT": v[i + 8], "CRITDMG": v[i + 9], "CRITResist": v[i + 10]})
xml = open(text_xml, encoding="utf-8", errors="replace").read()
id2name = {int(m.group(1)): m.group(2) for m in re.finditer(r'<List Id="(\d+)" Txt="([^"]*)"/>', xml)}
out = {}
for hid, recs in per.items():
    nm = id2name.get(hid)
    if not nm or len(nm) > 30 or nm.startswith("%"):
        continue
    cb = ccb.get(nm.lower())
    base = next((r for r in recs if cb and r["HP"] == cb["HP"] and r["ATK"] == cb["ATK"]), None) \
        or min(recs, key=lambda r: r["HP"])
    out[nm] = {"id": hid, **base}
json.dump(out, sys.stdout, indent=1, ensure_ascii=False)
