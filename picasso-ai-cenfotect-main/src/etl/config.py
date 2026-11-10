"""Project-wide configuration: paths, site constants, rate limit and credentials.

Credentials are read from `.env` (PICASSO_USER, PICASSO_PASS) and are never logged
or written anywhere else.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

# --- Paths -------------------------------------------------------------------
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
RECON_DIR = DATA_DIR / "recon"
PICASSO_DIR = DATA_DIR / "picasso"
INDEX_DIR = DATA_DIR / "index"
LOGS_DIR = DATA_DIR / "logs"

# --- Site --------------------------------------------------------------------
BASE_URL = "https://picasso.shsu.edu"
INDEX_URL = f"{BASE_URL}/index.php"
LOGIN_URL = f"{BASE_URL}/frontlogin.php"

# Artwork categories exactly as the site spells them. The order matters because the
# site builds the `category=` parameter by joining them with underscores.
CATEGORIES = [
    "painting", "collage", "photograph", "sculpture", "ceramic", "drawing",
    "watercolor", "gouache", "pastel", "engraving", "lithograph", "other",
]
ALL_CATEGORIES_PARAM = "_".join(CATEGORIES)

ARTWORK_YEARS = range(1881, 1974)   # Picasso 1881–1973
BIOGRAPHY_YEARS = range(1881, 1974)
WRITINGS_YEARS = range(1935, 1960)  # poems/plays effectively start in 1935
ARCHIVES_YEARS = range(1930, 2027)
LETTERS = [chr(c) for c in range(ord("A"), ord("Z") + 1)]

ITEMS_PER_LISTING_PAGE = 30

# --- Crawling policy ---------------------------------------------------------
RATE_LIMIT_SECONDS = float(os.getenv("RATE_LIMIT_SECONDS", "1.0"))
REQUEST_TIMEOUT_SECONDS = 60
MAX_RETRIES = 5
BACKOFF_BASE_SECONDS = 2.0
USER_AGENT = os.getenv(
    "PICASSO_USER_AGENT",
    "CENFOTEC-IA-PicassoProject/0.1 (academic research, Universidad CENFOTEC; "
    "contact: avillalobos@elevensystems.com)",
)


def get_credentials() -> tuple[str, str]:
    """Return (user, password) from the environment or raise a clear error."""
    user = os.getenv("PICASSO_USER")
    password = os.getenv("PICASSO_PASS")
    if not user or not password:
        raise RuntimeError(
            "Faltan PICASSO_USER / PICASSO_PASS en .env (ver README.md)."
        )
    return user, password
