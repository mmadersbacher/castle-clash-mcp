"""Formula-based FULL hero stat calculator (validated in-game: Serratica 10*/L200
= 180,695 HP and 7,881 ATK exactly).

HP / ATK      : perStar*Stars + inc*(Level-1)        (EVO1/2: base + perStar*Stars + perLevel*Level)
MOV SPD       : base + movinc*(Stars-1)              (movinc 5 typical, 10 for fast heroes)
ATK SPD, Range, ACC : constant per hero
Dodge, CRIT, CRIT DMG, CRIT Resist : per-hero base (usually 0; traits/gear add on top)
Sources: castleclashbuilds (HP/ATK base+growth, all heroes), casclash handbook (secondary
constants), Fandom (legacy heroes + exact EVO params), derived movinc.json.
"""
import re
from typing import Optional

from . import db, loadout as loadoutmod, sources

_PCT = re.compile(r"(Raises|Increases)\s+(ATK|HP|Max HP)\s+(?:and\s+Max HP\s+)?(?:in battle\s+)?by\s+(\d+(?:\.\d+)?)%", re.I)
SECONDARY = ("ATK SPD", "MOV SPD", "Attack Range", "ACC", "Dodge", "CRIT", "CRIT DMG", "CRIT Resist")


def _load(name):
    return sources.load(name, "sources") or {}


def _find(data: dict, hero: str):
    key = hero.strip().lower()
    for name, d in data.items():
        if not name.startswith("_") and name.lower() == key:
            return name, d
    return None, None


def base_stats(hero: str) -> Optional[dict]:
    name, g = _find(_load("game_hero_stats.json"), hero)
    if g:
        return {"name": name, "HP": g["HP"], "HPinc": g["HPinc"], "ATK": g["ATK"],
                "ATKinc": g["ATKinc"], "ATKSPD": g["ATKSPD"], "MOV": g["MOV"],
                "source": "game_hero_stats.json (APK Hero.data, authoritative)"}
    for fname in ("ccb_all_base_stats.json", "new_epic_base_stats.json"):
        name, d = _find(_load(fname), hero)
        if d:
            return {"name": name, "HP": d["HP"], "HPinc": d["HPinc"], "ATK": d["ATK"], "ATKinc": d["ATKinc"],
                    "ATKSPD": d.get("ATKSPD"), "MOV": d.get("MOV"), "source": fname}
    name, d = _find(_load("fandom_hero_variables.json"), hero)
    if d and all(str(d.get(k, "")).isdigit() for k in ("HP", "HPinc", "DMG", "DMGinc")):
        return {"name": name, "HP": int(d["HP"]), "HPinc": int(d["HPinc"]), "ATK": int(d["DMG"]),
                "ATKinc": int(d["DMGinc"]), "ATKSPD": d.get("ATKrate"), "MOV": d.get("MOVspeed"),
                "source": "fandom_hero_variables.json"}
    return None


def evo_params(hero: str) -> Optional[dict]:
    name, d = _find(_load("fandom_evo_params.json"), hero)
    return d if d and "e1hp" in d else None


def movinc(hero: str) -> tuple:
    """(movinc, source). derived movinc.json > Fandom MOVinc > default 5."""
    name, d = _find(_load("movinc.json"), hero)
    if d is not None:
        return int(d), "derived(casclash 1*->4*)"
    name, d = _find(_load("fandom_hero_variables.json"), hero)
    if d and str(d.get("MOVinc", "")).isdigit():
        return int(d["MOVinc"]), "fandom"
    return 5, "default(5)"


def secondary(conn, hero: str) -> dict:
    """Per-hero constants. Authoritative game Hero.data first, then casclash handbook, ccb Range, overrides."""
    name, g = _find(_load("game_hero_stats.json"), hero)
    if g:
        return {"ATK SPD": g["ATKSPD"], "MOV SPD": g["MOV"], "Attack Range": g["Range"], "ACC": g["ACC"],
                "Dodge": g["Dodge"], "CRIT": g["CRIT"], "CRIT DMG": g["CRITDMG"], "CRIT Resist": g["CRITResist"]}
    h = db.find_hero(conn, hero)
    st = (h or {}).get("stats") or {}
    out = {k: st.get(k) for k in SECONDARY}
    if out.get("Attack Range") is None:
        _, d = _find(_load("ccb_all_base_stats.json"), hero)
        if d and d.get("Range") is not None:
            out["Attack Range"] = d["Range"]
    _, ov = _find(_load("secondary_overrides.json"), hero)
    if ov:
        for k, v in ov.items():
            if out.get(k) is None and v is not None:
                out[k] = v
    return out


def talent_multipliers(conn, talent: Optional[str], talent_lvl: int) -> dict:
    out = {"HP": 0.0, "ATK": 0.0}
    if not talent or not talent_lvl:
        return out
    t = db.get_entity(conn, "talents", talent)
    if not t:
        return out
    row = next((L for L in (t.get("levels") or []) if str(L.get("level")) == str(talent_lvl)), None)
    text = (row or {}).get("effect") or t.get("effect") or ""
    for m in _PCT.finditer(text):
        stat = "HP" if "HP" in m.group(2).upper() else "ATK"
        out[stat] += float(m.group(3))
        if "and Max HP" in m.group(0):
            out["HP"] += float(m.group(3))
    return out


def calc(conn, hero: str, stars: int = 10, level: int = 200, evo: int = 0,
         talent: Optional[str] = None, talent_lvl: int = 0,
         inscription: int = 0, soularms: int = 0, soul: int = 0, artifact: int = 0,
         crest_name: Optional[str] = None, crest_level: int = 0,
         pet_talent: Optional[str] = None, pet_talent_level: int = 0, gear: list = None,
         loadout: Optional[dict] = None) -> dict:
    b = base_stats(hero)
    if not b:
        return {"error": f"no base stats for '{hero}'"}
    if evo == 0:
        hp = b["HP"] * stars + b["HPinc"] * (level - 1)
        atk = b["ATK"] * stars + b["ATKinc"] * (level - 1)
        formula = "perStar*Stars + inc*(Level-1)"
    else:
        ep = evo_params(hero)
        if not ep:
            return {"error": f"no exact EVO{evo} params for '{hero}' (Fandom covers Legendaries only)"}
        h, d = ep[f"e{evo}hp"], ep[f"e{evo}dmg"]
        hp = h["base"] + h["perStar"] * stars + h["perLevel"] * level
        atk = d["base"] + d["perStar"] * stars + d["perLevel"] * level
        formula = "base + perStar*Stars + perLevel*Level (Fandom exact)"
    sec = secondary(conn, hero)
    mov_base = sec.get("MOV SPD") or b.get("MOV")
    minc, minc_src = movinc(hero)
    mov = (mov_base + minc * (stars - 1)) if isinstance(mov_base, int) else None
    atkspd = sec.get("ATK SPD") or b.get("ATKSPD")
    mult = talent_multipliers(conn, talent, talent_lvl)
    stats = {
        "Attack": atk, "HP": hp, "ATK SPD": atkspd, "MOV SPD": mov,
        "Attack Range": sec.get("Attack Range"), "ACC": sec.get("ACC"),
        "Dodge": sec.get("Dodge") or 0, "CRIT": sec.get("CRIT") or 0,
        "CRIT DMG": sec.get("CRIT DMG") or 0, "CRIT Resist": sec.get("CRIT Resist") or 0,
    }
    if loadout:
        lo = loadoutmod.compute(loadout)
    else:
        lo = loadoutmod.total(inscription=inscription, soularms=soularms, soul=soul, artifact=artifact,
                              crest_name=crest_name, crest_level=crest_level,
                              pet_talent=pet_talent, pet_talent_level=pet_talent_level, gear=gear or [])
    d = lo["delta"]; lpct = lo.get("pct", {})
    atk_pct = mult["ATK"] + lpct.get("Attack", 0.0)
    eff = {
        "Attack": round(atk * (1 + atk_pct / 100)) + d["Attack"],
        "HP": round(hp * (1 + mult["HP"] / 100)) + d["HP"],
        "ATK SPD": stats["ATK SPD"], "MOV SPD": stats["MOV SPD"],
        "Attack Range": stats["Attack Range"], "ACC": stats["ACC"],
        "Dodge": (stats["Dodge"] or 0) + d["Dodge"],
        "CRIT": (stats["CRIT"] or 0) + d["Crit"],
        "CRIT DMG": (stats["CRIT DMG"] or 0) + d["Hit_DMG"],
        "CRIT Resist": stats["CRIT Resist"] or 0,
        "Tenacity": d["Tenacity"],
    }
    return {"hero": b["name"], "stars": stars, "level": level, "evo": evo, "formula": formula,
            "effective": eff, "loadout_delta": d, "loadout_sources": lo["parts"],
            "talent_pct": mult,
            "note": "effective Attack/HP = round(base x (1+talent%)) + flat loadout; Crit/Dodge/Tenacity/CritDMG from crest+soul; raw units",
            "stats": stats,
            "with_talent": {"Attack": round(atk * (1 + mult["ATK"] / 100)), "HP": round(hp * (1 + mult["HP"] / 100)),
                            "talent": talent, "lvl": talent_lvl, "ATK_pct": mult["ATK"], "HP_pct": mult["HP"]},
            "inputs": {"HP1": b["HP"], "HPinc": b["HPinc"], "ATK1": b["ATK"], "ATKinc": b["ATKinc"],
                       "MOV1": mov_base, "MOVinc": minc, "MOVinc_source": minc_src, "base_source": b["source"]},
            "note": "Dodge/CRIT/CRIT DMG/CRIT Resist/ACC are per-hero BASE values; traits, insignia, pets, gear add on top."}
