# -*- coding: utf-8 -*-
"""Generate all figures for the ParaSail research paper (deterministic
mathematical illustrations and schematic diagrams -- no fabricated data)."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from matplotlib.colors import LinearSegmentedColormap
import numpy as np
import os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "figures")
os.makedirs(OUT, exist_ok=True)

# Morandi low-saturation palette (per design system default)
C_BLUE, C_TAN, C_GREEN, C_RED, C_PURP = "#6B9DAD", "#C49B72", "#7BA68A", "#B87472", "#9687A8"
C_TEAL, C_STEEL, C_GOLD = "#7AADA0", "#7A9BB8", "#C8B87C"
GRID = dict(alpha=0.3, linewidth=0.6)

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 10,
    "axes.edgecolor": "#555555",
    "axes.linewidth": 0.8,
    "axes.titlesize": 11,
    "figure.facecolor": "white",
})

# ----------------------------------------------------------------------------
# Figure 1 -- Six-layer system architecture
# ----------------------------------------------------------------------------
def fig1():
    fig, ax = plt.subplots(figsize=(11.2, 5.6))
    ax.set_xlim(0, 112)
    ax.set_ylim(0, 56)
    ax.axis("off")

    layers = [
        ("1  INGESTION", C_STEEL, [
            "Open-Meteo (forecast /",
            "  marine)",
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

    bw, bh, gap, x0, ytop = 16.2, 34.5, 2.4, 1.0, 50.0
    for i, (title, color, items) in enumerate(layers):
        x = x0 + i * (bw + gap)
        # header band
        ax.add_patch(FancyBboxPatch((x, ytop - 5.2), bw, 5.2,
                     boxstyle="round,pad=0.15,rounding_size=0.6",
                     fc=color, ec="none"))
        ax.text(x + bw / 2, ytop - 2.6, title, ha="center", va="center",
                fontsize=9.5, fontweight="bold", color="white")
        # body box
        ax.add_patch(FancyBboxPatch((x, ytop - 5.2 - bh), bw, bh,
                     boxstyle="round,pad=0.15,rounding_size=0.6",
                     fc="white", ec=color, lw=1.6))
        yy = ytop - 8.6
        for it in items:
            cont = it.startswith("  ")
            ax.text(x + 1.0, yy, it.strip(), ha="left", va="center",
                fontsize=7.0, color="#333333",
                fontstyle="italic" if cont else "normal")
            yy -= 3.6
        # arrow to next layer
        if i < len(layers) - 1:
            ax.add_patch(FancyArrowPatch((x + bw + 0.35, ytop - 5.2 - bh / 2),
                         (x + bw + gap - 0.35, ytop - 5.2 - bh / 2),
                         arrowstyle="-|>", mutation_scale=16,
                         lw=2.0, color="#606060"))
    # left input / right output labels
    ax.annotate("open data &\nlocal uploads", xy=(x0 - 0.4, ytop - 5.2 - bh / 2),
                xytext=(x0 - 1.2, ytop - 5.2 - bh / 2 + 7.5), fontsize=8.5,
                ha="center", color="#505050",
                arrowprops=dict(arrowstyle="-|>", lw=1.4, color="#808080"))
    ax.annotate("advisory + context\n+ conversation",
                xy=(x0 + 5 * (bw + gap) + bw - 1.2, ytop - 5.2 - bh / 2),
                xytext=(x0 + 5 * (bw + gap) + bw + 0.8,
                        ytop - 5.2 - bh / 2 + 8.5), fontsize=8.5,
                ha="center", color="#505050",
                arrowprops=dict(arrowstyle="-|>", lw=1.4, color="#808080"))
    # infrastructure bar
    ax.add_patch(FancyBboxPatch((x0, 4.2), 6 * bw + 5 * gap, 6.4,
                 boxstyle="round,pad=0.15,rounding_size=0.6",
                 fc="#F2F4F6", ec="#909090", lw=1.0, hatch=None))
    ax.text(x0 + (6 * bw + 5 * gap) / 2, 7.4,
            "Shared infrastructure:  PostgreSQL + PostGIS  |  Qdrant vector DB  |  "
            "vLLM inference server (local AI)  |  Docker Compose  |  "
            "YAML config-driven deployment",
            ha="center", va="center", fontsize=8.2, color="#404040")
    for i in range(6):
        x = x0 + i * (bw + gap) + bw / 2
        ax.add_patch(FancyArrowPatch((x, ytop - 5.2 - bh - 0.4), (x, 10.8),
                     arrowstyle="-|>", mutation_scale=11, lw=1.1,
                     color="#B0B0B0", linestyle=(0, (4, 3))))
    fig.tight_layout(pad=0.4)
    fig.savefig(os.path.join(OUT, "fig1_architecture.png"), dpi=200,
                bbox_inches="tight", facecolor="white")
    plt.close(fig)

# ----------------------------------------------------------------------------
# Figure 2 -- Advisory scoring surface S(C, W) at B = 0.20 with class regions
# ----------------------------------------------------------------------------
def fig2():
    fig, ax = plt.subplots(figsize=(9.4, 5.3))
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
                        linewidths=1.3, linestyles="--")
        ax.clabel(cs, fmt={thr: f"S = {thr:.2f}"}, fontsize=8.5)

    ax.text(0.06, 0.06, "DELAY OR RELOCATE /\nDO NOT FISH", fontsize=8.5,
            color="#6d4a49", fontweight="bold", va="bottom")
    ax.text(0.30, 0.18, "DELAY OR RELOCATE", fontsize=8.5, color="#5c5545")
    ax.text(0.55, 0.44, "PROCEED WITH CAUTION", fontsize=8.5, color="#3f5a46")
    ax.text(0.74, 0.78, "PROCEED", fontsize=9.5, color="#2e4a36", fontweight="bold")

    cbar = fig.colorbar(cf, ax=ax, shrink=0.92, pad=0.02)
    cbar.set_label("Sustainability index  S", fontsize=9.5)
    ax.set_xlabel("Catch-likelihood composite  C", fontsize=10)
    ax.set_ylabel("Weather-safety component  W", fontsize=10)
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.grid(True, **GRID)
    ax.set_title("Decision surface at bycatch risk  B = 0.20  "
                 "(dashed lines: advisory class thresholds)", fontsize=10)
    fig.tight_layout(pad=0.6)
    fig.savefig(os.path.join(OUT, "fig2_scoring.png"), dpi=200,
                bbox_inches="tight", facecolor="white")
    plt.close(fig)

# ----------------------------------------------------------------------------
# Figure 3 -- Phase-gate methodology roadmap
# ----------------------------------------------------------------------------
def fig3():
    fig, ax = plt.subplots(figsize=(11.2, 4.3))
    ax.set_xlim(0, 112)
    ax.set_ylim(0, 43)
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
        "G1: region and\nrules inventory\nsigned off",
        "G2: live fetches\nvalidated; freshness\naudit passes",
        "G3: baselines beat\nnaive persistence",
        "G4: LoRA converges\nwithin memory\nbudget",
        "G5: closure / MPA\nblocks exact;\ntop-k relevant",
        "G6: answers grounded\n& cited; fallback\nexact; latency in budget",
    ]

    bw, bh, gap, x0, ytop = 13.6, 20.5, 2.2, 1.5, 40.0
    for i, (pid, name, color, note) in enumerate(phases):
        x = x0 + i * (bw + gap)
        ax.add_patch(FancyBboxPatch((x, ytop - bh), bw, bh,
                     boxstyle="round,pad=0.15,rounding_size=0.7",
                     fc=color, ec="none"))
        ax.text(x + bw / 2, ytop - 4.2, pid, ha="center", va="center",
                fontsize=9.5, fontweight="bold", color="white")
        ax.text(x + bw / 2, ytop - 9.6, name, ha="center", va="center",
                fontsize=7.4, fontweight="bold", color="white")
        ax.text(x + bw / 2, ytop - 16.4, note, ha="center", va="center",
                fontsize=6.4, color="white")
        if i < len(phases) - 1:
            gx = x + bw + gap / 2
            gate = gates[i]
            ax.plot([gx], [ytop - bh / 2], marker="D", markersize=6,
                    color="#C8B87C", markeredgecolor="#8a7a4a", zorder=5)
            ax.add_patch(FancyArrowPatch((x + bw + 0.25, ytop - bh / 2),
                         (x + bw + gap - 0.25, ytop - bh / 2),
                         arrowstyle="-|>", mutation_scale=12,
                         lw=1.6, color="#606060"))
            ax.text(gx, ytop - bh - 4.6, gate, ha="center", va="top",
                    fontsize=6.0, color="#555555", linespacing=1.3)

    ax.annotate("", xy=(110.5, 6.5), xytext=(1.5, 6.5),
                arrowprops=dict(arrowstyle="-|>", lw=2.2, color="#7A9BB8"))
    ax.text(56, 3.4, "iterative engineering with phase-gate acceptance checks "
            "(every gate must pass before the next phase begins)",
            ha="center", va="center", fontsize=9, color="#4a5a68")
    fig.tight_layout(pad=0.4)
    fig.savefig(os.path.join(OUT, "fig3_phases.png"), dpi=200,
                bbox_inches="tight", facecolor="white")
    plt.close(fig)

# ----------------------------------------------------------------------------
# Figure 4 -- Case study seasonal calendar (schematic)
# ----------------------------------------------------------------------------
def fig4():
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(9.8, 5.6),
                                   sharex=True,
                                   gridspec_kw={"height_ratios": [1, 1.35],
                                                "hspace": 0.30})
    months = np.arange(0, 12.02, 0.01)
    mlabels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    # --- top: schematic SST cycle ---
    sst = 28.1 + 1.65 * np.cos(2 * np.pi * (months - 4.4) / 12.0)
    ax1.plot(months, sst, color=C_RED, lw=2.2)
    ax1.set_ylabel("Sea-surface\ntemperature (°C)", fontsize=9)
    ax1.set_ylim(26.0, 30.2)
    ax1.set_xlim(0, 12)
    ax1.set_xticks(range(12)); ax1.set_xticklabels(mlabels, fontsize=8.5)
    ax1.grid(True, **GRID)
    # monsoon closure band (mid-June to end-July)
    ax1.axvspan(5.5, 7.0, color="#9BB0C4", alpha=0.35, hatch="///",
                edgecolor="#5c7a94", lw=0.8)
    ax1.text(6.25, 29.75, "monsoon\nfishing closure", ha="center",
             va="top", fontsize=8, color="#33506a", linespacing=1.2)
    ax1.text(0.25, 26.35, "schematic climatological cycle, southwest coast of India",
             fontsize=7.8, color="#777777", style="italic")

    # --- bottom: configured species seasons and closures ---
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
    # June-July spawning closure overlay on sardine row
    ax2.broken_barh([(5.5, 1.5)], (len(seasons) - 0.32 - 0.0, 0.64),
                    facecolors="none", edgecolor="#33506a", lw=1.6, hatch="xxx")
    ax2.set_yticks([len(seasons) - i for i in range(len(seasons))])
    ax2.set_yticklabels([s[0] for s in seasons], fontsize=8.3)
    ax2.set_xlim(0, 12)
    ax2.set_xticks(range(12)); ax2.set_xticklabels(mlabels, fontsize=8.5)
    ax2.grid(True, axis="x", **GRID)
    ax2.set_title("Species registry seasons, spawning closure (cross-hatched) and "
                  "monsoon closure band (blue)", fontsize=9.5)
    fig.tight_layout(pad=0.5)
    fig.savefig(os.path.join(OUT, "fig4_calendar.png"), dpi=200,
                bbox_inches="tight", facecolor="white")
    plt.close(fig)

# ----------------------------------------------------------------------------
# Figure 5 -- LoRA parameter efficiency (ViT-B/16, 12 encoder layers)
# ----------------------------------------------------------------------------
def fig5():
    fig, ax = plt.subplots(figsize=(8.6, 4.9))
    total = 85.8  # ViT-B/16 backbone, millions of parameters
    r_vals = [4, 8, 16]
    lora = [2 * 12 * r * (768 + 768) / 1e6 for r in r_vals]  # q+v, 12 layers
    cats = ["Full fine-tuning"] + [f"LoRA\n(rank r = {r})" for r in r_vals]
    vals = [total] + lora
    colors = [C_RED, "#A8C3CE", C_BLUE, "#4F7E92"]

    bars = ax.bar(cats, vals, color=colors, width=0.58,
                  edgecolor="white", lw=0.8)
    ax.set_yscale("log")
    ax.set_ylim(0.05, 300)
    ax.set_ylabel("Trainable parameters (millions, log scale)", fontsize=9.5)
    labels = [f"{total:.1f} M\n(100%)",
              f"{lora[0]:.3f} M\n({lora[0]/total*100:.2f}%)",
              f"{lora[1]:.3f} M\n({lora[1]/total*100:.2f}%)",
              f"{lora[2]:.3f} M\n({lora[2]/total*100:.2f}%)"]
    for bar, lab in zip(bars, labels):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() * 1.22,
                lab, ha="center", va="bottom", fontsize=8.8, color="#333333")
    # highlight the system default r = 8
    ax.annotate("system default", xy=(2, lora[1] * 1.05), xytext=(2.02, 22),
                fontsize=8.6, color="#2e5a6b", ha="center",
                arrowprops=dict(arrowstyle="-|>", lw=1.2, color="#2e5a6b"))
    ax.grid(True, axis="y", **GRID)
    ax.set_title("Parameter efficiency on ViT-B/16 (LoRA on query / value "
                 "projections of all 12 encoder blocks)", fontsize=10)
    fig.tight_layout(pad=0.5)
    fig.savefig(os.path.join(OUT, "fig5_lora.png"), dpi=200,
                bbox_inches="tight", facecolor="white")
    plt.close(fig)

# ----------------------------------------------------------------------------
# Figure 6 -- Monotonicity of the sustainability index in every input
# ----------------------------------------------------------------------------
def fig6():
    fig, axes = plt.subplots(1, 3, figsize=(11.0, 3.9), sharey=True)
    bands = [(0.00, 0.40, "#E8D5D4", "DO NOT FISH / DELAY"),
             (0.40, 0.60, "#F0E8D8", "DELAY OR RELOCATE"),
             (0.60, 0.75, "#E2EADB", "PROCEED WITH CAUTION"),
             (0.75, 1.00, "#CFE2CB", "PROCEED")]
    panels = [
        ("(a) vary C   (W = 0.70, B = 0.20)", np.linspace(0, 1, 201),
         lambda C: 0.45 * C + 0.25 * 0.70 + 0.30 * 0.80, "C", (0.70, 0.70, 0.20)),
        ("(b) vary W   (C = 0.70, B = 0.20)", np.linspace(0, 1, 201),
         lambda W: 0.45 * 0.70 + 0.25 * W + 0.30 * 0.80, "W", (0.70, 0.70, 0.20)),
        ("(c) vary B   (C = 0.70, W = 0.70)", np.linspace(0, 1, 201),
         lambda B: 0.45 * 0.70 + 0.25 * 0.70 + 0.30 * (1 - B), "B", (0.70, 0.70, 0.20)),
    ]
    for ax, (title, xs, f, xlabel, (c0, w0, b0)) in zip(axes, panels):
        for lo, hi, colr, lab in bands:
            ax.axhspan(lo, hi, color=colr, zorder=0)
        ys = f(xs)
        ax.plot(xs, ys, color="#2F4858", lw=2.4, zorder=3)
        # baseline marker
        bx = {"C": c0, "W": w0, "B": b0}[xlabel]
        ax.plot([bx], [f(bx)], "o", ms=7, color=C_RED, zorder=4,
                markeredgecolor="white", markeredgewidth=1.2)
        for thr in (0.40, 0.60, 0.75):
            ax.axhline(thr, color="#8a8a8a", lw=0.8, ls="--", zorder=1)
        ax.set_xlim(0, 1); ax.set_ylim(0.2, 1.0)
        ax.set_xlabel(xlabel, fontsize=10, style="italic")
        ax.set_title(title, fontsize=9.3)
        ax.grid(True, **GRID)
    axes[0].set_ylabel("Sustainability index  S", fontsize=10)
    # class labels on right edge of last panel
    for lo, hi, colr, lab in bands:
        axes[2].text(1.02, (lo + hi) / 2, lab, transform=axes[2].get_yaxis_transform(),
                     va="center", fontsize=7.4, color="#555555")
    fig.subplots_adjust(right=0.86, wspace=0.10)
    fig.savefig(os.path.join(OUT, "fig6_monotonic.png"), dpi=200,
                bbox_inches="tight", facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    fig1(); fig2(); fig3(); fig4(); fig5(); fig6()
    for f in sorted(os.listdir(OUT)):
        print("generated:", f)
