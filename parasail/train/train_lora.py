"""LoRA fine-tuning for the species classifier (development phase P4).

Trains low-rank adapters (r = 8, query/value projections, all 12 encoder
blocks) on a folder-structured image dataset:

    data/species_images/
        Sardinella_longiceps/*.jpg
        Rastrelliger_kanagurta/*.jpg
        ...

Gate G4: training must converge within the GPU memory budget - the printed
trainable-parameter report is the acceptance evidence (0.29M / 85.8M = 0.34%
for ViT-B/16).

Usage:
    python train/train_lora.py --data data/species_images --epochs 10
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import torch
from torch.utils.data import DataLoader
from torchvision import datasets, transforms

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from parasail.config import load_config                      # noqa: E402
from parasail.models.classifier import build_lora_classifier  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", required=True, type=Path,
                    help="root folder with one sub-folder per species")
    ap.add_argument("--epochs", type=int, default=10)
    ap.add_argument("--batch-size", type=int, default=32)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--out", type=Path, default=Path("artifacts/lora_adapter"))
    args = ap.parse_args()

    cfg = load_config()
    m = cfg.models

    train_tf = transforms.Compose([
        transforms.RandomResizedCrop(224, scale=(0.7, 1.0)),
        transforms.RandomHorizontalFlip(),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.5, 0.5, 0.5], std=[0.5, 0.5, 0.5]),
    ])
    dataset = datasets.ImageFolder(str(args.data), transform=train_tf)
    id2label = {i: name for name, i in dataset.class_to_idx.items()}
    loader = DataLoader(dataset, batch_size=args.batch_size, shuffle=True,
                        num_workers=4, pin_memory=True)

    model, _ = build_lora_classifier(
        m["classifier"], num_classes=len(id2label), lora_cfg=m["lora"])
    model.print_trainable_parameters()   # gate G4 evidence

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device)
    optim = torch.optim.AdamW(
        (p for p in model.parameters() if p.requires_grad), lr=args.lr)
    loss_fn = torch.nn.CrossEntropyLoss()

    for epoch in range(1, args.epochs + 1):
        model.train()
        running, seen = 0.0, 0
        for images, labels in loader:
            images, labels = images.to(device), labels.to(device)
            optim.zero_grad()
            loss = loss_fn(model(pixel_values=images).logits, labels)
            loss.backward()
            optim.step()
            running += loss.item() * labels.size(0)
            seen += labels.size(0)
        print(f"epoch {epoch:02d}/{args.epochs}  loss={running / seen:.4f}")

    args.out.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(args.out))
    (args.out / "id2label.json").write_text(
        __import__("json").dumps(id2label), encoding="utf-8")
    print(f"adapter saved to {args.out} - set models.classifier_adapter "
          f"in config.yaml to '{args.out}'")


if __name__ == "__main__":
    main()
