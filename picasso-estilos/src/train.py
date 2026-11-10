"""python -m src.train --model mlp|cnn|resnet18 --epochs 20  (guarda outputs/<model>.pt y .json)"""
import argparse, json, time, os, torch, torch.nn as nn
from torch.utils.data import DataLoader
from src.data.dataset import Styles
from src.models.models import make

def run(a):
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    tr, va, te = (Styles(a.data, s) for s in ("train", "val", "test"))
    n = len(tr.classes)
    cnt = torch.bincount(torch.tensor(tr.y), minlength=n).float()
    w = (cnt.sum() / (n * cnt)).to(dev)   # pesos por clase (desbalance)
    mk = lambda ds, sh: DataLoader(ds, a.batch, shuffle=sh, num_workers=a.workers, pin_memory=True)
    ltr, lva, lte = mk(tr, True), mk(va, False), mk(te, False)
    m = make(a.model, n).to(dev)
    opt = torch.optim.AdamW(m.parameters(), lr=a.lr, weight_decay=1e-4)
    sch = torch.optim.lr_scheduler.CosineAnnealingLR(opt, a.epochs)
    lossf = nn.CrossEntropyLoss(weight=w)
    def ev(l):
        m.eval(); c = t = 0
        with torch.no_grad():
            for x, y in l:
                p = m(x.to(dev)).argmax(1).cpu(); c += (p == y).sum().item(); t += len(y)
        return c / t
    best, hist = 0, []
    os.makedirs("outputs", exist_ok=True)
    for e in range(a.epochs):
        m.train(); t0 = time.time(); L = 0
        for x, y in ltr:
            x, y = x.to(dev), y.to(dev)
            opt.zero_grad(); loss = lossf(m(x), y); loss.backward(); opt.step(); L += loss.item()
        sch.step(); acc = ev(lva)
        hist.append(dict(epoch=e+1, loss=L/len(ltr), val_acc=acc, secs=time.time()-t0))
        print(hist[-1], flush=True)
        if acc > best: best = acc; torch.save(m.state_dict(), f"outputs/{a.model}.pt")
    m.load_state_dict(torch.load(f"outputs/{a.model}.pt")); tacc = ev(lte)
    print(f"TEST acc {a.model}: {tacc:.3f} (mejor val {best:.3f})")
    json.dump(dict(model=a.model, classes=tr.classes, test_acc=tacc, best_val=best, hist=hist),
              open(f"outputs/{a.model}.json", "w"), indent=1)

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--model", default="resnet18"); p.add_argument("--data", default="data/styles")
    p.add_argument("--epochs", type=int, default=20); p.add_argument("--batch", type=int, default=64)
    p.add_argument("--lr", type=float, default=1e-3); p.add_argument("--workers", type=int, default=4)
    run(p.parse_args())
