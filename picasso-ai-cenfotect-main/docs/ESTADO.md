# Estado del proyecto (punto de retoma)

Última actualización: 2026-10-09. Leer este archivo primero al retomar en una sesión nueva.

## Dónde estamos

1. **Fase 1 (reconocimiento)**: terminada y aprobada. Reporte en `docs/reporte_metadata.md`
   (tipos, campos, cobertura, respuestas a las preguntas del profesor, imágenes, datasets públicos,
   esquema y estimación de descarga). Comparación de datasets en `docs/datasets_publicos.md`.
2. **Fase 2 (ETL)**: implementada en `src/etl/` (ver README para el uso). Tests: `pytest` (31 tests
   de parsers con HTML real en `tests/fixtures/`).
3. **Piloto de 100 obras (año 1907)**: ejecutado el 2026-10-09; resultados en la sección siguiente.
4. **Pendiente de decisión del usuario**: lanzar la descarga completa. No lanzarla sin instrucción
   explícita.

## Resultado del piloto

Ver `data/index/summary.json` y `data/index/catalog.csv` (se regeneran con `--phase load`).

Piloto `--years 1907 --limit 100` (ejecutado 2026-10-09, 21:23–21:38):

| Métrica | Valor |
|---|---|
| Obras extraídas / transformadas / fallidas | 100 / 100 / 0 (las primeras 100 por OPP id de 1907) |
| Requests de extracción | 357 en 7,2 min (≈ 4,3 por obra: listados Summary + ≈2,3 pop-ups + imagen) |
| Contexto 1907 (biografía 34 entradas + 143 fichas de lugares/personas) | 146 requests, 2,7 min |
| Categorías | drawing 56, painting 28, gouache 8, pastel 4, watercolor 2, engraving 1, other 1 |
| Cobertura de pop-ups | literature 100 %, exhibitions 73 %, notes 68 %, provenance 55 %, commentary 52 % |
| Contexto | residence 98 % (Le Bateau-Lavoir), events 65 % (30 vínculos explícitos del OPP) |
| Imágenes | 100/100; lado largo mediana 1.920 px (399–11.227); peso medio 1,62 MB, mediana 0,61 MB; máx. 37 MB (Les demoiselles d'Avignon) |

Nota: el peso medio real (1,62 MB) es el doble del estimado en la Fase 1 (0,8 MB): la descarga completa
de imágenes rondaría 65–70 GB, no 31 GB. Conviene decidir si se descargan todas o sólo hasta cierto año/categoría.

Además de las 100 del piloto, una prueba de registro de fallos (`--categories other`) extrajo las 77 obras
de categoría `other` de 1907; quedan también transformadas. Verificado: repetir el comando no vuelve a
descargar nada (1 request de comprobación de sesión), y un ID inexistente queda como `failed` en el manifiesto
con el error 404. Etiquetas de periodo/tema: ver `data/picasso/context/periods.json` (descarga lanzada el
2026-10-09 con `--phase context --parts labels`; si quedó incompleta, el mismo comando la continúa).

## Cómo retomar

```bash
cd ~/Development/picasso && .venv/bin/python -m pytest -q          # sanity check
.venv/bin/python -m src.etl.run_pipeline --phase load                # resumen de lo que hay en disco
```

Descarga completa recomendada (Nivel 1 primero, luego pop-ups):

```bash
# Nivel 1: catálogo (1.116 requests) + imágenes (41.932) + contexto completo (~6.000) ≈ 14 h a 1 req/s
.venv/bin/python -m src.etl.run_pipeline --phase all --no-popups --resume
# Nivel 2: pop-ups de detalle (≈ 120.000 requests ≈ 33 h), por rangos de años si se prefiere
.venv/bin/python -m src.etl.run_pipeline --phase extract --resume --years 1881-1910
.venv/bin/python -m src.etl.run_pipeline --phase transform --resume && .venv/bin/python -m src.etl.run_pipeline --phase load
```

Ambos comandos se pueden interrumpir (Ctrl-C) y relanzar: el HTML crudo está en `data/raw/`, las
imágenes no se vuelven a pedir y el manifiesto (`data/index/manifest.sqlite`) sabe qué ítems faltan.
Si el pipeline termina con código 2, el sitio devolvió un bloqueo o CAPTCHA: no reintentar, avisar.

## Restricciones vigentes (acordadas con el usuario)

- Credenciales sólo en `.env`; nunca imprimirlas ni escribirlas en otro archivo. `.env` y `data/`
  están en `.gitignore`; los datos no se suben ni redistribuyen. Uso académico, no comercial.
- Máximo 1 request/segundo (`RATE_LIMIT_SECONDS`), User-Agent académico de CENFOTEC, backoff ante
  429/5xx. No evadir CAPTCHAs ni bloqueos: detenerse y avisar.
- Imágenes: los Términos del OPP exigen autorización escrita; el usuario confirmó que existe
  (Prof. Mallen). Existe `--no-images` por si hiciera falta.

## Decisiones técnicas tomadas

- `requests.Session` + BeautifulSoup (sitio PHP clásico, sin JavaScript necesario). Login POST a
  `frontlogin.php` sin seguir la redirección (perdería la cookie `cookFRONTIT`); cookies persistidas
  en `data/.cookies.json`.
- Descubrimiento por `ArtworkLarge&year&category` (12 categorías × 93 años), que trae toda la
  metadata base. Los listados `ArtworkSummary` (4 trimestres `quarter=1..4` × páginas de 30) sólo se
  leen para saber qué pop-ups anuncia cada obra; el pop-up *Details* no se pide porque repite el listado.
- El servidor devuelve a veces cascarones vacíos o un error MySQL bajo carga: catálogos y pop-ups
  vacíos se reintentan una vez; el indicador de pop-up del listado no garantiza contenido (p. ej.
  `commentary` anunciado pero vacío).
- Directorios por categoría del sitio (`painting`, `drawing`, `gouache`, …) en vez de
  paintings/drawings/sculptures/manuscripts; los "manuscritos" son la sección Writings
  (`--type writings`).
- Residencia por obra: heurística sobre la cronología (entrada con verbo de mudanza/estancia que
  enlaza un lugar a nivel de ciudad o más fino); siempre se conserva también `creation_place`.

## Ideas pendientes / mejoras posibles

- Afinar la heurística de residencia con una lista curada de mudanzas (pocas decenas) si el
  análisis lo necesita.
- Añadir `--type archives` sólo si la prensa se usa en el análisis (23.305 artículos ≈ 6,5 h).
- Descargar también las imágenes alternativas (`alt_*.jpg`) de las obras que las tienen (`ArtworkMaster`).
