"""Phase `context`: biography, places/people, style labels, collections, references.

Everything lands in data/picasso/context/*.json. `build_chronology` turns the
biography into a dated list of events with the places they link, from which
`residence_at` infers where Picasso lived on a given date (a heuristic: the latest
entry that reads like a move and links a city-or-finer place of the Places tree).
"""

from __future__ import annotations

import json
import logging
import math
import re
from pathlib import Path
from typing import Any

from . import config
from . import transform as T
from .manifest import Manifest
from .session import OppClient

log = logging.getLogger("etl.context")
RAW = config.RAW_DIR
CONTEXT_DIR = config.PICASSO_DIR / "context"

MOVE_RE = re.compile(
    r"\b(moves?|moving|settles?|installs?|takes? (?:a |an |the )?(?:new |small |large |second )?"
    r"(?:studio|apartment|flat|house|room|villa|home)|rents?|leases?|buys? (?:a |the )?(?:house|villa|château|chateau)|"
    r"lives? (?:at|in)|living (?:at|in)|returns? to|back (?:in|to)|arrives? (?:in|at)|"
    r"spends? (?:the )?(?:summer|winter|spring|autumn|months?|weeks?)|stays? (?:at|in)|"
    r"leaves? for|goes? to|travels? to|departs? for)\b", re.I)


# --- json helpers ---------------------------------------------------------------------
def read_json(name: str, default: Any) -> Any:
    path = CONTEXT_DIR / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def write_json(name: str, data: Any) -> Path:
    CONTEXT_DIR.mkdir(parents=True, exist_ok=True)
    path = CONTEXT_DIR / name
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return path


# --- biography ------------------------------------------------------------------------
def crawl_biography(client: OppClient, manifest: Manifest, years: list[int]) -> dict[str, list[dict[str, Any]]]:
    """Fetch every BioIndex page of `years` plus the commentaries and explicit
    artwork links (artworksDated) of each entry. Merges into biography.json by year."""
    biography = read_json("biography.json", {})
    for year in years:
        if manifest.is_done(f"context:biography:{year}") and str(year) in biography:
            continue
        entries = _crawl_bio_year(client, year)
        biography[str(year)] = entries
        manifest.mark_done(f"context:biography:{year}", str(len(entries)))
        manifest.commit()
        write_json("biography.json", biography)
        log.info("biografía %d: %d entradas", year, len(entries))
    return biography


def _crawl_bio_year(client: OppClient, year: int) -> list[dict[str, Any]]:
    entries, page = [], 1
    while True:
        html = client.get_view_cached(RAW / "biography" / f"{year}_p{page}.html", "BioIndex", year=year, page=page)
        batch = T.parse_bio_index(html)
        entries.extend(batch)
        if not batch or page >= T.last_page(html):
            break
        page += 1
    for n, entry in enumerate(entries, 1):
        entry["entry_id"] = f"{year}-{n:03d}"
        entry["year"] = year
        entry["range"] = T.date_range(entry["date_desc"], year)
        entry["place_ids"] = sorted({p["id"] for p in entry["links"].get("BioResource", []) if p.get("id")})
        entry["opp_ids"] = _entry_artworks(entry)
        _fetch_entry_extras(client, entry)
    return entries


def _entry_artworks(entry: dict[str, Any]) -> list[str]:
    """Artworks the entry cites: in its text, in ArtworkInfo links and in "multiple" galleries."""
    ids = set(entry.get("opp_ids", []))
    ids |= {p["OPPID"] for p in entry["links"].get("ArtworkInfo", []) if p.get("OPPID")}
    for p in entry["links"].get("multiple", []):
        ids |= set(T.OPP_ID_RE.findall(p.get("OPPs", "")))
    return sorted(ids)


def _fetch_entry_extras(client: OppClient, entry: dict[str, Any]) -> None:
    links = entry["links"]
    if "BioCommentary" in links:
        cid = links["BioCommentary"][0]["id"]
        html = client.get_view_cached(RAW / "biography" / f"commentary_{cid}.html", "biographycommentary", id=cid)
        entry["commentary"] = T.parse_bio_commentary(html)
    if "DatedArtworksSummary" in links:
        p = links["DatedArtworksSummary"][0]
        name = f"dated_{p['startYear']}-{p['startMonth']}-{p['startDay']}_{p['endYear']}-{p['endMonth']}-{p['endDay']}"
        html = client.get_view_cached(RAW / "biography" / f"{name}.html", "artworksDated", **p)
        entry["dated_range"] = p
        entry["dated_opp_ids"] = T.parse_dated_artworks(html)


# --- places and people ------------------------------------------------------------------
def crawl_places(client: OppClient, manifest: Manifest) -> tuple[list[dict], list[dict]]:
    """The Places tree (residences, studios, cities, people, documents) and one page per node."""
    if manifest.is_done("context:places"):
        return read_json("places.json", []), read_json("people.json", [])
    tree = T.parse_bio_tree(client.get_view_cached(RAW / "biography" / "tree.html", "bioTree"))
    places, people = [], []
    for node in tree:
        html = client.get_view_cached(RAW / "biography" / f"resource_{node['id']}.html", "BioResource", id=node["id"])
        record = {**node, "kind": _node_kind(node), **T.parse_bio_resource(html)}
        (people if record["kind"] == "person" else places).append(record)
    write_json("places.json", places)
    write_json("people.json", people)
    manifest.mark_done("context:places", f"{len(places)} places, {len(people)} people")
    manifest.commit()
    log.info("árbol de lugares: %d lugares/documentos, %d personas", len(places), len(people))
    return places, people


def _node_kind(node: dict[str, Any]) -> str:
    if "People" in node["path"]:
        return "person"
    if "Documents" in node["path"]:
        return "document"
    return "place"


# --- chronology -------------------------------------------------------------------------
def build_chronology(biography: dict[str, list[dict]], places: list[dict]) -> list[dict[str, Any]]:
    """Flatten the biography into dated events with resolved places; saves chronology.json."""
    by_id = {p["id"]: p for p in places}
    events = []
    for year, entries in sorted(biography.items(), key=lambda kv: int(kv[0])):
        for entry in entries:
            linked = [by_id[i] for i in entry["place_ids"] if i in by_id and by_id[i]["kind"] == "place"]
            event = {
                "entry_id": entry["entry_id"], "year": int(year), "date_desc": entry["date_desc"],
                "start": entry["range"]["start"] if entry["range"] else None,
                "end": entry["range"]["end"] if entry["range"] else None,
                "precision": entry["range"]["precision"] if entry["range"] else None,
                "places": [{"id": p["id"], "name": p["name"], "path": p["path"]} for p in linked],
                "people": [i for i in entry["place_ids"] if i in by_id and by_id[i]["kind"] == "person"],
                "is_move": bool(MOVE_RE.search(entry["text"])) and any(_is_residence_grade(p) for p in linked),
                "opp_ids": entry.get("opp_ids", []),
                "dated_opp_ids": entry.get("dated_opp_ids", []),
                "text": entry["text"],
            }
            events.append(event)
    events.sort(key=lambda e: (e["start"] or "", e["entry_id"]))
    write_json("chronology.json", events)
    return events


def _is_residence_grade(place: dict[str, Any]) -> bool:
    """City level or finer (streets, studios, villas): path deeper than Places > continent > country."""
    return len(place["path"]) >= 3


def residence_at(chronology: list[dict[str, Any]], date_iso: str) -> dict[str, Any] | None:
    """Most recent move whose start is on or before `date_iso` (ISO yyyy-mm-dd)."""
    latest = None
    for event in chronology:
        if not event["is_move"] or not event["start"] or event["start"] > date_iso:
            continue
        if latest is None or event["start"] >= latest["start"]:
            latest = event
    if latest is None:
        return None
    place = next(p for p in latest["places"] if _is_residence_grade(p))
    return {"place_id": place["id"], "name": place["name"], "path": place["path"],
            "since": latest["start"], "entry_id": latest["entry_id"]}


def events_for(chronology: list[dict[str, Any]], opp_id: str, art_range: dict[str, Any] | None,
               max_overlaps: int = 15) -> list[dict[str, Any]]:
    """Biography entries tied to an artwork: explicit links first, then entries whose
    date range overlaps the artwork's (skipped when either side only knows the year)."""
    explicit, overlapping = [], []
    for event in chronology:
        if opp_id in event["opp_ids"] or opp_id in event["dated_opp_ids"]:
            explicit.append(_event_summary(event, explicit=True))
        elif (art_range and art_range["precision"] != "year" and event["precision"] not in (None, "year")
              and T.ranges_overlap(art_range, event)):
            overlapping.append(_event_summary(event, explicit=False))
    return explicit + overlapping[:max_overlaps]


def _event_summary(event: dict[str, Any], explicit: bool) -> dict[str, Any]:
    return {"entry_id": event["entry_id"], "date_desc": event["date_desc"], "start": event["start"],
            "end": event["end"], "explicit": explicit, "places": [p["name"] for p in event["places"]],
            "text": event["text"][:400] + ("…" if len(event["text"]) > 400 else "")}


# --- style labels (periods / themes) ------------------------------------------------------
def crawl_labels(client: OppClient, manifest: Manifest, kinds: list[str]) -> dict[str, dict[str, list[str]]]:
    """For every period/theme of the Guide, list the OPP ids it contains (GuideSearchS)."""
    labels = read_json("periods.json", {"periods": {}, "themes": {}})
    sources = {"periods": ("GuideList", "StyleSearch"), "themes": ("GuideListThemes", "ThemeSearch")}
    for kind in kinds:
        view, prefix = sources[kind]
        options = T.parse_checkboxes(client.get_view_cached(RAW / "guide" / f"{kind}.html", view), prefix)
        counts = {"stylenum": 71, "themenum": 109}
        for opt in options:
            if manifest.is_done(f"context:{kind}:{opt['value']}") and opt["value"] in labels[kind]:
                continue
            ids = _search_label(client, kind, opt, counts)
            labels[kind][opt["value"]] = ids
            manifest.mark_done(f"context:{kind}:{opt['value']}", str(len(ids)))
            manifest.commit()
            write_json("periods.json", labels)
            log.info("%s '%s': %d obras", kind, opt["value"], len(ids))
    return labels


def _search_label(client: OppClient, kind: str, opt: dict[str, str], counts: dict[str, int]) -> list[str]:
    slug = re.sub(r"[^a-z0-9]+", "-", opt["value"].lower()).strip("-")
    cats = {f"CategorySearchIn{i + 1}": cat for i, cat in enumerate(config.CATEGORIES)}
    common = dict(SortBy1="OPP", SortDirection1="Asc", SortBy2="OPP", SortDirection2="Asc", **counts, **cats)
    ids, page, pages = [], 1, 1
    while page <= pages:
        html = client.get_view_cached(RAW / "guide" / f"search_{kind[:-1]}_{slug}_p{page}.html", "GuideSearchS",
                                      **{opt["param"]: opt["value"]}, page=page, **common)
        items = T.parse_artwork_listing(html)
        ids.extend(i["id"] for i in items)
        if page == 1:
            pages = max(1, math.ceil((T.count_catalogued(html) or len(items)) / config.ITEMS_PER_LISTING_PAGE))
        if not items:
            break
        page += 1
    return sorted(set(ids))


# --- collections and references ------------------------------------------------------------
def crawl_collections(client: OppClient, manifest: Manifest) -> list[dict[str, Any]]:
    if manifest.is_done("context:collections"):
        return read_json("collections.json", [])
    rows = _crawl_letters(client, "Collections", "collections", T.parse_collections_index, T.count_entries)
    write_json("collections.json", rows)
    manifest.mark_done("context:collections", str(len(rows)))
    manifest.commit()
    return rows


def crawl_references(client: OppClient, manifest: Manifest) -> list[dict[str, Any]]:
    if manifest.is_done("context:references"):
        return read_json("references.json", [])
    rows = _crawl_letters(client, "Reference", "references", T.parse_references_index, T.count_entries)
    write_json("references.json", rows)
    manifest.mark_done("context:references", str(len(rows)))
    manifest.commit()
    return rows


def _crawl_letters(client: OppClient, view: str, folder: str, parser, counter) -> list[dict[str, Any]]:
    rows = []
    for letter in config.LETTERS:
        page = 1
        while True:
            html = client.get_view_cached(RAW / folder / f"{letter}_p{page}.html", view, letter=letter, page=page)
            batch = parser(html)
            for row in batch:
                row["letter"] = letter
            rows.extend(batch)
            pages = max(1, math.ceil((counter(html) or 0) / config.ITEMS_PER_LISTING_PAGE), T.last_page(html))
            if not batch or page >= pages:
                break
            page += 1
        log.info("%s letra %s: %d acumuladas", folder, letter, len(rows))
    return rows
