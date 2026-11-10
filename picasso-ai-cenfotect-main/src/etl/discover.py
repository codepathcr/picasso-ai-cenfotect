"""Phase `discover`: walk the site listings and register every item in the manifest.

Artworks come from the yearly catalogue (`ArtworkLarge`, one request per year and
category) which already carries the base metadata of each work. Writings and press
articles come from their yearly indexes. Every listing page is cached in data/raw/.
"""

from __future__ import annotations

import logging
import math
import time
from pathlib import Path
from typing import Any

from . import config
from . import transform as T
from .manifest import Manifest
from .session import OppClient

log = logging.getLogger("etl.discover")
RAW = config.RAW_DIR


def fetch_catalogue(client: OppClient, path: Path, attempts: int = 3, **params) -> list[dict[str, Any]]:
    """Fetch one `ArtworkLarge` page; the server sometimes answers an empty shell under
    load, so an empty result is retried before being trusted. Cached files are trusted."""
    if path.exists():
        return T.parse_artwork_listing(path.read_text(encoding="utf-8"))
    for attempt in range(1, attempts + 1):
        items = T.parse_artwork_listing(client.get_view_cached(path, "ArtworkLarge", **params))
        if items:
            return items
        if attempt < attempts:
            log.warning("catálogo vacío %s (intento %d/%d); reintentando", path.name, attempt, attempts)
            path.unlink(missing_ok=True)
            time.sleep(5 * attempt)
    return []


def discover_artworks(client: OppClient, manifest: Manifest, years: list[int],
                      categories: list[str] | None = None) -> int:
    """Register the artworks of `years` (all 12 categories unless `categories` is given)."""
    total = 0
    for year in years:
        found = 0
        for category in categories or config.CATEGORIES:
            key = f"discover:artwork:{year}:{category}"
            path = RAW / "artworks" / "catalogue" / f"{year}_{category}.html"
            items = fetch_catalogue(client, path, year=year, category=category)
            for item in items:
                manifest.upsert_item(item["id"], "artwork", year, item, category)
            manifest.mark_done(key, str(len(items)))
            found += len(items)
        manifest.commit()
        _check_year_total(year, found, categories)
        log.info("descubrimiento %d: %d obras", year, found)
        total += found
    return total


def _check_year_total(year: int, found: int, categories: list[str] | None) -> None:
    """Compare against the all-categories catalogue cached in Phase 1 when available."""
    if categories:
        return
    path = RAW / "artworks" / "catalogue" / f"{year}.html"
    if path.exists():
        expected = len(T.parse_artwork_listing(path.read_text(encoding="utf-8")))
        if expected != found:
            log.warning("%d: la suma por categoría (%d) no coincide con el catálogo anual (%d)",
                        year, found, expected)


def discover_writings(client: OppClient, manifest: Manifest, years: list[int]) -> int:
    """Poems and plays: `Writings&year&page`, 30 per page."""
    total = 0
    for year in years:
        if manifest.is_done(f"discover:writing:{year}"):
            total += len(manifest.select("writing", [year]))
            continue
        page, count = 1, 0
        while True:
            html = client.get_view_cached(RAW / "writings" / f"{year}_p{page}.html", "Writings", year=year, page=page)
            rows = T.parse_writings_index(html)
            for row in rows:
                manifest.upsert_item(f"W.{row['mid']}", "writing", year, row)
            count += len(rows)
            if not rows or page >= _pages_for(T.count_catalogued(html)):
                break
            page += 1
        manifest.mark_done(f"discover:writing:{year}", str(count))
        manifest.commit()
        log.info("descubrimiento escritos %d: %d", year, count)
        total += count
    return total


def discover_archives(client: OppClient, manifest: Manifest, years: list[int]) -> int:
    """Press articles: `Archives&year&page`, 30 per page (the pager only shows 10 links,
    so the page count is derived from the total announced on the page)."""
    total = 0
    for year in years:
        if manifest.is_done(f"discover:archive:{year}"):
            total += len(manifest.select("archive", [year]))
            continue
        page, count = 1, 0
        while True:
            name = f"{year}.html" if page == 1 else f"{year}_p{page}.html"
            html = client.get_view_cached(RAW / "archives" / name, "Archives", year=year, page=page)
            rows = T.parse_archives_index(html)
            for row in rows:
                manifest.upsert_item(f"A.{row['id']}", "archive", year, row)
            count += len(rows)
            if not rows or page >= _pages_for(T.count_entries(html)):
                break
            page += 1
        manifest.mark_done(f"discover:archive:{year}", str(count))
        manifest.commit()
        log.info("descubrimiento prensa %d: %d", year, count)
        total += count
    return total


def _pages_for(count: int | None) -> int:
    return max(1, math.ceil((count or 0) / config.ITEMS_PER_LISTING_PAGE))
