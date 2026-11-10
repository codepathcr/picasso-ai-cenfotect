# Picasso — estilos por período (CNN + IA distribuida)

Proyecto académico (curso de IA distribuida, CENFOTEC). Usa los datos del proyecto de descarga
`../picasso-ai-cenfotect-main` (uso estrictamente académico; no se redistribuyen imágenes ni modelos).

## Plan
1. **Dataset por períodos**: `catalog.csv` + `periods.json` del proyecto de descarga -> imágenes etiquetadas por período.
2. **Clasificador de período (CNN)**: perceptrón/feed-forward como línea base, luego CNN (backpropagation + descenso del gradiente).
3. **Entrenamiento distribuido** (una sola computadora, procesos simulados): paralelismo de datos (`torch.distributed`, backend `gloo`)
   y/o aprendizaje federado (FedAvg). Comparar 1, 2 y 4 procesos (tiempo y precisión).
4. **Transferencia de estilo** (Gatys, VGG): obra de un período con el estilo de otro; evaluar con el clasificador.

## Estructura
```
src/data/            preparación del dataset y DataLoader
src/models/          perceptrón, MLP y CNN
src/distributed/     entrenamiento en paralelo de datos y FedAvg
src/style_transfer/  transferencia de estilo y evaluación
notebooks/           exploración
data/                (ignorado por git) imágenes y splits
outputs/             (ignorado por git) modelos, métricas, imágenes generadas
docs/                informe y notas
```
