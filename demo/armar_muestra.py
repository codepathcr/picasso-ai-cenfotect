"""Arma un dataset de DEMOSTRACION con las 40 pinturas de muestra (4 por periodo) del repositorio.

Crea picasso-estilos/data/muestra/ con la misma estructura que el dataset completo
(train/val/test/<periodo>/*.jpg + labels.csv + saturation.csv + perfiles_periodo.json),
asi todos los scripts de picasso-estilos funcionan con --data apuntando ahi.

Reparto por periodo: 2 train (las de color mas intenso, para que sirvan de estilo), 1 val, 1 test.
No modifica nada fuera de picasso-estilos/data/muestra/. Solo usa la libreria estandar.
  python demo/armar_muestra.py
"""
import csv, json, os, shutil, sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ESTILOS = os.path.join(RAIZ, "picasso-estilos")
ORIGEN = os.path.join(ESTILOS, "data", "styles")           # labels.csv, saturation.csv y perfiles del dataset completo
MUESTRAS = os.path.join(RAIZ, "muestras", "pinturas")
DESTINO = os.path.join(ESTILOS, "data", "muestra")


def leer(path, clave="id"):
    with open(path, encoding="utf-8", newline="") as f:
        return {r[clave]: r for r in csv.DictReader(f)}


def main():
    labels = leer(os.path.join(ORIGEN, "labels.csv"))
    sat = leer(os.path.join(ORIGEN, "saturation.csv"))
    if os.path.isdir(DESTINO):
        shutil.rmtree(DESTINO)
    filas, faltan = [], []
    for periodo in sorted(os.listdir(MUESTRAS)):
        obras = []
        for nombre in sorted(os.listdir(os.path.join(MUESTRAS, periodo))):
            if not nombre.lower().endswith(".jpg"):
                continue
            oid = os.path.splitext(nombre)[0].replace("_", ":", 1)          # OPP.01_020 -> OPP.01:020
            if oid not in labels:
                faltan.append(oid); continue
            obras.append((float(sat[oid]["sat"]), oid, nombre))
        obras.sort(reverse=True)                                              # mas saturadas primero
        train, resto = obras[:2], sorted(obras[2:], key=lambda o: o[1])
        reparto = [("train", o) for o in train] + [("val", o) for o in resto[:1]] + [("test", o) for o in resto[1:2]]
        for split, (s, oid, nombre) in reparto:
            rel = f"{split}/{periodo}/{nombre}"
            os.makedirs(os.path.dirname(os.path.join(DESTINO, rel)), exist_ok=True)
            shutil.copyfile(os.path.join(MUESTRAS, periodo, nombre), os.path.join(DESTINO, rel))
            r = labels[oid]
            filas.append(dict(id=oid, year=r["year"], style=r["style"], split=split, file=rel, title=r["title"], sat=sat[oid]["sat"]))
    if faltan:
        print("AVISO: no estan en labels.csv:", faltan)
    cols = ["id", "year", "style", "split", "file", "title"]
    with open(os.path.join(DESTINO, "labels.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, cols, extrasaction="ignore"); w.writeheader(); w.writerows(filas)
    with open(os.path.join(DESTINO, "saturation.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, cols + ["sat"]); w.writeheader(); w.writerows(filas)
    # fichas de color por periodo: las del dataset completo (promedio real de 5,118 pinturas)
    shutil.copyfile(os.path.join(ORIGEN, "perfiles_periodo.json"), os.path.join(DESTINO, "perfiles_periodo.json"))
    conteo = {}
    for r in filas:
        conteo[r["split"]] = conteo.get(r["split"], 0) + 1
    print(f"Dataset de muestra listo en {DESTINO}\n  {len(filas)} imagenes: {conteo}")
    if len(filas) != 40:
        sys.exit("ERROR: se esperaban 40 imagenes")


if __name__ == "__main__":
    main()
