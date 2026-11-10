# Simulador Picasso · colores

Página web local para llevar una pintura de Picasso a otro de sus períodos cambiando **solo la paleta y la textura de la pincelada**
(motor de colores: Gatys con VGG19). La forma de la obra no se toca.

Es la versión de solo colores del simulador del proyecto completo: no usa difusión, LoRA, ControlNet ni juez de trazos, así que
no descarga modelos de Hugging Face. Corre en el puerto **8767**.

## Cómo abrirlo

1. Una sola vez: `picasso-estilos\setup_entorno.bat` (crea el entorno de Python; ver el README de la raíz).
2. Doble clic en `iniciar_simulador_colores.bat`. El navegador abre http://127.0.0.1:8767 a los ~20 s.

`probar_simulador_colores.bat` hace una autoprueba (genera una simulación a 256 px, verifica el caché y la regeneración) y deja `log_prueba.txt`.

## Con qué datos corre

El simulador se adapta a lo que haya en el repositorio:

| Qué | Si existe | Si no existe |
| --- | --- | --- |
| **Estilo de cada período** (obras de entrenamiento) | `picasso-estilos\data\styles\train` (dataset completo, 5,118 pinturas) | `picasso-estilos\data\muestra`, que arma solo `demo\armar_muestra.bat` con las 40 pinturas de muestra (2 por período para el estilo) |
| **Obras que se pueden simular** | Catálogo del ETL en `picasso-ai-cenfotect-main\data` (miles de obras con imagen) | Las 40 pinturas de `muestras\pinturas` |

Las fichas de color de cada período (`perfiles_periodo.json`) son siempre las del dataset completo. Con la muestra, el estilo de cada período se calcula con
2 pinturas en lugar de 16, por eso se ve menos fiel; el motor y los jueces son los mismos.

Opciones de `server.py`: `--port`, `--catalog-dir <carpeta data del ETL>`, `--data <dataset de estilos>`, `--todas-las-categorias`, `--selftest`.

## Qué hace

1. Galería paginada (10, 20 o 30 obras por página) con búsqueda por título, lugar o número y filtro por período.
2. Período destino en un combo, con tamaño (256, 384 o 512 px) y pasos de Gatys (250, 400 o 600).
3. Taller con avance en vivo: vista previa mientras se pinta, paso actual, tiempo transcurrido y restante, y cola si hay varias simulaciones.
4. Caché en disco (`cache\<obra>\`): si se pide lo mismo aparece al instante. «Volver a generar» crea otra versión; las anteriores se conservan.
5. Resultado con deslizador antes/después, 5 rasgos medidos (intensidad, claridad, contraste, temperatura y pincelada) frente al promedio real del período,
   paleta dominante con nombres en español, ficha histórica del período y lo que el motor no puede copiar.
6. Dos jueces entrenados por nosotros: la **CNN propia** (independiente: nunca participa en la generación) y la **ResNet18**.

## De dónde salen los modelos (solo lectura)

- `..\picasso-estilos\outputs\cnn.pt` y `resnet18.pt` (con sus `.json`): jueces de colores.
- `..\picasso-estilos\src\style_transfer\`: Gatys (`transfer.py`), medidas y explicaciones (`explain.py`) y fichas de períodos (`periodos_info.py`).
- VGG19 pre-entrenado: lo baja torchvision la primera vez.

Lo único que escribe el simulador es la carpeta `cache\` (ignorada por git).
