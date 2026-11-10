"""Phase `extract`: download, per item, the raw HTML sub-pages and the image.

Artworks: the Summary listing says which pop-ups exist (provenance, exhibited,
literature, notes, commentary); only those are requested. The full-size image lives
at `artworks19580830/<year>/<oppYY-NNN>` and is saved next to the future metadata.json.
"""

from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import Any

from PIL import Image

Image.MAX_IMAGE_PIXELS = None  # trusted source; some works exceed 100 Mpx (e.g. Les demoiselles d'Avignon)

from . import config
from . import transform as T
from .manifest import Manifest
from .session import OppClient

log = logging.getLogger("etl.extract")
RAW = config.RAW_DIR

# Summary-page button label -> (inner view, raw file name)
POPUPS = {
    "provenance": ("former", "provenance"),
    "exhibited": ("exhibitedPrint", "exhibitions"),
    "literature": ("bibliography", "literature"),
    "notes": ("note", "note"),
    "commentary": ("commentary", "commentary"),
}
IMAGE_PATH_PREFIX = "artworks19580830"


def artwork_dir(item: dict[str, Any]) -> Path:
    return config.PICASSO_DIR / "artworks" / (item["category"] or "other") / T.safe_id(item["id"])


def raw_artwork_dir(item_id: str) -> Path:
    return RAW / "artworks" / T.safe_id(item_id)


def image_url(item: dict[str, Any]) -> str:
    return f"{config.BASE_URL}/{IMAGE_PATH_PREFIX}/{item['year']}/{T.image_alpha(item['id'])}"


def ensure_flags(client: OppClient, manifest: Manifest, item: dict[str, Any]) -> list[str]:
    """Return the sub-page flags of an artwork. The first time a year is needed, all its
    Summary pages (4 quarters x N pages, cached) are read and the flags of every listed
    work are stored; works the Summary does not list get every flag (safe default)."""
    if item["flags"] is not None:
        return item["flags"]
    year = item["year"]
    if not manifest.is_done(f"flags:{year}"):
        scan_summary_flags(client, manifest, year)
    refreshed = manifest.get(item["id"])  # the row may have been flagged by the scan
    if refreshed and refreshed["flags"] is not None:
        return refreshed["flags"]
    log.warning("%s no aparece en los listados Summary de %d; se piden todos los pop-ups", item["id"], year)
    flags = sorted(POPUPS) + ["zoom"]
    manifest.set_flags(item["id"], flags)
    return flags


def scan_summary_flags(client: OppClient, manifest: Manifest, year: int) -> int:
    """Read every `ArtworkSummary` page of a year (quarters 1-4) and store the flags."""
    seen = 0
    for quarter in (1, 2, 3, 4):
        page = 1
        while True:
            suffix = f"_p{page}" if quarter == 1 else f"_q{quarter}_p{page}"
            path = RAW / "artworks" / "summary" / f"{year}{suffix}.html"
            html = client.get_view_cached(path, "ArtworkSummary", year=year, quarter=quarter,
                                          category=config.ALL_CATEGORIES_PARAM, page=page)
            listed = T.parse_artwork_listing(html)
            for listed_item in listed:
                if manifest.get(listed_item["id"]) is not None:
                    manifest.set_flags(listed_item["id"], listed_item["has"])
            seen += len(listed)
            if not listed or page >= T.last_page(html):
                break
            page += 1
    manifest.mark_done(f"flags:{year}", str(seen))
    manifest.commit()
    log.info("listados Summary %d: %d obras con indicadores de pop-ups", year, seen)
    return seen


def fetch_popup(client: OppClient, path: Path, view: str, opp_id: str, attempts: int = 2) -> None:
    """Fetch one pop-up; the server sometimes answers an empty shell under load, so an
    empty page that the listing announced as existing is re-requested once."""
    for attempt in range(1, attempts + 1):
        html = client.get_view_cached(path, view, OPPID=opp_id)
        if _popup_has_content(html):
            if attempt > 1:
                log.info("pop-up %s para %s recuperado en el reintento", view, opp_id)
            return
        if attempt == attempts:
            return
        log.warning("pop-up vacío %s para %s; reintentando", view, opp_id)
        path.unlink(missing_ok=True)


def _popup_has_content(html: str) -> bool:
    return any(marker in html for marker in ('class="Label"', "<li>", "<li ", 'class="noteTitle"', 'class="commentaryTitle"'))


def extract_artwork(client: OppClient, manifest: Manifest, item: dict[str, Any],
                    images: bool = True, popups: bool = True) -> None:
    """Download everything an artwork needs; every file is skipped when it already exists."""
    flags = ensure_flags(client, manifest, item) if (popups or images) else []
    raw_dir = raw_artwork_dir(item["id"])
    if popups:
        for flag, (view, name) in POPUPS.items():
            if flag in flags:
                fetch_popup(client, raw_dir / f"{name}.html", view, item["id"])
    if images and "zoom" in flags:
        download_image(client, item)


def download_image(client: OppClient, item: dict[str, Any]) -> Path | None:
    """Save the full-size JPEG as image.jpg; a non-image answer counts as a failure."""
    target = artwork_dir(item) / "image.jpg"
    if target.exists():
        return target
    content = client.get_bytes(image_url(item))
    try:
        with Image.open(io.BytesIO(content)) as im:
            im.verify()
    except Exception as exc:  # noqa: BLE001 - any decoding problem means "not an image"
        raise RuntimeError(f"La respuesta de la imagen de {item['id']} no es una imagen válida ({exc})")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    return target


def extract_writing(client: OppClient, item: dict[str, Any]) -> None:
    mid = item["listing"]["mid"]
    client.get_view_cached(RAW / "writings" / f"{mid}.html", "WritingsInfo", mid=mid, year=item["year"])


def extract_archive(client: OppClient, item: dict[str, Any]) -> None:
    aid = item["listing"]["id"]
    client.get_view_cached(RAW / "archives" / f"article_{aid}.html", "ArchiveArticle", year=item["year"], id=aid)


def extract_items(client: OppClient, manifest: Manifest, items: list[dict[str, Any]],
                  images: bool = True, popups: bool = True) -> dict[str, int]:
    """Run the extraction for a list of manifest rows, recording failures in the manifest."""
    stats = {"ok": 0, "failed": 0}
    for n, item in enumerate(items, 1):
        try:
            if item["type"] == "artwork":
                extract_artwork(client, manifest, item, images=images, popups=popups)
            elif item["type"] == "writing":
                extract_writing(client, item)
            elif item["type"] == "archive":
                extract_archive(client, item)
            manifest.set_status(item["id"], "extracted")
            stats["ok"] += 1
        except Exception as exc:  # noqa: BLE001 - recorded in the manifest, the run goes on
            if exc.__class__.__name__ == "BlockedError":
                raise
            log.error("fallo al extraer %s: %s", item["id"], exc)
            manifest.set_status(item["id"], "failed", str(exc)[:500])
            stats["failed"] += 1
        manifest.commit()
        if n % 25 == 0 or n == len(items):
            log.info("extracción %d/%d (%d requests)", n, len(items), client.request_count)
    return stats
