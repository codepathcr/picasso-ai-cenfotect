"""Phases `transform` and `load`.

`transform_items` turns the cached raw HTML of each item into its metadata.json
(data/picasso/<type>/.../metadata.json), joining the context (residence, events,
periods, themes). `load_index` builds data/index/catalog.csv and summary.json from
every metadata.json on disk and returns the Spanish summary printed by the CLI.
"""

from __future__ import annotations

import csv
import json
import logging
from collections import Counter
from pathlib import Path
from typing import Any

from PIL import Image

Image.MAX_IMAGE_PIXELS = None  # trusted source; some works exceed 100 Mpx (e.g. Les demoiselles d'Avignon)

from . import config
from . import context as C
from . import transform as T
from .extract import POPUPS, artwork_dir, image_url, raw_artwork_dir
from .manifest import Manifest, now_iso

log = logging.getLogger("etl.load")
POPUP_PARSERS = {
    "provenance": T.parse_provenance, "exhibitions": T.parse_exhibitions,
    "literature": T.parse_literature, "note": T.parse_note, "commentary": T.parse_commentary,
}
POPUP_FIELDS = {"provenance": "provenance", "exhibitions": "exhibitions", "literature": "literature",
                "note": "notes", "commentary": "commentary"}


class Context:
    """Everything transform needs from data/picasso/context, loaded once."""

    def __init__(self) -> None:
        self.chronology = C.read_json("chronology.json", [])
        labels = C.read_json("periods.json", {"periods": {}, "themes": {}})
        self.periods_by_id = _invert(labels.get("periods", {}))
        self.themes_by_id = _invert(labels.get("themes", {}))


def _invert(label_to_ids: dict[str, list[str]]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for label, ids in label_to_ids.items():
        for opp_id in ids:
            out.setdefault(opp_id, []).append(label)
    return out


# --- artworks --------------------------------------------------------------------------
def artwork_metadata(item: dict[str, Any], ctx: Context) -> dict[str, Any]:
    """Assemble the metadata.json of one artwork from the manifest row, raw pop-ups and context."""
    listing, raw_dir = item["listing"], raw_artwork_dir(item["id"])
    date = dict(listing["date"])
    date["range"] = T.date_range(listing["date_text"] or "", item["year"])
    meta: dict[str, Any] = {
        "id": item["id"], "type": "artwork", "category": item["category"], "year": item["year"],
        "title": listing["title"], "place": listing["place"], "date_text": listing["date_text"], "date": date,
        "medium": listing["medium"], "dimensions": listing["dimensions"], "collection": listing["collection"],
        "credit_line": listing["credit_line"], "catalogs": listing["references"],
        "provenance": [], "exhibitions": [], "literature": [], "notes": [], "commentary": [],
        "sub_pages_announced": item["flags"],
        "periods": ctx.periods_by_id.get(item["id"], []), "themes": ctx.themes_by_id.get(item["id"], []),
        "thumbnail_url": f"{config.BASE_URL}/{listing['thumbnail']}" if listing.get("thumbnail") else None,
        "image": _image_info(item),
        "source_url": f"{config.INDEX_URL}?view=ArtworkInfo&OPPID={item['id']}",
        "extracted_at": now_iso(),
    }
    for name, parser in POPUP_PARSERS.items():
        path = raw_dir / f"{name}.html"
        if path.exists():
            meta[POPUP_FIELDS[name]] = parser(path.read_text(encoding="utf-8"))
    meta["context"] = _artwork_context(item, date["range"], ctx)
    return meta


def _image_info(item: dict[str, Any]) -> dict[str, Any] | None:
    path = artwork_dir(item) / "image.jpg"
    if not path.exists():
        return None
    with Image.open(path) as im:
        return {"file": "image.jpg", "width": im.width, "height": im.height, "format": im.format,
                "bytes": path.stat().st_size, "source": image_url(item)}


def _artwork_context(item: dict[str, Any], art_range: dict[str, Any] | None, ctx: Context) -> dict[str, Any]:
    """Residence at the (start of the) artwork date, plus linked biography events."""
    start = art_range["start"] if art_range else f"{item['year']}-01-01"
    return {
        "creation_place": item["listing"]["place"],
        "residence": C.residence_at(ctx.chronology, start),
        "events": C.events_for(ctx.chronology, item["id"], art_range),
    }


# --- writings and archives --------------------------------------------------------------
def writing_metadata(item: dict[str, Any]) -> dict[str, Any]:
    listing = item["listing"]
    html = (config.RAW_DIR / "writings" / f"{listing['mid']}.html").read_text(encoding="utf-8")
    parsed = T.parse_writing(html)
    date_text = parsed["date_text"] or listing.get("date_text")
    return {"id": item["id"], "type": "writing", "mid": listing["mid"], "year": item["year"],
            "title": parsed["title"] or listing["title"], "date_text": date_text,
            "date": T.normalize_date(date_text or ""), "text": parsed["text"],
            "source_url": f"{config.INDEX_URL}?view=WritingsInfo&mid={listing['mid']}&year={item['year']}",
            "extracted_at": now_iso()}


def archive_metadata(item: dict[str, Any]) -> dict[str, Any]:
    listing = item["listing"]
    html = (config.RAW_DIR / "archives" / f"article_{listing['id']}.html").read_text(encoding="utf-8")
    parsed = T.parse_archive_article(html)
    return {"id": item["id"], "type": "archive", "article_id": listing["id"], "year": item["year"],
            "title": parsed["title"] or listing["title"], "publisher": parsed["publisher"] or listing.get("publisher"),
            "language": listing.get("language"), "date_text": listing.get("date_text"),
            "dateline": parsed["dateline"], "text": parsed["text"],
            "source_url": f"{config.INDEX_URL}?view=ArchiveArticle&year={item['year']}&id={listing['id']}",
            "extracted_at": now_iso()}


def item_dir(item: dict[str, Any]) -> Path:
    if item["type"] == "artwork":
        return artwork_dir(item)
    folder = "writings" if item["type"] == "writing" else "archives"
    return config.PICASSO_DIR / folder / item["id"].split(".", 1)[1]


def transform_items(manifest: Manifest, items: list[dict[str, Any]]) -> dict[str, int]:
    """Write metadata.json for every item; failures are recorded in the manifest."""
    ctx = Context()
    stats = {"ok": 0, "failed": 0}
    for item in items:
        try:
            if item["type"] == "artwork":
                meta = artwork_metadata(item, ctx)
            elif item["type"] == "writing":
                meta = writing_metadata(item)
            else:
                meta = archive_metadata(item)
            target = item_dir(item) / "metadata.json"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
            manifest.set_status(item["id"], "transformed")
            stats["ok"] += 1
        except Exception as exc:  # noqa: BLE001
            log.error("fallo al transformar %s: %s", item["id"], exc)
            manifest.set_status(item["id"], "failed", str(exc)[:500])
            stats["failed"] += 1
    manifest.commit()
    return stats


# --- index and summary --------------------------------------------------------------------
CSV_COLUMNS = ["id", "type", "category", "year", "title", "place", "date_text", "date_start", "date_end",
               "date_precision", "medium", "dimensions", "collection", "n_catalogs", "n_literature",
               "n_exhibitions", "n_provenance", "n_notes", "n_commentary", "periods", "themes",
               "residence", "n_events", "image_file", "image_width", "image_height", "path"]


def csv_row(meta: dict[str, Any], path: Path) -> dict[str, Any]:
    rng = (meta.get("date") or {}).get("range") or {}
    image = meta.get("image") or {}
    context = meta.get("context") or {}
    residence = context.get("residence") or {}
    return {
        "id": meta["id"], "type": meta["type"], "category": meta.get("category"), "year": meta.get("year"),
        "title": meta.get("title"), "place": meta.get("place") or meta.get("publisher"),
        "date_text": meta.get("date_text"), "date_start": rng.get("start"), "date_end": rng.get("end"),
        "date_precision": rng.get("precision"), "medium": meta.get("medium"), "dimensions": meta.get("dimensions"),
        "collection": meta.get("collection"), "n_catalogs": len(meta.get("catalogs") or []),
        "n_literature": len(meta.get("literature") or []), "n_exhibitions": len(meta.get("exhibitions") or []),
        "n_provenance": len(meta.get("provenance") or []), "n_notes": len(meta.get("notes") or []),
        "n_commentary": len(meta.get("commentary") or []), "periods": "; ".join(meta.get("periods") or []),
        "themes": "; ".join(meta.get("themes") or []), "residence": residence.get("name"),
        "n_events": len(context.get("events") or []), "image_file": image.get("file"),
        "image_width": image.get("width"), "image_height": image.get("height"),
        "path": str(path.parent.relative_to(config.DATA_DIR)),
    }


def load_index(manifest: Manifest) -> dict[str, Any]:
    """Scan every metadata.json, write catalog.csv + summary.json and return the summary."""
    config.INDEX_DIR.mkdir(parents=True, exist_ok=True)
    rows, metas = [], []
    for path in sorted(config.PICASSO_DIR.rglob("metadata.json")):
        if "context" in path.parts:
            continue
        meta = json.loads(path.read_text(encoding="utf-8"))
        metas.append(meta)
        rows.append(csv_row(meta, path))
    with (config.INDEX_DIR / "catalog.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    summary = {
        "generated_at": now_iso(),
        "items_on_disk": dict(Counter(m["type"] for m in metas)),
        "manifest": manifest.counts(),
        "failures": manifest.failures(),
        "coverage": {t: _coverage([m for m in metas if m["type"] == t]) for t in {m["type"] for m in metas}},
        "images": sum(1 for m in metas if m.get("image")),
        "categories": dict(Counter(m.get("category") for m in metas if m["type"] == "artwork")),
    }
    (config.INDEX_DIR / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    return summary


COVERAGE_FIELDS = {
    "artwork": ["title", "place", "date_text", "medium", "dimensions", "collection", "credit_line", "catalogs",
                "literature", "exhibitions", "provenance", "notes", "commentary", "periods", "themes", "image",
                "context.residence", "context.events"],
    "writing": ["title", "date_text", "text"],
    "archive": ["title", "publisher", "language", "date_text", "dateline", "text"],
}


def _coverage(metas: list[dict[str, Any]]) -> dict[str, float]:
    if not metas:
        return {}
    kind = metas[0]["type"]
    out = {}
    for field in COVERAGE_FIELDS[kind]:
        present = 0
        for meta in metas:
            value = meta
            for part in field.split("."):
                value = (value or {}).get(part) if isinstance(value, dict) else None
            present += bool(value)
        out[field] = round(100 * present / len(metas), 1)
    return out


def format_summary(summary: dict[str, Any]) -> str:
    """Human-readable (Spanish) summary for the terminal."""
    lines = ["", "=== Resumen del pipeline ==="]
    lines.append("Ítems con metadata.json: " + ", ".join(f"{k}: {v}" for k, v in summary["items_on_disk"].items()))
    lines.append(f"Imágenes descargadas: {summary['images']}")
    if summary["categories"]:
        lines.append("Obras por categoría: " + ", ".join(f"{k}: {v}" for k, v in sorted(summary["categories"].items())))
    lines.append("Manifiesto (tipo/estado): " + ", ".join(f"{r['type']}/{r['status']}: {r['n']}" for r in summary["manifest"]))
    for kind, cov in summary["coverage"].items():
        lines.append(f"Cobertura de campos ({kind}): " + ", ".join(f"{k} {v}%" for k, v in cov.items()))
    if summary["failures"]:
        lines.append(f"Fallos registrados ({len(summary['failures'])} mostrados):")
        lines += [f"  - {f['id']} ({f['attempts']} intentos): {f['error']}" for f in summary["failures"][:10]]
    else:
        lines.append("Fallos registrados: ninguno")
    return "\n".join(lines)
