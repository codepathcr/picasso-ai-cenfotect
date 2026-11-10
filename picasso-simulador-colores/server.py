"""Simulador Picasso · colores: elegir una obra y llevarla a otro periodo cambiando SOLO paleta y textura (Gatys + VGG19).

    picasso-estilos\\.venv\\Scripts\\python server.py [--port 8767] [--catalog-dir <carpeta data del ETL>] [--data <dataset de estilos>]

De donde lee (solo lectura, no modifica nada fuera de cache\\):
  - ..\\picasso-estilos\\outputs      : juez ResNet18 y CNN propia (entrenados por nosotros)
  - dataset de estilos (--data)     : obras de entrenamiento de cada periodo = el "estilo" del periodo, y las fichas de color.
        Por defecto: picasso-estilos\\data\\styles si tiene las imagenes (dataset completo);
        si no, picasso-estilos\\data\\muestra (40 pinturas de demostracion, la arma demo\\armar_muestra.bat).
  - catalogo de obras a simular     : el del ETL (picasso-ai-cenfotect-main\\data\\index\\catalog.csv) si existe;
        si no, las 40 pinturas de muestra de ..\\muestras\\pinturas.
Cada resultado se guarda en cache\\<obra>\\ (imagen + json). Si se vuelve a pedir lo mismo se muestra el guardado;
"volver a generar" crea una version nueva (las anteriores se conservan). Los trabajos van a una cola (una sola GPU)
y la pagina consulta el avance con vista previa en vivo.
"""
import argparse, base64, glob, io, json, os, queue, re, sys, threading, time, traceback, unicodedata, uuid
from argparse import Namespace
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, unquote

HERE = os.path.dirname(os.path.abspath(__file__))
PROY = os.path.dirname(HERE)
ESTILOS = os.path.join(PROY, "picasso-estilos")
MUESTRAS = os.path.join(PROY, "muestras", "pinturas")
CACHE = os.path.join(HERE, "cache")
sys.path.insert(0, ESTILOS)

import pandas as pd, torch, torch.nn as nn, torch.nn.functional as F  # noqa: E402
from PIL import Image  # noqa: E402
from torchvision import transforms as T  # noqa: E402

from src.data.build_dataset import PERIODS as RANGOS  # noqa: E402
from src.models.models import make  # noqa: E402
from src.style_transfer.transfer import Transfer, norm, gram, STYLE_L, CONTENT_L, DEV  # noqa: E402
from src.style_transfer import explain as X  # noqa: E402
from src.style_transfer.periodos_info import PERIODOS  # noqa: E402

Image.MAX_IMAGE_PIXELS = None
CATS = {"painting": "Pintura", "drawing": "Dibujo", "engraving": "Grabado", "lithograph": "Litografía",
        "ceramic": "Cerámica", "sculpture": "Escultura", "watercolor": "Acuarela", "gouache": "Gouache",
        "pastel": "Pastel", "collage": "Collage", "photograph": "Fotografía", "other": "Otro"}
# Solo obras pictoricas a color: los modelos aprendieron de pinturas; no tiene sentido simular cartas, ceramica o esculturas.
SIMULABLES = ("painting", "watercolor", "gouache", "pastel")
LADOS, PASOS, POR_PAGINA = (256, 384, 512), (250, 400, 600), (10, 20, 30)


def periodo_de(y):
    for n, a, b in RANGOS:
        if a <= y <= b: return n
    return None


def sin_acentos(s):
    return "".join(c for c in unicodedata.normalize("NFD", str(s).lower()) if unicodedata.category(c) != "Mn")


def b64(im, q=90):
    buf = io.BytesIO(); im.convert("RGB").save(buf, "JPEG", quality=q)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def abrir(path, lado):
    im = Image.open(path)
    try: im.draft("RGB", (lado * 2, lado * 2))
    except Exception: pass
    im = im.convert("RGB")
    w, h = im.size; s = lado / max(w, h)
    return im.resize((max(8, round(w * s / 8) * 8), max(8, round(h * s / 8) * 8)), Image.LANCZOS)


def miniatura(im, lado=320):
    im = im.copy(); im.thumbnail((lado, lado)); return b64(im, 80)


def seguro(oid):
    return re.sub(r"[^A-Za-z0-9_.-]", "_", oid)


def clave_de(periodo, lado, pasos):
    return f"colores__{periodo}__{lado}px__{pasos}p__-f"


def catalogo_muestras(data):
    """Catalogo minimo a partir de muestras/pinturas (las 40 obras que trae el repositorio)."""
    lab = pd.read_csv(os.path.join(data, "labels.csv")).set_index("id")
    filas = []
    for ruta in sorted(glob.glob(os.path.join(MUESTRAS, "*", "*.jpg"))):
        oid = os.path.splitext(os.path.basename(ruta))[0].replace("_", ":", 1)
        if oid in lab.index:
            r = lab.loc[oid]
            filas.append(dict(id=oid, title=r["title"], year=int(r["year"]), place="", category="painting", ruta=ruta))
    return pd.DataFrame(filas)


def catalogo_etl(catalog_dir):
    cat = pd.read_csv(os.path.join(catalog_dir, "index", "catalog.csv"))
    cat = cat[cat.image_file.notna() & cat.year.notna()].copy()
    cat["ruta"] = [os.path.join(catalog_dir, p.replace("\\", os.sep), f) for p, f in zip(cat.path, cat.image_file)]
    return cat


class App:
    def __init__(self, a):
        self.a = a
        if a.catalog_dir:
            cat = catalogo_etl(a.catalog_dir)
            if not a.todas_las_categorias: cat = cat[cat.category.isin(SIMULABLES)]
            self.catalogo_csv = os.path.join(a.catalog_dir, "index", "catalog.csv")
        else:
            cat, self.catalogo_csv = catalogo_muestras(a.data), ""
        cat["year"] = cat.year.astype(int)
        cat["periodo"] = cat.year.map(periodo_de)
        cat = cat[cat.periodo.notna()].copy()
        cat["place"] = cat.place.fillna("")
        cat["buscar"] = (cat.id + " " + cat.title.fillna("") + " " + cat.place).map(sin_acentos)
        self.cat = cat.sort_values(["year", "id"]).set_index("id", drop=False)
        print(f"Catálogo: {len(self.cat):,} obras ({'ETL' if a.catalog_dir else 'muestras del repositorio'})", flush=True)
        out = os.path.join(ESTILOS, "outputs")
        self.tr = Transfer(Namespace(data=a.data, judge=os.path.join(out, "resnet18.pt"), judge_meta=os.path.join(out, "resnet18.json"),
                                     n_style=16, size=256, seed=0, steps=400, lr=0.02, content_weight=1.0, style_weight=1e6,
                                     tv_weight=1e-2, judge_weight=0.0))
        meta = json.load(open(os.path.join(out, "cnn.json")))
        self.cnn = make("cnn", len(meta["classes"]))
        self.cnn.load_state_dict(torch.load(os.path.join(out, "cnn.pt"), map_location=DEV)); self.cnn.to(DEV).eval()
        self.cnn_t = T.Compose([T.Resize(224), T.CenterCrop(224), T.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])])
        lab = pd.read_csv(os.path.join(a.data, "labels.csv"))
        self.prof = X.perfiles(a.data, lab, os.path.join(a.data, "perfiles_periodo.json"))
        self.lug = X.lugares(self.catalogo_csv, lab) if self.catalogo_csv else {}
        self.thumbs = {}
        self.jobs, self.q = {}, queue.Queue()
        self.rate = 0.03                                      # segundos por paso (se ajusta con cada trabajo)
        self.ilock = threading.Lock()
        os.makedirs(CACHE, exist_ok=True)
        self.indice = {}
        for f in glob.glob(os.path.join(CACHE, "*", "*.json")):
            try: self._indexar(json.load(open(f, encoding="utf-8")))
            except Exception: pass
        print(f"Simulaciones guardadas: {sum(len(v) for v in self.indice.values())} en {len(self.indice)} obras", flush=True)
        threading.Thread(target=self._worker, daemon=True).start()

    # ---------- catalogo ----------
    def periodos(self):
        return {k: dict(v, id=k, perfil=self.prof.get(k), lugares_catalogo=self.lug.get(k, []),
                        n_catalogo=int((self.cat.periodo == k).sum())) for k, v in PERIODOS.items()}

    def buscar(self, q="", periodo="", cat="", page=0, n=20, solo_gen=False):
        n = n if n in POR_PAGINA else 20
        d = self.cat
        if solo_gen: d = d[d.id.isin(list(self.indice))]
        if periodo: d = d[d.periodo == periodo]
        if cat: d = d[d.category == cat]
        for w in sin_acentos(q).split():
            d = d[d.buscar.str.contains(re.escape(w), regex=True, na=False)]
        tot = len(d); pages = max(1, -(-tot // n)); page = max(0, min(page, pages - 1))
        d = d.iloc[page * n:(page + 1) * n]
        return dict(total=tot, page=page, pages=pages, n=n, items=[dict(
            id=r.id, titulo=str(r.title), anio=int(r.year), categoria=CATS.get(r.category, r.category), periodo=r.periodo,
            generadas=len(self.indice.get(r.id, []))) for r in d.itertuples()])

    def thumb(self, oid):
        if oid not in self.thumbs:
            buf = io.BytesIO(); abrir(self.cat.loc[oid, "ruta"], 180).save(buf, "JPEG", quality=82)
            if len(self.thumbs) > 3000: self.thumbs.clear()
            self.thumbs[oid] = buf.getvalue()
        return self.thumbs[oid]

    # ---------- cache ----------
    def _indexar(self, j):
        p = j["params"]
        e = dict(clave=j["clave"], version=j["version"], modo="colores", periodo=p["periodo"], lado=p["lado"], pasos=p["pasos"],
                 fecha=j["fecha"], segundos=j["t"]["segundos"])
        with self.ilock:
            L = self.indice.setdefault(p["id"], [])
            L[:] = [x for x in L if not (x["clave"] == e["clave"] and x["version"] == e["version"])] + [e]
            L.sort(key=lambda x: x["fecha"], reverse=True)

    def guardadas(self, oid):
        return self.indice.get(oid, [])

    def versiones(self, oid, clave):
        return sorted(x["version"] for x in self.indice.get(oid, []) if x["clave"] == clave)

    def resultado(self, oid, clave, v=None):
        vs = self.versiones(oid, clave)
        if not vs: raise KeyError(clave)
        v = int(v) if v else vs[-1]
        base = os.path.join(CACHE, seguro(oid), f"{clave}__v{v}")
        j = json.load(open(base + ".json", encoding="utf-8"))
        r = self.cat.loc[oid]
        j["obra"]["img"] = b64(abrir(r.ruta, j["params"]["lado"]))
        j["t"]["img"] = b64(Image.open(base + ".jpg"), 92)
        j["t"]["archivo_url"] = f"/img/{seguro(oid)}/{clave}__v{v}.jpg"
        j["versiones"] = vs
        return j

    # ---------- trabajos ----------
    def pedir(self, b):
        oid = b["id"]
        if oid not in self.cat.index: raise KeyError(oid)
        periodo = b.get("periodo", "")
        if periodo not in PERIODOS: raise ValueError("Elige un período destino.")
        if periodo == self.cat.loc[oid, "periodo"]:
            raise ValueError(f"Esta obra ya es del {PERIODOS[periodo]['nombre']}: no hay nada que cambiar. Elige otro período destino.")
        lado = int(b.get("lado", 384)); lado = lado if lado in LADOS else 384
        pasos = int(b.get("pasos", 400)); pasos = pasos if pasos in PASOS else 400
        clave = clave_de(periodo, lado, pasos)
        if not b.get("regenerar") and self.versiones(oid, clave):
            return dict(cache=True, resultado=self.resultado(oid, clave))
        for j in self.jobs.values():   # el mismo pedido ya esta en la cola o corriendo
            if j["estado"] in ("en_cola", "corriendo") and j["params"]["id"] == oid and j["clave"] == clave:
                return dict(job=j["id"])
        jid = uuid.uuid4().hex[:12]
        etapas = [("paleta", "Aplicando la paleta y la textura (Gatys)", pasos)]
        self.jobs[jid] = dict(id=jid, clave=clave, estado="en_cola", params=dict(id=oid, periodo=periodo, lado=lado, pasos=pasos),
                              etapas=etapas, etapa=0, paso=0, total=pasos, nota="", creado=time.time(), inicio=None, fin=None,
                              preview=None, preview_v=0, resultado=None, error=None)
        if len(self.jobs) > 60:
            for k in [k for k, j in self.jobs.items() if j["estado"] in ("listo", "error")][:20]: self.jobs.pop(k, None)
        self.q.put(jid)
        return dict(job=jid)

    def estado(self, jid, pv=0):
        j = self.jobs[jid]
        out = {k: j[k] for k in ("id", "estado", "etapa", "paso", "total", "nota", "error", "clave", "preview_v")}
        out["etapas"] = [dict(tipo=t, nombre=n, pasos=p) for t, n, p in j["etapas"]]
        pend = [x for x in self.jobs.values() if x["estado"] == "en_cola" and x["creado"] < j["creado"]]
        out["en_cola_antes"] = len(pend) + sum(1 for x in self.jobs.values() if x["estado"] == "corriendo" and x["id"] != jid)
        now = time.time()
        out["transcurrido"] = round(now - (j["inicio"] or j["creado"]), 1)
        if j["estado"] == "corriendo":
            out["restante"] = round((j["total"] - j["paso"]) * self.rate, 1)
        if j["preview"] and j["preview_v"] > pv: out["preview"] = j["preview"]
        if j["estado"] == "listo": out["resultado"] = j["resultado"]
        return out

    def _worker(self):
        while True:
            jid = self.q.get()
            j = self.jobs.get(jid)
            if not j: continue
            try:
                j["estado"], j["inicio"] = "corriendo", time.time()
                j["resultado"] = self._correr(j)
                j["estado"] = "listo"
            except Exception as e:
                traceback.print_exc(); j["estado"], j["error"] = "error", str(e)
            j["fin"] = time.time()

    def _avance(self, j, paso, preview=None):
        j["paso"] = paso
        if preview is not None: j["preview"] = preview; j["preview_v"] += 1

    def _paleta(self, j, im, periodo, pasos, sw=1e6, tvw=1e-2):
        """Gatys: ajusta los pixeles para conservar el contenido y acercarse al estilo (matrices Gram) del periodo."""
        tr = self.tr; t0 = time.time()
        content = T.ToTensor()(im).unsqueeze(0).to(DEV)
        G = tr.style_grams(periodo)
        with torch.no_grad(): cf = tr.vgg(norm(content))
        x = content.clone().requires_grad_(True)
        opt = torch.optim.Adam([x], lr=tr.a.lr)
        for step in range(pasos):
            opt.zero_grad()
            f = tr.vgg(norm(x))
            lc = sum(F.mse_loss(f[i], cf[i]) for i in CONTENT_L)
            ls = sum(F.mse_loss(gram(f[i]), G[i]) for i in STYLE_L)
            tv = (x[..., 1:, :] - x[..., :-1, :]).abs().mean() + (x[..., :, 1:] - x[..., :, :-1]).abs().mean()
            (tr.a.content_weight * lc + sw * ls + tvw * tv).backward(); opt.step()
            with torch.no_grad(): x.clamp_(0, 1)
            prev = miniatura(T.ToPILImage()(x.detach()[0].cpu())) if (step % 20 == 19 or step + 1 == pasos) else None
            self._avance(j, step + 1, prev)
        self.rate = 0.7 * self.rate + 0.3 * (time.time() - t0) / max(1, pasos)
        return T.ToPILImage()(x.detach()[0].cpu())

    def _correr(self, j):
        p = j["params"]; oid, periodo = p["id"], p["periodo"]
        r = self.cat.loc[oid]; t0 = time.time()
        vs = self.versiones(oid, j["clave"]); version = (vs[-1] + 1) if vs else 1
        im = abrir(r.ruta, p["lado"])
        self._avance(j, 0, miniatura(im))
        gen = self._paleta(j, im, periodo, p["pasos"])
        secs = time.time() - t0
        res = self._explicar(oid, r, im, gen, periodo)
        res.update(clave=j["clave"], version=version, params=p, fecha=time.strftime("%Y-%m-%d %H:%M:%S"))
        res["t"]["segundos"] = round(secs, 1)
        d = os.path.join(CACHE, seguro(oid)); os.makedirs(d, exist_ok=True)
        nombre = f"{j['clave']}__v{version}"
        gen.save(os.path.join(d, nombre + ".jpg"), quality=95)
        json.dump(res, open(os.path.join(d, nombre + ".json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        self._indexar(res)
        return self.resultado(oid, j["clave"], version)

    # ---------- explicacion y jueces ----------
    def _explicar(self, oid, r, im, gen, periodo):
        es = lambda s: PERIODOS.get(s, {}).get("nombre", s)
        tr = self.tr
        c0, c1 = T.ToTensor()(im).unsqueeze(0).to(DEV), T.ToTensor()(gen.resize(im.size)).unsqueeze(0).to(DEV)
        p0, p1 = tr.judge_probs(c0), tr.judge_probs(c1); ti = tr.classes.index(periodo)
        info = dict(target=periodo, judge_target=periodo, content=oid, source_style=r.periodo,
                    p_target_before=round(p0[ti].item(), 3), p_target_after=round(p1[ti].item(), 3),
                    pred_before=tr.classes[p0.argmax().item()], pred_after=tr.classes[p1.argmax().item()])
        m0, m1 = X.medidas(im), X.medidas(gen)
        e = X.explicar(info, m0, m1, self.prof, es)
        with torch.no_grad():
            q0, q1 = (F.softmax(self.cnn(self.cnn_t(c)), 1)[0] for c in (c0, c1))
        cls = tr.classes
        e["juez"] = (f"Juez de colores (CNN propia, no participa en la generación): veía la original como «{es(cls[q0.argmax().item()])}» "
                     f"y la nueva como «{es(cls[q1.argmax().item()])}». Probabilidad de {es(periodo)}: {q0[ti].item():.0%} → {q1[ti].item():.0%}. "
                     + e["juez"])
        e["modo"] = "Solo colores"
        return dict(obra=dict(id=oid, titulo=str(r.title), anio=int(r.year), categoria=CATS.get(r.category, r.category),
                              periodo=r.periodo, periodo_nombre=es(r.periodo), lugar=str(r.place or ""), medidas=m0),
                    t=dict(target=periodo, modo="colores", medidas=m1, explicacion=e,
                           cnn=dict(antes=round(q0[ti].item(), 3), despues=round(q1[ti].item(), 3)),
                           resnet=dict(antes=info["p_target_before"], despues=info["p_target_after"])))


def handler(app):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a): pass

        def send(self, code, body, ctype="application/json; charset=utf-8"):
            if isinstance(body, (dict, list)): body = json.dumps(body, ensure_ascii=False).encode()
            elif isinstance(body, str): body = body.encode()
            self.send_response(code); self.send_header("Content-Type", ctype)
            self.send_header("Cache-Control", "no-store" if "json" in ctype or "html" in ctype else "max-age=86400")
            self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

        def do_GET(self):
            u = urlparse(self.path); q = {k: v[0] for k, v in parse_qs(u.query).items()}
            try:
                if u.path == "/":
                    return self.send(200, open(os.path.join(HERE, "index.html"), encoding="utf-8").read(), "text/html; charset=utf-8")
                if u.path == "/api/periodos": return self.send(200, app.periodos())
                if u.path == "/api/categorias":
                    return self.send(200, CATS if app.a.todas_las_categorias else {k: CATS[k] for k in SIMULABLES})
                if u.path == "/api/buscar":
                    return self.send(200, app.buscar(q.get("q", ""), q.get("periodo", ""), q.get("cat", ""), int(q.get("page", 0)),
                                                     int(q.get("n", 20)), q.get("solo_gen") == "1"))
                if u.path == "/api/guardadas": return self.send(200, app.guardadas(q["id"]))
                if u.path == "/api/resultado": return self.send(200, app.resultado(q["id"], q["clave"], q.get("v")))
                if u.path == "/api/trabajo": return self.send(200, app.estado(q["job"], int(q.get("pv", 0))))
                if u.path.startswith("/thumb/"): return self.send(200, app.thumb(unquote(u.path[7:])), "image/jpeg")
                if u.path.startswith("/img/"):
                    f = os.path.normpath(os.path.join(CACHE, unquote(u.path[5:])))
                    if not f.startswith(CACHE + os.sep) or not f.endswith(".jpg") or not os.path.exists(f): raise KeyError(f)
                    return self.send(200, open(f, "rb").read(), "image/jpeg")
                self.send(404, {"error": "no existe"})
            except KeyError:
                self.send(404, {"error": "no encontrado"})
            except Exception as e:
                traceback.print_exc(); self.send(500, {"error": str(e)})

        def do_POST(self):
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
                if urlparse(self.path).path == "/api/generar": return self.send(200, app.pedir(body))
                self.send(404, {"error": "no existe"})
            except KeyError as e:
                self.send(400, {"error": f"no encontrado: {e}"})
            except ValueError as e:
                self.send(400, {"error": str(e)})
            except Exception as e:
                traceback.print_exc(); self.send(500, {"error": str(e)})
    return H


def selftest(app):
    """Busca, genera una simulacion de colores (256 px, rapido), verifica el cache y la regeneracion."""
    r = app.buscar(""); print("obras:", r["total"], [i["titulo"] for i in r["items"][:3]], flush=True)
    oid = app.buscar("", periodo="01_azul")["items"][0]["id"]

    def esperar(res):
        if "resultado" in res: return res["resultado"], True
        jid = res["job"]
        while app.jobs[jid]["estado"] in ("en_cola", "corriendo"):
            s = app.estado(jid)
            print(f"   paso {s['paso']}/{s['total']} · {s['transcurrido']} s · preview v{s['preview_v']}", flush=True)
            time.sleep(1)
        if app.jobs[jid]["estado"] == "error": raise SystemExit("ERROR: " + app.jobs[jid]["error"])
        return app.jobs[jid]["resultado"], False

    pedido = dict(id=oid, periodo="07_surrealista", lado=256, pasos=250)
    t0 = time.time(); res, cache = esperar(app.pedir(pedido)); e = res["t"]["explicacion"]
    print(f"{oid} -> 07_surrealista: v{res['version']} cache={cache} {time.time() - t0:.1f} s · juez CNN {res['t']['cnn']['antes']:.0%} → "
          f"{res['t']['cnn']['despues']:.0%}\n   {e['resumen']}", flush=True)
    t0 = time.time(); res, cache = esperar(app.pedir(pedido))
    print(f"de nuevo: cache={cache} en {time.time() - t0:.2f} s (debe ser True y rapido)", flush=True)
    res, cache = esperar(app.pedir(dict(pedido, regenerar=True)))
    print(f"regenerar: version {res['version']} versiones {res['versiones']}", flush=True)
    print("guardadas de la obra:", [(x["periodo"], x["version"]) for x in app.guardadas(oid)], flush=True)
    print("AUTOPRUEBA OK", flush=True)


def datos_estilos(pedido):
    """Dataset de estilos a usar: el indicado, el completo si tiene imagenes, o la muestra de demostracion."""
    if pedido: return os.path.abspath(pedido)
    completo, muestra = os.path.join(ESTILOS, "data", "styles"), os.path.join(ESTILOS, "data", "muestra")
    if os.path.isdir(os.path.join(completo, "train")): return completo
    if os.path.exists(os.path.join(muestra, "labels.csv")): return muestra
    raise SystemExit("No hay imágenes de estilo. Corre demo\\armar_muestra.bat (dataset de demostración) o arma el dataset completo "
                     "(ver README, paso 2).")


def main():
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass
    p = argparse.ArgumentParser()
    p.add_argument("--catalog-dir", default="", help="carpeta data del ETL; si no se indica, se usa picasso-ai-cenfotect-main/data si existe, o las muestras")
    p.add_argument("--data", default="", help="dataset de estilos (por defecto el completo o, si falta, picasso-estilos/data/muestra)")
    p.add_argument("--port", type=int, default=8767)
    p.add_argument("--selftest", action="store_true")
    p.add_argument("--todas-las-categorias", action="store_true", help="incluir dibujos, grabados, ceramica, etc. (solo con catálogo del ETL)")
    a = p.parse_args()
    a.data = datos_estilos(a.data)
    if not a.catalog_dir:
        c = os.path.join(PROY, "picasso-ai-cenfotect-main", "data")
        if os.path.exists(os.path.join(c, "index", "catalog.csv")): a.catalog_dir = c
    print("Dataset de estilos:", a.data, flush=True)
    app = App(a)
    if a.selftest: return selftest(app)
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), handler(app))
    print(f"Simulador de colores listo: http://127.0.0.1:{a.port}  (cierra esta ventana para detenerlo)", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
