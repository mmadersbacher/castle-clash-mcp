import re, json, collections
w = open("Template_Hero_Variables.wiki", encoding="utf-8").read()
pairs = re.findall(r"\{\{#vardefine:\s*([^|}]+?)\s*\|\s*([^}]*?)\s*\}\}", w)
print("vardefines:", len(pairs))
heroes = collections.defaultdict(dict)
for name, val in pairs:
    parts = name.split()
    if len(parts) < 2:
        continue
    var = parts[-1]; hero = " ".join(parts[:-1])
    heroes[hero][var] = val
print("heroes with variables:", len(heroes))
vars_all = collections.Counter(v for d in heroes.values() for v in d)
print("variable keys (top 30):", vars_all.most_common(30))
json.dump(heroes, open("hero_variables.json", "w"), indent=1)
for h in ("Serratica", "Malefica", "Dynamica", "Bell Elk Maiden", "Angel"):
    print(f"\n{h}: {heroes.get(h)}")
