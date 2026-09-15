"""ParaSail prediction models (development phases P3-P4).

One representative per family, selected for coastal deployability:
  detection.py    - YOLOv8n catch detector
  classifier.py   - ViT-B/16 + LoRA species classifier (r=8, q/v)
  forecaster.py   - 2-layer LSTM movement-tendency model (24 steps)
  habitat.py      - random-forest habitat-suitability fallback
"""
