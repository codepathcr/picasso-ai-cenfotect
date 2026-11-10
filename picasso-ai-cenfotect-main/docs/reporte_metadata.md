# Reporte de metadata — Online Picasso Project (OPP)

**Proyecto:** análisis computacional de la obra de Picasso (Universidad CENFOTEC, curso de IA)
**Fuente:** https://picasso.shsu.edu/ — Prof. Dr. Enrique Mallen (acceso con credenciales académicas)
**Fecha del reconocimiento:** 2026-10-09 · **Páginas e imágenes descargadas:** 579 (a 1.0 req/s, en dos corridas de ~10 min)
**Uso:** estrictamente académico y no comercial. Los datos (`data/`) y las credenciales (`.env`) no se suben a ningún repositorio.

---

## 1. Resumen ejecutivo

- El OPP es un **catálogo razonado digital** con **41.932 obras** (1881–1973) más cinco secciones de contexto: biografía (16.759 entradas, 1.337 comentarios), escritos (poemas y obras de teatro, 1935–1959), archivo de prensa (23.305 artículos, 1930–hoy), colecciones (5.556 museos/coleccionistas) y referencias bibliográficas (9.054). Los totales oficiales aparecen en la portada al iniciar sesión.
- Es un sitio **PHP clásico sin dependencia de JavaScript**: el login es un formulario POST y todo el contenido es HTML servido por `index.php?view=...`. Se usa `requests.Session` + BeautifulSoup; **no hace falta Playwright**.
- **Cada obra trae lugar de creación, fecha (con precisión variable), técnica, dimensiones, colección y concordancias** con los catálogos razonados clásicos (Zervos, Daix-Rosselet, Palau i Fabre…), y pop-ups con procedencia, exposiciones, literatura, notas de museo y comentarios académicos con referencias cruzadas a otras obras.
- **Sí se puede saber dónde vivía Picasso** en cada fecha: (1) cada obra tiene un campo *Location* (lugar de creación), (2) la biografía narra mudanzas y viajes por fecha y enlaza fichas de residencias/estudios (árbol de *Places*), y (3) cada entrada biográfica enlaza explícitamente las obras hechas en su rango de fechas (`artworksDated`).
- El sitio tiene **etiquetas de estilo propias**: 71 *Periods* (p.ej. Blue Period, Rose Period, Analytic Cubism…) y 109 *Themes* (p.ej. Animal: Bull), consultables como búsquedas que devuelven listas de obras. Son etiquetas listas para clasificación supervisada de estilo.
- Imágenes: JPEG a tamaño completo de ~787 KB de media (1.100–4.000 px en el lado largo), más miniaturas de 300 px y 100 px.
- **Restricción crítica de los Términos:** descargar imágenes sin autorización escrita del OPP implica la cancelación permanente del acceso. El usuario confirmó que existe autorización escrita del Prof. Mallen; el pipeline lo documenta y permite `--no-images`.
- Descarga completa estimada a 1 req/s (§10): **13.7 h** para metadata base + imágenes + contexto (Nivel 1) y **47.2 h** si se añaden todos los pop-ups de detalle (Nivel 2); ambas reanudables.

## 2. Método

1. Inspección pública (sin login) de `robots.txt` (no existe → sin restricciones declaradas), portada, menús y Términos.
2. Login con `requests.Session` (POST a `frontlogin.php`; el servidor responde con la cookie `cookFRONTIT`). Hallazgo: el POST redirige a `http://` y seguir esa redirección pierde la cookie *Secure*, así que el cliente no sigue el redirect. El login es rechazado ocasionalmente sin motivo visible; el cliente reintenta y persiste las cookies en `data/.cookies.json` para no re-autenticarse en cada ejecución.
3. Muestra: los 93 catálogos anuales completos (`ArtworkLarge`), 44 obras con sus 6 pop-ups, 79 entradas de biografía de 1900, 1907, 1937 con comentarios, fichas de lugares/personas y vínculos a obras, 24 escritos, 11 artículos de prensa, 332 colecciones, 60 referencias y 5 búsquedas por periodo/tema.
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
| Obras (todas las categorías) | **41.932** | suma de los 93 catálogos anuales (portada: 41.932) |
| Notas de obra | 24.623 | portada |
| Comentarios de obra | 9.017 | portada |
| Entradas biográficas | 16.759 | portada |
| Comentarios biográficos | 1.337 | portada |
| Lugares y personas (fichas) | 77 lugares + 66 personas | árbol `bioTree` |
| Escritos (poemas, teatro) | 615 (1935–1959) | suma de los índices anuales |
| Artículos de prensa | 23.305 | portada |
| Colecciones | 5.556 | portada |
| Referencias bibliográficas | 9.054 | portada |
| Periodos / temas (etiquetas) | 71 / 109 | formularios de *Overview* |

Obras por década:

| Década | Obras catalogadas |
|---|---|
| 1880s | 2 |
| 1890s | 2.836 |
| 1900s | 5.144 |
| 1910s | 3.806 |
| 1920s | 4.103 |
| 1930s | 5.246 |
| 1940s | 5.306 |
| 1950s | 6.908 |
| 1960s | 6.842 |
| 1970s | 1.739 |

Años con más obras:

| Año | Obras |
|---|---|
| 1962 | 953 |
| 1956 | 952 |
| 1933 | 919 |
| 1957 | 869 |
| 1907 | 844 |
| 1899 | 840 |
| 1939 | 831 |
| 1959 | 830 |
| 1968 | 823 |
| 1905 | 788 |

Comprobación de categorías (catálogo anual por categoría vs. total del año):

| Categoría | 1907 | 1937 |
|---|---|---|
| painting | 53 | 137 |
| collage | 0 | 4 |
| photograph | 1 | 15 |
| sculpture | 12 | 28 |
| ceramic | 0 | 5 |
| drawing | 542 | 176 |
| watercolor | 100 | 7 |
| gouache | 38 | 32 |
| pastel | 10 | 11 |
| engraving | 11 | 75 |
| lithograph | 0 | 1 |
| other | 77 | 123 |
| **suma categorías** | 844 | 614 |
| **catálogo del año** | 844 | 614 |

## 5. Campos por tipo de ítem

### 5.1 Obras — campos del listado (presentes en el catálogo anual, 41.932 obras)

| Campo | Descripción | Ejemplo real | Cobertura |
|---|---|---|---|
| id | Número de catálogo OPP (`OPP.AA:NNN`, AA = año) | `OPP.95:006` | 100.0% |
| title | Título (francés/español/inglés) | `Tête et épaule de Don José couché` | 100.0% |
| place | Lugar de creación | `A Coruña` | 100.0% |
| date_text | Fecha tal como la publica el sitio | `1-January/1895 [1900]` | 100.0% |
| medium | Técnica / soporte | `Graphite pencil on greenish paper, with two strokes of white paint` | 100.0% |
| dimensions | Dimensiones (cm) | `12,5 x 19 cm` | 100.0% |
| collection | Colección o museo actual | `Museu Picasso, Barcelona` | 100.0% |
| credit_line | Nº de inventario / forma de adquisición | `Carnet A Coruña 2. Dation 1970` | 54.6% |
| references | Concordancias con catálogos razonados (Zervos, Daix, Palau…) y literatura | `['MPB:111.503', 'P.I:45', 'PP.95:002', 'JR.91:49p', 'MG.15:283p', 'NM.95:10p', 'WO.92:14p…` | 90.8% |
| thumbnail | Ruta de la miniatura (y de ahí la imagen completa) | `graphics/1895/xthumbs/xopp95-006.jpg` | 100.0% |

Precisión de la fecha (campo normalizado por el parser):

| Precisión | Obras | % |
|---|---|---|
| month | 25444 | 60.7% |
| year | 9480 | 22.6% |
| season | 7000 | 16.7% |
| unknown | 8 | 0.0% |

El 24.1% de las fechas lleva corchetes (fecha atribuida/incierta según el editor). La fecha original se conserva siempre junto a la normalizada.

Lugares de creación más frecuentes (422 lugares distintos):

| Lugar de creación | Obras |
|---|---|
| Paris | 15396 |
| Mougins | 6988 |
| Vallauris | 4443 |
| Cannes | 3074 |
| Barcelona | 2737 |
| Royan | 885 |
| Boisgeloup | 696 |
| Juan-les-Pins | 633 |
| A Coruña | 528 |
| [Cannes] | 434 |
| [Paris] | 352 |
| Dinard | 315 |
| Golfe-Juan | 307 |
| Madrid | 299 |
| Gósol | 259 |

Los corchetes en el lugar («[Cannes]») marcan atribución incierta; el ETL guarda el valor original y una versión normalizada sin corchetes.

Técnicas más frecuentes:

| Técnica | Obras |
|---|---|
| Oil on canvas | 3262 |
| Pencil on paper | 1492 |
| Graphite on paper | 1185 |
| India ink on paper | 1075 |
| Pencil | 818 |
| Ink on paper | 783 |
| Pen & ink on paper | 713 |
| Lead pencil on paper | 640 |
| Etching | 607 |
| Graphite pencil on paper | 583 |

### 5.2 Obras — pop-ups de detalle (muestra de 44 obras, los 6 pop-ups pedidos a todas)

| Campo | Descripción | Ejemplo real | Cobertura |
|---|---|---|---|
| has_details | Pop-up *Details*: mismos campos + Catalogs/Books/Exhibited separados | `True` | 100.0% |
| has_provenance | Pop-up *Provenance*: cadena de propietarios (lugar, fecha, precio) | `True` | 36.4% |
| has_exhibitions | Pop-up *Exhibited*: exposiciones con sede, fechas y catálogo | `True` | 65.9% |
| has_literature | Pop-up *Literature*: bibliografía completa de la obra | `True` | 88.6% |
| has_note | Pop-up *Notes*: fichas de museos/catálogos (descripción, inscripciones, procedencia) | `True` | 63.6% |
| has_commentary | Pop-up *Commentary*: comentarios académicos con referencias cruzadas a otras obras | `True` | 29.5% |

La cobertura coincide con los botones que muestra el listado *Summary*: cuando el botón no aparece, la vista interna viene vacía. El ETL sólo pedirá los pop-ups anunciados por el listado.

Ejemplo real — `OPP.45:011`, *Femme debout*:

Procedencia:

| # | Propietario | Lugar | Fecha | Precio |
|---|---|---|---|---|
| 1 | Private collection | Barcelona |  |  |
| 2 | Christie's | London | 02/05/02 |  |
| 3 | Private collection | Barcelona |  |  |
| 4 | Private collection |  |  |  |
| 5 | Heather James Fine Art | Palm Desert | 2009 |  |

Exposición: `Pablo Picasso: Recent Work (Buchholz Gallery, New York, March 8 - April 2, 1949) . [NY.49a*] Catalogue: Anonymous . New York . 1949 . (n/a)`

Nota de museo: `Sale Title: Impressionist & Modern Art Day Sale / Source: Christie's - New York / Sale Date: 11/18/2025`

Comentario: «Müller (2002) dates this artwork as of January/1945 (cf. MM.02*:75p).» → obras relacionadas: —

### 5.3 Biografía (79 entradas de 1900, 1907, 1937)

| Campo | Descripción | Ejemplo real | Cobertura |
|---|---|---|---|
| date_desc | Descriptor de fecha (día, mes, 'Early-March', 'Summer'…) | `Year-Forth` | 100.0% |
| text | Narrativa biográfica del periodo (con citas a la literatura) | `By 1900, despite his reputation as a grumpy old man who glares at prospective customers f…` | 100.0% |
| opp_ids | Obras citadas dentro del texto | `['OPP.00:004', 'OPP.00:021', 'OPP.00:034', 'OPP.00:035', 'OPP.00:037', 'OPP.00:039', 'OPP…` | 35.4% |
| images | Fotografías/documentos insertados | `['photos/1900/xthumbs/xoppf00-032.jpg']` | 41.8% |

Enlaces disponibles por entrada:

| Enlace | Qué aporta | % entradas |
|---|---|---|
| BioResource | Fichas de lugares (residencias, estudios) y personas | 59.5% |
| ArtworkInfo | Obras enlazadas directamente | 35.4% |
| BioCommentary | Comentario/cita ampliada del editor | 27.8% |
| DatedArtworksSummary | Obras fechadas dentro del rango de la entrada (vínculo evento → obras) | 25.3% |
| DatedPhotos | Documentos y fotos del periodo | 22.8% |
| BioIndex | Navegación entre años | 5.1% |
| multiple | Comparación múltiple de obras | 3.8% |
| BioWritings | Escritos de Picasso de esas fechas | 1.3% |
| MasterArtworkSearch | Obra concreta de otro artista relacionada | 1.3% |
| MasterSearch | Obras de otros artistas (maestros) relacionadas | 1.3% |

Ejemplo real (1900, «Year-Forth»): «By 1900, despite his reputation as a grumpy old man who glares at prospective customers from the depths of his dusty gallery, Ambroise Vollard lives surrounded by artists. In the basement of his gallery he has a dining room, familiarly known as a cave' (the cellar), where he entertains the artistic and literary elite of his day, and others, includ…»

Ejemplo de vínculo entrada → obras: rango 1900-1-1 → 1900-1-31 → 32 obras (OPP.00:004, OPP.00:021, OPP.00:034, OPP.00:035, OPP.00:037, OPP.00:038…).

Árbol de lugares (ejemplos): Europe › Spain › Barcelona › Carrer d'Avinyó; Europe › Spain › Barcelona › Calle del Comercio; Europe › Spain › Barcelona › Calle d'Escudillers Blancs; Europe › Spain › Barcelona › Calle de la Merced; Europe › Spain › Barcelona › Carrer Nou; Europe › Spain › Barcelona › Calle de la Plata.

Ficha de lugar — *Le Bateau-Lavoir* (22 fotos con pie): «The Bateau-Lavoir in Montmartre, Paris Otto Freundlich Le Bateau-Lavoir (the laundry-boat) was the name given to a block of ramshackle, one-story buildings at 13 Rue Ravignan (Place Emile Goudeau), in the Montmartre section of Paris. Artists first settled there in the 1890's, but the best-known arr…»

### 5.4 Escritos (24 textos)

| Año | Poemas catalogados | Páginas |
|---|---|---|
| 1935 | 142 | 5 |
| 1941 | 14 | 1 |
| 1951 | 18 | 1 |

| Campo | Descripción | Ejemplo real | Cobertura |
|---|---|---|---|
| mid | Identificador del escrito | `437` | 100.0% |
| title | Título / primer verso | `Un peintre avait une femme` | 91.7% |
| date_text | Fecha y parte | `January-December,1935 - Part: 1` | 100.0% |
| text | Texto completo (francés o español) | `Un peintre avait une femme très jolie il était jaloux elle devait sortir ce jour pour all…` | 91.7% |

### 5.5 Archivo de prensa (11 artículos)

El archivo de prensa se concentra en las décadas recientes (artículos por año, muestra):

| Año | Artículos |
|---|---|
| 1937 | 1 |
| 1950 | 1 |
| 1973 | 11 |
| 1980 | 11 |
| 1990 | 8 |
| 2000 | 343 |
| 2010 | 1110 |
| 2020 | 668 |
| 2025 | 0 |

Años muestreados en detalle:

| Año | Artículos | Páginas |
|---|---|---|
| 1937 | 1 | 1 |
| 1944 | 2 | 1 |
| 1960 | 0 | 1 |
| 1973 | 11 | 1 |
| 1990 | 8 | 1 |

| Campo | Descripción | Ejemplo real | Cobertura |
|---|---|---|---|
| id | Identificador del artículo | `19224` | 100.0% |
| title | Titular | `The Tragedy of Guernica` | 90.9% |
| language | Idioma (bandera) | `en` | 100.0% |
| publisher | Medio | `The Times` | 90.9% |
| date_text | Fecha de publicación | `04/28/37` | 100.0% |
| dateline | Lugar/fecha de redacción | `Bilbao, April 28 1937` | 90.9% |
| text | Cuerpo completo del artículo | `Town Destroyed in Air Attack. Eye-witness's Account. From Our Special Correspondent. Guer…` | 90.9% |

### 5.6 Colecciones (332 filas)

| Letra | Colecciones |
|---|---|
| A | 86 |
| M | 246 |

| Campo | Descripción | Ejemplo real | Cobertura |
|---|---|---|---|
| name | Nombre del museo/colección | `A. C. Mazo Collection, Paris` | 100.0% |
| count | Nº de obras en el OPP | `1` | 100.0% |
| search | Búsqueda que lista sus obras | `{'view': 'ListArtworkSearchS', 'page': '1', 'Keyword': 'A. C. Mazo Collection, Paris', 'S…` | 100.0% |

### 5.7 Referencias (60 filas)

| Letra | Referencias | Páginas |
|---|---|---|
| A | 3942 | 11 |
| M | 444 | 11 |

| Campo | Descripción | Ejemplo real | Cobertura |
|---|---|---|---|
| author | Autor(es) | `Aagesen, Dorthe, ed` | 100.0% |
| date | Año | `2002-2003` | 100.0% |
| titles | Título de libro/catálogo | `The Avant-Garde in Danish and European Art, 1909-19 (Statens Museum for Kunst, Copenhagen…` | 73.3% |
| title | Título de artículo | `"An Abstract Painting by Picasso"` | 26.7% |
| publisher | Ciudad: editorial | `Copenhagen` | 78.3% |
| journal | Revista | `Bulletin of Smith College Museum of Art` | 21.7% |
| issue | Número/fecha | `Northampton, Mass., No. 14 (May)` | 21.7% |
| codes | Código OPP de la referencia (p.ej. `[WO.92*]`) | `['CG.02a*']` | 35.0% |

### 5.8 Periodos y temas (etiquetas de estilo)

Periodos definidos por el OPP: The Málaga Years, Academic Period, A Coruña Years, Social Realism, Barcelona Years, Madrid Years, Symbolism, Black Period, Post-Impressionism, Proto-Fauvism, Toulouse-Lautrec Period, Pre-Blue Period, Blue Period, Dirty Period, Rose Period, Circus Period, Harlequin Period, Iberian Period, Classical Period, Exorcist Phase, Proto-Cubism, Cézannian Cubism, Analytic Cubism, Geometrical Cubism, Hermetic Cubism, High Analytic Cubism, Synthetic Cubism, First Generation of Papiers Collés, Pointllist Cubism, Second Generation of Papiers Collés, Surrealist Cubism, First World War Years, Third Series of Papiers Collés, Confetti Cubism, Crystal Period, Rococo Cubism, Realist Cubism, Amorous Cubism, Ballet Years, Neoclassicism, Olga Period, Epoque des Duchesses, Purist Cubism, Biomorphic Style, Surrealism, Magic Series, Crucifixion Series, Cabana Series, Marie-Thérèse Years, 1927 Cannes Cabana Series, 1928 Dinard Cabana Series, Deucalion Period, 1929 Cabana Series, Sculpture and Minotaur, Bone Period, 1930-1938 Cabana Series, Civil War Years, Dora Maar Years, Guernica Era, Second World War Years, Françoise Years, Purple Period, Red Period, Antibes & Vallauris, Mediterranean Years, Antipolis Series, Californie Years, Jacqueline Years, Vauvenargues Years, Notre Dame de Vie Years, Last Years.

| Etiqueta | Tipo | Obras | Primeros IDs |
|---|---|---|---|
| Blue Period | period | 859 | OPP.01:002, OPP.01:008, OPP.01:027, OPP.01:081 |
| Rose Period | period | 1439 | OPP.04:001, OPP.04:002, OPP.04:004, OPP.04:016 |
| Analytic Cubism | period | 595 | OPP.09:001, OPP.09:002, OPP.09:003, OPP.09:004 |
| Synthetic Cubism | period | 1432 | OPP.12:001, OPP.12:002, OPP.12:003, OPP.12:004 |
| Animal: Bull | theme | 296 | OPP.90:002, OPP.91:005, OPP.92:001, OPP.92:009 |

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

| Tamaño | Archivo | Formato | Píxeles | Peso |
|---|---|---|---|---|
| full | full_opp07-005.jpeg | JPEG | 1562×2048 | 604 KB |
| full | full_opp07-022.jpeg | JPEG | 1180×879 | 196 KB |
| full | full_opp21-010.jpeg | JPEG | 1500×1967 | 560 KB |
| full | full_opp37-001.jpeg | JPEG | 3984×1860 | 1455 KB |
| full | full_opp55-003.jpeg | JPEG | 2850×1929 | 1122 KB |
| xthumb | xthumb_opp07-005.jpeg | JPEG | 76×100 | 3 KB |
| xthumb | xthumb_opp07-022.jpeg | JPEG | 100×74 | 2 KB |
| xthumb | xthumb_opp21-010.jpeg | JPEG | 76×100 | 3 KB |
| xthumb | xthumb_opp37-001.jpeg | JPEG | 100×47 | 3 KB |
| xthumb | xthumb_opp55-003.jpeg | JPEG | 100×68 | 3 KB |
| ythumb | ythumb_opp07-005.jpeg | JPEG | 229×300 | 14 KB |
| ythumb | ythumb_opp07-022.jpeg | JPEG | 300×223 | 14 KB |
| ythumb | ythumb_opp21-010.jpeg | JPEG | 229×300 | 15 KB |
| ythumb | ythumb_opp37-001.jpeg | JPEG | 300×140 | 15 KB |
| ythumb | ythumb_opp55-003.jpeg | JPEG | 300×203 | 20 KB |

- Formato JPEG RGB; el tamaño completo varía entre ~1.100 y ~4.000 px en el lado largo (media ≈ 787 KB por imagen → ≈ 31.5 GB para las 41.932 obras).
- Algunas obras tienen imágenes alternativas (`AlternateCompare`: reversos, reflectografías, estados); el ETL guarda la principal y registra las alternativas.
- Limitaciones: (1) no hay API, sólo HTML; (2) fechas con precisión heterogénea y corchetes de incertidumbre; (3) títulos en varios idiomas; (4) el servidor devuelve errores transitorios bajo carga; (5) **licencia**: uso académico, sin redistribución de texto ni imágenes, y descarga de imágenes sólo con autorización escrita (confirmada).

## 8. Datasets públicos de otros pintores

_Verificación: 2026-10-09. Las cifras marcadas "(consulta en vivo)" se obtuvieron ejecutando las APIs/SPARQL o contando filas de los CSV descargados ese día; las demás provienen de la documentación oficial citada. "No verificado" = no se pudo confirmar en una fuente oficial._

### Tabla comparativa

| Fuente | Licencia metadata | Licencia imágenes | Volumen | Metadata disponible | Acceso | API key | Facilidad 1-5 |
|---|---|---|---|---|---|---|---|
| **WikiArt / dataset ArtGAN (HF `huggan/wikiart`)** | Sin licencia declarada ("unknown"); "solo investigación no comercial" | Mixta: dominio público + obras con copyright bajo *fair use* (baja resolución); mismas restricciones | Sitio: ~250.000 obras / 3.000 artistas. Dataset: 81.444 imágenes declaradas (en HF solo 11.320 filas alojadas); 129 artistas, 27 estilos, 11 géneros | artista, estilo, género (etiquetas de clase); sin fecha, medio ni dimensiones | HuggingFace `load_dataset` / zip 25,4 GB (Google Drive) | No | 4 — una línea de código y ya trae etiquetas de estilo, pero licencia gris |
| **Wikidata (+ Commons)** | CC0 | Por archivo en Commons (PD-Art, CC BY, CC BY-SA…); sin *fair use* | 1.084.353 pinturas (P31=Q3305213); 408.796 con imagen P18; 382.007 con género; 15.963 con movimiento. Picasso: 1.824 pinturas, solo 4 con imagen | título, autor, fecha, movimiento (P135), género (P136), colección, material, dimensiones, inventario, enlaces a museos; biografía del artista como ítem | SPARQL (`query.wikidata.org`), dumps, API MediaWiki; imágenes vía URL de Commons | No | 3 — SPARQL es potente pero hay curva de aprendizaje, *timeouts* y casi no hay imágenes de artistas con copyright |
| **The Met Open Access** | CC0 | CC0 solo para obras en dominio público (`isPublicDomain`); obras con copyright sin imagen | 484.956 filas en CSV / 502.899 IDs en API; 248.472 en dominio público; 9.185 "Paintings" (5.435 PD). Picasso: 554 registros, 0 PD | título, fecha, medio, dimensiones, clasificación, período/cultura, etiquetas temáticas (AAT/Wikidata), nacionalidad y fechas del artista, línea de crédito, URL Wikidata; **sin** estilo, procedencia ni exposiciones | CSV en GitHub + REST JSON (imágenes JPEG) | No (80 req/s) | 5 — CSV único + API sin clave; muy fácil |
| **Art Institute of Chicago API** | CC0 (campo `description` CC BY 4.0) | CC0 para obras en dominio público (>50.000 imágenes); resto no reutilizable | 133.120 obras; 59.063 PD con imagen; 3.916 pinturas (1.875 PD con imagen). Picasso: 359 obras, 0 PD | título, fecha, medio, dimensiones, **style_titles** (p. ej. Cubism 391, Surrealism 164), clasificación, técnica, tema, lugar, **procedencia, historial de exposiciones y bibliografía**, biografía del artista | REST JSON + IIIF + dumps mensuales (JSON, ~2,5 GB) | No (60 req/min; *scraping* 1 req/s) | 5 — API JSON limpia, IIIF y dumps; la más completa en metadata |
| **Rijksmuseum Data Services** | CC0 / dominio público en su mayoría; algunos datos CC BY 4.0 | Mayoría PD/CC0; fotos de obras con copyright restringidas | 800.000 objetos, ~600.000 fotos alta resolución (580.039 en dump `image.tar.gz`); técnica "painting": 4.292. Picasso: 14 objetos (grabados) | Linked Art (CIDOC-CRM): título, autor, fecha, técnica, material, dimensiones, tipo, conjunto; EDM/DC vía OAI-PMH; **sin** estilo explícito | Search API (Linked Art, sin clave), OAI-PMH, LDES, resolver `id.rijksmuseum.nl`, IIIF Image (Micrio), dumps N-Triples | No (API antigua con clave está retirada) | 3 — sin clave, pero JSON-LD verboso y flujo en dos pasos (buscar IDs → resolver); casi no hay arte moderno |
| **National Gallery of Art (Washington)** | CC0 | Enlaces CC0 pero solo las imágenes con `openaccess=1` (obras PD) son libres; las demás solo *fair use* a baja resolución | 146.099 objetos en `objects.csv`; 4.454 pinturas; 69.374 imágenes *open access* (63.861 objetos); 2.927 pinturas con imagen libre. Picasso: 318 objetos (17 pinturas), **0** con imagen libre | título, fecha, años inicio/fin, medio, dimensiones, inscripción, atribución, **procedencia**, crédito, clasificación, Wikidata ID; tablas de constituyentes (biografías), términos, textos (exposiciones/bibliografía), ubicaciones | 15 CSV en GitHub (actualización diaria) + IIIF `api.nga.gov/iiif/{uuid}` | No | 4 — CSV relacionales + IIIF sin clave; pero sin imágenes de los modernos |
| **Europeana** | CC0 | Según `edm:rights` de cada registro (PD, CC0, CC BY, CC BY-NC, InC…); filtro `reusability=open` | 62.818.654 registros totales (consulta en vivo). "Picasso" tipo IMAGE: 1.741; "painting" IMAGE abierto: 121.032 | Dublin Core/EDM: título, creador, año, tipo, proveedor, país, derechos, miniatura; **sin** estilo normalizado; calidad heterogénea | REST Search/Record API, SPARQL, OAI-PMH, dumps, IIIF | Sí (gratuita; clave personal inmediata, de proyecto 1-5 días) | 3 — API sencilla pero metadata desigual, derechos variables y clave obligatoria |
| **Cleveland Museum of Art** | CC0 | CC0 cuando `share_license_status=CC0` | 68.781 obras; 41.814 CC0 con imagen; 3.952 pinturas CC0 con imagen. Picasso: 78 (13 CC0) | título, fecha, técnica, tipo, cultura, dimensiones, **procedencia, exposiciones, citas bibliográficas**, imágenes (web/print/full) | REST JSON + dump JSON/CSV en GitHub | No | 5 — API con filtros `cc0`, `has_image`, `type`; muy simple |
| **Harvard Art Museums** | Sin licencia abierta: "solo uso no comercial", sin cachear >2 semanas | Excluidas para obras con restricciones (casi todo el s. XX); IIIF v2.1 | ~224.111 objetos (cifra de ejemplo en docs; no verificado) | objeto, persona, exposición, publicación, galería, clasificación, siglo, cultura, medio, período, técnica, tipo de obra | REST JSON | Sí (2.500 llamadas/día) | 2 — clave, cuota baja, uso no comercial y sin imágenes modernas |
| **Smithsonian Open Access** | CC0 | CC0 para los ítems *open access* | >11 millones de registros (GitHub); 14.522.295 en API; `object_type:Painting*` 13.957 (12.930 con imagen). Picasso con imagen: 20 | esquema EDAN genérico: nombre, fecha, tipo de objeto, tema, notas, descripción física, medios | REST (`api.si.edu` vía api.data.gov) + dumps JSONL en S3 | Sí (api.data.gov; 1.000 req/h por defecto) | 2 — clave, esquema genérico, muy poca pintura relevante |
| **Painter by Numbers (Kaggle)** | Reglas de la competencia; copyright de los artistas ("no reside en los organizadores") | Igual que WikiArt (mixta, *fair use*) | 79.433 imágenes de entrenamiento / 1.584 pintores + 23.817 de prueba = 103.250 | `train_info.csv`: filename, artist, title, **style, genre, date** | Descarga zip desde Kaggle (cuenta requerida) | No (cuenta Kaggle) | 4 — un CSV y carpetas de imágenes; licencia igual de gris que WikiArt |

### Notas por fuente

**1. WikiArt / dataset ArtGAN.** El sitio declara "some 250.000 artworks by 3.000 artists" y aclara que muestra obras protegidas "in accordance with fair use principle" en copias de baja resolución (https://www.wikiart.org/en/about, https://www.wikiart.org/en/terms-of-use); no existe API oficial documentada. El dataset "refinado" de ArtGAN (zip de 25,4 GB con carpetas Style/Artist/Genre y CSV train/val) "can be used only for non-commercial research purpose" (https://github.com/cs-chan/ArtGAN/tree/master/WikiArt%20Dataset). La copia en HuggingFace `huggan/wikiart` declara 81.444 imágenes, 129 artistas, 27 estilos y 11 géneros, licencia "unknown" y la misma restricción no comercial, pero el servidor de datasets reporta solo 11.320 filas alojadas (https://huggingface.co/datasets/huggan/wikiart). Las clases de estilo incluyen `Cubism`, `Analytical_Cubism`, `Synthetic_Cubism`, `Fauvism`, `Expressionism`, `Post_Impressionism`, y entre los artistas están pablo-picasso, georges-braque, juan-gris, henri-matisse, salvador-dali, paul-cezanne, fernand-leger y raoul-dufy (Miró no aparece). Otra copia, `Artificio/WikiArt`, tiene 103.250 filas a 256×256 px con title/artist/date/genre (43 clases)/style (137 clases) y embeddings, sin licencia declarada (https://huggingface.co/datasets/Artificio/WikiArt). Es la única familia de datasets con etiquetas de estilo listas para clasificación supervisada, a costa de una situación legal ambigua (adecuada para uso académico, no para redistribuir).

**2. Wikidata + Wikimedia Commons.** Los datos estructurados son CC0 (https://www.wikidata.org/wiki/Wikidata:Licensing); cada archivo en Commons tiene su propia licencia, las reproducciones fieles de obras 2D en dominio público se aceptan como PD-Art y Commons "does not accept fair use justifications" (https://commons.wikimedia.org/wiki/Commons:Licensing). Consultas SPARQL en vivo (2026-10-09, https://query.wikidata.org): 1.084.353 pinturas, 408.796 con imagen, 382.007 con género (P136) y 15.963 con movimiento (P135). Picasso tiene 1.824 pinturas pero solo 4 con imagen; Dalí 1.071 (5 con imagen), Braque 371 (2), Miró 304 (2), Matisse 684 (472), Cézanne 718 (todas con imagen). Las etiquetas de movimiento para Picasso existen pero son escasas (cubism 29, analytical cubism 20, synthetic cubism 5, surrealism 5, Blue Period 3). Útil como **grafo de conocimiento y etiquetas débiles** (movimiento, género, fecha, colección) para unir con imágenes de otras fuentes, no como corpus de imágenes de Picasso. Sin clave; hay que enviar `User-Agent` y respetar el *timeout* de consulta (límites numéricos no verificados).

**3. The Met Open Access.** Dataset CC0 "on more than 470,000 artworks", CSV `MetObjects.csv` en https://github.com/metmuseum/openaccess; API sin clave, "limit request rate to 80 requests per second", imágenes JPEG solo para obras en dominio público; el endpoint `v1/search` se retiró el 2026-10-01 y hay que usar `v1.1/search` (limit ≤500, offset+limit ≤10.000) (https://metmuseum.github.io/). Conteo en vivo del CSV: 484.956 filas, 248.472 con `Is Public Domain=True`, 9.185 "Paintings" (5.435 PD). Picasso: 554 registros (37 pinturas), ninguno en dominio público (p. ej. "© 2026 Estate of Pablo Picasso / ARS" en `rightsAndReproduction`); Matisse 177, Braque 37, Gris 26, Miró 51, Dalí 25, todos con 0 PD; Cézanne 45 (39 PD). El anuncio original de 2017 hablaba de "more than 375,000 images" CC0 (https://www.metmuseum.org/perspectives/open-access-at-the-met). Metadata rica en clasificación, período, cultura y etiquetas temáticas, pero **sin estilo ni procedencia**.

**4. Art Institute of Chicago.** Documentación en https://api.artic.edu/docs/: datos CC0 (campo `description` CC BY 4.0), sin clave, 60 req/min anónimos, para *scraping* "un solo hilo, no más de una petición por segundo", IIIF `https://www.artic.edu/iiif/2/{image_id}/full/843,/0/default.jpg`, dumps en https://github.com/art-institute-of-chicago/api-data (refresco mensual, ~115 MB comprimidos / 2,5 GB). Imágenes: "free, unrestricted use of over 50,000 images... under Creative Commons Zero" solo para obras en dominio público (https://www.artic.edu/open-access/open-access-images). En vivo: 133.120 obras, 59.063 PD con imagen, 3.916 pinturas (1.875 PD con imagen). Picasso: 359 obras (incluye *The Old Guitarist*, con `provenance_text`, `exhibition_history` y `publication_history`), **0 en dominio público**. Facetas `style_titles`: Cubism 391, Surrealism 164, Impressionism 223, Post-Impressionism 102. Contemporáneos: Matisse 210, Miró 73, Braque 46, Dalí 41, Cézanne 34, Gris 21. Es la mejor fuente de **metadata curatorial** (estilo, procedencia, exposiciones, bibliografía); las imágenes de Picasso y su círculo solo se pueden consultar vía IIIF para análisis, no redistribuir.

**5. Rijksmuseum Data Services.** La API antigua con clave de Rijksstudio (`www.rijksmuseum.nl/api`) fue sustituida: el repositorio de su documentación se archivó el 3 de marzo de 2025 y remite a https://data.rijksmuseum.nl (https://github.com/Rijksmuseum/rijksmuseum.github.io). Servicios actuales (https://data.rijksmuseum.nl/docs/): Search API Linked Art en `https://data.rijksmuseum.nl/search/collection` con parámetros `creator`, `title`, `type`, `material`, `technique`, `imageAvailable`, `creationDate`, 100 resultados por página y "No API key is needed" (https://data.rijksmuseum.nl/docs/search); OAI-PMH en `https://data.rijksmuseum.nl/oai` (EDM y oai_dc, sin clave) (https://data.rijksmuseum.nl/docs/oai-pmh/); IIIF Image API vía Micrio `https://iiif.micr.io/{id}/info.json` (https://data.rijksmuseum.nl/docs/iiif/image); dumps N-Triples con `image.tar.gz` de 580.039 registros (https://data.rijksmuseum.nl/docs/data-dumps/); SRU marcado "deprecated". Volumen declarado: 800.000 objetos, 600.000 fotos de alta resolución (https://data.rijksmuseum.nl/). Política: la mayoría del material es dominio público o CC0, algunos casos CC BY 4.0 y las fotos de obras con copyright no son libres (https://data.rijksmuseum.nl/policy/). Límites de tasa: no documentados. En vivo: `technique=painting` devuelve 4.292 objetos y `creator=Picasso` 14 (grabados, p. ej. punta seca de 1905). Colección centrada en arte neerlandés: aporta poco para contemporáneos de Picasso.

**6. National Gallery of Art (Washington).** Datos CC0 para "130,000+ artworks", CSV UTF-8 actualizados "usually once a day"; "the image files themselves are not included" (https://github.com/NationalGalleryOfArt/opendata). El diccionario de datos aclara que los enlaces se publican bajo CC0 pero "the content of the linked sites might still be copyrighted", que `published_images.iiifurl` es la base IIIF, que `openaccess = 1` indica imagen libre y `0` imagen restringida "available only under fair use doctrine", limitada por `maxpixels` (https://github.com/NationalGalleryOfArt/opendata/blob/main/documentation/Data%20Dictionary.txt). Conteo en vivo: 146.099 objetos (4.454 pinturas), 129.548 imágenes publicadas, 69.374 con `openaccess=1`, 2.927 pinturas con imagen libre. Picasso: 318 objetos (17 pinturas, p. ej. *Family of Saltimbanques*, *Le gourmet*) y **0 imágenes open access**; Miró 189, Matisse 129, Braque 78, Dalí 8 objetos. Tiene procedencia textual, tablas de exposiciones/bibliografía y `wikidataid`, pero las imágenes de los modernos solo están a baja resolución bajo *fair use*.

**7. Europeana.** "All Metadata available on europeana.eu are published free of restrictions" bajo CC0; el uso de miniaturas y contenido depende del `edm:rights` de cada registro y, si falta, se asume copyright (https://www.europeana.eu/en/rights/terms-of-use). Clave obligatoria salvo Thumbnail API, OAI-PMH y SPARQL; clave personal inmediata (una por cuenta) y clave de proyecto revisada en 1-5 días laborables; solo las claves de proyecto tienen nivel de servicio definido (https://europeana.atlassian.net/wiki/spaces/EF/pages/2462351393/Accessing+the+APIs). La política de uso justo permite bloquear claves por exceso y recomienda OAI-PMH o dumps para volúmenes grandes (https://europeana.atlassian.net/wiki/spaces/EF/pages/2704146433). Search API: `rows` máx. 100, paginación por `cursor`, filtros `reusability=open|restricted|permission`, `media`, `thumbnail`, `qf=TYPE:IMAGE` (https://europeana.atlassian.net/wiki/spaces/EF/pages/2385739812/Search+API+Documentation). Consulta en vivo con la clave de demostración: 62.818.654 registros; "Picasso" con TYPE:IMAGE 1.741 (mezcla de obras, fotos y documentos); "painting" IMAGE reutilizable 121.032. Metadata heterogénea y sin etiquetas de estilo normalizadas; útil para ampliar con museos europeos (Cézanne, Matisse en colecciones francesas) filtrando por derechos.

**8. Cleveland Museum of Art.** CC0 "to this dataset"; "more than 64,000 artwork records" e "images... for over 37,000 works", filtros `cc0`, `copyrighted`, `has_image`, `type`, `artists`, sin mención de clave ni límites (https://openaccess-api.clevelandart.org/); dump `data.json`/`data.csv` en Git LFS (https://github.com/ClevelandMuseumArt/openaccess). En vivo: 68.781 obras, 41.814 CC0 con imagen, 3.952 pinturas CC0 con imagen; Picasso 78 obras (13 CC0, en su mayoría obra gráfica temprana). Incluye procedencia, exposiciones y citas. Pequeño, pero el más limpio para un estudiante.

**9. Harvard Art Museums.** Clave obligatoria (`apikey`), "limiting the number of API calls to 2500 per day", "for non-commercial use only", prohibido cachear contenido más de dos semanas y "images for objects with rights restrictions are excluded... many 20th and 21st century works are unavailable"; IIIF v2.1 (https://github.com/harvardartmuseums/api-docs, https://harvardartmuseums.org/collections/api). Volumen: ~224.111 objetos según el ejemplo de la documentación (no verificado). No recomendable para un proyecto de Picasso.

**10. Smithsonian Open Access.** CC0, "Over 11 million metadata records", JSON por líneas; el repo de GitHub se archivó el 2026-05-21 y la descarga masiva pasó a S3 (https://github.com/Smithsonian/OpenAccess). API `https://api.si.edu/openaccess/api/v1.0/search` con clave de api.data.gov, cuyo límite por defecto es "1,000 requests per hour" (https://api.data.gov/docs/developer-manual/). En vivo: 14.522.295 registros, `object_type:Painting*` 13.957 (12.930 con imagen), "Picasso" con imagen 20 (muchos son libros o fotografías). Esquema EDAN genérico sin estilo.

**11. Painter by Numbers (Kaggle).** Competencia en https://www.kaggle.com/c/painter-by-numbers; datos "sourced primarily from wikiart.org" y "the copyright does not reside with the contest organizers, but rather with the artists" (https://www.kaggle.com/c/painter-by-numbers/discussion/21392); `train_info.csv` con filename, artist, title, style, genre, date. Tamaño: 79.433 imágenes de entrenamiento de 1.584 pintores y 23.817 de prueba (https://github.com/inejc/painters), total 103.250, cifra que coincide exactamente con `Artificio/WikiArt` en HuggingFace. Requiere cuenta Kaggle y aceptar las reglas; mismo estatus legal gris que WikiArt.

### Fuentes con etiquetas de estilo/período/género y con contemporáneos de Picasso

- **Etiquetas de estilo listas para clasificación supervisada:** WikiArt/ArtGAN (27 estilos, incl. Analytical/Synthetic Cubism), Painter by Numbers / Artificio (style y genre en texto libre, 137 estilos), AIC (`style_titles`, p. ej. Cubism 391 obras), Wikidata (P135 movimiento, P136 género; cobertura parcial: 15.963 pinturas con movimiento). Met, NGA, Cleveland, Rijksmuseum, Europeana, Harvard y Smithsonian **no** ofrecen estilo normalizado (solo clasificación/medio/período).
- **Contemporáneos (Braque, Matisse, Miró, Gris, Dalí, Cézanne):** WikiArt/ArtGAN (todos salvo Miró), Painter by Numbers (1.584 pintores), AIC (Matisse 210, Miró 73, Braque 46, Dalí 41, Cézanne 34, Gris 21; solo Cézanne en dominio público), Met (Matisse 177, Miró 51, Cézanne 45, Braque 37, Gris 26, Dalí 25; solo Cézanne PD), NGA (Miró 189, Matisse 129, Braque 78, Dalí 8; sin imágenes libres), Wikidata (Cézanne y Matisse con cientos de imágenes; Braque/Miró/Dalí casi sin imagen). Regla general: **solo Cézanne (†1906) está en dominio público** en los museos; para el resto solo hay metadata o imágenes bajo *fair use*.

### Recomendación

1. **WikiArt/ArtGAN (HF `huggan/wikiart`) o Painter by Numbers** como corpus principal de imágenes etiquetadas: son los únicos con Picasso, Braque, Gris, Matisse, Dalí y Cézanne junto a etiquetas de estilo (cubismo analítico/sintético, fauvismo, etc.) para entrenar o validar clasificadores de período; documentar que su uso es "solo investigación no comercial" y no redistribuir las imágenes.
2. **Art Institute of Chicago API** como fuente de metadata curatorial de referencia (estilo, medio, dimensiones, procedencia, exposiciones, bibliografía) y de imágenes CC0 vía IIIF para las obras en dominio público (Cézanne, impresionistas) que sirven de contraste a los embeddings; sin clave y con dumps mensuales, trivial de integrar en Python.
3. **Wikidata (SPARQL, CC0)** como capa de enriquecimiento y *ground truth* débil: movimiento, género, fecha, colección y QID para alinear registros entre WikiArt, AIC y Met (ambos exponen URL Wikidata), aunque no como fuente de imágenes de Picasso (solo 4 de 1.824 pinturas tienen imagen).
4. Como complemento opcional, **The Met (CSV CC0)** y **Cleveland (API CC0)** aportan fácilmente pinturas de dominio público con imagen para una línea base de "no modernos"; Rijksmuseum, Europeana, Harvard y Smithsonian añaden poco a un proyecto centrado en Picasso.
5. En todos los casos conviene filtrar por `is_public_domain`/`cc0`/`openaccess`/`reusability=open` al descargar imágenes y citar la fuente en el informe académico.


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

| Bloque | Requests | Tiempo a 1 req/s |
|---|---|---|
| Catálogo anual × categoría (descubrimiento + metadata base de las 41.932 obras) | 1209 | 0.3 h |
| Imágenes a tamaño completo (1 por obra) | 41932 | 11.6 h |
| Contexto: biografía (93 años, comentarios, lugares/personas), escritos, referencias, colecciones, periodos/temas | 6148 | 1.7 h |
| **Nivel 1 = catálogo + imágenes + contexto** | 49289 | **13.7 h** |
| Listados *Summary* (30/página) para saber qué pop-ups existen | 1398 | 0.4 h |
| Pop-ups de detalle sólo cuando existen (procedencia, exposiciones, literatura, notas, comentario; ≈2,8 por obra) | 119086 | 33.1 h |
| **Nivel 2 = Nivel 1 + pop-ups** | 169773 | **47.2 h** |
| Pop-ups: los 5 para todas las obras (peor caso, sin leer los listados) | 209660 | 58.2 h |
| Nivel 3 (opcional): archivo de prensa completo (23.305 artículos) | 23402 | 6.5 h |

Lectura: el **Nivel 1** (toda la metadata base de las 41.932 obras con imagen, más biografía, escritos, referencias, colecciones y etiquetas de periodo/tema) cuesta **13.7 h** de reloj a 1.0 req/s. Los pop-ups de detalle son el bloque caro: llevan el total a **47.2 h** (Nivel 2, ≈ 2 días dejando el proceso corriendo; es reanudable). El pop-up *Details* no se pide: repite los campos del listado. La prensa (Nivel 3) se deja opcional. Un piloto de 100 obras con todo (Nivel 2 + imágenes) toma unos 10 minutos.

Recomendación: ejecutar primero el Nivel 1 completo (metadata + imágenes + contexto, suficiente para embeddings, clustering y evolución por periodos) y lanzar el Nivel 2 después, por rangos de años, según el tiempo disponible.

## 11. Decisiones para la Fase 2

1. Descubrimiento por `ArtworkLarge` año × categoría (1.209 requests) → manifest con metadata base ya completa.
2. Pop-ups: leer los listados *Summary* (1.398 páginas) y pedir sólo los pop-ups que cada obra anuncia (≈2,8 por obra en vez de 5); omitir *Details* porque repite el listado.
3. Imágenes a tamaño completo (autorización escrita confirmada); `--no-images` disponible.
4. Contexto: biografía completa (93 años), árbol de lugares y fichas, periodos y temas; prensa opcional.
5. Directorios por categoría del sitio (12), en vez de paintings/drawings/sculptures/manuscripts: los "manuscritos" son la sección Writings.
