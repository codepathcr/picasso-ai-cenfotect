# Picasso — análisis computacional de la obra (CENFOTEC, curso de IA)

Extracción académica del **Online Picasso Project** (https://picasso.shsu.edu/, Prof. Dr. Enrique Mallen).
Uso estrictamente académico y no comercial; los datos no se redistribuyen ni se suben a ningún repositorio
(`data/` y `.env` están en `.gitignore`).

## Estado

- **Fase 1 (reconocimiento)**: completada → `docs/reporte_metadata.md` y `docs/datasets_publicos.md`.
- **Fase 2 (pipeline ETL)**: implementada; piloto de 100 obras ejecutado. La descarga completa espera
  aprobación. El punto de retoma para una nueva sesión está en `docs/ESTADO.md`.

## Instalación

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env   # y rellenar PICASSO_USER / PICASSO_PASS (nunca se imprimen ni se escriben en otro archivo)
.venv/bin/python -m pytest -q   # tests de los parsers con HTML real guardado en tests/fixtures/
```

Variables opcionales en `.env`: `RATE_LIMIT_SECONDS` (por defecto `1.0`), `PICASSO_USER_AGENT`.

## Requisitos de uso del sitio

- Máximo 1 request por segundo (configurable), User-Agent que identifica el proyecto como académico de
  CENFOTEC, reintentos con backoff exponencial ante 429/5xx y errores de red. No se evade ningún mecanismo
  de protección: si aparece un CAPTCHA o una página de bloqueo el pipeline se detiene (`BlockedError`,
  código de salida 2) y hay que avisar.
- Los Términos del OPP exigen **autorización escrita para descargar imágenes**. Este proyecto cuenta con la
  autorización del Prof. Mallen; sin ella debe ejecutarse con `--no-images`.

## Pipeline ETL (Fase 2)

```bash
# Piloto: 100 obras de 1907 con pop-ups, imágenes y contexto biográfico de ese año
.venv/bin/python -m src.etl.run_pipeline --phase all --years 1907 --limit 100

# Descarga completa, Nivel 1 (catálogo + imágenes + contexto; ~14 h a 1 req/s), reanudable
.venv/bin/python -m src.etl.run_pipeline --phase all --no-popups --resume

# Nivel 2: añadir después los pop-ups de detalle (procedencia, exposiciones, literatura, notas, comentario)
.venv/bin/python -m src.etl.run_pipeline --phase extract --resume
.venv/bin/python -m src.etl.run_pipeline --phase transform && .venv/bin/python -m src.etl.run_pipeline --phase load

# Otros tipos de ítem y partes del contexto
.venv/bin/python -m src.etl.run_pipeline --phase all --type writings          # 615 poemas/obras de teatro
.venv/bin/python -m src.etl.run_pipeline --phase all --type archives --years 1937-1945   # prensa (opcional)
.venv/bin/python -m src.etl.run_pipeline --phase context --parts labels        # periodos y temas → periods.json
```

Fases (`--phase`): `discover` (listados → manifiesto), `extract` (pop-ups e imagen por ítem),
`context` (biografía, lugares/personas, periodos/temas, colecciones, referencias), `transform`
(HTML en caché → `metadata.json`), `load` (`catalog.csv`, `summary.json` y resumen en pantalla), `all`.

Opciones: `--type artworks|writings|archives|all`, `--limit N`, `--years 1907 1910-1912`,
`--categories painting drawing …`, `--resume` (salta lo terminado y reintenta lo fallido), `--no-images`,
`--no-popups`, `--parts biography,places,labels,collections,references`, `--rate` (segundos entre requests).

Todo es idempotente: el HTML crudo se cachea en `data/raw/` y las imágenes no se vuelven a pedir si ya
existen, así que repetir un comando no genera requests nuevos. El manifiesto (`data/index/manifest.sqlite`)
guarda el estado de cada ítem (`pending → extracted → transformed`, o `failed` con el error y el número de
intentos) y el progreso de los listados.

### Contexto por obra

Cada `metadata.json` de obra lleva una sección `context`:

- `creation_place`: el lugar de creación que el OPP asigna a la obra.
- `residence`: dónde vivía Picasso en la fecha de la obra según la cronología. Heurística: la entrada
  biográfica más reciente, anterior o igual a la fecha de inicio de la obra, que narra una mudanza o estancia
  (verbos como *moves, settles, rents, returns to, spends the summer*) y enlaza una ficha de lugar del árbol
  *Places* a nivel de ciudad o más fino (estudio, calle, villa). Se guarda con `since` y `entry_id` para poder
  revisarla.
- `events`: entradas biográficas vinculadas. Primero las que el OPP enlaza explícitamente a la obra
  (`explicit: true`: citan el OPP id o la incluyen en su rango `artworksDated`); después, las que se solapan
  con la fecha de la obra (sólo cuando ambas fechas tienen precisión mejor que el año; máximo 15).

Los contextos completos están en `data/picasso/context/`: `biography.json` (entradas por año con enlaces,
comentarios y obras vinculadas), `chronology.json` (eventos fechados con lugares resueltos), `places.json`,
`people.json`, `periods.json` (periodo/tema → OPP ids), `collections.json`, `references.json`.

## Estructura

```
src/etl/config.py        rutas, constantes del sitio, rate limit, credenciales (.env)
src/etl/session.py       cliente autenticado: login, rate limit, backoff, caché de HTML, detección de bloqueos
src/etl/transform.py     parsers HTML -> dict (puros, testeados) y normalización de fechas
src/etl/manifest.py      manifiesto SQLite (estado por ítem, progreso de listados)
src/etl/discover.py      fase discover: catálogos anuales por categoría, índices de escritos y prensa
src/etl/extract.py       fase extract: indicadores de pop-ups (Summary), pop-ups e imagen por obra
src/etl/context.py       fase context: biografía, lugares/personas, cronología, periodos/temas, colecciones, referencias
src/etl/load.py          fases transform (metadata.json) y load (catalog.csv, summary.json, resumen)
src/etl/run_pipeline.py  CLI
src/recon/               muestreo y generador del reporte de la Fase 1
tests/                   tests de parsers con fixtures HTML reales (sin credenciales ni imágenes)
docs/                    reporte de metadata, comparación de datasets, estado del proyecto (ESTADO.md)
data/                    (ignorado por git)
  raw/<tipo>/...                         HTML crudo cacheado
  picasso/artworks/<categoría>/<OPP.YY_NNN>/metadata.json + image.jpg
  picasso/writings/<mid>/metadata.json   picasso/archives/<id>/metadata.json
  picasso/context/*.json
  index/catalog.csv, index/manifest.sqlite, index/summary.json
  logs/pipeline.log
```
