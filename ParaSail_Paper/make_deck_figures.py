# -*- coding: utf-8 -*-
"""Slide-optimized figures for the ParaSail presentation (16:9 deck).
Same content as the paper figures, larger typography for on-screen display."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from matplotlib.colors import LinearSegmentedColormap
import numpy as np
import os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "deck_figures")
os.makedirs(OUT, exist_ok=True)

C_BLUE, C_TAN, C_GREEN, C_RED, C_PURP = "#6B9DAD", "#C49B72", "#7BA68A", "#B87472", "#9687A8"
C_TEAL, C_STEEL, C_GOLD = "#7AADA0", "#7A9BB8", "#C8B87C"
GRID = dict(alpha=0.3, linewidth=0.6)

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 12,
    "axes.edgecolor": "#555555",
    "axes.linewidth": 0.9,
    "figure.facecolor": "white",
})

# ----------------------------------------------------------------------------
# Deck figure 1 -- six-layer architecture (full-width slide graphic)
# ----------------------------------------------------------------------------
def fig1():
    fig, ax = plt.subplots(figsize=(12.9, 5.7))
    ax.set_xlim(0, 129)
    ax.set_ylim(0, 57)
    ax.axis("off")

    layers = [
        ("1  INGESTION", C_STEEL, [
            "Open-Meteo (wind, waves)",
            "Copernicus Marine NRT",
            "NASA ERDDAP (SST, chl-a)",
            "GBIF / OBIS occurrences",
            "FishBase / WoRMS traits",
            "Sentinel-2/3 GeoTIFF",
            "  tiles",
        ]),
        ("2  PROCESSING", C_BLUE, [
            "Coordinate & timestamp",
            "  validation",
            "Taxonomy normalisation",
            "Common spatiotemporal",
            "  grid (regridding)",
            "Feature engineering",
            "Quality gates & freshness",
            "  audit",
        ]),
        ("3  PREDICTION", C_GREEN, [
            "YOLOv8 catch detector",
            "ViT + LoRA classifier",
            "  (r = 8, q/v, <1% params)",
            "LSTM 24-step movement",
            "  tendency model",
            "Random-forest habitat",
            "  baseline (data-poor)",
        ]),
        ("4  RAG", C_PURP, [
            "Qdrant text collection",
            "  (regulations, closures,",
            "  guidance, local",
            "  knowledge)",
            "Qdrant satellite tiles",
            "  (OpenCLIP + bbox)",
            "Hybrid top-k retrieval",
        ]),
        ("5  ADVISORY", C_TAN, [
            "Rules engine (MPA /",
            "  closure hard blocks)",
            "Scoring S = 0.45C +",
            "  0.25W + 0.30(1-B)",
            "4 advisory classes",
            "FastAPI + dashboard",
        ]),
        ("6  ASSISTANT", C_GOLD, [
            "Grounded VLM Q&A +",
            "  plain-language summaries",
            "Qwen2.5-VL-7B (AWQ)",
            "  on vLLM, 8-12 GB VRAM",
            "Catch-photo / tile /",
            "  chart reading",
            "Guardrails: grounded,",
            "  cited, class-consistent",
            "Template fallback (CPU)",
        ]),
    ]

    bw, bh, gap, x0, ytop = 19.0, 36.0, 2.8, 0.8, 52.0
    for i, (title, color, items) in enumerate(layers):
        x = x0 + i * (bw + gap)
        ax.add_patch(FancyBboxPatch((x, ytop - 5.6), bw, 5.6,
                     boxstyle="round,pad=0.15,rounding_size=0.6",
                     fc=color, ec="none"))
        ax.text(x + bw / 2, ytop - 2.8, title, ha="center", va="center",
                fontsize=12.5, fontweight="bold", color="white")
        ax.add_patch(FancyBboxPatch((x, ytop - 5.6 - bh), bw, bh,
                     boxstyle="round,pad=0.15,rounding_size=0.6",
                     fc="white", ec=color, lw=2.0))
        yy = ytop - 9.4
        for it in items:
            cont = it.startswith("  ")
            ax.text(x + 1.2, yy, it.strip(), ha="left", va="center",
                    fontsize=9.2, color="#333333",
                    fontstyle="italic" if cont else "normal")
            yy -= 4.2
        if i < len(layers) - 1:
            ax.add_patch(FancyArrowPatch((x + bw + 0.4, ytop - 5.6 - bh / 2),
                         (x + bw + gap - 0.4, ytop - 5.6 - bh / 2),
                         arrowstyle="-|>", mutation_scale=18,
                         lw=2.4, color="#606060"))
    ax.text(x0 - 0.6, ytop - 5.6 - bh - 3.0, "open data &\nlocal uploads", fontsize=11.5,
            ha="center", va="top", color="#505050")
    ax.text(x0 + 6 * (bw + gap) - 1.4, ytop - 5.6 - bh - 3.0,
            "advisory + context\n+ conversation", fontsize=11.5, ha="center", va="top", color="#505050")
    ax.add_patch(FancyBboxPatch((x0, 3.6), 6 * bw + 5 * gap, 6.8,
                 boxstyle="round,pad=0.15,rounding_size=0.6",
                 fc="#F2F4F6", ec="#909090", lw=1.1))
    ax.text(x0 + (6 * bw + 5 * gap) / 2, 7.0,
            "PostgreSQL + PostGIS   |   Qdrant vector DB   |   vLLM inference server (local AI)   |   "
            "Docker Compose   |   YAML config-driven deployment",
            ha="center", va="center", fontsize=10.5, color="#404040")
    fig.tight_layout(pad=0.4)
    fig.savefig(os.path.join(OUT, "fig1_architecture.png"), dpi=200,
                bbox_inches="tight", facecolor="white")
    plt.close(fig)

# ----------------------------------------------------------------------------
# Deck figure 2 -- advisory scoring surface (left panel of slide)
# ----------------------------------------------------------------------------
def fig2():
    fig, ax = plt.subplots(figsize=(8.6, 5.6))
    C = np.linspace(0, 1, 401)
    W = np.linspace(0, 1, 401)
    CC, WW = np.meshgrid(C, W)
    B = 0.20
    S = 0.45 * CC + 0.25 * WW + 0.30 * (1 - B)

    cmap = LinearSegmentedColormap.from_list(
        "morandi_rg", ["#B87472", "#E3D9C6", "#F2EFE6", "#CBD9C4", "#7BA68A"])
    cf = ax.contourf(CC, WW, S, levels=np.linspace(0.30, 0.95, 27), cmap=cmap)
    for thr in (0.40, 0.60, 0.75):
        cs = ax.contour(CC, WW, S, levels=[thr], colors="#404040",
                        linewidths=1.6, linestyles="--")
        ax.clabel(cs, fmt={thr: f"S = {thr:.2f}"}, fontsize=11)

    ax.text(0.05, 0.05, "DELAY OR RELOCATE /\nDO NOT FISH", fontsize=10.5,
            color="#6d4a49", fontweight="bold", va="bottom")
    ax.text(0.30, 0.16, "DELAY OR RELOCATE", fontsize=10.5, color="#5c5545")
    ax.text(0.52, 0.44, "PROCEED WITH CAUTION", fontsize=10.5, color="#3f5a46")
    ax.text(0.74, 0.80, "PROCEED", fontsize=12, color="#2e4a36", fontweight="bold")

    cbar = fig.colorbar(cf, ax=ax, shrink=0.92, pad=0.02)
    cbar.set_label("Sustainability index  S", fontsize=12)
    cbar.ax.tick_params(labelsize=10.5)
    ax.set_xlabel("Catch-likelihood composite  C", fontsize=12.5)
    ax.set_ylabel("Weather-safety component  W", fontsize=12.5)
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.tick_params(labelsize=10.5)
    ax.grid(True, **GRID)
    fig.tight_layout(pad=0.6)
    fig.savefig(os.path.join(OUT, "fig2_scoring.png"), dpi=200,
                bbox_inches="tight", facecolor="white")
    plt.close(fig)

# ----------------------------------------------------------------------------
# Deck figure 3 -- phase-gate roadmap (full-width slide graphic)
# ----------------------------------------------------------------------------
def fig3():
    fig, ax = plt.subplots(figsize=(12.9, 4.7))
    ax.set_xlim(0, 129)
    ax.set_ylim(0, 47)
    ax.axis("off")

    phases = [
        ("P1", "Governance &\nregion selection", C_STEEL,
         "licences, ethics\nregulatory inventory"),
        ("P2", "Ingestion &\ndatabase schema", C_BLUE,
         "live fetch tests\nPostGIS schema"),
        ("P3", "Baseline\npredictive models", C_GREEN,
         "model training\noffline baselines"),
        ("P4", "LoRA fine-tune &\ncustom ingestion", C_TEAL,
         "GPU memory budget\ncustom species data"),
        ("P5", "RAG & advisory\nAPI integration", C_PURP,
         "retrieval relevance\nclosure enforcement"),
        ("P6", "Dashboard &\npilot feedback", C_TAN,
         "advisory schema\nfeedback loop"),
        ("P7", "Grounded AI\nassistant", C_GOLD,
         "grounded answers\nlatency + fallback"),
    ]
    gates = [
        "G1: region and rules\ninventory signed off",
        "G2: live fetches\nvalidated; freshness\naudit passes",
        "G3: baselines beat\nnaive persistence",
        "G4: LoRA converges\nwithin memory budget",
        "G5: closure / MPA\nblocks exact; top-k\nrelevant",
        "G6: answers grounded\n& cited; fallback\nexact; latency in budget",
    ]

    bw, bh, gap, x0, ytop = 15.8, 22.5, 2.6, 1.5, 44.0
    for i, (pid, name, color, note) in enumerate(phases):
        x = x0 + i * (bw + gap)
        ax.add_patch(FancyBboxPatch((x, ytop - bh), bw, bh,
                     boxstyle="round,pad=0.15,rounding_size=0.7",
                     fc=color, ec="none"))
        ax.text(x + bw / 2, ytop - 4.6, pid, ha="center", va="center",
                fontsize=12.5, fontweight="bold", color="white")
        ax.text(x + bw / 2, ytop - 10.6, name, ha="center", va="center",
                fontsize=9.8, fontweight="bold", color="white")
        ax.text(x + bw / 2, ytop - 18.0, note, ha="center", va="center",
                fontsize=8.4, color="white")
        if i < len(phases) - 1:
            gx = x + bw + gap / 2
            ax.plot([gx], [ytop - bh / 2], marker="D", markersize=7,
                    color=C_GOLD, markeredgecolor="#8a7a4a", zorder=5)
            ax.add_patch(FancyArrowPatch((x + bw + 0.3, ytop - bh / 2),
                         (x + bw + gap - 0.3, ytop - bh / 2),
                         arrowstyle="-|>", mutation_scale=13, lw=1.8,
                         color="#606060"))
            ax.text(gx, ytop - bh - 2.0, gates[i], ha="center", va="top",
                    fontsize=8.0, color="#555555", linespacing=1.3)

    ax.annotate("", xy=(127.5, 8.5), xytext=(1.5, 8.5),
                arrowprops=dict(arrowstyle="-|>", lw=2.6, color="#7A9BB8"))
    ax.text(64.5, 4.6, "iterative engineering with phase-gate acceptance checks "
            "(every gate must pass before the next phase begins)",
            ha="center", va="center", fontsize=12, color="#4a5a68")
    fig.tight_layout(pad=0.4)
    fig.savefig(os.path.join(OUT, "fig3_phases.png"), dpi=200,
                bbox_inches="tight", facecolor="white")
    plt.close(fig)

# ----------------------------------------------------------------------------
# Deck figure 4 -- case study seasonal calendar (left panel of slide)
# ----------------------------------------------------------------------------
def fig4():
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(9.4, 5.9), sharex=True,
                                   gridspec_kw={"height_ratios": [1, 1.35],
                                                "hspace": 0.30})
    months = np.arange(0, 12.02, 0.01)
    mlabels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    sst = 28.1 + 1.65 * np.cos(2 * np.pi * (months - 4.4) / 12.0)
    ax1.plot(months, sst, color=C_RED, lw=2.6)
    ax1.set_ylabel("Sea-surface\ntemperature (°C)", fontsize=11.5)
    ax1.set_ylim(26.0, 30.4)
    ax1.set_xlim(0, 12)
    ax1.set_xticks(range(12)); ax1.set_xticklabels(mlabels, fontsize=10.5)
    ax1.tick_params(labelsize=10.5)
    ax1.grid(True, **GRID)
    ax1.axvspan(5.5, 7.0, color="#9BB0C4", alpha=0.35, hatch="///",
                edgecolor="#5c7a94", lw=0.8)
    ax1.text(6.25, 29.9, "monsoon\nfishing closure", ha="center",
             va="top", fontsize=10.5, color="#33506a", linespacing=1.2)
    ax1.text(0.25, 26.3, "schematic climatological cycle, southwest coast of India",
             fontsize=9.8, color="#777777", style="italic")

    seasons = [
        ("Sardinella longiceps\n(Indian oil sardine)", [(8.6, 4.4)], C_BLUE),
        ("Rastrelliger kanagurta\n(Indian mackerel)", [(7.2, 5.8)], C_GREEN),
        ("Thunnus tonggol\n(longtail tuna)", [(9.2, 3.4)], C_TAN),
        ("Penaeus monodon\n(giant tiger prawn)", [(4.3, 6.4)], C_PURP),
    ]
    for i, (name, spans, color) in enumerate(seasons):
        y = len(seasons) - i
        for (start, dur) in spans:
            ax2.broken_barh([(start, dur)], (y - 0.32, 0.64), facecolors=color,
                            edgecolor="white", lw=0.6)
    ax2.broken_barh([(5.5, 1.5)], (len(seasons) - 0.32, 0.64),
                    facecolors="none", edgecolor="#33506a", lw=1.8, hatch="xxx")
    ax2.set_yticks([len(seasons) - i for i in range(len(seasons))])
    ax2.set_yticklabels([s[0] for s in seasons], fontsize=10.2)
    ax2.set_xlim(0, 12)
    ax2.set_xticks(range(12)); ax2.set_xticklabels(mlabels, fontsize=10.5)
    ax2.tick_params(labelsize=10.5)
    ax2.grid(True, axis="x", **GRID)
    ax2.text(6.25, 0.28, "cross-hatch: June-July spawning closure on the oil sardine; "
             "blue band: monsoon closure", ha="center", fontsize=9.8, color="#4a5a68")
    fig.tight_layout(pad=0.5)
    fig.savefig(os.path.join(OUT, "fig4_calendar.png"), dpi=200,
                bbox_inches="tight", facecolor="white")
    plt.close(fig)

# ----------------------------------------------------------------------------
# Deck figure 5 -- LoRA parameter efficiency (left panel of slide)
# ----------------------------------------------------------------------------
def fig5():
    fig, ax = plt.subplots(figsize=(8.2, 5.3))
    total = 85.8
    r_vals = [4, 8, 16]
    lora = [2 * 12 * r * (768 + 768) / 1e6 for r in r_vals]
    cats = ["Full\nfine-tuning"] + [f"LoRA\n(rank r = {r})" for r in r_vals]
    vals = [total] + lora
    colors = [C_RED, "#A8C3CE", C_BLUE, "#4F7E92"]

    bars = ax.bar(cats, vals, color=colors, width=0.58, edgecolor="white", lw=0.8)
    ax.set_yscale("log")
    ax.set_ylim(0.05, 300)
    ax.set_ylabel("Trainable parameters (millions, log scale)", fontsize=11.5)
    labels = [f"{total:.1f} M\n(100%)",
              f"{lora[0]:.3f} M\n({lora[0]/total*100:.2f}%)",
              f"{lora[1]:.3f} M\n({lora[1]/total*100:.2f}%)",
              f"{lora[2]:.3f} M\n({lora[2]/total*100:.2f}%)"]
    for bar, lab in zip(bars, labels):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() * 1.22,
                lab, ha="center", va="bottom", fontsize=11, color="#333333")
    ax.annotate("system default", xy=(2, lora[1] * 1.05), xytext=(2.05, 26),
                fontsize=11, color="#2e5a6b", ha="center",
                arrowprops=dict(arrowstyle="-|>", lw=1.4, color="#2e5a6b"))
    ax.tick_params(labelsize=11)
    ax.grid(True, axis="y", **GRID)
    fig.tight_layout(pad=0.5)
    fig.savefig(os.path.join(OUT, "fig5_lora.png"), dpi=200,
                bbox_inches="tight", facecolor="white")
    plt.close(fig)

# ----------------------------------------------------------------------------
# Deck figure 6 -- monotonicity panels (full-width slide graphic)
# ----------------------------------------------------------------------------
def fig6():
    fig, axes = plt.subplots(1, 3, figsize=(12.9, 4.5), sharey=True)
    bands = [(0.00, 0.40, "#E8D5D4", "DO NOT FISH / DELAY"),
             (0.40, 0.60, "#F0E8D8", "DELAY OR RELOCATE"),
             (0.60, 0.75, "#E2EADB", "PROCEED WITH CAUTION"),
             (0.75, 1.00, "#CFE2CB", "PROCEED")]
    panels = [
        ("(a) vary C   (W = 0.70, B = 0.20)", np.linspace(0, 1, 201),
         lambda C: 0.45 * C + 0.25 * 0.70 + 0.30 * 0.80, "C", 0.70),
        ("(b) vary W   (C = 0.70, B = 0.20)", np.linspace(0, 1, 201),
         lambda W: 0.45 * 0.70 + 0.25 * W + 0.30 * 0.80, "W", 0.70),
        ("(c) vary B   (C = 0.70, W = 0.70)", np.linspace(0, 1, 201),
         lambda B: 0.45 * 0.70 + 0.25 * 0.70 + 0.30 * (1 - B), "B", 0.20),
    ]
    for ax, (title, xs, f, xlabel, bx) in zip(axes, panels):
        for lo, hi, colr, lab in bands:
            ax.axhspan(lo, hi, color=colr, zorder=0)
        ys = f(xs)
        ax.plot(xs, ys, color="#2F4858", lw=3.0, zorder=3)
        ax.plot([bx], [f(bx)], "o", ms=9, color=C_RED, zorder=4,
                markeredgecolor="white", markeredgewidth=1.4)
        for thr in (0.40, 0.60, 0.75):
            ax.axhline(thr, color="#8a8a8a", lw=0.9, ls="--", zorder=1)
        ax.set_xlim(0, 1); ax.set_ylim(0.2, 1.0)
        ax.set_xlabel(xlabel, fontsize=13, style="italic")
        ax.set_title(title, fontsize=12)
        ax.tick_params(labelsize=11)
        ax.grid(True, **GRID)
    axes[0].set_ylabel("Sustainability index  S", fontsize=12.5)
    for lo, hi, colr, lab in bands:
        axes[2].text(1.03, (lo + hi) / 2, lab, transform=axes[2].get_yaxis_transform(),
                     va="center", fontsize=10.2, color="#555555")
    fig.subplots_adjust(right=0.85, wspace=0.10)
    fig.savefig(os.path.join(OUT, "fig6_monotonic.png"), dpi=200,
                bbox_inches="tight", facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    fig1(); fig2(); fig3(); fig4(); fig5(); fig6()
    from PIL import Image
    for f in sorted(os.listdir(OUT)):
        if f.endswith(".png"):
            im = Image.open(os.path.join(OUT, f))
            print(f"generated: {f}  {im.size[0]}x{im.size[1]}px  AR={im.size[0]/im.size[1]:.2f}")
