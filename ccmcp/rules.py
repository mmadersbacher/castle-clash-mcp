"""Slot-aware rule engine: check_build + recommend_build.

Castle Clash heroes equip five independent choice slots:
    talent, crest, insignia, enchantment, pet
Crests mirror talents (e.g. "Revitalize Crest I"), so a crest's capabilities are
derived from its base talent. Rules never look at names, only hero *tags* and the
*capabilities* each slot provides -> explainable, consistent, no double-buying.
"""
import re
from typing import Optional

from . import catalog_caps as cc, db

SLOTS = ["talent", "crest", "insignia", "enchantment", "pet"]
SLOT_STORE = {
    "talent": ("table", "talents"), "insignia": ("table", "insignias"),
    "enchantment": ("table", "enchantments"),
    "crest": ("catalog", "crest"), "pet": ("catalog", "pet"),
}
REFLECT_FAMILY = {"reflect_cap", "reflect_ignore"}
ENERGY_FAMILY = {"energy", "energy_burst", "energy_regen"}
ATK_FAMILY = {"atk", "atk_pct"}
OFFENSE = {"crit", "skill_dmg", "atk", "atk_pct"}
BURST_MODES = {"arena", "blitz"}


def _energy_prefer(mode):
    """Constant energy (Empower) is better for sustained recasts; burst (Revitalize)
    only wins in modes decided in the opening seconds."""
    return "energy_burst" if (mode or "").lower() in BURST_MODES else "energy_regen"
_CREST_RE = re.compile(r"\s+Crest\s+[IVXLC]+$", re.IGNORECASE)


def _tags(entry: Optional[dict]) -> dict:
    return (entry.get("tags") or {}) if entry else {}


def _provides(tags: dict) -> set:
    return set(tags.get("provides") or [])


def _crest_base(name: str) -> str:
    return _CREST_RE.sub("", name or "").strip()


def _resolve(conn, slot: str, name: Optional[str]) -> Optional[dict]:
    if not name:
        return None
    if slot == "enchantment":
        it = cc.find(cc.enchantments, name)
        if it:
            return {"slot": slot, "name": it["name"], "provides": set(it["caps"]),
                    "tags": {"provides": it["caps"]}, "unknown": False, "effect": it["effect"]}
    kind, key = SLOT_STORE[slot]
    entry = db.get_entity(conn, key, name) if kind == "table" else db.get_catalog_entry(conn, key, name)
    if not entry:
        return {"slot": slot, "name": name, "provides": set(), "tags": {},
                "unknown": True, "effect": None}
    tags = _tags(entry)
    if slot == "talent" and not tags.get("provides"):  # derive talent caps from effect text
        tags = {"provides": cc.talent_caps(conn, name)}
    if slot == "crest" and not tags.get("provides"):  # derive crest caps from base talent
        base = db.get_entity(conn, "talents", _crest_base(name))
        tags = _tags(base)
    return {"slot": slot, "name": entry.get("name", name), "provides": _provides(tags),
            "tags": tags, "unknown": False, "effect": entry.get("effect")}


def _resolve_build(conn, build: dict) -> list[dict]:
    return [c for c in (_resolve(conn, s, build.get(s)) for s in SLOTS) if c]


def _has(comps, family):
    return [c for c in comps if c["provides"] & family]


# ---------------------------------------------------------------- rules
def _rule_reflect_redundancy(ht, comps, hero):
    src = _has(comps, REFLECT_FAMILY)
    if len(src) < 2:
        return None
    names = [c["name"] for c in src]
    ignore = [c["name"] for c in src if "reflect_ignore" in c["provides"]]
    if ignore:
        adv = (f"Keep {ignore[0]} (full immunity) and free the other slot for pure offense; "
               f"drop {', '.join(n for n in names if n != ignore[0])}.")
    else:
        adv = "One reflection source is enough; free the other slot."
    return {"rule": "reflect_redundancy", "severity": "warn",
            "slots": [c["slot"] for c in src],
            "message": f"Redundant reflection from {', '.join(names)}. {adv}"}


def _rule_energy_gap(ht, comps, hero):
    if not ht.get("energy_dependent") or _has(comps, ENERGY_FAMILY):
        return None
    return {"rule": "energy_gap", "severity": "warn", "slots": ["talent", "crest"],
            "message": ("Energy-dependent hero with no energy source; the skill casts too slowly. "
                        "Put Revitalize in the talent slot, or Revitalize Crest in the crest slot.")}


def _rule_reflect_gap(ht, comps, hero):
    if not ht.get("reflect_vulnerable") or _has(comps, REFLECT_FAMILY):
        return None
    return {"rule": "reflect_gap", "severity": "warn", "slots": ["enchantment"],
            "message": ("Multi-hit AoE with no reflection mitigation; dies to reflect setups. "
                        "Bold Ambition (enchantment) gives full immunity and keeps the talent slot free.")}


def _rule_atk_gap(ht, comps, hero):
    if not ht.get("atk_scaling") or _has(comps, ATK_FAMILY):
        return None
    return {"rule": "atk_gap", "severity": "info", "slots": ["crest", "talent"],
            "message": "Skill scales with ATK but nothing adds ATK; a War God crest amplifies it."}


def _rule_revive(ht, comps, hero):
    if not ht.get("channeler") or _has(comps, {"revive"}):
        return None
    return {"rule": "revive_suggestion", "severity": "info", "slots": ["insignia"],
            "message": "Channeler: Winged Rebirth doubles battlefield uptime (revive once)."}


def _rule_hp_penalty(ht, comps, hero):
    for c in comps:
        pen = c["tags"].get("hp_penalty")
        sig = c["tags"].get("signature_hero")
        if pen and sig and sig.lower() not in (hero or "").lower():
            return {"rule": "hp_penalty_misuse", "severity": "warn", "slots": [c["slot"]],
                    "message": (f"{c['name']} cuts Max HP by {int(pen*100)}% on non-{sig} heroes; "
                                f"bad fit for {hero}. Use a normal talent/crest instead.")}
    return None


RULES = [_rule_reflect_redundancy, _rule_energy_gap, _rule_reflect_gap,
         _rule_atk_gap, _rule_revive, _rule_hp_penalty]


def check_build(conn, hero: str, talent=None, crest=None, insignia=None,
                enchantment=None, pet=None) -> dict:
    h = db.find_hero(conn, hero)
    if not h:
        return {"error": f"hero not found: {hero}"}
    ht = h.get("tags") or {}
    build = {"talent": talent, "crest": crest, "insignia": insignia,
             "enchantment": enchantment, "pet": pet}
    comps = _resolve_build(conn, build)
    findings = [f for f in (r(ht, comps, h["name"]) for r in RULES) if f]
    for c in comps:
        if c.get("unknown"):
            findings.append({"rule": "unknown_component", "severity": "info", "slots": [c["slot"]],
                             "message": f"'{c['name']}' not found for slot '{c['slot']}' (run refresh_data)."})
    return {"hero": h["name"], "build": {k: v for k, v in build.items() if v},
            "provides": sorted({p for c in comps for p in c["provides"]}),
            "findings": findings, "ok": not any(f["severity"] == "warn" for f in findings)}


def _candidates(conn, slot: str) -> list[str]:
    if slot == "enchantment":
        return [it["name"] for it in cc.enchantments()]  # real 44 Soul-Arms skills
    kind, key = SLOT_STORE[slot]
    if kind == "table":
        return [r["name"] for r in conn.execute(f"SELECT name FROM {key}").fetchall()]
    return [r["name"] for r in conn.execute(
        "SELECT name FROM catalog WHERE category=?", (key,)).fetchall()]


def _pick(conn, slot: str, want: set, avoid: set, prefer: Optional[str] = None) -> Optional[str]:
    best, best_score = None, 0.0
    for name in _candidates(conn, slot):
        c = _resolve(conn, slot, name)
        prov = c["provides"]
        if prov & avoid:
            continue
        score = float(len(prov & want))
        if prefer and prefer in prov:
            score += 0.5
        if c["tags"].get("uncertain"):
            score -= 0.4
        if c["tags"].get("hp_penalty"):
            score -= 1.0  # signature-locked talents are a bad generic pick
        if score > best_score:
            best, best_score = c["name"], score
    return best


def recommend_build(conn, hero: str, talent=None, crest=None, insignia=None,
                    enchantment=None, pet=None, mode: Optional[str] = None) -> dict:
    h = db.find_hero(conn, hero)
    if not h:
        return {"error": f"hero not found: {hero}"}
    ht = h.get("tags") or {}
    build = {"talent": talent, "crest": crest, "insignia": insignia,
             "enchantment": enchantment, "pet": pet}
    why = []

    def cov():
        return {p for c in _resolve_build(conn, build) for p in c["provides"]}

    # 1) insignia: revive for channelers
    if not build["insignia"] and ht.get("channeler"):
        p = _pick(conn, "insignia", {"revive"}, set())
        if p:
            build["insignia"] = p
            why.append(f"insignia={p}: channeler -> revive doubles uptime.")

    # 2) enchantment: put reflection HERE (Bold Ambition = immunity + crit) so the
    #    talent slot stays free for energy; else pure offense
    if not build["enchantment"]:
        if ht.get("reflect_vulnerable") and not (cov() & REFLECT_FAMILY):
            p = _pick(conn, "enchantment", {"reflect_ignore", "crit"}, set(), prefer="reflect_ignore")
            if p:
                build["enchantment"] = p
                why.append(f"enchantment={p}: full reflection immunity + crit, kept off the talent slot.")
        else:
            p = _pick(conn, "enchantment", OFFENSE, REFLECT_FAMILY)
            if p:
                build["enchantment"] = p
                why.append(f"enchantment={p}: reflection already covered -> pure offense (no double-buy).")

    # 3) talent: energy is the priority for energy-dependent heroes
    if not build["talent"]:
        if ht.get("energy_dependent") and not (cov() & ENERGY_FAMILY):
            p = _pick(conn, "talent", ENERGY_FAMILY, set(), prefer=_energy_prefer(mode))
            if p:
                build["talent"] = p
                why.append(f"talent={p}: energy is this hero's lifeblood.")
        if not build["talent"] and ht.get("atk_scaling"):
            p = _pick(conn, "talent", {"atk_pct"}, set())
            if p:
                build["talent"] = p
                why.append(f"talent={p}: amplifies the ATK-scaling skill.")
        if not build["talent"] and h.get("rec_talents"):
            build["talent"] = h["rec_talents"][0]
            why.append(f"talent={build['talent']}: hero's recommended talent.")

    # 4) crest: fill the leftover need (energy if the talent slot is taken by a
    #    non-energy talent; else ATK; else survivability)
    if not build["crest"]:
        if ht.get("energy_dependent") and not (cov() & ENERGY_FAMILY):
            p = _pick(conn, "crest", ENERGY_FAMILY, set(), prefer=_energy_prefer(mode))
            if p:
                build["crest"] = p
                why.append(f"crest={p}: talent slot is taken by a non-energy talent, so energy comes from the crest.")
        elif ht.get("atk_scaling"):
            p = _pick(conn, "crest", {"atk_pct"}, set())
            if p:
                build["crest"] = p
                why.append(f"crest={p}: extra ATK to amplify the skill.")
        else:
            p = _pick(conn, "crest", {"hp", "survivability"}, set())
            if p:
                build["crest"] = p
                why.append(f"crest={p}: survivability to keep channeling.")

    result = check_build(conn, hero, **build)
    result["rationale"] = why
    result["mode"] = mode
    result["note_pet"] = "pet slot left open: casclash lists pet names only, no effects (needs a second source)."
    return result
