"""Explica cada imagen generada: que cambio (medido) y por que (ficha del periodo).

python -m src.style_transfer.explain --results outputs/transfer_v2/results.json
Escribe <carpeta>/explicaciones.json (incluye imagenes en base64 para la galeria).

Medidas (todas sobre la imagen 256x256):
  saturacion  - intensidad del color (0 = gris, 1 = color puro), media del canal S de HSV
  brillo      - claridad media (canal V de HSV)
  contraste   - desviacion estandar de la claridad: luces y sombras marcadas
  calidez     - % pixeles calidos (rojos/naranjas/amarillos) menos % frios (azules/verdes)
  textura     - energia de bordes (gradiente medio): pinceladas y trazos visibles
  paleta      - 5 colores dominantes (k-means) con nombre y porcentaje
Cada medida se compara con el promedio real del periodo destino (obras a color del dataset).
"""
import argparse, base64, colorsys, io, json, os
import numpy as np, pandas as pd
from PIL import Image
from src.style_transfer.periodos_info import PERIODOS

# ---------- color ----------
import colorsys

def nombre_color(rgb):
    """Nombre en espanol por tono, claridad e intensidad (mas fiel que el vecino mas cercano para
    colores apagados, que son la mayoria en pintura)."""
    r, g, b = (float(x) / 255 for x in rgb)
    h, s, v = colorsys.rgb_to_hsv(r, g, b); h *= 360
    if v < 0.16: return "negro"
    if s < 0.12 or (v < 0.3 and s < 0.25):
        return "gris oscuro" if v < 0.4 else "gris" if v < 0.68 else "gris claro" if v < 0.88 else "blanco"
    if 15 <= h < 55:                                   # zona tierra: marrones, ocres, beige, naranja
        if v < 0.55: return "marrón oscuro" if v < 0.32 else "marrón"
        if s < 0.32: return "beige"
        if h < 32 and s > 0.55: return "naranja"
        return "ocre" if s < 0.6 or h < 42 else "amarillo"
    if h < 15 or h >= 335:
        if v < 0.42: return "granate"
        return "rosa" if s < 0.45 else "rojo"
    base = ("amarillo" if h < 70 else "verde oliva" if h < 95 and v < 0.6 else "verde" if h < 165
            else "azul verdoso" if h < 200 else "azul" if h < 255 else "violeta" if h < 295 else "rosa")
    if base in ("verde oliva",): return base
    if v < 0.36: return base + " oscuro"
    if s < 0.3: return base + " grisáceo"
    if v > 0.82 and s < 0.5: return base + " claro"
    return base


def kmeans(px, k=5, it=20, seed=0):
    rng = np.random.default_rng(seed)
    c = px[rng.choice(len(px), k, replace=False)].astype(np.float64)
    for _ in range(it):
        lab = ((px[:, None, :] - c[None]) ** 2).sum(-1).argmin(1)
        for j in range(k):
            if (lab == j).any(): c[j] = px[lab == j].mean(0)
    pct = np.bincount(lab, minlength=k) / len(px)
    o = np.argsort(-pct)
    return [dict(hex="#%02x%02x%02x" % tuple(int(v) for v in c[j]), nombre=nombre_color(c[j]),
                 pct=round(float(pct[j]), 3)) for j in o]


def medidas(im, paleta=True):
    im = im.convert("RGB")
    hsv = np.asarray(im.convert("HSV"), dtype=np.float32) / 255
    v = hsv[..., 2]
    gy, gx = np.gradient(v)
    h, s = hsv[..., 0] * 360, hsv[..., 1]
    col = s > 0.15
    calido = (col & ((h < 70) | (h >= 330))).mean()
    frio = (col & (h >= 150) & (h < 270)).mean()
    m = dict(saturacion=float(s.mean()), brillo=float(v.mean()), contraste=float(v.std()),
             calidez=float(calido - frio), textura=float(np.hypot(gx, gy).mean()))
    if paleta:
        px = np.asarray(im.resize((64, 64)), dtype=np.float64).reshape(-1, 3)
        m["paleta"] = kmeans(px)
    return m


# ---------- perfiles de periodo (promedio real del dataset) ----------
def perfiles(data, lab, cache):
    if os.path.exists(cache):
        out = json.load(open(cache, encoding="utf-8"))
        for v in out.values():          # recalcula nombres por si cambio la regla de nombres
            for c in v["paleta"]:
                c["nombre"] = nombre_color(tuple(int(c["hex"][i:i + 2], 16) for i in (1, 3, 5)))
        return out
    sat = pd.read_csv(f"{data}/saturation.csv")[["id", "sat"]]
    d = lab.merge(sat, on="id")
    d = d[d.sat >= 0.08]
    out = {}
    for st, g in d.groupby("style"):
        g = g.sample(min(150, len(g)), random_state=0)
        ms, pool = [], []
        for f in g.file:
            im = Image.open(f"{data}/{f}").convert("RGB")
            ms.append(medidas(im, paleta=False))
            pool.append(np.asarray(im.resize((24, 24)), dtype=np.float64).reshape(-1, 3))
        prof = {k: float(np.mean([m[k] for m in ms])) for k in ms[0]}
        prof["paleta"] = kmeans(np.concatenate(pool), k=6)
        prof["n_obras"] = int((lab["style"] == st).sum())
        out[st] = prof
    json.dump(out, open(cache, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return out


def lugares(catalog, lab):
    if not os.path.exists(catalog): return {}
    c = pd.read_csv(catalog, usecols=["id", "place"])
    d = lab.merge(c, on="id")
    d["place"] = d.place.fillna("").str.replace(r"[\[\]]", "", regex=True).str.strip()
    out = {}
    for st, g in d[d.place != ""].groupby("style"):
        vc = g.place.value_counts().head(3)
        out[st] = [dict(lugar=k, obras=int(v)) for k, v in vc.items()]
    return out


# ---------- texto ----------
RASGOS = [  # clave, nombre, sube, baja, umbral minimo para decir que cambio, formato
    ("saturacion", "Intensidad del color", "colores más vivos", "colores más apagados", 0.02, "{:.2f}"),
    ("brillo", "Claridad", "imagen más clara", "imagen más oscura", 0.02, "{:.2f}"),
    ("contraste", "Contraste", "luces y sombras más marcadas", "luces y sombras más suaves", 0.01, "{:.2f}"),
    ("calidez", "Temperatura del color", "más cálida (rojos, naranjas, amarillos)",
     "más fría (azules, verdes)", 0.03, "{:+.2f}"),
    ("textura", "Pincelada y trazo", "pinceladas y trazos más visibles", "superficie más lisa", 0.003, "{:.3f}"),
]


def mezcla(target):
    out = []
    for part in target.split(","):
        n, _, w = part.partition(":")
        out.append((n.strip(), float(w) if w else 1.0))
    t = sum(w for _, w in out)
    return [(n, w / t) for n, w in out]


def perfil_destino(mix, prof):
    return {k: sum(w * prof[n][k] for n, w in mix) for k in ("saturacion", "brillo", "contraste", "calidez", "textura")}


def nombres_paleta(p, n=3):
    vistos = []
    for c in p:
        if c["nombre"] not in vistos: vistos.append(c["nombre"])
    return ", ".join(vistos[:n])


def explicar(r, antes, despues, prof, classes_es):
    mix = mezcla(r["target"])
    dest = perfil_destino(mix, prof)
    fichas = [PERIODOS[n]["nombre"] for n, _ in mix]
    destino_txt = fichas[0] if len(mix) == 1 else " + ".join(
        f"{PERIODOS[n]['nombre']} ({w:.0%})" for n, w in mix)
    filas, acerca = [], 0
    for k, nom, up, down, thr, fmt in RASGOS:
        a, b, t = antes[k], despues[k], dest[k]
        cambio = b - a
        hacia = abs(b - t) < abs(a - t)
        acerca += hacia
        if abs(cambio) < thr:
            efecto = "casi no cambia"
        else:
            efecto = up if cambio > 0 else down
        filas.append(dict(rasgo=nom, antes=fmt.format(a), despues=fmt.format(b), periodo=fmt.format(t),
                          efecto=efecto, se_acerca=bool(hacia)))
    pa, pd_ = antes["paleta"], despues["paleta"]
    nuevos = list(dict.fromkeys(c["nombre"] for c in pd_[:3] if c["nombre"] not in {x["nombre"] for x in pa}))
    pal_txt = (f"Los colores dominantes pasan de {nombres_paleta(pa)} a {nombres_paleta(pd_)}."
               + (f" Aparecen tonos que no estaban: {', '.join(nuevos)}." if nuevos else ""))
    resumen = (f"La obra toma la paleta y la textura de {destino_txt}. "
               f"De 5 rasgos medidos, {acerca} se acercan al promedio real de ese período en el dataset.")
    juez = (f"El clasificador (ResNet18) veía la original como «{classes_es(r['pred_before'])}» "
            f"y la nueva como «{classes_es(r['pred_after'])}». Probabilidad de {fichas[0]}: "
            f"{r['p_target_before']:.0%} → {r['p_target_after']:.0%}.")
    if len(mix) > 1:
        resumen += (" Es una mezcla de influencias: el estilo se calculó combinando "
                    + " y ".join(f"{w:.0%} de {PERIODOS[n]['nombre']}" for n, w in mix) + ".")
    return dict(destino=destino_txt, resumen=resumen, paleta_texto=pal_txt, rasgos=filas, juez=juez,
                rasgos_cerca=acerca, no_reproduce=[PERIODOS[n]["no_reproduce"] for n, _ in mix])


def b64(path, size=256):
    im = Image.open(path).convert("RGB").resize((size, size))
    buf = io.BytesIO(); im.save(buf, "JPEG", quality=88)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--results", default="outputs/transfer_v2/results.json")
    p.add_argument("--data", default="data/styles")
    p.add_argument("--catalog", default="")
    a = p.parse_args()
    folder = os.path.dirname(a.results)
    lab = pd.read_csv(f"{a.data}/labels.csv")
    prof = perfiles(a.data, lab, f"{a.data}/perfiles_periodo.json")
    lug = lugares(a.catalog, lab) if a.catalog else {}
    es = lambda s: PERIODOS.get(s, {}).get("nombre", s)
    res = json.load(open(a.results))
    obras, cache = {}, {}
    for r in res:
        row = lab[lab["id"] == r["content"]].iloc[0]
        src = f"{a.data}/{row.file}"
        if r["content"] not in cache:
            cache[r["content"]] = medidas(Image.open(src))
            obras[r["content"]] = dict(id=r["content"], titulo=str(row.title), anio=int(row.year),
                                       periodo=r["source_style"], periodo_nombre=es(r["source_style"]),
                                       img=b64(src), medidas=cache[r["content"]])
        gen = f"{folder}/{r['file']}"
        m = medidas(Image.open(gen))
        r.update(explicacion=explicar(r, cache[r["content"]], m, prof, es), medidas=m, img=b64(gen))
    out = dict(periodos={k: dict(v, id=k, perfil=prof.get(k), lugares_catalogo=lug.get(k, []))
                         for k, v in PERIODOS.items()},
               obras=list(obras.values()), transferencias=res)
    json.dump(out, open(f"{folder}/explicaciones.json", "w", encoding="utf-8"), ensure_ascii=False)
    for r in res:
        e = r["explicacion"]
        print(f"\n== {r['content']} -> {e['destino']}\n{e['resumen']}\n{e['paleta_texto']}")
        for f in e["rasgos"]:
            print(f"  {f['rasgo']}: {f['antes']} -> {f['despues']} (periodo {f['periodo']}) "
                  f"{f['efecto']}{' ✓' if f['se_acerca'] else ''}")
        print(" ", e["juez"])


if __name__ == "__main__":
    main()
