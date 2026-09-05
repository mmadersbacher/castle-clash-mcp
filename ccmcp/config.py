import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("CCMCP_DATA", BASE_DIR / "data"))
DB_PATH = Path(os.environ.get("CCMCP_DB", DATA_DIR / "ccmcp.sqlite"))

# Data-source roots — single source of truth. Every loader resolves through
# these (see data/sources/MANIFEST.md). Override any with an env var to point
# the server at a different dataset (e.g. a freshly captured sweep).
SOURCES_DIR = Path(os.environ.get("CCMCP_SOURCES", DATA_DIR / "sources"))
GAME_DIR = Path(os.environ.get("CCMCP_GAME_DIR", SOURCES_DIR / "game"))
ENRICHED_DIR = Path(os.environ.get("CCMCP_ENRICHED_DIR", SOURCES_DIR / "enriched"))
RAW_DIR = SOURCES_DIR / "raw"

BASE_URL = "https://en.casclash.com"
HEROES_INDEX = f"{BASE_URL}/handbook/heroes/"
TALENTS_INDEX = f"{BASE_URL}/handbook/talents/"

USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64; rv:129.0) Gecko/20100101 Firefox/129.0"
REQUEST_TIMEOUT = 15
CRAWL_DELAY = 1.0  # seconds between requests, be polite
