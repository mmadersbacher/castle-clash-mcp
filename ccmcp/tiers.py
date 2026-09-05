"""Tier-list ingestion.

Community tier sites (AllClash, Zathong) are HTML-heavy and partly paywalled
(AllClash PRO), so blindly scraping them is unreliable and against their terms
for the locked parts. We therefore ship the current known rankings as seed data
and expose fetch_tiers() as a documented hook to add a parser later. Seeded tiers
carry source='seed' so a future scraped source can coexist per hero/mode.
"""
from . import seed


def seed_tiers() -> list[dict]:
    out = []
    for h in seed.HEROES:
        for mode, tier in (h.get("tiers") or {}).items():
            out.append({"hero": h["name"], "mode": mode, "tier": tier, "source": "seed"})
    return out


def fetch_tiers() -> list[dict]:
    """Placeholder for a future tier-site parser. Returns [] for now."""
    return []
