"""Build the Markdown tables of docs/reporte_metadata.md from data/recon/*.json.

The narrative lives in src/recon/report_template.md; this script only fills the
`{placeholders}` with tables computed from the sample, so the report is reproducible.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.etl import config

OUT = config.RECON_DIR
TEMPLATE = Path(__file__).with_name("report_template.md")
REPORT = config.PROJECT_ROOT / "docs" / "reporte_metadata.md"


def load(name: str) -> Any:
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def table(headers: list[str], rows: list[list[Any]]) -> str:
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    for row in rows:
        out.append("| " + " | ".join(str(c).replace("|", "\\|").replace("\n", " ") for c in row) + " |")
    return "\n".join(out)


def truncate(text: Any, n: int = 90) -> str:
    text = str(text) if text is not None else ""
    return text if len(text) <= n else text[: n - 1] + "…"


def example(items: list[dict], field: str) -> str:
    for it in items:
        if it.get(field):
            return truncate(it[field])
    return "—"


def field_table(items: list[dict], spec: list[tuple[str, str]], cov: dict[str, float]) -> str:
    """spec = [(field, description)] -> table with description, example and coverage."""
    rows = [[f, d, f"`{example(items, f)}`", f"{cov.get(f, 0)}%"] for f, d in spec]
    return table(["Campo", "Descripción", "Ejemplo real", "Cobertura"], rows)


def pct(n: float) -> str:
    return f"{n:.1f}%"


def main() -> None:
    s = load("recon_summary.json")
    artworks = load("sample_artworks.json")
    bio = load("sample_biography.json")
    wr = load("sample_writings.json")
    ar = load("sample_archives.json")
    refs = [r for block in load("sample_references.json") for r in block["rows"]]
    colls = [r for block in load("sample_collections.json") for r in block["rows"]]
    guide = load("sample_guide.json")
    extra = load("extra_counts.json") if (OUT / "extra_counts.json").exists() else {}
    a = s["artworks"]

    per_year = a["per_year"]
    decades: dict[str, int] = {}
    for year, n in per_year.items():
        decades[f"{year[:3]}0s"] = decades.get(f"{year[:3]}0s", 0) + n
    top_years = sorted(per_year.items(), key=lambda kv: -kv[1])[:10]

    details = [x["details"] for x in artworks if x.get("details")]
    listing_spec = [
        ("id", "Número de catálogo OPP (`OPP.AA:NNN`, AA = año)"), ("title", "Título (francés/español/inglés)"),
        ("place", "Lugar de creación"), ("date_text", "Fecha tal como la publica el sitio"),
        ("medium", "Técnica / soporte"), ("dimensions", "Dimensiones (cm)"),
        ("collection", "Colección o museo actual"), ("credit_line", "Nº de inventario / forma de adquisición"),
        ("references", "Concordancias con catálogos razonados (Zervos, Daix, Palau…) y literatura"),
        ("thumbnail", "Ruta de la miniatura (y de ahí la imagen completa)"),
    ]
    detail_spec = [
        ("has_details", "Pop-up *Details*: mismos campos + Catalogs/Books/Exhibited separados"),
        ("has_provenance", "Pop-up *Provenance*: cadena de propietarios (lugar, fecha, precio)"),
        ("has_exhibitions", "Pop-up *Exhibited*: exposiciones con sede, fechas y catálogo"),
        ("has_literature", "Pop-up *Literature*: bibliografía completa de la obra"),
        ("has_note", "Pop-up *Notes*: fichas de museos/catálogos (descripción, inscripciones, procedencia)"),
        ("has_commentary", "Pop-up *Commentary*: comentarios académicos con referencias cruzadas a otras obras"),
    ]
    detail_items = [{k: (v if not isinstance(v, list) else (v or None)) for k, v in x.items()} for x in artworks]
    bio_spec = [("date_desc", "Descriptor de fecha (día, mes, 'Early-March', 'Summer'…)"),
                ("text", "Narrativa biográfica del periodo (con citas a la literatura)"),
                ("opp_ids", "Obras citadas dentro del texto"), ("images", "Fotografías/documentos insertados")]
    bio_items = [{**e, "opp_ids": e["opp_ids"] or None, "images": e.get("images") or None,
                  "links": ", ".join(sorted(e["links"]))} for e in bio["entries"]]
    link_cov = s["biography"]["link_coverage"]
    link_rows = [[k, {"DatedArtworksSummary": "Obras fechadas dentro del rango de la entrada (vínculo evento → obras)",
                     "BioCommentary": "Comentario/cita ampliada del editor", "DatedPhotos": "Documentos y fotos del periodo",
                     "BioResource": "Fichas de lugares (residencias, estudios) y personas", "BioWritings": "Escritos de Picasso de esas fechas",
                     "ArtworkInfo": "Obras enlazadas directamente", "ArtworkDisplay": "Listado de obras del trimestre",
                     "ArtworkSummary": "Resumen de obras del trimestre", "ArtworkConcordance": "Concordancia de catálogos",
                     "BioIndex": "Navegación entre años", "multiple": "Comparación múltiple de obras",
                     "MasterSearch": "Obras de otros artistas (maestros) relacionadas", "MasterArtworkSearch": "Obra concreta de otro artista relacionada"}.get(k, ""), pct(v)] for k, v in sorted(link_cov.items(), key=lambda kv: -kv[1])]
    wr_spec = [("mid", "Identificador del escrito"), ("title", "Título / primer verso"),
               ("date_text", "Fecha y parte"), ("text", "Texto completo (francés o español)")]
    ar_spec = [("id", "Identificador del artículo"), ("title", "Titular"), ("language", "Idioma (bandera)"),
               ("publisher", "Medio"), ("date_text", "Fecha de publicación"), ("dateline", "Lugar/fecha de redacción"),
               ("text", "Cuerpo completo del artículo")]
    ref_spec = [("author", "Autor(es)"), ("date", "Año"), ("titles", "Título de libro/catálogo"), ("title", "Título de artículo"),
                ("publisher", "Ciudad: editorial"), ("journal", "Revista"), ("issue", "Número/fecha"),
                ("codes", "Código OPP de la referencia (p.ej. `[WO.92*]`)")]
    ref_items = [{**r, "codes": r["codes"] or None} for r in refs]
    ref_cov = s["references"]["coverage"]
    coll_spec = [("name", "Nombre del museo/colección"), ("count", "Nº de obras en el OPP"), ("search", "Búsqueda que lista sus obras")]
    coll_cov = {"name": 100.0, "count": round(100 * sum(1 for c in colls if c["count"]) / max(1, len(colls)), 1), "search": 100.0}

    full = [x for x in artworks if all(x.get(f"has_{k}") for k in ("provenance", "exhibitions", "note", "commentary"))]
    sample_detail = (full or [x for x in artworks if x.get("has_provenance") and x.get("has_commentary")])[0]
    prov_rows = [[p["order"], p["owner"], p["place"] or "", p["date"] or "", p["price"] or ""] for p in sample_detail["provenance"][:5]]
    comm = sample_detail["commentary"][0]
    dated = bio["dated_artworks"][0] if bio["dated_artworks"] else {"range": {}, "opp_ids": []}
    places = [r for r in bio["tree"] if "People" not in r["path"]]
    place_examples = [p for p in bio["resources"] if p.get("introduction")]
    period_rows = [[g["name"], g["kind"], g["count"], ", ".join(g["sample_ids"][:4])] for g in guide["searches"]]
    img_rows = [[i["kind"], i["file"], i["format"], f'{i["width"]}×{i["height"]}', f'{i["bytes"] / 1024:.0f} KB'] for i in s["images"]]
    full = [i for i in s["images"] if i["kind"] == "full"]
    avg_full_kb = sum(i["bytes"] for i in full) / len(full) / 1024 if full else 0

    total = a["total"]
    rate = config.RATE_LIMIT_SECONDS
    cov = a["detail_coverage"]
    popups_optimized = int(total * sum(v for k, v in cov.items() if k != "has_details") / 100)
    summary_pages = -(-total // 30)
    est = {
        "catalogue_pages": len(config.ARTWORK_YEARS) * (1 + len(config.CATEGORIES)),
        "summary_pages": summary_pages,
        "popups_optimized": popups_optimized,
        "popups_all": total * 5,
        "images": total,
        "biography": 93 * 5 + 1337 + 143,
        "writings": len(config.WRITINGS_YEARS) + extra.get("writings_total", 350),
        "references": -(-9054 // 30) + 26,
        "collections": 26 * 10,
        "guide": (s["guide"]["periods"] + s["guide"]["themes"]) + 2 * total // 30,
        "archives": 97 + 23305,
    }
    tier1 = est["catalogue_pages"] + est["images"]
    ctx = est["biography"] + est["writings"] + est["references"] + est["collections"] + est["guide"]
    tier2 = est["summary_pages"] + est["popups_optimized"]
    hours = lambda n: f"{n * rate / 3600:.1f} h"
    est_rows = [
        ["Catálogo anual × categoría (descubrimiento + metadata base de las 41.932 obras)", est["catalogue_pages"], hours(est["catalogue_pages"])],
        ["Imágenes a tamaño completo (1 por obra)", est["images"], hours(est["images"])],
        ["Contexto: biografía (93 años, comentarios, lugares/personas), escritos, referencias, colecciones, periodos/temas", ctx, hours(ctx)],
        ["**Nivel 1 = catálogo + imágenes + contexto**", tier1 + ctx, f"**{hours(tier1 + ctx)}**"],
        ["Listados *Summary* (30/página) para saber qué pop-ups existen", est["summary_pages"], hours(est["summary_pages"])],
        ["Pop-ups de detalle sólo cuando existen (procedencia, exposiciones, literatura, notas, comentario; ≈2,8 por obra)", est["popups_optimized"], hours(est["popups_optimized"])],
        ["**Nivel 2 = Nivel 1 + pop-ups**", tier1 + ctx + tier2, f"**{hours(tier1 + ctx + tier2)}**"],
        ["Pop-ups: los 5 para todas las obras (peor caso, sin leer los listados)", est["popups_all"], hours(est["popups_all"])],
        ["Nivel 3 (opcional): archivo de prensa completo (23.305 artículos)", est["archives"], hours(est["archives"])],
    ]
    horas_n1, horas_n2 = hours(tier1 + ctx), hours(tier1 + ctx + tier2)

    values = {
        "fecha": __import__("datetime").date.today().isoformat(),
        "requests": sum(1 for _ in config.RAW_DIR.rglob("*.html")) + sum(1 for _ in (OUT / "smoke").rglob("*")),
        "elapsed": s["elapsed_minutes"],
        "total_obras": f"{total:,}".replace(",", "."),
        "tabla_decadas": table(["Década", "Obras catalogadas"], [[d, f"{n:,}".replace(",", ".")] for d, n in sorted(decades.items())]),
        "tabla_top_years": table(["Año", "Obras"], [[y, n] for y, n in top_years]),
        "tabla_categorias": table(["Categoría"] + [str(y) for y in a["per_category"]],
                                  [[cat] + [a["per_category"][y].get(cat, 0) for y in a["per_category"]] for cat in config.CATEGORIES]
                                  + [["**suma categorías**"] + [sum(a["per_category"][y].values()) for y in a["per_category"]],
                                     ["**catálogo del año**"] + [per_year[str(y)] for y in a["per_category"]]]),
        "tabla_campos_listado": field_table(artworks, listing_spec, a["listing_coverage"]),
        "tabla_campos_detalle": field_table(detail_items, detail_spec, a["detail_coverage"]),
        "n_sample_artworks": a["sample_size"],
        "precision_fechas": table(["Precisión", "Obras", "%"], [[k, v, pct(100 * v / total)] for k, v in sorted(a["date_precision"].items(), key=lambda kv: -kv[1])]),
        "pct_inciertas": pct(a["date_uncertain_pct"]),
        "tabla_lugares": table(["Lugar de creación", "Obras"], [[p, n] for p, n in a["top_places"][:15]]),
        "n_lugares": a["distinct_places"],
        "escritos_total": extra.get("writings_total", "≈ 350"), "escritos_rango": extra.get("writings_range", "1935–1959"),
        "tabla_archivos_decadas": table(["Año", "Artículos"], [[y, n] for y, n in extra.get("archives_years", {}).items()]),
        "tabla_medios": table(["Técnica", "Obras"], [[m, n] for m, n in a["top_media"][:10]]),
        "ejemplo_id": sample_detail["id"], "ejemplo_titulo": sample_detail["title"],
        "tabla_procedencia": table(["#", "Propietario", "Lugar", "Fecha", "Precio"], prov_rows),
        "ejemplo_comentario": truncate(comm["text"], 400), "ejemplo_comentario_ids": ", ".join(comm["related_ids"]) or "—",
        "ejemplo_exposicion": truncate(sample_detail["exhibitions"][0]["text"], 250) if sample_detail["exhibitions"] else "—",
        "ejemplo_nota": truncate(" / ".join(f'{n["label"]}: {n["text"]}' for n in sample_detail["note"][:3]), 300) if sample_detail["note"] else "—",
        "n_bio_entries": s["biography"]["entries_sampled"], "bio_years": ", ".join(str(y) for y in sorted({e["year"] for e in bio["entries"]})),
        "tabla_campos_bio": field_table(bio_items, bio_spec, s["biography"]["coverage"]),
        "tabla_links_bio": table(["Enlace", "Qué aporta", "% entradas"], link_rows),
        "ejemplo_bio_fecha": bio["entries"][0]["date_desc"], "ejemplo_bio_year": bio["entries"][0]["year"],
        "ejemplo_bio_texto": truncate(next(e["text"] for e in bio["entries"] if e["text"]), 350),
        "ejemplo_dated_rango": f'{dated["range"].get("startYear")}-{dated["range"].get("startMonth")}-{dated["range"].get("startDay")} → {dated["range"].get("endYear")}-{dated["range"].get("endMonth")}-{dated["range"].get("endDay")}',
        "ejemplo_dated_n": len(dated["opp_ids"]), "ejemplo_dated_ids": ", ".join(dated["opp_ids"][:6]),
        "n_tree_places": s["biography"]["tree_places"], "n_tree_people": s["biography"]["tree_people"],
        "ejemplo_tree": "; ".join(" › ".join(r["path"][1:] + [r["name"]]) for r in places[3:9]),
        "ejemplo_lugar_nombre": place_examples[0]["name"] if place_examples else "—",
        "ejemplo_lugar_intro": truncate(place_examples[0]["introduction"], 300) if place_examples else "—",
        "ejemplo_lugar_fotos": len(place_examples[0]["photos"]) if place_examples else 0,
        "tabla_escritos_idx": table(["Año", "Poemas catalogados", "Páginas"], [[i["year"], i["count"], i["pages"]] for i in wr["index"]]),
        "tabla_campos_escritos": field_table(wr["writings"], wr_spec, s["writings"]["coverage"]), "n_escritos": len(wr["writings"]),
        "tabla_archivos_idx": table(["Año", "Artículos", "Páginas"], [[i["year"], i["count"] if i["count"] is not None else len(i["rows"]), i["pages"]] for i in ar["index"]]),
        "tabla_campos_archivos": field_table(ar["articles"], ar_spec, s["archives"]["coverage"]), "n_articulos": len(ar["articles"]),
        "tabla_colecciones_idx": table(["Letra", "Colecciones"], [[c["letter"], c["count"] or c["rows"]] for c in s["collections"]]),
        "tabla_campos_colecciones": field_table(colls, coll_spec, coll_cov), "n_colecciones": len(colls),
        "tabla_referencias_idx": table(["Letra", "Referencias", "Páginas"], [[r["letter"], r["count"], r["pages"]] for r in s["references"]["index"]]),
        "tabla_campos_referencias": field_table(ref_items, ref_spec, ref_cov), "n_referencias": len(refs),
        "n_periodos": s["guide"]["periods"], "n_temas": s["guide"]["themes"],
        "lista_periodos": ", ".join(p["value"] for p in guide["periods"]),
        "tabla_periodos": table(["Etiqueta", "Tipo", "Obras", "Primeros IDs"], period_rows),
        "tabla_imagenes": table(["Tamaño", "Archivo", "Formato", "Píxeles", "Peso"], img_rows),
        "avg_full_kb": f"{avg_full_kb:.0f}", "gb_imagenes": f"{avg_full_kb * total / 1024 / 1024:.1f}",
        "rate": rate, "tabla_estimacion": table(["Bloque", "Requests", f"Tiempo a {rate:g} req/s"], est_rows),
        "horas_n1": horas_n1, "horas_n2": horas_n2,
        "datasets_publicos": (config.PROJECT_ROOT / "docs" / "datasets_publicos.md").read_text(encoding="utf-8")
        if (config.PROJECT_ROOT / "docs" / "datasets_publicos.md").exists() else "_(pendiente)_",
    }
    text = TEMPLATE.read_text(encoding="utf-8")
    for key, value in values.items():
        text = text.replace("{" + key + "}", str(value))
    REPORT.parent.mkdir(exist_ok=True)
    REPORT.write_text(text, encoding="utf-8")
    print(f"Reporte escrito en {REPORT} ({len(text):,} caracteres)")


if __name__ == "__main__":
    main()
