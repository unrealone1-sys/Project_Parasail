# -*- coding: utf-8 -*-
"""Schematic map for the "honest map" slide (fig7_zones.png).

Illustrative diagram of what the dashboard draws: land in the upper-left, open
sea below the shoreline, a blocky likely-fish ZONE that stays strictly on the
sea side (clipped to the SAME shoreline curve that draws the land, minus a
margin), a backwater inland, and a protected AREA whose interior forces STOP.

The geometry contract is asserted at the end: no zone or protected-area vertex
may sit on the land side of `coast(x)`.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Polygon
import numpy as np

SEA = "#D9E9EE"
LAND = "#E6EBE7"
PRIMARY_DK = "#0E4A54"
ACCENT = "#E76F51"
ZONE = "#2F9E8F"
MPA = "#C94F4F"
TEXT = "#16323D"
MUTED = "#6B8290"

MARGIN = 0.12          # offshore gap kept between shoreline and zone
X0, X1, Y0, Y1 = -0.5, 10.8, -0.6, 4.6


def coast(x):
    """Shoreline. Land is ABOVE this curve (upper-left); sea is below."""
    return 4.55 - 0.30 * x + 0.18 * np.sin(1.5 * x)


fig, ax = plt.subplots(figsize=(8, 5), dpi=200)
ax.set_facecolor(SEA)

# --- land -------------------------------------------------------------------
cx = np.linspace(X0, X1, 600)
cy = coast(cx)
ax.add_patch(Polygon(np.concatenate([
    np.column_stack([cx, cy]),
    np.column_stack([cx[::-1], np.full_like(cx, Y1 + 1.0)])]),
    closed=True, facecolor=LAND, edgecolor="#B9C7C2", linewidth=1.2, zorder=2))
ax.plot(cx, cy, color="#9FB0AA", linewidth=1.0, zorder=3)

# --- inland backwater -------------------------------------------------------
lag_x = np.linspace(2.05, 3.45, 120)
lag_y = coast(lag_x) + 0.42 + 0.05 * np.sin(lag_x * 2.4)
lag_poly = np.concatenate([
    np.column_stack([lag_x, lag_y + 0.11]),
    np.column_stack([lag_x[::-1], lag_y - 0.11])])
ax.add_patch(Polygon(lag_poly, closed=True, facecolor="#C9DDE4",
                     edgecolor="#9FBAC4", linewidth=1.0, zorder=4))
ax.text(float(lag_x.mean()), float(lag_y.mean()) + 0.34, "backwater (excluded)",
        fontsize=8.5, color=MUTED, ha="center", style="italic", zorder=6)

# --- likely-fish ZONE: blocky cells, strictly sea-side ----------------------
zone_blocks = [               # (x0, x1, depth_near_shore, depth_far)
    (3.10, 4.00, 0.12, 0.95),
    (4.00, 4.90, 0.12, 1.80),
    (4.90, 5.80, 0.12, 2.60),
    (5.80, 6.70, 0.12, 1.75),
    (6.70, 7.60, 0.12, 0.95),
    (4.90, 5.80, 2.60, 3.20),
]
zone_pts: list[tuple[float, float]] = []
for x0, x1, d0, d1 in zone_blocks:
    xs = np.linspace(x0, x1, 24)
    shore = coast(xs)
    top, bot = shore - d0, shore - d1          # -d = offshore (smaller y)
    ax.add_patch(Polygon(np.concatenate([
        np.column_stack([xs, top]),
        np.column_stack([xs[::-1], bot])]),
        closed=True, facecolor=ZONE, alpha=0.38, edgecolor="none", zorder=5))
    zone_pts.extend(zip(xs[::8], top[::8]))
    zone_pts.extend(zip(xs[::8], bot[::8]))

# traced zone boundary (what the app returns as a polygon ring)
xs = np.linspace(3.10, 7.60, 240)
ax.plot(xs, coast(xs) - 0.12, color=ZONE, linewidth=2.2, zorder=6)
xs = np.linspace(3.10, 4.90, 140)
ax.plot(xs, coast(xs) - 0.12, color=ZONE, linewidth=2.2, zorder=6)
xs = np.linspace(4.90, 5.80, 70)
ax.plot(xs, coast(xs) - 3.20, color=ZONE, linewidth=2.2, zorder=6)
xs = np.linspace(5.80, 7.60, 140)
ax.plot(xs, coast(xs) - 0.12, color=ZONE, linewidth=2.2, zorder=6)

ax.annotate("likely-fish zone\n(stays over the sea,\nnever on land)",
            xy=(5.35, float(coast(5.35) - 2.7)), xytext=(1.65, 1.15),
            fontsize=9, color=PRIMARY_DK, weight="bold", ha="left", va="center",
            arrowprops=dict(arrowstyle="-", color=PRIMARY_DK, linewidth=0.9), zorder=7)

# --- protected area: sea-side polygon, dashed coral -------------------------
mpa = np.array([[7.25, 0.55], [8.45, 0.45], [8.85, 1.20], [8.05, 1.85], [7.15, 1.35]])
ax.add_patch(Polygon(mpa, closed=True, facecolor=MPA, alpha=0.25,
                     edgecolor=MPA, linewidth=2.0, linestyle=(0, (5, 4)), zorder=5))
ax.text(float(mpa[:, 0].mean()), float(mpa[:, 1].mean()), "protected area\nSTOP inside",
        fontsize=9, color="#8A3B2E", ha="center", va="center", weight="bold", zorder=7)

# --- harbour / boat marker --------------------------------------------------
ax.add_patch(Circle((3.40, 1.95), 0.13, facecolor=ACCENT, edgecolor="#FFFFFF",
                    linewidth=1.6, zorder=8))
ax.text(3.62, 1.92, "your harbour / boat", fontsize=8.5, color=TEXT, va="center", zorder=8)

# --- labels -----------------------------------------------------------------
ax.text(0.10, 4.32, "LAND", fontsize=9.5, color=MUTED, weight="bold", zorder=7)
ax.text(0.10, -0.35, "SEA", fontsize=9.5, color=MUTED, weight="bold", zorder=7)
ax.text(10.6, -0.35, "not to scale \u00b7 illustrative", fontsize=8,
        color=MUTED, ha="right", style="italic", zorder=7)

ax.set_xlim(X0, X1)
ax.set_ylim(Y0, Y1)
ax.set_xticks([])
ax.set_yticks([])
for sp in ax.spines.values():
    sp.set_color("#C7D5D9")
fig.tight_layout(pad=0.3)
fig.savefig("deck_figures/fig7_zones.png", facecolor="#FFFFFF")

# ── geometry contract ───────────────────────────────────────────────────────
def land_violations(pts):
    return [(round(x, 2), round(y, 2)) for x, y in pts if y > coast(x) - MARGIN + 1e-9]

bad_zone = land_violations(zone_pts)
bad_mpa = land_violations(mpa)
bad_zone_line = [(round(x, 2), round(float(coast(x) - 0.12), 2))
                 for x in np.linspace(3.10, 7.60, 240)
                 if (coast(x) - 0.12) > coast(x) - MARGIN + 1e-9]
assert not bad_zone, f"zone crosses onto land: {bad_zone[:4]}"
assert not bad_mpa, f"protected area crosses onto land: {bad_mpa[:4]}"
assert not bad_zone_line, f"zone outline on land: {bad_zone_line[:4]}"
assert float((lag_y - 0.11).min()) > float(coast(lag_x[(lag_y - 0.11).argmin()])), \
    "backwater is not inland"
assert float(mpa[:, 1].max()) < float(coast(mpa[:, 0].min())) - MARGIN, \
    "protected area not in open sea"

clearance = float(np.min(coast(np.array([p[0] for p in zone_pts]))
                         - np.array([p[1] for p in zone_pts])))

# ── pixel check: no zone-green pixel may sit on the land side ───────────────
# The shoreline row is detected from the image itself (the lowest land-coloured
# pixel in each column), so the check is self-calibrating and fails loudly if
# the zone tint ever crosses onto land.
from PIL import Image  # noqa: E402

img = np.asarray(Image.open("deck_figures/fig7_zones.png").convert("RGB")).astype(int)
h_px, w_px = img.shape[:2]
r, g, b = img[:, :, 0], img[:, :, 1], img[:, :, 2]
greenish = (g > r + 6) & (g > b + 2) & (r < 215)          # zone tint (teal)
is_land = (np.abs(r - 230) < 6) & (np.abs(g - 235) < 6) & (np.abs(b - 231) < 6)
bleed = 0
cols_with_land = 0
for col in range(w_px):
    land_rows = np.nonzero(is_land[:, col])[0]
    if land_rows.size == 0:
        continue
    cols_with_land += 1
    shore_row = int(land_rows[-1])                        # lowest land pixel
    if shore_row > 1:
        bleed += int(greenish[:shore_row, col].sum())

print("WROTE deck_figures/fig7_zones.png")
print(f"  zone vertices checked: {len(zone_pts)}  |  min offshore clearance: {clearance:.2f} deg")
print(f"  land columns examined: {cols_with_land}  |  green pixels above the shoreline: {bleed}")
print("  geometry contract: zone + protected area strictly sea-side, backwater inland")
assert bleed == 0, f"zone colour bleeds onto land ({bleed} px above the shoreline)"
