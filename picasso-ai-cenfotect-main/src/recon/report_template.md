# Reporte de metadata — Online Picasso Project (OPP)

**Proyecto:** análisis computacional de la obra de Picasso (Universidad CENFOTEC, curso de IA)
**Fuente:** https://picasso.shsu.edu/ — Prof. Dr. Enrique Mallen (acceso con credenciales académicas)
**Fecha del reconocimiento:** {fecha} · **Páginas e imágenes descargadas:** {requests} (a {rate} req/s, en dos corridas de ~10 min)
**Uso:** estrictamente académico y no comercial. Los datos (`data/`) y las credenciales (`.env`) no se suben a ningún repositorio.

---

## 1. Resumen ejecutivo

- El OPP es un **catálogo razonado digital** con **{total_obras} obras** (1881–1973) más cinco secciones de contexto: biografía (16.759 entradas, 1.337 comentarios), escritos (poemas y obras de teatro, 1935–1959), archivo de prensa (23.305 artículos, 1930–hoy), colecciones (5.556 museos/coleccionistas) y referencias bibliográficas (9.054). Los totales oficiales aparecen en la portada al iniciar sesión.
- Es un sitio **PHP clásico sin dependencia de JavaScript**: el login es un formulario POST y todo el contenido es HTML servido por `index.php?view=...`. Se usa `requests.Session` + BeautifulSoup; **no hace falta Playwright**.
- **Cada obra trae lugar de creación, fecha (con precisión variable), técnica, dimensiones, colección y concordancias** con los catálogos razonados clásicos (Zervos, Daix-Rosselet, Palau i Fabre…), y pop-ups con procedencia, exposiciones, literatura, notas de museo y comentarios académicos con referencias cruzadas a otras obras.
- **Sí se puede saber dónde vivía Picasso** en cada fecha: (1) cada obra tiene un campo *Location* (lugar de creación), (2) la biografía narra mudanzas y viajes por fecha y enlaza fichas de residencias/estudios (árbol de *Places*), y (3) cada entrada biográfica enlaza explícitamente las obras hechas en su rango de fechas (`artworksDated`).
- El sitio tiene **etiquetas de estilo propias**: {n_periodos} *Periods* (p.ej. Blue Period, Rose Period, Analytic Cubism…) y {n_temas} *Themes* (p.ej. Animal: Bull), consultables como búsquedas que devuelven listas de obras. Son etiquetas listas para clasificación supervisada de estilo.
- Imágenes: JPEG a tamaño completo de ~{avg_full_kb} KB de media (1.100–4.000 px en el lado largo), más miniaturas de 300 px y 100 px.
- **Restricción crítica de los Términos:** descargar imágenes sin autorización escrita del OPP implica la cancelación permanente del acceso. El usuario confirmó que existe autorización escrita del Prof. Mallen; el pipeline lo documenta y permite `--no-images`.
- Descarga completa estimada a 1 req/s (§10): **{horas_n1}** para metadata base + imágenes + contexto (Nivel 1) y **{horas_n2}** si se añaden todos los pop-ups de detalle (Nivel 2); ambas reanudables.

## 2. Método

1. Inspección pública (sin login) de `robots.txt` (no existe → sin restricciones declaradas), portada, menús y Términos.
2. Login con `requests.Session` (POST a `frontlogin.php`; el servidor responde con la cookie `cookFRONTIT`). Hallazgo: el POST redirige a `http://` y seguir esa redirección pierde la cookie *Secure*, así que el cliente no sigue el redirect. El login es rechazado ocasionalmente sin motivo visible; el cliente reintenta y persiste las cookies en `data/.cookies.json` para no re-autenticarse en cada ejecución.
3. Muestra: los 93 catálogos anuales completos (`ArtworkLarge`), {n_sample_artworks} obras con sus 6 pop-ups, {n_bio_entries} entradas de biografía de {bio_years} con comentarios, fichas de lugares/personas y vínculos a obras, {n_escritos} escritos, {n_articulos} artículos de prensa, {n_colecciones} colecciones, {n_referencias} referencias y 5 búsquedas por periodo/tema.
4. Todo el HTML crudo quedó en `data/raw/` (reutilizable por el ETL) y las muestras parseadas en `data/recon/*.json`.

## 3. Estructura del sitio

Todo cuelga de `https://picasso.shsu.edu/index.php?view=<Vista>&<parámetros>`. Las ventanas emergentes son cascarones con un `<iframe>` que carga la vista interna real; el ETL pide directamente la vista interna.

| Sección | Índice | Listado | Detalle (vista interna) | Identificador |
|---|---|---|---|---|
| Artworks | `MenuArtworksYear` (1881–1973) | `ArtworkLarge&year=Y&category=C` (catálogo completo del año, sin paginar); `ArtworkSummary`/`ArtworkDisplay&year=Y&category=C&page=N` (30/página) | `ArtworkDetails`, `former` (procedencia), `exhibitedPrint`, `bibliography`, `note`, `commentary`, `zoom&alpha=oppYY-NNN` (imagen) | `OPP.YY:NNN` (`OPP.07:005` = obra 5 de 1907) |
| Biography | `MenuBiographyYear` | `BioIndex&year=Y&page=N` (20 entradas/página) | `biographycommentary&id=`, `artworksDated&startYear…endDay`, `photos&year&id`, `BioResource&id=<lugar|persona>`, `bioTree` | id numérico de entrada; id textual de recurso (`bateaulavoir`, `matisse,henri`) |
| Writings | `MenuWritingsYear` | `Writings&year=Y&page=N` | `WritingsInfo&mid=M&year=Y` (texto; pestaña *Translation* en algunos) | `mid` |
| Archives | `MenuArchivesYear` (1930–hoy) | `Archives&year=Y&page=N` | `ArchiveArticle&year=Y&id=I` | `id` |
| Collections | `MenuCollectionsLetter` | `Collections&letter=L&page=N` → búsqueda `ListArtworkSearchS&Keyword=<nombre>&SearchIn=Collection` | — | nombre |
| References | `MenuReferencesLetter` | `Reference&letter=L&page=N` (30/página) | — | código OPP de la referencia (`[JR.96]`, `[WO.92*]` = catálogo de exposición) |
| Overview | `GuideList` (Periods), `GuideListThemes` (Themes), `GuideMaster` (Artists: 234 artistas relacionados) | `GuideSearchS&StyleSearchN=<Period>` / `ThemeSearchN=<Theme>` (30/página, formato Summary) | — | nombre del periodo/tema |

**Categorías de obra** (parámetro `category`): painting, collage, photograph, sculpture, ceramic, drawing, watercolor, gouache, pastel, engraving, lithograph, other. El catálogo anual se puede pedir por categoría y la suma de categorías coincide con el total del año (ver §4), así que la categoría se obtiene sin heurísticas.

**Cómo se enlaza todo:**
- Obra → año (en el ID), lugar de creación, colección (→ sección Collections), códigos de literatura/exposiciones (→ sección References), obras relacionadas (IDs OPP citados en *Commentary* y en las notas).
- Entrada biográfica → rango de fechas exacto → obras de ese rango (`artworksDated`), fotos/documentos, comentario, fichas de lugares y personas (`BioResource`), escritos (`BioWritings`).
- Periodo/tema → lista de obras (etiquetas de estilo y de iconografía).

**Comportamientos del servidor a tener en cuenta:** (1) devuelve a veces una página de error MySQL ("Commands out of sync") o un catálogo anual vacío; el cliente lo detecta y reintenta; (2) el conteo "N Catalogued Items" de `ArtworkDisplay` no coincide con el catálogo anual (p.ej. 240 vs 844 en 1907), por lo que el ETL usa `ArtworkLarge` como fuente de verdad; (3) no hay API ni exportación: todo es HTML.

## 4. Tipos de ítems y cantidades

| Tipo | Cantidad | Fuente del número |
|---|---|---|
| Obras (todas las categorías) | **{total_obras}** | suma de los 93 catálogos anuales (portada: 41.932) |
| Notas de obra | 24.623 | portada |
| Comentarios de obra | 9.017 | portada |
| Entradas biográficas | 16.759 | portada |
| Comentarios biográficos | 1.337 | portada |
| Lugares y personas (fichas) | {n_tree_places} lugares + {n_tree_people} personas | árbol `bioTree` |
| Escritos (poemas, teatro) | {escritos_total} ({escritos_rango}) | suma de los índices anuales |
| Artículos de prensa | 23.305 | portada |
| Colecciones | 5.556 | portada |
| Referencias bibliográficas | 9.054 | portada |
| Periodos / temas (etiquetas) | {n_periodos} / {n_temas} | formularios de *Overview* |

Obras por década:

{tabla_decadas}

Años con más obras:

{tabla_top_years}

Comprobación de categorías (catálogo anual por categoría vs. total del año):

{tabla_categorias}

## 5. Campos por tipo de ítem

### 5.1 Obras — campos del listado (presentes en el catálogo anual, {total_obras} obras)

{tabla_campos_listado}

Precisión de la fecha (campo normalizado por el parser):

{precision_fechas}

El {pct_inciertas} de las fechas lleva corchetes (fecha atribuida/incierta según el editor). La fecha original se conserva siempre junto a la normalizada.

Lugares de creación más frecuentes ({n_lugares} lugares distintos):

{tabla_lugares}

Los corchetes en el lugar («[Cannes]») marcan atribución incierta; el ETL guarda el valor original y una versión normalizada sin corchetes.

Técnicas más frecuentes:

{tabla_medios}

### 5.2 Obras — pop-ups de detalle (muestra de {n_sample_artworks} obras, los 6 pop-ups pedidos a todas)

{tabla_campos_detalle}

La cobertura coincide con los botones que muestra el listado *Summary*: cuando el botón no aparece, la vista interna viene vacía. El ETL sólo pedirá los pop-ups anunciados por el listado.

Ejemplo real — `{ejemplo_id}`, *{ejemplo_titulo}*:

Procedencia:

{tabla_procedencia}

Exposición: `{ejemplo_exposicion}`

Nota de museo: `{ejemplo_nota}`

Comentario: «{ejemplo_comentario}» → obras relacionadas: {ejemplo_comentario_ids}

### 5.3 Biografía ({n_bio_entries} entradas de {bio_years})

{tabla_campos_bio}

Enlaces disponibles por entrada:

{tabla_links_bio}

Ejemplo real ({ejemplo_bio_year}, «{ejemplo_bio_fecha}»): «{ejemplo_bio_texto}»

Ejemplo de vínculo entrada → obras: rango {ejemplo_dated_rango} → {ejemplo_dated_n} obras ({ejemplo_dated_ids}…).

Árbol de lugares (ejemplos): {ejemplo_tree}.

Ficha de lugar — *{ejemplo_lugar_nombre}* ({ejemplo_lugar_fotos} fotos con pie): «{ejemplo_lugar_intro}»

### 5.4 Escritos ({n_escritos} textos)

{tabla_escritos_idx}

{tabla_campos_escritos}

### 5.5 Archivo de prensa ({n_articulos} artículos)

El archivo de prensa se concentra en las décadas recientes (artículos por año, muestra):

{tabla_archivos_decadas}

Años muestreados en detalle:

{tabla_archivos_idx}

{tabla_campos_archivos}

### 5.6 Colecciones ({n_colecciones} filas)

{tabla_colecciones_idx}

{tabla_campos_colecciones}

### 5.7 Referencias ({n_referencias} filas)

{tabla_referencias_idx}

{tabla_campos_referencias}

### 5.8 Periodos y temas (etiquetas de estilo)

Periodos definidos por el OPP: {lista_periodos}.

{tabla_periodos}

## 6. Respuestas a las preguntas del profesor

### a) ¿Qué datos adicionales tiene cada obra?

Además de título, lugar, fecha, técnica, dimensiones y colección, cada obra puede tener:
- **Procedencia** (`former`): cadena ordenada de propietarios con ciudad, fecha de venta y precio (subastas).
- **Exposiciones** (`exhibitedPrint`): título de la exposición, sedes y fechas, catálogo (autores, editorial, año, nº de catálogo).
- **Literatura** (`bibliography`): bibliografía completa con códigos OPP que enlazan con la sección References.
- **Notas** (`note`): fichas de museos y catálogos (descripción oficial, inscripciones, firmas, medidas alternativas, procedencia y bibliografía según cada fuente).
- **Comentarios** (`commentary`): observaciones del editor y de la literatura (dataciones alternativas, medidas, interpretación iconográfica) con **referencias cruzadas a otras obras** (IDs OPP), lo que permite construir un grafo de obras relacionadas (estudios, versiones, reversos).
- **Concordancias** con catálogos razonados (Zervos `Z.`, Daix-Rosselet `DR`, Palau `PP`, Musée Picasso `MPP`, etc.), útiles para cruzar con otros datasets.
- **Artistas relacionados** (`ArtworkMaster`/`GuideMaster`): obras de otros artistas (234) con las que el OPP relaciona la obra (fuentes, influencias).
- Cobertura en la muestra: ver §5.2.

### b) ¿Se puede saber dónde vivía Picasso en el año de cada obra?

Sí, por tres vías complementarias, de más a menos directa:
1. **Campo *Location* de la obra** (lugar de creación, cobertura ≈ 100 % en el catálogo): «Paris», «Barcelona», «Mougins», «Cannes»… Para el análisis por periodos es el dato más fiable porque está al nivel de la obra y con la misma fecha.
2. **Biografía por fecha** (`BioIndex`): entradas con descriptor de fecha («Early-March», «June 15»…) cuyo texto narra residencias, viajes y mudanzas, y que enlazan **fichas de lugar** (`BioResource`: Bateau-Lavoir, 11 boulevard de Clichy, La Californie, Mougins…) organizadas en un árbol *Places › Europe › France › Paris › 18 Arrondissement › 13, Rue Ravignan › Le Bateau-Lavoir*. El ETL construye `chronology.json` (fecha → lugar(es) de residencia + eventos) a partir de estas entradas: cada vez que una entrada enlaza un lugar del árbol, se registra como residencia/estancia vigente desde esa fecha.
3. **Vínculo explícito entrada → obras**: cada entrada biográfica con obras enlaza `artworksDated&startYear…endDay`, es decir, el propio OPP asigna a cada evento biográfico las obras de ese rango. Así cada `metadata.json` puede llevar `context.events` (las entradas cuyo rango contiene la fecha de la obra) y `context.residence` (el lugar vigente según la cronología).

Limitación: la normalización de fechas tiene precisión variable (ver §5.1); para obras con sólo año, el contexto se asigna a nivel de año (lista de residencias de ese año).

### c) ¿Hay contexto histórico asociado (eventos, personas, relaciones)?

Sí:
- **Eventos**: 16.759 entradas biográficas con texto y citas, 1.337 comentarios ampliados, documentos/fotos fechados.
- **Personas**: fichas `BioResource` de personas (Matisse, Kahnweiler, Apollinaire, Breton…) con fotos y texto, enlazadas desde las entradas donde aparecen → `people.json` con la lista de entradas (y por tanto fechas y obras) en las que interviene cada persona.
- **Contexto histórico externo**: la sección Archives contiene prensa de época (p.ej. *The Times*, «The Tragedy of Guernica», 28/04/1937) con texto completo, fecha, medio e idioma.
- **Relaciones obra–obra** (referencias cruzadas en comentarios), **obra–artista** (234 artistas relacionados) y **obra–literatura/exposición** (códigos de referencia).

## 7. Calidad de las imágenes y limitaciones

Muestra de 5 obras en los tres tamaños que sirve el sitio (`artworks19580830/<año>/oppYY-NNN` tamaño completo sin extensión; `graphics/<año>/ythumbs/y…jpg` 300 px; `graphics/<año>/xthumbs/x…jpg` 100 px):

{tabla_imagenes}

- Formato JPEG RGB; el tamaño completo varía entre ~1.100 y ~4.000 px en el lado largo (media ≈ {avg_full_kb} KB por imagen → ≈ {gb_imagenes} GB para las {total_obras} obras).
- Algunas obras tienen imágenes alternativas (`AlternateCompare`: reversos, reflectografías, estados); el ETL guarda la principal y registra las alternativas.
- Limitaciones: (1) no hay API, sólo HTML; (2) fechas con precisión heterogénea y corchetes de incertidumbre; (3) títulos en varios idiomas; (4) el servidor devuelve errores transitorios bajo carga; (5) **licencia**: uso académico, sin redistribución de texto ni imágenes, y descarga de imágenes sólo con autorización escrita (confirmada).

## 8. Datasets públicos de otros pintores

{datasets_publicos}

## 9. Esquema de datos recomendado

```
data/picasso/
  artworks/<categoría>/<OPP.YY_NNN>/metadata.json + image.jpg (+ alt_*.jpg)
  writings/<mid>/metadata.json
  archives/<id>/metadata.json
  context/chronology.json   # [{date_start, date_end, precision, residence: [place_id], events: [entry_id]}]
          biography.json    # entradas completas con enlaces
          places.json       # árbol de lugares + fichas
          people.json       # fichas de personas + entradas donde aparecen
          periods.json      # periodo/tema -> [OPP ids]
          collections.json, references.json
index/catalog.csv, index/manifest.sqlite
```

`metadata.json` de obra (campos clave):

```json
{
  "id": "OPP.07:005", "category": "gouache", "title": "Portrait de Max Jacob",
  "place": "Paris", "date_text": "Early/1907",
  "date": {"year": 1907, "month_start": null, "month_end": null, "day": null, "precision": "year", "qualifiers": ["early"], "uncertain": false},
  "medium": "Gouache on paper mounted on cardboard", "dimensions": "62,7 x 48 cm",
  "collection": "Museum Ludwig, Köln", "credit_line": "(Inv ML/Z 2001/044). Schenkung 2001",
  "catalogs": ["DR:48", "FM:36", "P.I:1412", "PP.07:620", "Z.IIa:9"], "literature": [...], "exhibitions": [...],
  "provenance": [{"order": 1, "owner": "Raoul Pellequer", "place": "Paris", "date": null, "price": null}],
  "notes": [...], "commentary": [{"text": "...", "related_ids": ["OPP.07:311"]}],
  "periods": ["Iberian Period"], "themes": [...],
  "image": {"file": "image.jpg", "width": 1562, "height": 2048, "source": "https://picasso.shsu.edu/artworks19580830/1907/opp07-005"},
  "source_url": "https://picasso.shsu.edu/index.php?view=ArtworkInfo&OPPID=OPP.07:005",
  "extracted_at": "2026-10-10T12:00:00Z",
  "context": {"residence": ["Le Bateau-Lavoir, 13 Rue Ravignan, Paris"], "events": [{"entry_id": 364, "date_desc": "Early-Year", "text": "..."}]}
}
```

## 10. Estimación de la descarga completa

{tabla_estimacion}

Lectura: el **Nivel 1** (toda la metadata base de las 41.932 obras con imagen, más biografía, escritos, referencias, colecciones y etiquetas de periodo/tema) cuesta **{horas_n1}** de reloj a {rate} req/s. Los pop-ups de detalle son el bloque caro: llevan el total a **{horas_n2}** (Nivel 2, ≈ 2 días dejando el proceso corriendo; es reanudable). El pop-up *Details* no se pide: repite los campos del listado. La prensa (Nivel 3) se deja opcional. Un piloto de 100 obras con todo (Nivel 2 + imágenes) toma unos 10 minutos.

Recomendación: ejecutar primero el Nivel 1 completo (metadata + imágenes + contexto, suficiente para embeddings, clustering y evolución por periodos) y lanzar el Nivel 2 después, por rangos de años, según el tiempo disponible.

## 11. Decisiones para la Fase 2

1. Descubrimiento por `ArtworkLarge` año × categoría (1.209 requests) → manifest con metadata base ya completa.
2. Pop-ups: leer los listados *Summary* (1.398 páginas) y pedir sólo los pop-ups que cada obra anuncia (≈2,8 por obra en vez de 5); omitir *Details* porque repite el listado.
3. Imágenes a tamaño completo (autorización escrita confirmada); `--no-images` disponible.
4. Contexto: biografía completa (93 años), árbol de lugares y fichas, periodos y temas; prensa opcional.
5. Directorios por categoría del sitio (12), en vez de paintings/drawings/sculptures/manuscripts: los "manuscritos" son la sección Writings.
