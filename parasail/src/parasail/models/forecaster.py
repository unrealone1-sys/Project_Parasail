"""LSTM movement-tendency model (development phase P3).

A two-layer LSTM (hidden size 128) over 24 hourly steps of gridded
environmental features, trained for data-rich species. Output is a
normalised aggregation / movement-tendency index Chat in [0, 1] consumed by
the catch composite. The naive-persistence baseline in train_forecaster.py
is the gate this model must beat before deployment.
"""
from __future__ import annotations

import torch
import torch.nn as nn

N_FEATURES = 6          # sst, sst_anomaly, chlorophyll_a, wind_u, wind_v, current
HORIZON = 24


class LSTMTendency(nn.Module):
    def __init__(self, n_features: int = N_FEATURES, hidden: int = 128,
                 layers: int = 2, horizon: int = HORIZON):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=n_features, hidden_size=hidden,
            num_layers=layers, batch_first=True, dropout=0.1,
        )
        self.head = nn.Sequential(
            nn.Linear(hidden, 64), nn.ReLU(), nn.Linear(64, 1), nn.Sigmoid(),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """x: (batch, seq_len, n_features) -> (batch,) tendency index."""
        out, _ = self.lstm(x)
        return self.head(out[:, -1, :]).squeeze(-1)

    @torch.no_grad()
    def tendency(self, sequence: torch.Tensor) -> float:
        """Single-sequence convenience API -> Chat in [0, 1]."""
        self.eval()
        if sequence.dim() == 2:
            sequence = sequence.unsqueeze(0)
        return float(self.forward(sequence).item())
