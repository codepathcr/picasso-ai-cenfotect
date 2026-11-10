# Plan del proyecto (Picasso — estilos por período, CNN + IA distribuida)

Hardware: NVIDIA GeForce RTX 3080 Ti (una sola computadora). Entrega: ~3 semanas desde 2026-10-15 (≈ 2026-11-05).
Regla permanente: **antes de cualquier cambio sobre los datos o la carpeta, sacar un backup** (ver paso 0).

## Pasos
0. **Backup antes de cada cambio** (copia de `data/` del proyecto de descarga y de `picasso-estilos/`, con fecha; verificar que abre). Se repite antes de: reintentos con --resume, fase load, filtrado/preprocesado del dataset y cualquier limpieza o borrado.
1. Cerrar la descarga: reintentar errores (--resume), `--phase load`, verificar totales (obras, imágenes, períodos).
2. Dataset de entrenamiento: unir catalog.csv + periods.json, filtrar (pinturas / períodos bien representados), redimensionar (p. ej. 224 px), dividir train/val/test por obra, reporte de obras por período.
3. Línea base: perceptrón y MLP (feed-forward).
4. CNN clasificadora de período (backpropagation + descenso del gradiente, aumento de datos), usada como "juez de estilo".
5. Componente distribuido (una computadora): paralelismo de datos (torch.distributed, backend gloo/nccl) y/o federado (FedAvg); comparar 1, 2 y 4 procesos (tiempo y precisión).
6. Transferencia de estilo (Gatys/VGG): obra de un período con el estilo de otro; evaluar con la CNN del paso 4.
7. Informe y presentación.

## Cronograma tentativo (3 semanas)
- Semana 1: pasos 0–3 (backup, cierre de descarga, dataset, línea base).
- Semana 2: pasos 4–5 (CNN y entrenamiento distribuido/federado, métricas).
- Semana 3: pasos 6–7 (transferencia de estilo, informe, presentación) + margen.

## Pendiente de decidir
- ¿Se descarga el Nivel 2 (comentarios, ~33 h)? Por defecto no.
- Qué acepta el curso como "distribuido" en una sola máquina (procesos simulados).
