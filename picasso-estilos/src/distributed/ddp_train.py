"""Entrenamiento distribuido (paralelismo de datos) de ResNet18 con torch.distributed.
python -m src.distributed.ddp_train --world 1|2|4 --epochs 8
Cada proceso = un 'worker' con su porcion de datos (DistributedSampler); los gradientes se promedian
(all-reduce) en cada paso. Backend gloo (nccl no existe en Windows). Todos los workers comparten la GPU."""
import argparse, json, os, time, torch, torch.nn as nn
import torch.distributed as dist, torch.multiprocessing as mp
from torch.nn.parallel import DistributedDataParallel as DDP
from torch.utils.data import DataLoader, DistributedSampler
from src.data.dataset import Styles
from src.models.models import make

def worker(rank, a):
    init = "file:///" + os.path.abspath(f"outputs/ddp_init_{a.world}").replace("\\", "/")
    dist.init_process_group("gloo", init_method=init, rank=rank, world_size=a.world)
    dev = "cuda"; torch.manual_seed(0)
    tr, va, te = (Styles(a.data, s) for s in ("train", "val", "test"))
    n = len(tr.classes)
    cnt = torch.bincount(torch.tensor(tr.y), minlength=n).float()
    lossf = nn.CrossEntropyLoss(weight=(cnt.sum() / (n * cnt)).to(dev))
    smp = DistributedSampler(tr, a.world, rank, shuffle=True)
    bs = a.batch // a.world                      # batch global constante = a.batch
    ltr = DataLoader(tr, bs, sampler=smp, num_workers=1, persistent_workers=True)
    m = DDP(make("resnet18", n).to(dev))
    opt = torch.optim.AdamW(m.parameters(), lr=a.lr * 0.5, weight_decay=1e-4)
    t0 = time.time(); hist = []
    for e in range(a.epochs):
        smp.set_epoch(e); m.train(); L = 0
        for x, y in ltr:
            opt.zero_grad(); loss = lossf(m(x.to(dev)), y.to(dev)); loss.backward(); opt.step(); L += loss.item()
        hist.append(dict(epoch=e + 1, loss=L / len(ltr), t=time.time() - t0))
        if rank == 0: print(hist[-1], flush=True)
    secs = time.time() - t0
    if rank == 0:
        net = m.module   # evaluar sin DDP: evita colectivas (sync de buffers) mientras los otros esperan
        def ev(ds):
            net.eval(); c = t = 0
            with torch.no_grad():
                for x, y in DataLoader(ds, 64, num_workers=1):
                    c += (net(x.to(dev)).argmax(1).cpu() == y).sum().item(); t += len(y)
            return c / t
        r = dict(world=a.world, epochs=a.epochs, train_secs=secs, val_acc=ev(va), test_acc=ev(te), hist=hist)
        print("RESULT", {k: v for k, v in r.items() if k != "hist"}, flush=True)
        json.dump(r, open(f"outputs/ddp_{a.world}.json", "w"), indent=1)
    dist.barrier(); dist.destroy_process_group()

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--world", type=int, default=1); p.add_argument("--epochs", type=int, default=8)
    p.add_argument("--batch", type=int, default=64); p.add_argument("--lr", type=float, default=1e-3)
    p.add_argument("--data", default="data/styles")
    a = p.parse_args(); os.makedirs("outputs", exist_ok=True)
    mp.spawn(worker, args=(a,), nprocs=a.world, join=True)
