"""LSTM forecaster training (development phase P3) with the persistence gate.

Gate G3: the LSTM must beat the naive persistence baseline before it is
allowed into the advisory path; otherwise the habitat fallback carries the
catch composite on its own.

Input sequences are (seq_len, 6) arrays of gridded features
[sst, sst_anomaly, chlorophyll_a, wind_u, wind_v, current_speed] with a
target aggregation index in [0, 1] derived from occurrence density.

Usage:
    python train/train_forecaster.py --sequences data/sequences.npz
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from parasail.config import load_config               # noqa: E402
from parasail.models.forecaster import LSTMTendency    # noqa: E402


def persistence_baseline(x: torch.Tensor) -> torch.Tensor:
    """Predict the target equals the last observed value of the 0th channel
    (a normalised aggregation proxy). The bar the LSTM must clear."""
    return x[:, -1, 0]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sequences", required=True, type=Path)
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--out", type=Path, default=Path("artifacts/lstm_tendency.pt"))
    args = ap.parse_args()

    cfg = load_config()
    fc = cfg.models["forecaster"]

    blob = np.load(args.sequences)
    X = torch.tensor(blob["x"], dtype=torch.float32)     # (N, seq_len, F)
    y = torch.tensor(blob["y"], dtype=torch.float32)     # (N,)
    n_train = int(0.8 * len(X))
    train = DataLoader(TensorDataset(X[:n_train], y[:n_train]),
                       batch_size=64, shuffle=True)
    val_x, val_y = X[n_train:], y[n_train:]

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = LSTMTendency(hidden=fc["hidden"], layers=fc["layers"],
                         horizon=fc["horizon_steps"]).to(device)
    optim = torch.optim.Adam(model.parameters(), lr=1e-3)
    loss_fn = nn.BCELoss()

    for epoch in range(1, args.epochs + 1):
        model.train()
        running = 0.0
        for xb, yb in train:
            xb, yb = xb.to(device), yb.to(device)
            optim.zero_grad()
            loss = loss_fn(model(xb), yb)
            loss.backward()
            optim.step()
            running += loss.item()
        print(f"epoch {epoch:02d}/{args.epochs}  bce={running / len(train):.4f}")

    # ---- gate G3: beat naive persistence on the validation split ---------
    model.eval()
    with torch.no_grad():
        lstm_mae = (model(val_x.to(device)).cpu() - val_y).abs().mean().item()
        pers_mae = (persistence_baseline(val_x) - val_y).abs().mean().item()
    print(f"validation MAE - lstm={lstm_mae:.4f}  persistence={pers_mae:.4f}")
    if lstm_mae >= pers_mae:
        print("GATE G3 FAILED: LSTM does not beat persistence; "
              "keep the habitat fallback in the advisory path")
        sys.exit(1)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), args.out)
    print(f"gate G3 passed; checkpoint saved to {args.out}")


if __name__ == "__main__":
    main()
