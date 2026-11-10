"""Phase 1 reconnaissance: take a representative sample of every item type.

Everything downloaded is cached under data/raw/ (re-runs skip what exists) and the
parsed samples plus coverage statistics are written to data/recon/. Run with:

    python -m src.recon.sample
"""

from __future__ import annotations

import io
import json
import logging
import re
import time
from collections import Counter
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup
from PIL import Image

from src.etl import config
from src.etl import transform as T
from src.etl.session import OppClient

log = logging.getLogger("recon")

RAW = config.RAW_DIR
OUT = config.RECON_DIR
SAMPLE_YEARS = [1895, 1901, 1907, 1912, 1921, 1932, 1937, 1945, 1955, 1962, 1969]
CATEGORY_CHECK_YEARS = [1907, 1937]
BIO_YEARS = [1900, 1907, 1937]
WRITING_YEARS = [1935, 1941, 1951]
ARCHIVE_YEARS = [1937, 1944, 1960, 1973, 1990]
PERIOD_SAMPLES = ["Blue Period", "Rose Period", "Analytic Cubism", "Synthetic Cubism"]
THEME_SAMPLES = ["Animal: Bull"]
ARTWORK_VIEWS = {
    "details": "ArtworkDetails", "provenance": "former", "exhibitions": "exhibitedPrint",
    "literature": "bibliography", "note": "note", "commentary": "commentary",
}
ARTWORK_PARSERS = {
    "details": T.parse_artwork_details, "provenance": T.parse_provenance,
    "exhibitions": T.parse_exhibitions, "literature": T.parse_literature,
    "note": T.parse_note, "commentary": T.parse_commentary,
}


def write_json(name: str, data: Any) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def coverage(items: list[dict[str, Any]], fields: list[str] | None = None) -> dict[str, float]:
    """Percentage of items where each field has a non-empty value."""
    if not items:
        return {}
    fields = fields or sorted({k for it in items for k in it})
    return {f: round(100 * sum(1 for it in items if it.get(f)) / len(items), 1) for f in fields}


def safe_id(opp_id: str) -> str:
    return opp_id.replace(":", "_")


# --- artworks ----------------------------------------------------------------------
def fetch_catalogue(client: OppClient, path: Path, attempts: int = 3, **params) -> list[dict[str, Any]]:
    """`ArtworkLarge` sometimes answers an empty shell under load: retry before trusting a zero."""
    if path.exists():  # a cached result (even an empty one) was already verified
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


def catalogue_counts(client: OppClient) -> dict[str, Any]:
    """One yearly catalogue page per year (1881-1973): exact totals + full metadata."""
    per_year, per_category, first_items = {}, {}, {}
    for year in config.ARTWORK_YEARS:
        items = fetch_catalogue(client, RAW / "artworks" / "catalogue" / f"{year}.html",
                                year=year, category=config.ALL_CATEGORIES_PARAM)
        per_year[year] = len(items)
        first_items[year] = items
        log.info("catálogo %d: %d obras", year, len(items))
    for year in CATEGORY_CHECK_YEARS:
        per_category[year] = {}
        for cat in config.CATEGORIES:
            per_category[year][cat] = len(fetch_catalogue(client, RAW / "artworks" / "catalogue" / f"{year}_{cat}.html",
                                                          attempts=2, year=year, category=cat))
    return {"per_year": per_year, "per_category": per_category, "items": first_items}


def sample_artworks(client: OppClient, items_by_year: dict[int, list[dict]]) -> list[dict[str, Any]]:
    """~4 artworks per sample year; fetch the Summary page (for the sub-page flags) and
    all six detail views so coverage can be measured against the flags."""
    sample = []
    for year in SAMPLE_YEARS:
        summary = client.get_view_cached(RAW / "artworks" / "summary" / f"{year}_p1.html", "ArtworkSummary",
                                         year=year, category=config.ALL_CATEGORIES_PARAM, page=1)
        listed = T.parse_artwork_listing(summary)
        if not listed:
            listed = items_by_year.get(year, [])[:30]
        step = max(1, len(listed) // 4)
        for item in listed[::step][:4]:
            sample.append(enrich_artwork(client, item))
    return sample


def enrich_artwork(client: OppClient, item: dict[str, Any]) -> dict[str, Any]:
    folder = RAW / "artworks" / safe_id(item["id"])
    for key, view in ARTWORK_VIEWS.items():
        html = client.get_view_cached(folder / f"{key}.html", view, OPPID=item["id"])
        parsed = ARTWORK_PARSERS[key](html)
        item[key] = parsed
        item[f"has_{key}"] = bool(parsed)
    log.info("obra %s: %s", item["id"], {k: v for k, v in item.items() if k.startswith("has_")})
    return item


# --- biography ---------------------------------------------------------------------
def sample_biography(client: OppClient) -> dict[str, Any]:
    entries, commentaries, dated, resources = [], [], [], []
    for year in BIO_YEARS:
        page = 1
        while True:
            html = client.get_view_cached(RAW / "biography" / f"{year}_p{page}.html", "BioIndex", year=year, page=page)
            batch = T.parse_bio_index(html)
            for e in batch:
                e["year"] = year
            entries.extend(batch)
            if page >= T.last_page(html) or not batch:
                break
            page += 1
        log.info("biografía %d: %d entradas", year, sum(1 for e in entries if e["year"] == year))
    for e in [e for e in entries if "BioCommentary" in e["links"]][:12]:
        cid = e["links"]["BioCommentary"][0]["id"]
        html = client.get_view_cached(RAW / "biography" / f"commentary_{cid}.html", "biographycommentary", id=cid)
        commentaries.append({"id": cid, "year": e["year"], "date_desc": e["date_desc"],
                             "remarks": T.parse_bio_commentary(html)})
    for e in [e for e in entries if "DatedArtworksSummary" in e["links"]][:8]:
        p = e["links"]["DatedArtworksSummary"][0]
        name = f"dated_{p['startYear']}-{p['startMonth']}-{p['startDay']}_{p['endYear']}-{p['endMonth']}-{p['endDay']}"
        html = client.get_view_cached(RAW / "biography" / f"{name}.html", "artworksDated", **p)
        dated.append({"year": e["year"], "date_desc": e["date_desc"], "range": p,
                      "opp_ids": T.parse_dated_artworks(html)})
    tree_html = client.get_view_cached(RAW / "biography" / "tree.html", "bioTree")
    tree = T.parse_bio_tree(tree_html)
    wanted = ["bateaulavoir", "rue-13,ravignan", "boulevard-11,clichy", "map-europe",
              "matisse,henri", "kahnweiler,daniel-henry", "apollinaire,guillaume", "breton,andre"]
    for rid in wanted:
        html = client.get_view_cached(RAW / "biography" / f"resource_{rid}.html", "BioResource", id=rid)
        resources.append({"id": rid, **T.parse_bio_resource(html)})
    return {"entries": entries, "commentaries": commentaries, "dated_artworks": dated,
            "tree": tree, "resources": resources}


# --- writings / archives / collections / references ------------------------------------
def sample_writings(client: OppClient) -> dict[str, Any]:
    index, writings = [], []
    for year in WRITING_YEARS:
        html = client.get_view_cached(RAW / "writings" / f"{year}_p1.html", "Writings", year=year, page=1)
        rows = T.parse_writings_index(html)
        index.append({"year": year, "count": T.count_catalogued(html), "pages": T.last_page(html), "rows": rows})
        for row in rows[:8]:
            w_html = client.get_view_cached(RAW / "writings" / f"{row['mid']}.html", "WritingsInfo", mid=row["mid"], year=year)
            writings.append({**row, **T.parse_writing(w_html)})
    return {"index": index, "writings": writings}


def sample_archives(client: OppClient) -> dict[str, Any]:
    index, articles = [], []
    for year in ARCHIVE_YEARS:
        html = client.get_view_cached(RAW / "archives" / f"{year}.html", "Archives", year=year)
        rows = T.parse_archives_index(html)
        index.append({"year": year, "count": T.count_entries(html), "pages": T.last_page(html), "rows": rows})
        for row in rows[:4]:
            a_html = client.get_view_cached(RAW / "archives" / f"article_{row['id']}.html", "ArchiveArticle", year=year, id=row["id"])
            articles.append({**row, **T.parse_archive_article(a_html)})
    return {"index": index, "articles": articles}


def sample_collections(client: OppClient) -> list[dict[str, Any]]:
    rows = []
    for letter in ["A", "M"]:
        html = client.get_view_cached(RAW / "collections" / f"{letter}_p1.html", "Collections", letter=letter, page=1)
        rows.append({"letter": letter, "count": T.count_entries(html), "rows": T.parse_collections_index(html)})
    return rows


def sample_references(client: OppClient) -> list[dict[str, Any]]:
    rows = []
    for letter in ["A", "M"]:
        html = client.get_view_cached(RAW / "references" / f"{letter}_p1.html", "Reference", letter=letter, page=1)
        rows.append({"letter": letter, "count": T.count_entries(html), "pages": T.last_page(html),
                     "rows": T.parse_references_index(html)})
    return rows


# --- periods & themes (style labels) ----------------------------------------------------
def checkbox_values(html: str, prefix: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "lxml")
    return [{"param": cb["name"], "value": cb["value"]}
            for cb in soup.find_all("input", {"type": "checkbox"}) if cb.get("name", "").startswith(prefix)]


def sample_guide(client: OppClient) -> dict[str, Any]:
    periods_html = client.get_view_cached(RAW / "guide" / "periods.html", "GuideList")
    themes_html = client.get_view_cached(RAW / "guide" / "themes.html", "GuideListThemes")
    periods = checkbox_values(periods_html, "StyleSearch")
    themes = checkbox_values(themes_html, "ThemeSearch")
    cats = {f"CategorySearchIn{i + 1}": cat for i, cat in enumerate(config.CATEGORIES)}
    common = dict(stylenum=len(periods), themenum=len(themes), SortBy1="OPP", SortDirection1="Asc",
                  SortBy2="OPP", SortDirection2="Asc", page=1, **cats)
    searches = []
    for kind, names, options in [("period", PERIOD_SAMPLES, periods), ("theme", THEME_SAMPLES, themes)]:
        for name in names:
            opt = next((o for o in options if o["value"] == name), None)
            if not opt:
                continue
            slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
            html = client.get_view_cached(RAW / "guide" / f"search_{kind}_{slug}_p1.html", "GuideSearchS",
                                          **{opt["param"]: name}, **common)
            items = T.parse_artwork_listing(html)
            searches.append({"kind": kind, "name": name, "param": opt["param"], "count": T.count_catalogued(html),
                             "sample_ids": [i["id"] for i in items[:10]]})
            log.info("%s '%s': %s obras", kind, name, T.count_catalogued(html))
    return {"periods": periods, "themes": themes, "searches": searches}


# --- images --------------------------------------------------------------------------
def measure_images() -> list[dict[str, Any]]:
    rows = []
    for path in sorted((OUT / "smoke" / "images").glob("*")):
        with Image.open(path) as im:
            rows.append({"file": path.name, "kind": path.name.split("_")[0], "format": im.format,
                         "width": im.width, "height": im.height, "mode": im.mode, "bytes": path.stat().st_size})
    return rows


# --- main ----------------------------------------------------------------------------
def main() -> None:
    config.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[logging.FileHandler(config.LOGS_DIR / "recon.log"), logging.StreamHandler()])
    started = time.monotonic()
    client = OppClient()
    client.ensure_logged_in()

    cat = catalogue_counts(client)
    artworks = sample_artworks(client, cat["items"])
    write_json("sample_artworks.json", artworks)
    bio = sample_biography(client); write_json("sample_biography.json", bio)
    wr = sample_writings(client); write_json("sample_writings.json", wr)
    ar = sample_archives(client); write_json("sample_archives.json", ar)
    co = sample_collections(client); write_json("sample_collections.json", co)
    re_ = sample_references(client); write_json("sample_references.json", re_)
    guide = sample_guide(client); write_json("sample_guide.json", guide)

    all_items = [it for items in cat["items"].values() for it in items]
    places = Counter(it["place"] for it in all_items if it["place"])
    media = Counter(it["medium"] for it in all_items if it["medium"])
    summary = {
        "requests": client.request_count,
        "elapsed_minutes": round((time.monotonic() - started) / 60, 1),
        "artworks": {
            "total": sum(cat["per_year"].values()),
            "per_year": cat["per_year"],
            "per_category": cat["per_category"],
            "listing_coverage": coverage(all_items, ["id", "title", "place", "date_text", "medium",
                                                      "dimensions", "collection", "credit_line", "references", "thumbnail"]),
            "date_precision": Counter(it["date"]["precision"] for it in all_items),
            "date_uncertain_pct": round(100 * sum(it["date"]["uncertain"] for it in all_items) / len(all_items), 1),
            "top_places": places.most_common(25),
            "distinct_places": len(places),
            "top_media": media.most_common(15),
            "detail_coverage": coverage(artworks, [f"has_{k}" for k in ARTWORK_VIEWS]),
            "details_fields": coverage([a["details"] for a in artworks if a["details"]]),
            "sample_size": len(artworks),
        },
        "biography": {
            "entries_sampled": len(bio["entries"]),
            "coverage": coverage(bio["entries"], ["date_desc", "text", "images", "opp_ids"]),
            "link_coverage": coverage([{k: True for k in e["links"]} for e in bio["entries"]]),
            "tree_places": sum(1 for r in bio["tree"] if "People" not in r["path"]),
            "tree_people": sum(1 for r in bio["tree"] if "People" in r["path"]),
        },
        "writings": {"index": [{k: v for k, v in i.items() if k != "rows"} for i in wr["index"]],
                     "coverage": coverage(wr["writings"], ["mid", "title", "date_text", "text"])},
        "archives": {"index": [{k: v for k, v in i.items() if k != "rows"} for i in ar["index"]],
                     "coverage": coverage(ar["articles"], ["id", "title", "language", "publisher", "date_text", "dateline", "text"])},
        "collections": [{"letter": c["letter"], "count": c["count"], "rows": len(c["rows"])} for c in co],
        "references": {"index": [{k: v for k, v in r.items() if k != "rows"} for r in re_],
                       "coverage": coverage([row for r in re_ for row in r["rows"]])},
        "guide": {"periods": len(guide["periods"]), "themes": len(guide["themes"]), "searches": guide["searches"]},
        "images": measure_images(),
    }
    write_json("recon_summary.json", summary)
    log.info("Listo: %d requests en %.1f min", client.request_count, summary["elapsed_minutes"])


if __name__ == "__main__":
    main()
