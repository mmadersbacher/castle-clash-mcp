"""Hand-curated seed catalog with the engine's capability tags.

Capability vocabulary (what a slot component `provides`):
  reflect_cap     partial reflection mitigation (caps reflected dmg)
  reflect_ignore  full reflection immunity (strictly stronger than reflect_cap)
  energy_burst    instant energy at battle start
  energy_regen    ongoing energy regeneration
  energy          umbrella for either energy source
  atk / atk_pct   flat / percentage attack ; atk_spd attack speed
  crit            crit rate ; skill_dmg skill damage
  revive          revive once ; hp / survivability ; dmg_reduction
Special tag: hp_penalty (+ signature_hero) marks a signature talent that
punishes the wrong hero (e.g. Voidwalker Staff: -40% Max HP on non-Voidwalker).

Hero tags that drive recommendations:
  energy_dependent  needs an energy source (skill-spam identity)
  reflect_vulnerable / multi_hit_aoe   reflection-vulnerable
  atk_scaling  skill scales with ATK
  channeler    channels over time -> revive (Winged Rebirth) doubles uptime
"""

# --- slot pools --------------------------------------------------------------
TALENTS = [
    {"name": "Wicked Armor", "source": "seed",
     "effect": "Raises ATK by 9% and limits reflected DMG taken to 50,000.",
     "tags": {"provides": ["atk_pct", "reflect_cap"], "atk_pct": 9, "reflect_cap": 50000}},
    {"name": "Revitalize", "source": "seed",
     "effect": "Grants an instant boost of energy at the start of the battle.",
     "tags": {"provides": ["energy_burst", "energy"]}},
    {"name": "Empower", "source": "seed",
     "effect": "Grants 5 Energy per second in battle.",
     "tags": {"provides": ["energy_regen", "energy"], "energy_per_sec": 5}},
    {"name": "Nimble", "source": "seed",
     "effect": "Grants 3 Energy when attacked (even when Dodged, 2s cooldown). Raises Dodge by 4%.",
     "tags": {"provides": ["energy_regen", "energy", "dodge"], "conditional": True}},
    {"name": "Regenerate", "source": "seed",
     "effect": "Raises Energy recovery by 10% and healing by 20% (energy from DMG and basic ATK only).",
     "tags": {"provides": ["energy_regen", "energy", "heal"]}},
    {"name": "Voidwalker Staff", "source": "seed",
     "effect": "Raises ATK by 10% and Energy regain rate by 8%. Reduces Max HP by 40% if used by a non-Voidwalker hero.",
     "tags": {"provides": ["atk_pct", "energy_regen", "energy"], "hp_penalty": 0.40, "signature_hero": "Voidwalker"}},
    {"name": "War God", "source": "seed",
     "effect": "Increases ATK (up to +200% at max).", "tags": {"provides": ["atk_pct"]}},
    {"name": "Tenacity", "source": "seed",
     "effect": "Increases HP (up to +230% at max).", "tags": {"provides": ["hp", "survivability"]}},
    {"name": "Berserk", "source": "seed",
     "effect": "Increases ATK SPD (up to +120% at max).", "tags": {"provides": ["atk_spd"]}},
    {"name": "Bulwark", "source": "seed",
     "effect": "Increases ATK and Max HP in battle.", "tags": {"provides": ["atk_pct", "hp"]}},
    {"name": "Stone Skin", "source": "seed",
     "effect": "Reduces damage taken.", "tags": {"provides": ["dmg_reduction", "survivability"]}},
    {"name": "Sacred Light", "source": "seed",
     "effect": "Reduces damage taken; pairs with Wicked Armor / Flame Guard.",
     "tags": {"provides": ["dmg_reduction"]}},
    {"name": "Flame Guard", "source": "seed",
     "effect": "Reduces damage taken and adds a reflect element.",
     "tags": {"provides": ["dmg_reduction"]}},
]

INSIGNIAS = [
    {"name": "Winged Rebirth", "source": "seed",
     "effect": "Revive once when killed in battle, gaining bonus ATK and speed.",
     "tags": {"provides": ["revive", "atk", "move_spd"]}},
    {"name": "Trueheart", "source": "seed", "effect": "Generic survivability insignia.",
     "tags": {"provides": ["survivability"]}},
]

ENCHANTMENTS = [
    {"name": "Bold Ambition", "source": "seed",
     "effect": "Increases crit rate and lets the hero ignore damage reflection.",
     "tags": {"provides": ["crit", "reflect_ignore"]}},
    {"name": "Serpents Force", "source": "seed",
     "effect": "Offensive enchantment (damage-oriented). Exact numbers unverified.",
     "tags": {"provides": ["skill_dmg"], "uncertain": True}},
]

EQUIPMENT = [
    {"name": "Voidwalker Staff", "source": "seed",
     "effect": "NOTE: Voidwalker Staff is a TALENT, not a separate equipment slot. Kept here only for backward lookup.",
     "tags": {"provides": ["atk", "energy_regen"], "is_talent": True}},
]

# --- heroes (tiers: {mode: tier}, 'overall' = cross-mode) ---------------------
HEROES = [
    {"id": "70205", "name": "Serratica", "source": "seed",
     "role": "AoE DPS / energy-drain + anti-heal control (dragon)",
     "skill_base": "Deals 120% ATK DMG to 6 enemies every second for 5s (ignores DMG limits; Scale Mark targets take 3x). Enemies that attack her get a Scale Mark: 90% less healing and -30 Energy/s for 5s. Immune to conditions, max 40,000 DMG per hit, 30% chance to heal 10% Max HP when hit.",
     "tags": {"energy_dependent": True, "multi_hit_aoe": True, "reflect_vulnerable": True,
              "atk_scaling": True, "channeler": True},
     "rec_talents": ["Revitalize"], "rec_equipment": ["Serrated Scale"], "rec_enchant": ["Bold Ambition"],
     "tiers": {"overall": "A+", "Guild War": "A+", "Arena": "S", "Dungeons": "A"}},
    {"id": "malefica", "name": "Malefica", "source": "seed", "role": "Top-tier all-round DPS/control",
     "tags": {"multi_hit_aoe": True, "atk_scaling": True, "reflect_vulnerable": True, "channeler": True, "energy_dependent": True},
     "tiers": {"overall": "S+", "Guild War": "S+", "Dungeons": "S+", "HBM/LBF": "S+", "Blitz": "S+"}},
    {"id": "bell-elk-maiden", "name": "Bell Elk Maiden", "source": "seed", "role": "All-round support/DPS",
     "tiers": {"overall": "S+", "Guild War": "S+", "Dungeons": "S+", "HBM/LBF": "S+", "Arena": "S+"}},
    {"id": "dynamica", "name": "Dynamica", "source": "seed", "role": "All-round DPS",
     "tags": {"atk_scaling": True, "energy_dependent": True},
     "tiers": {"overall": "S+", "Guild War": "S+", "Dungeons": "S+", "HBM/LBF": "S+", "Arena": "S+"}},
    {"id": "necrofica", "name": "Necrofica", "source": "seed", "role": "All-round",
     "tiers": {"overall": "S", "Guild War": "S", "Dungeons": "S", "HBM/LBF": "S"}},
    {"id": "celestica", "name": "Celestica", "source": "seed", "role": "Guild War / Blitz specialist",
     "tiers": {"overall": "S", "Guild War": "S", "HBM/LBF": "S", "Blitz": "S"}},
    {"id": "dreadshade", "name": "Dreadshade", "source": "seed", "role": "Anti-Malefica counter, Dungeons/Arena",
     "tiers": {"overall": "S", "Dungeons": "S", "Arena": "S"}},
    {"id": "wraith-binder", "name": "Wraith Binder", "source": "seed", "role": "Dungeon specialist",
     "tiers": {"overall": "S", "Dungeons": "S+"}},
    {"id": "bone-butcher", "name": "Bone Butcher", "source": "seed", "role": "Dungeon / HBM",
     "tiers": {"overall": "S", "Dungeons": "S", "HBM/LBF": "S"}},
]
