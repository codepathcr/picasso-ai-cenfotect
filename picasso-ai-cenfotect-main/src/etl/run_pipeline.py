"""CLI of the ETL pipeline. Examples:

    python -m src.etl.run_pipeline --phase all --limit 100 --years 1907      # pilot
    python -m src.etl.run_pipeline --phase all --resume                       # full run (level 1 + pop-ups)
    python -m src.etl.run_pipeline --phase all --no-popups --resume           # level 1 only
    python -m src.etl.run_pipeline --phase context --parts labels             # periods/themes only

Phases run sequentially with one authenticated client; everything is resumable.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time

from . import config
from . import context as C
from . import discover as D
from . import extract as E
from . import load as L
from .manifest import Manifest
from .session import BlockedError, OppClient

log = logging.getLogger("etl")
PHASES = ["discover", "extract", "context", "transform", "load"]
TYPES = {"artworks": "artwork", "writings": "writing", "archives": "archive"}
CONTEXT_PARTS = ["biography", "places", "labels", "collections", "references"]


def parse_years(values: list[str] | None, default: range) -> list[int]:
    """"1907 1910-1912" -> [1907, 1910, 1911, 1912]."""
    if not values:
        return list(default)
    years: list[int] = []
    for value in values:
        if "-" in value:
            a, b = value.split("-", 1)
            years.extend(range(int(a), int(b) + 1))
        else:
            years.append(int(value))
    return sorted(set(years))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Pipeline ETL del Online Picasso Project (uso académico).")
    p.add_argument("--phase", choices=PHASES + ["all"], default="all")
    p.add_argument("--type", choices=list(TYPES) + ["all"], default="artworks",
                   help="tipo de ítem (por defecto: artworks)")
    p.add_argument("--limit", type=int, help="procesar sólo los primeros N ítems (piloto)")
    p.add_argument("--years", nargs="*", help="años a procesar, p.ej. 1907 1910-1912")
    p.add_argument("--categories", nargs="*", choices=config.CATEGORIES, help="categorías de obra")
    p.add_argument("--resume", action="store_true", help="saltar ítems ya completados y reintentar los fallidos")
    p.add_argument("--no-images", action="store_true", help="no descargar imágenes")
    p.add_argument("--no-popups", action="store_true", help="no descargar pop-ups de detalle (Nivel 1)")
    p.add_argument("--parts", help="partes del contexto, separadas por coma: " + ",".join(CONTEXT_PARTS))
    p.add_argument("--rate", type=float, default=config.RATE_LIMIT_SECONDS, help="segundos entre requests")
    return p


def setup_logging() -> None:
    config.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                        handlers=[logging.FileHandler(config.LOGS_DIR / "pipeline.log"),
                                  logging.StreamHandler(sys.stdout)])


def selected_types(args: argparse.Namespace) -> list[str]:
    return list(TYPES.values()) if args.type == "all" else [TYPES[args.type]]


def years_for(item_type: str, args: argparse.Namespace) -> list[int]:
    defaults = {"artwork": config.ARTWORK_YEARS, "writing": config.WRITINGS_YEARS, "archive": config.ARCHIVES_YEARS}
    return parse_years(args.years, defaults[item_type])


def select_items(manifest: Manifest, item_type: str, args: argparse.Namespace, done_status: str) -> list[dict]:
    """Manifest rows for a phase; with --resume, rows already past `done_status` are skipped."""
    years = args.years and parse_years(args.years, range(0))
    items = manifest.select(item_type, years or None, args.limit, categories=args.categories)
    if args.resume:
        order = ["pending", "extracted", "transformed"]
        items = [i for i in items if i["status"] == "failed" or order.index(i["status"]) < order.index(done_status)]
    return items


def run_discover(client: OppClient, manifest: Manifest, args: argparse.Namespace) -> None:
    for item_type in selected_types(args):
        years = years_for(item_type, args)
        if item_type == "artwork":
            D.discover_artworks(client, manifest, years, args.categories)
        elif item_type == "writing":
            D.discover_writings(client, manifest, years)
        else:
            D.discover_archives(client, manifest, years)


def run_extract(client: OppClient, manifest: Manifest, args: argparse.Namespace) -> None:
    for item_type in selected_types(args):
        items = select_items(manifest, item_type, args, "extracted")
        log.info("extracción de %d ítems de tipo %s", len(items), item_type)
        stats = E.extract_items(client, manifest, items, images=not args.no_images, popups=not args.no_popups)
        log.info("extracción %s: %s", item_type, stats)


def run_context(client: OppClient, manifest: Manifest, args: argparse.Namespace) -> None:
    """Biography + places always (year-filtered); labels, collections and references only in
    a full run or when asked for with --parts, because they cost ~2,000 requests."""
    pilot = bool(args.limit or args.years)
    parts = args.parts.split(",") if args.parts else (["biography", "places"] if pilot else CONTEXT_PARTS)
    years = parse_years(args.years, config.BIOGRAPHY_YEARS)
    if "biography" in parts:
        C.crawl_biography(client, manifest, years)
    if "places" in parts:
        C.crawl_places(client, manifest)
    if "labels" in parts:
        C.crawl_labels(client, manifest, ["periods", "themes"])
    if "collections" in parts:
        C.crawl_collections(client, manifest)
    if "references" in parts:
        C.crawl_references(client, manifest)
    C.build_chronology(C.read_json("biography.json", {}), C.read_json("places.json", []))
    log.info("contexto listo (partes: %s)", ", ".join(parts))


def run_transform(manifest: Manifest, args: argparse.Namespace) -> None:
    for item_type in selected_types(args):
        items = select_items(manifest, item_type, args, "transformed")
        items = [i for i in items if i["status"] in ("extracted", "transformed", "failed")]
        stats = L.transform_items(manifest, items)
        log.info("transformación %s: %s", item_type, stats)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    setup_logging()
    phases = PHASES if args.phase == "all" else [args.phase]
    needs_client = any(p in phases for p in ("discover", "extract", "context"))
    started = time.monotonic()
    client = None
    try:
        with Manifest() as manifest:
            if needs_client:
                client = OppClient(rate_limit_seconds=args.rate)
                client.ensure_logged_in()
            for phase in phases:
                log.info("--- fase %s ---", phase)
                if phase == "discover":
                    run_discover(client, manifest, args)
                elif phase == "extract":
                    run_extract(client, manifest, args)
                elif phase == "context":
                    run_context(client, manifest, args)
                elif phase == "transform":
                    run_transform(manifest, args)
                elif phase == "load":
                    print(L.format_summary(L.load_index(manifest)))
    except BlockedError as exc:
        log.error("DETENIDO: %s", exc)
        return 2
    finally:
        minutes = (time.monotonic() - started) / 60
        log.info("fin: %d requests en %.1f min", client.request_count if client else 0, minutes)
    return 0


if __name__ == "__main__":
    sys.exit(main())
