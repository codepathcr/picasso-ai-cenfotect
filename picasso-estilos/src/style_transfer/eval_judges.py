"""Evalua las transferencias con dos jueces: ResNet18 (usada para guiar en la variante 'juez')
y la CNN propia (independiente: nunca participa en la generacion).
python -m src.style_transfer.eval_judges --folders outputs/transfer_v2 outputs/transfer_v2_juez"""
import argparse, json, torch, torch.nn.functional as F, pandas as pd
from PIL import Image
from src.data.dataset import tfms
from src.models.models import make

DEV = "cuda" if torch.cuda.is_available() else "cpu"


def load_judge(name):
    meta = json.load(open(f"outputs/{name}.json"))
    m = make(name, len(meta["classes"])); m.load_state_dict(torch.load(f"outputs/{name}.pt", map_location=DEV))
    return m.to(DEV).eval(), meta["classes"]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--folders", nargs="+", default=["outputs/transfer_v2", "outputs/transfer_v2_juez"])
    p.add_argument("--data", default="data/styles")
    a = p.parse_args()
    judges = {n: load_judge(n) for n in ("resnet18", "cnn")}
    t = tfms(False)
    lab = pd.read_csv(f"{a.data}/labels.csv").set_index("id")
    prob = lambda m, path: F.softmax(m(t(Image.open(path).convert("RGB")).unsqueeze(0).to(DEV)), 1)[0].cpu()
    rows = []
    with torch.no_grad():
        for folder in a.folders:
            for r in json.load(open(f"{folder}/results.json")):
                tgt = r["target"].split(",")[0].split(":")[0]
                if tgt == r["source_style"]: continue          # misma epoca: no es transferencia
                orig = f"{a.data}/{lab.loc[r['content'], 'file']}"
                gen = f"{folder}/{r['file']}"
                row = dict(variante=folder.split("/")[-1], content=r["content"], target=r["target"])
                for n, (m, cl) in judges.items():
                    i = cl.index(tgt); p0, p1 = prob(m, orig), prob(m, gen)
                    row[f"{n}_antes"] = round(p0[i].item(), 3); row[f"{n}_despues"] = round(p1[i].item(), 3)
                    row[f"{n}_acierta"] = bool(p1.argmax().item() == i)
                rows.append(row)
    df = pd.DataFrame(rows)
    pd.set_option("display.width", 200)
    print(df.to_string())
    s = df.groupby("variante").agg(n=("content", "size"),
                                   resnet_p=("resnet18_despues", "mean"), resnet_acierta=("resnet18_acierta", "mean"),
                                   cnn_p_antes=("cnn_antes", "mean"), cnn_p=("cnn_despues", "mean"),
                                   cnn_acierta=("cnn_acierta", "mean")).round(3)
    print("\nRESUMEN\n" + s.to_string())
    df.to_csv("outputs/eval_jueces.csv", index=False)
    s.to_csv("outputs/eval_jueces_resumen.csv")


if __name__ == "__main__":
    main()
