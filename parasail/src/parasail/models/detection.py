"""YOLOv8n catch detector (development phase P3).

Real-time catch/bycatch recognition on modest hardware. Used to verify
landed catch imagery against the declared target species; detections feed
the bycatch proxy B when pilot users upload trip photos.
"""
from __future__ import annotations

from pathlib import Path


class CatchDetector:
    def __init__(self, weights: str = "yolov8n.pt", confidence: float = 0.35):
        # Ultralytics imports torch and downloads weights on first use.
        from ultralytics import YOLO
        self.model = YOLO(weights)
        self.confidence = confidence

    def detect(self, image_path: str | Path) -> list[dict]:
        results = self.model.predict(str(image_path), conf=self.confidence,
                                      verbose=False)
        out: list[dict] = []
        for result in results:
            for box in result.boxes:
                out.append({
                    "class_id": int(box.cls.item()),
                    "class_name": result.names.get(int(box.cls.item()), "?"),
                    "confidence": round(float(box.conf.item()), 4),
                    "xyxy": [round(float(v), 1) for v in box.xyxy[0].tolist()],
                })
        return out
