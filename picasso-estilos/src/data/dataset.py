import pandas as pd, torch
from PIL import Image
from torch.utils.data import Dataset
from torchvision import transforms as T

MEAN, STD = [0.485, 0.456, 0.406], [0.229, 0.224, 0.225]

def tfms(train, size=224):
    if train:
        return T.Compose([T.RandomResizedCrop(size, scale=(0.6, 1.0)), T.RandomHorizontalFlip(),
                          T.ColorJitter(0.2, 0.2, 0.1), T.ToTensor(), T.Normalize(MEAN, STD)])
    return T.Compose([T.Resize(size), T.CenterCrop(size), T.ToTensor(), T.Normalize(MEAN, STD)])

class Styles(Dataset):
    def __init__(self, root, split, size=224, train_aug=None):
        d = pd.read_csv(f"{root}/labels.csv")
        self.classes = sorted(d["style"].unique())
        self.d = d[d.split == split].reset_index(drop=True)
        self.root = root
        self.t = tfms(split == "train" if train_aug is None else train_aug, size)
        self.y = [self.classes.index(s) for s in self.d["style"]]
    def __len__(self): return len(self.d)
    def __getitem__(self, i):
        return self.t(Image.open(f"{self.root}/{self.d.file[i]}").convert("RGB")), self.y[i]
