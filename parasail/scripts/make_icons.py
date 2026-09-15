"""Generate the ParaSail app icons for the installable mobile web app (PWA).

Draws the brand mark at high resolution with Pillow and downsamples:
a coral sail over teal waves on the deep-ocean background.

Outputs (src/parasail/static/icons/):
  icon-192.png, icon-512.png          - regular PWA icons
  icon-maskable-512.png               - maskable (safe-zone padded)
  apple-touch-icon.png (180)          - iOS home screen
  favicon-32.png                      - browser tab

Requires Pillow (already in the dev environment); re-run only when the
brand mark changes - the PNGs are committed with the app.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parents[1] / "src" / "parasail" / "static" / "icons"
OUT.mkdir(parents=True, exist_ok=True)

BG = (10, 46, 60, 255)        # deep ocean #0A2E3C
TEAL = (20, 112, 124, 255)    # #14707C
LIGHT_TEAL = (122, 173, 160, 255)
CORAL = (231, 111, 81, 255)   # #E76F51
WHITE = (242, 248, 249, 255)


def draw_mark(size: int, pad_frac: float = 0.0) -> Image.Image:
    """The ParaSail mark: coral sail, white pennant dot, three teal waves."""
    img = Image.new("RGBA", (size, size), BG)
    d = ImageDraw.Draw(img)
    pad = size * pad_frac
    s = size - 2 * pad                       # working square
    x0, y0 = pad, pad

    # hull/wave area (bottom third): three arcs, lightest at the top
    for i, color in enumerate((TEAL, TEAL, LIGHT_TEAL)):
        cy = y0 + s * (0.70 + 0.09 * i)
        r = s * (0.34 + 0.05 * i)
        d.arc([x0 + s / 2 - r, cy - r * 0.55, x0 + s / 2 + r, cy + r * 0.9],
              start=200, end=340, fill=color, width=max(3, int(s * 0.045)))

    # sail: coral triangle rising from the waves
    d.polygon([
        (x0 + s * 0.50, y0 + s * 0.16),      # apex
        (x0 + s * 0.50, y0 + s * 0.74),      # mast foot
        (x0 + s * 0.80, y0 + s * 0.74),      # boom end
    ], fill=CORAL)
    # small second sail for balance
    d.polygon([
        (x0 + s * 0.46, y0 + s * 0.26),
        (x0 + s * 0.46, y0 + s * 0.74),
        (x0 + s * 0.26, y0 + s * 0.74),
    ], fill=(231, 111, 81, 215))
    # sun/pennant dot
    r = s * 0.055
    d.ellipse([x0 + s * 0.76 - r, y0 + s * 0.14 - r,
               x0 + s * 0.76 + r, y0 + s * 0.14 + r], fill=WHITE)
    return img


def rounded(img: Image.Image, radius_frac: float = 0.22) -> Image.Image:
    """Rounded-square mask (regular icons; maskable ones stay full-bleed)."""
    size = img.size[0]
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, size, size], radius=int(size * radius_frac), fill=255)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(img, (0, 0), mask)
    return out


def main() -> None:
    base = draw_mark(1024)
    # regular + iOS icons: rounded corners, content at ~92% (no extra pad)
    for size, name in ((512, "icon-512.png"), (192, "icon-192.png"),
                       (180, "apple-touch-icon.png"), (32, "favicon-32.png")):
        img = base.resize((size, size), Image.LANCZOS)
        if name != "favicon-32.png":         # tiny favicon stays square-ish
            img = rounded(img)
        img.save(OUT / name)
        print("wrote", OUT / name)
    # maskable: full-bleed with the mark inside the 80% safe zone
    maskable = draw_mark(1024, pad_frac=0.12).resize((512, 512), Image.LANCZOS)
    maskable.save(OUT / "icon-maskable-512.png")
    print("wrote", OUT / "icon-maskable-512.png")


if __name__ == "__main__":
    main()
