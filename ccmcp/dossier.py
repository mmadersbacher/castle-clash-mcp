"""One-call complete hero knowledge: base + every evolution grade's exact stats,
base combat ratings, main + totem skill, tier/role, and a recommended build.
The knowledge-library view of a single hero, assembled from the verified sources.
"""
import html

from . import buildscore, combat, rules, skills as skillmod, sources, statcalc, systems

_GRADE_ORDER = {"Ordinary": 0, "Evo1": 1, "Evo2": 2, "Evo3": 3, "Evo4": 4}


def _grades(hero: str):
    """Per-grade formula params from live_hero_params, with 10*/L200 stats.
    Flags the Ordinary grade if it disagrees with the validated APK base."""
    d = sources.load("live_hero_params.json", "sources") or {}
    v = next((x for x in d.values() if str(x.get("name", "")).lower() == hero.lower()), None)
    if not v:
        return None
    out, seen = [], set()
    for ev in v.get("evolutions", []):
        for t in ev.get("tiers", []):
            g = t.get("grade")
            if not g or g in seen:
                continue
            seen.add(g)
            out.append({
                "grade": g,
                "perStar_HP": t["perStar_HP"], "HPinc": t["HPinc"],
                "perStar_ATK": t["perStar_ATK"], "ATKinc": t["ATKinc"], "ACC": t.get("ACC"),
                "HP_10star_L200": t["perStar_HP"] * 10 + t["HPinc"] * 199,
                "ATK_10star_L200": t["perStar_ATK"] * 10 + t["ATKinc"] * 199,
            })
    out.sort(key=lambda x: _GRADE_ORDER.get(x["grade"], 9))
    return {"id": v.get("id"), "range": v.get("range"), "atkspd": v.get("atkspd"),
            "n_forms": v.get("n_evo_forms"), "grades": out}


def build(conn, hero: str) -> dict:
    base = statcalc.base_stats(hero)
    if not base:
        return {"error": f"unknown hero: {hero}"}
    name = base["name"]
    sec = statcalc.secondary(conn, hero)
    calc = statcalc.calc(conn, hero, stars=10, level=200, evo=0)
    grades = _grades(name)

    # reconcile live Ordinary vs APK base (catch the wrong-form extractions)
    recon = None
    if grades:
        ordg = next((g for g in grades["grades"] if g["grade"] == "Ordinary"), None)
        if ordg and (ordg["perStar_HP"], ordg["HPinc"], ordg["perStar_ATK"], ordg["ATKinc"]) != \
                (base["HP"], base["HPinc"], base["ATK"], base["ATKinc"]):
            recon = (f"live_hero_params Ordinary ({ordg['perStar_HP']}/{ordg['HPinc']}/"
                     f"{ordg['perStar_ATK']}/{ordg['ATKinc']}) disagrees with APK base "
                     f"({base['HP']}/{base['HPinc']}/{base['ATK']}/{base['ATKinc']}) -> "
                     f"trust APK for Ordinary")

    rec = None
    rec_grade = None
    try:
        rec = rules.recommend_build(conn, hero)
        rt = (rec or {}).get("build", {}).get("talent") if isinstance(rec, dict) else None
        if rt:
            g = buildscore.score(conn, hero, talent=rt, talent_lvl=10)
            if "metrics" in g:
                rec_grade = {"with_talent": rt, "ATK": g["effective"]["ATK"],
                             "offense_score": g["metrics"]["offense_score"],
                             "EHP": g["metrics"]["EHP"]}
    except Exception:
        pass

    hrec = systems.hero(name) if hasattr(systems, "hero") else {}
    hrec = hrec if isinstance(hrec, dict) and "error" not in hrec else {}

    # compact the main skill to its name + distinct scaling descriptions
    main_skill = None
    ms = hrec.get("main_skill") or hrec.get("skill")
    if isinstance(ms, dict):
        descs, seen = [], set()
        for r in ms.get("per_level") or []:
            d = html.unescape((r.get("desc") or "").strip())
            if d and d not in seen:
                seen.add(d)
                descs.append(d)
        main_skill = {"name": ms.get("name"), "scaling": descs[:10]}
    elif ms:
        main_skill = ms
    if isinstance(main_skill, dict) and main_skill.get("name"):
        sd = skillmod.skill_data(main_skill["name"])
        dmg_levels = [L for L in sd.get("levels", []) if (L.get("damage_pct") or 0) > 0]
        prog = []  # first progression run; a name maps to several form variants
        for L in dmg_levels:
            v = L["damage_pct"]
            if prog and v < prog[-1]:
                break  # a drop = the next form's block restarting, stop here
            if not prog or prog[-1] != v:
                prog.append(v)
        if prog:
            main_skill["damage_pct_by_level"] = prog[:15]
            eff_atk = calc["effective"]["Attack"]
            main_skill["max_hit_at_own_atk"] = {
                "pct": prog[-1], "atk": eff_atk,
                "damage_per_hit": combat.skill_value(prog[-1], eff_atk),
            }
            tgts = [L.get("targets") for L in dmg_levels if 0 < (L.get("targets") or 0) <= 12]
            if tgts:
                main_skill["targets"] = max(tgts)

    totem = hrec.get("totem_skill")
    if isinstance(totem, dict):
        totem = totem.get("name") or totem.get("skill_name")
    if not totem:
        try:
            t = systems.totem_skill(name)
            totem = t.get("skill_name") if isinstance(t, dict) and "error" not in t else None
        except Exception:
            totem = None

    return {
        "hero": name,
        "id": (grades or {}).get("id"),
        "combat_base": {
            "range": sec.get("Attack Range"), "atk_spd": sec.get("ATK SPD"),
            "ACC": sec.get("ACC"), "Dodge": sec.get("Dodge"), "CRIT": sec.get("CRIT"),
            "CRIT DMG": sec.get("CRIT DMG"), "CRIT Resist": sec.get("CRIT Resist"),
        },
        "ordinary_10star_L200": {"HP": calc["effective"]["HP"], "ATK": calc["effective"]["Attack"]},
        "grades": (grades or {}).get("grades", []),
        "grade_reconciliation": recon,
        "main_skill": main_skill,
        "totem_skill": totem,
        "tier": hrec.get("tier") or hrec.get("tiers"),
        "role": hrec.get("role"),
        "tags": hrec.get("tags"),
        "recommended_build": rec,
        "recommended_build_grade": rec_grade,
        "note": "Ordinary stats VERIFIED (formula); evolved grades from live_hero_params "
                "(DERIVED, some multi-form heroes mis-extract Ordinary -> see reconciliation).",
    }
