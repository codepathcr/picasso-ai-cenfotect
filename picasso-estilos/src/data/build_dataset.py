"""Construye el dataset de estilos: pinturas de Picasso -> 256px, etiqueta = macro-periodo (por año),
split train/val/test (80/10/10) estratificado por periodo. Uso:
  python -m src.data.build_dataset --src <picasso-ai.../data> --out data/styles [--size 256]
Solo LEE de --src. Escribe en --out."""
import argparse, os, json
import pandas as pd
from PIL import Image

# (nombre, año_inicio, año_fin) -- etiquetas por año de la obra; criterio clasico de la historiografia
PERIODS = [
    ("00_temprano", 1881, 1900),
    ("01_azul", 1901, 1904),
    ("02_rosa", 1905, 1906),
    ("03_iberico_africano", 1907, 1908),
    ("04_cubismo_analitico", 1909, 1912),
    ("05_cubismo_sintetico", 1913, 1919),
    ("06_neoclasico", 1920, 1924),
    ("07_surrealista", 1925, 1936),
    ("08_guerra", 1937, 1945),
    ("09_tardio", 1946, 1973),
]


def label(y):
    for n, a, b in PERIODS:
        if a <= y <= b:
            return n
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", default="data/styles")
    ap.add_argument("--size", type=int, default=256)
    ap.add_argument("--category", default="painting")
    a = ap.parse_args()
    d = pd.read_csv(os.path.join(a.src, "index", "catalog.csv"))
    d = d[(d.category == a.category) & d.image_file.notna() & d.year.notna()].copy()
    d["style"] = d.year.astype(int).map(label)
    d = d[d.style.notna()].reset_index(drop=True)
    d = d.sample(frac=1, random_state=42)
    d["split"] = "train"
    for s, g in d.groupby("style"):
        n = len(g); nv = max(1, round(n * .1)); nt = max(1, round(n * .1))
        d.loc[g.index[:nv], "split"] = "val"
        d.loc[g.index[nv:nv + nt], "split"] = "test"
    rows = []
    os.makedirs(a.out, exist_ok=True)
    for r in d.itertuples():
        p = os.path.join(a.src, r.path.replace("\\", "/"), r.image_file)
        rel = f"{r.split}/{r.style}/{r.id.replace(':', '_')}.jpg"
        dst = os.path.join(a.out, rel)
        if not os.path.exists(dst):
            try:
                im = Image.open(p).convert("RGB")
                w, h = im.size; s = a.size / min(w, h)
                im = im.resize((max(a.size, round(w * s)), max(a.size, round(h * s))), Image.LANCZOS)
                w, h = im.size; l, t = (w - a.size) // 2, (h - a.size) // 2
                im = im.crop((l, t, l + a.size, t + a.size))
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                im.save(dst, quality=92)
            except Exception as e:
                print("skip", r.id, e); continue
        rows.append(dict(id=r.id, year=r.year, style=r.style, split=r.split, file=rel, title=r.title))
    m = pd.DataFrame(rows)
    m.to_csv(os.path.join(a.out, "labels.csv"), index=False)
    print(m.pivot_table(index="style", columns="split", values="id", aggfunc="count", margins=True))


if __name__ == "__main__":
    main()
