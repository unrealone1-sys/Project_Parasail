# -*- coding: utf-8 -*-
"""Simplified 'how it works' figure for the general-audience ParaSail deck:
four plain-language steps, large type, no jargon."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "deck_figures")
os.makedirs(OUT, exist_ok=True)

TEAL, STEEL, GREEN, TAN, PURP = "#14707C", "#7A9BB8", "#7BA68A", "#C49B72", "#9687A8"

fig, ax = plt.subplots(figsize=(12.9, 4.6))
ax.set_xlim(0, 129)
ax.set_ylim(0, 46)
ax.axis("off")

steps = [
    ("1", "WATCH THE SEA", TEAL,
     "Free satellite and weather data,\nupdated every hour"),
    ("2", "PREDICT THE FISH", GREEN,
     "Where sardines and mackerel\nare likely to be tomorrow"),
    ("3", "CHECK THE RULES", TAN,
     "Protected zones and closed\nseasons, checked automatically"),
    ("4", "GIVE SIMPLE ADVICE", PURP,
     "One clear answer, with the\nreasons shown to you"),
]

bw, bh, gap, x0, ytop = 27.5, 30.0, 4.6, 2.0, 42.0
for i, (num, name, color, sub) in enumerate(steps):
    x = x0 + i * (bw + gap)
    # number badge
    ax.add_patch(plt.Circle((x + 4.6, ytop - 4.6), 3.6, color=color))
    ax.text(x + 4.6, ytop - 4.7, num, ha="center", va="center",
            fontsize=20, fontweight="bold", color="white")
    # body
    ax.add_patch(FancyBboxPatch((x, ytop - bh), bw, bh - 9.5,
                 boxstyle="round,pad=0.2,rounding_size=1.0",
                 fc="white", ec=color, lw=2.4))
    ax.text(x + bw / 2, ytop - 14.0, name, ha="center", va="center",
            fontsize=15.5, fontweight="bold", color=color)
    ax.text(x + bw / 2, ytop - 22.5, sub, ha="center", va="center",
            fontsize=11.5, color="#404040", linespacing=1.45)
    if i < 3:
        ax.add_patch(FancyArrowPatch((x + bw + 0.6, ytop - bh / 2 - 4),
                     (x + bw + gap - 0.6, ytop - bh / 2 - 4),
                     arrowstyle="-|>", mutation_scale=22, lw=3.0,
                     color="#8aa0aa"))

fig.tight_layout(pad=0.4)
fig.savefig(os.path.join(OUT, "fig_simple_how.png"), dpi=200,
            bbox_inches="tight", facecolor="white")
plt.close(fig)
print("generated: fig_simple_how.png")
