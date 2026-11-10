import torch.nn as nn
from torchvision import models

def make(name, n_classes, size=224):
    if name == "mlp":      # perceptron multicapa sobre pixeles (baseline)
        s = 64
        return nn.Sequential(nn.AdaptiveAvgPool2d(s), nn.Flatten(), nn.Linear(3*s*s, 512), nn.ReLU(), nn.Dropout(0.3),
                             nn.Linear(512, 128), nn.ReLU(), nn.Linear(128, n_classes))
    if name == "cnn":      # CNN propia desde cero
        def b(i, o): return nn.Sequential(nn.Conv2d(i, o, 3, padding=1), nn.BatchNorm2d(o), nn.ReLU(), nn.MaxPool2d(2))
        return nn.Sequential(b(3, 32), b(32, 64), b(64, 128), b(128, 256), nn.AdaptiveAvgPool2d(1), nn.Flatten(),
                             nn.Dropout(0.4), nn.Linear(256, n_classes))
    if name == "resnet18": # transfer learning
        m = models.resnet18(weights=models.ResNet18_Weights.DEFAULT)
        m.fc = nn.Linear(m.fc.in_features, n_classes)
        return m
    raise ValueError(name)
