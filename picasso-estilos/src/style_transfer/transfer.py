"""Transferencia de estilo por periodo (Gatys et al. 2016) + evaluacion con el juez ResNet18.

El 'estilo de un periodo' = promedio de matrices Gram (VGG19) de N obras de ese periodo (train).
Se pueden mezclar periodos como influencias:  --target "08_guerra:0.7,01_azul:0.3"
Opcional: --judge-weight > 0 agrega guia del clasificador (empuja la imagen hacia la clase destino).

Uso:
  python -m src.style_transfer.transfer --content OPP.03_026 --target 04_cubismo_analitico
  python -m src.style_transfer.transfer --demo        (grilla obras x periodos + results.json)
"""
import argparse, json, os, random
import pandas as pd, torch, torch.nn as nn, torch.nn.functional as F
from PIL import Image, ImageDraw
from torchvision import models, transforms as T
from src.models.models import make

DEV = "cuda" if torch.cuda.is_available() else "cpu"
MEAN = torch.tensor([0.485, 0.456, 0.406], device=DEV).view(1, 3, 1, 1)
STD = torch.tensor([0.229, 0.224, 0.225], device=DEV).view(1, 3, 1, 1)
STYLE_L, CONTENT_L = [1, 6, 11, 20, 29], [22]          # relu1_1..relu5_1, relu4_2
norm = lambda x: (x - MEAN) / STD


class VGGFeat(nn.Module):
    def __init__(self):
        super().__init__()
        f = models.vgg19(weights=models.VGG19_Weights.DEFAULT).features[:30].eval()
        for i, m in enumerate(f):
            if isinstance(m, nn.ReLU): f[i] = nn.ReLU(inplace=False)
            if isinstance(m, nn.MaxPool2d): f[i] = nn.AvgPool2d(2)   # avg-pool da texturas mas suaves
        for p in f.parameters(): p.requires_grad_(False)
        self.f = f.to(DEV)

    def forward(self, x):
        out = {}
        for i, m in enumerate(self.f):
            x = m(x)
            if i in STYLE_L or i in CONTENT_L: out[i] = x
        return out


def gram(x):
    b, c, h, w = x.shape
    f = x.reshape(b, c, h * w)
    return (f @ f.transpose(1, 2) / (c * h * w)).mean(0, keepdim=True)


def load(path, size):
    im = Image.open(path).convert("RGB")
    return T.Compose([T.Resize(size), T.CenterCrop(size), T.ToTensor()])(im).unsqueeze(0).to(DEV)


def parse_target(s):
    out = []
    for part in s.split(","):
        name, _, w = part.partition(":")
        out.append((name.strip(), float(w) if w else 1.0))
    tot = sum(w for _, w in out)
    return [(n, w / tot) for n, w in out]


class Transfer:
    def __init__(self, a):
        self.a = a
        self.lab = pd.read_csv(f"{a.data}/labels.csv")
        sat = f"{a.data}/saturation.csv"      # generado al medir color; B/N = saturacion media < 0.08
        self.lab["color"] = (pd.read_csv(sat).set_index("id").loc[self.lab["id"], "sat"].values >= 0.08
                             if os.path.exists(sat) else True)
        self.vgg = VGGFeat()
        meta = json.load(open(a.judge_meta))
        self.classes = meta["classes"]
        self.judge = make("resnet18", len(self.classes))
        self.judge.load_state_dict(torch.load(a.judge, map_location=DEV))
        self.judge.to(DEV).eval()
        for p in self.judge.parameters(): p.requires_grad_(False)
        self._gcache = {}

    def style_grams(self, style):
        if style not in self._gcache:
            rows = self.lab[(self.lab["split"] == "train") & (self.lab["style"] == style) & self.lab["color"]]
            files = rows["file"].sample(min(self.a.n_style, len(rows)), random_state=self.a.seed)
            x = torch.cat([load(f"{self.a.data}/{f}", self.a.size) for f in files])
            with torch.no_grad():
                feats = self.vgg(norm(x))
            self._gcache[style] = {i: gram(feats[i]) for i in STYLE_L}
        return self._gcache[style]

    def judge_probs(self, x):
        with torch.no_grad():
            return F.softmax(self.judge(norm(x)), 1)[0]

    def run(self, content, target):
        a = self.a
        mix = parse_target(target)
        G = {i: sum(w * self.style_grams(n)[i] for n, w in mix) for i in STYLE_L}
        main = max(mix, key=lambda t: t[1])[0]
        tidx = self.classes.index(main)
        with torch.no_grad():
            cf = self.vgg(norm(content))
        x = content.clone().requires_grad_(True)
        opt = torch.optim.Adam([x], lr=a.lr)
        for step in range(a.steps):
            opt.zero_grad()
            f = self.vgg(norm(x))
            lc = sum(F.mse_loss(f[i], cf[i]) for i in CONTENT_L)
            ls = sum(F.mse_loss(gram(f[i]), G[i]) for i in STYLE_L)
            tv = (x[..., 1:, :] - x[..., :-1, :]).abs().mean() + (x[..., :, 1:] - x[..., :, :-1]).abs().mean()
            loss = a.content_weight * lc + a.style_weight * ls + a.tv_weight * tv
            if a.judge_weight > 0:
                loss = loss + a.judge_weight * F.cross_entropy(self.judge(norm(x)), torch.tensor([tidx], device=DEV))
            loss.backward(); opt.step()
            with torch.no_grad(): x.clamp_(0, 1)
        p0, p1 = self.judge_probs(content), self.judge_probs(x.detach())
        info = dict(target=target, judge_target=main,
                    p_target_before=round(p0[tidx].item(), 3), p_target_after=round(p1[tidx].item(), 3),
                    pred_before=self.classes[p0.argmax().item()], pred_after=self.classes[p1.argmax().item()])
        return x.detach(), info


def to_pil(x):
    return T.ToPILImage()(x[0].cpu())


def grid(rows, header, size, path):
    cols = len(header); pad = 22
    g = Image.new("RGB", (cols * size, len(rows) * (size + pad) + pad), "white")
    d = ImageDraw.Draw(g)
    for c, h in enumerate(header): d.text((c * size + 4, 4), h[:34], fill="black")
    for r, cells in enumerate(rows):
        y = pad + r * (size + pad)
        for c, (im, cap) in enumerate(cells):
            g.paste(im.resize((size, size)), (c * size, y))
            d.text((c * size + 4, y + size + 4), cap[:40], fill="black")
    g.save(path)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--data", default="data/styles")
    p.add_argument("--judge", default="outputs/resnet18.pt"); p.add_argument("--judge-meta", default="outputs/resnet18.json")
    p.add_argument("--content", help="id de obra (OPP.03_026) o ruta a imagen")
    p.add_argument("--target", help="periodo destino o mezcla 'a:0.7,b:0.3'")
    p.add_argument("--demo", action="store_true")
    p.add_argument("--size", type=int, default=256); p.add_argument("--steps", type=int, default=400)
    p.add_argument("--lr", type=float, default=0.02); p.add_argument("--n-style", type=int, default=16)
    p.add_argument("--content-weight", type=float, default=1.0); p.add_argument("--style-weight", type=float, default=1e6)
    p.add_argument("--tv-weight", type=float, default=1e-2); p.add_argument("--judge-weight", type=float, default=0.0)
    p.add_argument("--seed", type=int, default=0); p.add_argument("--out", default="outputs/transfer")
    p.add_argument("--color-content", action="store_true", help="demo: usar solo obras a color como contenido")
    a = p.parse_args()
    random.seed(a.seed); torch.manual_seed(a.seed); os.makedirs(a.out, exist_ok=True)
    tr = Transfer(a)

    def content_from(cid):
        if os.path.exists(cid): return load(cid, a.size), os.path.basename(cid), "?"
        row = tr.lab[tr.lab["id"].str.replace(":", "_") == cid.replace(":", "_")].iloc[0]
        return load(f"{a.data}/{row.file}", a.size), row.id, row["style"]

    if not a.demo:
        c, cid, src = content_from(a.content)
        x, info = tr.run(c, a.target)
        name = f"{cid.replace(':', '_')}__to__{a.target.replace(':', '-').replace(',', '+')}.jpg"
        to_pil(x).save(f"{a.out}/{name}", quality=95)
        info.update(content=cid, source_style=src, file=name); print(info)
        return

    # DEMO: obras de prueba de 3 periodos x 4 destinos (+1 mezcla de influencias)
    sources = ["01_azul", "04_cubismo_analitico", "09_tardio"]
    targets = ["01_azul", "04_cubismo_analitico", "07_surrealista", "09_tardio", "08_guerra:0.6,01_azul:0.4"]
    test = tr.lab[(tr.lab["split"] == "test") & (tr.lab["color"] if a.color_content else True)]
    results, rows = [], []
    for s in sources:
        r = test[test["style"] == s].sample(1, random_state=a.seed).iloc[0]
        c = load(f"{a.data}/{r.file}", a.size)
        p0 = tr.judge_probs(c)
        cells = [(to_pil(c), f"{r.id} ({s}) juez:{tr.classes[p0.argmax().item()][3:]}")]
        for t in targets:
            x, info = tr.run(c, t)
            name = f"{r.id.replace(':', '_')}__to__{t.replace(':', '-').replace(',', '+')}.jpg"
            to_pil(x).save(f"{a.out}/{name}", quality=95)
            info.update(content=r.id, source_style=s, file=name); results.append(info); print(info, flush=True)
            cells.append((to_pil(x), f"p={info['p_target_before']:.2f}->{info['p_target_after']:.2f}"))
        rows.append(cells)
    grid(rows, ["original"] + targets, a.size, f"{a.out}/demo_grid.jpg")
    json.dump(results, open(f"{a.out}/results.json", "w"), indent=1)
    df = pd.DataFrame(results)
    df["sube"] = df.p_target_after > df.p_target_before
    print(df[["content", "source_style", "target", "p_target_before", "p_target_after", "pred_after"]].to_string())
    main_t = df.target.str.split(":").str[0]
    print("Juez sube prob. del destino:", int(df.sube.sum()), "/", len(df),
          "| juez clasifica como destino:", int((df.pred_after == main_t).sum()), "/", len(df))


if __name__ == "__main__":
    main()
