"""Embed Sentinel tiles into the Qdrant satellite collection (phase P5).

Each GeoTIFF is cut into tiles, embedded with OpenCLIP ViT-B/32 and stored
with bbox + acquisition metadata as payload, enabling the tile lookup that
attaches recent satellite context to advisories.

Usage:
    python scripts/embed_satellite_tiles.py --tiles data/sentinel/
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from parasail.config import load_config   # noqa: E402
from parasail.rag import RagService       # noqa: E402

TILE = 512


def iter_tiles(path: Path):
    """Yield (tile_rgb_uint8, bbox, acquired) from Sentinel GeoTIFFs.

    Requires rasterio in the deployment environment; kept as a generator so
    huge scenes stream instead of loading whole.
    """
    import rasterio
    from datetime import datetime
    for tif in sorted(path.rglob("*.tif*")):
        with rasterio.open(tif) as src:
            meta = src.tags()
            acquired = meta.get("GRANULE_ID", tif.stem)[:10] or None
            # Scene footprint from the transform (approximate bbox).
            xs = [src.bounds.left, src.bounds.right]
            ys = [src.bounds.bottom, src.bounds.top]
            bbox = [min(xs), min(ys), max(xs), max(ys)]
            for row in range(0, src.height - TILE + 1, TILE):
                for col in range(0, src.width - TILE + 1, TILE):
                    window = rasterio.windows.Window(col, row, TILE, TILE)
                    rgb = src.read([1, 2, 3], window=window)
                    rgb = np.clip(rgb.transpose(1, 2, 0) / 3000.0, 0, 1)
                    yield (rgb, bbox, acquired)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tiles", required=True, type=Path)
    ap.add_argument("--limit", type=int, default=5000)
    args = ap.parse_args()

    import torch
    import open_clip

    cfg = load_config()
    clip_cfg = cfg.models["clip"]
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model, _, preprocess = open_clip.create_model_and_transforms(
        clip_cfg["model"], pretrained=clip_cfg["pretrained"])
    model = model.to(device).eval()

    from qdrant_client.models import PointStruct
    rag = RagService(cfg)
    rag.ensure_collections()

    points, pid = [], 0
    with torch.no_grad():
        for rgb, bbox, acquired in iter_tiles(args.tiles):
            if pid >= args.limit:
                break
            tensor = preprocess(
                __import__("PIL.Image", fromlist=["Image"]).fromarray(
                    (rgb * 255).astype("uint8"))
            ).unsqueeze(0).to(device)
            vec = model.encode_image(tensor).squeeze(0).cpu().numpy()
            points.append(PointStruct(
                id=pid, vector=vec.tolist(),
                payload={"bbox": bbox, "acquired": acquired,
                         "source": "sentinel"},
            ))
            pid += 1
    if points:
        rag.client.upsert(cfg.rag["satellite_collection"], points=points)
    print(f"embedded {pid} tiles into '{cfg.rag['satellite_collection']}'")


if __name__ == "__main__":
    main()
