"""ViT-B/16 + LoRA species classifier (development phase P4).

LoRA (Hu et al., ICLR 2022) freezes the pretrained weights and injects a
low-rank additive update  W' = W0 + BA  with rank r = 8 on the query and
value projections of all twelve encoder blocks - 0.29M of 85.8M parameters
trainable (0.34%), which keeps regional adaptation within mid-range GPU
memory.
"""
from __future__ import annotations

from pathlib import Path

import torch
from PIL import Image


def build_lora_classifier(model_name: str, num_classes: int,
                           lora_cfg: dict, adapter_path: str | None = None):
    """Return (model, processor, id2label) ready for inference or training."""
    from peft import LoraConfig, get_peft_model
    from transformers import AutoImageProcessor, ViTForImageClassification

    processor = AutoImageProcessor.from_pretrained(model_name)
    model = ViTForImageClassification.from_pretrained(
        model_name, num_labels=num_classes, ignore_mismatched_sizes=True)

    peft_cfg = LoraConfig(
        r=lora_cfg.get("r", 8),
        lora_alpha=lora_cfg.get("alpha", 16),
        lora_dropout=lora_cfg.get("dropout", 0.05),
        target_modules=lora_cfg.get("target_modules", ["query", "value"]),
        task_type="IMAGE_CLASSIFICATION",
    )
    model = get_peft_model(model, peft_cfg)

    if adapter_path:
        from peft import PeftModel
        model = PeftModel.from_pretrained(model, adapter_path)
    model.eval()
    return model, processor


class SpeciesClassifier:
    """Inference wrapper used by the API for field-imagery verification."""

    def __init__(self, model_name: str, id2label: dict[int, str],
                 lora_cfg: dict, adapter_path: str | None = None,
                 device: str | None = None):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.model, self.processor = build_lora_classifier(
            model_name, len(id2label), lora_cfg, adapter_path)
        self.model.to(self.device)
        self.id2label = id2label

    @torch.no_grad()
    def predict(self, image_path: str | Path) -> dict:
        image = Image.open(image_path).convert("RGB")
        inputs = self.processor(images=image, return_tensors="pt").to(self.device)
        logits = self.model(**inputs).logits
        probs = torch.softmax(logits, dim=-1).squeeze(0)
        top = int(probs.argmax())
        return {
            "species": self.id2label[top],
            "confidence": round(float(probs[top]), 4),
        }
