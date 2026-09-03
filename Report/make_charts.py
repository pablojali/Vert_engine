"""Generate all chart PNGs used in the report, at high DPI, transparent bg."""
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib.patches import FancyBboxPatch
import numpy as np
import os

import theme as T

for f in fm.findSystemFonts(fontpaths=["/usr/share/fonts/opentype/inter", "/usr/share/fonts/truetype/jetbrains-mono"]):
    fm.fontManager.addfont(f)
plt.rcParams["font.family"] = "Inter"

OUT = "/home/claude/vertlabs_pdf/charts"
os.makedirs(OUT, exist_ok=True)

with open("/home/claude/vertlabs_pdf/data/wayne_walsh_lavaredo120k_2026.json") as f:
    D = json.load(f)


def style_ax(ax, ylabel=None):
    ax.set_facecolor("none")
    for s in ax.spines.values():
        s.set_visible(False)
    ax.spines["bottom"].set_visible(True)
    ax.spines["bottom"].set_color(T.LINE)
    ax.spines["bottom"].set_linewidth(0.8)
    ax.tick_params(colors=T.TEXT_MUTED, labelsize=8, length=0)
    ax.grid(axis="y", color=T.GRID, linewidth=0.7, alpha=0.9)
    ax.set_axisbelow(True)
    for lbl in ax.get_xticklabels() + ax.get_yticklabels():
        lbl.set_fontfamily("Inter")
    if ylabel:
        ax.set_ylabel(ylabel, color=T.TEXT_MUTED, fontsize=8.5, labelpad=6)


def save(fig, name, w, h):
    fig.set_size_inches(w, h)
    fig.savefig(f"{OUT}/{name}.png", dpi=300, transparent=True,
                bbox_inches="tight", pad_inches=0.04)
    plt.close(fig)


# ---------------------------------------------------------------- VPI mini
def line_chart(dist, values, color, name, ylabel, w=3.35, h=1.05, fill=True,
                elevation_x=None, elevation_y=None, label_fs=8, tick_fs=8):
    fig, ax = plt.subplots()

    if elevation_x is not None:
        ax2 = ax.twinx()
        ax2.fill_between(elevation_x, 0, elevation_y, color=T.TEXT_FAINT, alpha=0.10, zorder=1)
        ax2.set_ylim(0, max(elevation_y) * 3.4)
        ax2.axis("off")

    ax.plot(dist, values, color=color, linewidth=2.0, solid_capstyle="round", zorder=3)
    ax.scatter([dist[0], dist[-1]], [values[0], values[-1]], color=color, s=14, zorder=4, edgecolors="none")
    if fill:
        ax.fill_between(dist, values, min(values) - (max(values) - min(values)) * 0.15,
                         color=color, alpha=0.10, zorder=2)
    style_ax(ax, ylabel)
    ax.tick_params(labelsize=tick_fs)
    ax.yaxis.label.set_size(label_fs)
    ax.set_xlim(dist[0], dist[-1])
    pad = (max(values) - min(values)) * 0.22 or 1
    ax.set_ylim(min(values) - pad, max(values) + pad)
    ax.set_xlabel("Distance (km)", color=T.TEXT_MUTED, fontsize=label_fs, labelpad=4)
    save(fig, name, w, h)


elev_x = D["degradation_index"]["distance_km"]
elev_y = D["degradation_index"]["elevation_m"]

line_chart(D["vpi_progression"]["distance_km"], D["vpi_progression"]["value_m_h"],
           T.CYAN, "vpi_progression", "VPI (m/h)", w=4.55, h=0.92,
           elevation_x=elev_x, elevation_y=elev_y, label_fs=9, tick_fs=8.5)
line_chart(D["dmi_progression"]["distance_km"], D["dmi_progression"]["value_km_h"],
           T.ORANGE, "dmi_progression", "DMI (km/h)", w=4.55, h=0.92,
           elevation_x=elev_x, elevation_y=elev_y, label_fs=9, tick_fs=8.5)

# effort pace — inverted feel: slower pace = higher number = worse, keep literal
line_chart(D["effort_pace_progression"]["distance_km"], D["effort_pace_progression"]["pace_min_km"],
           T.GREEN, "pace_progression", "Pace (min/km)", w=4.55, h=0.92,
           elevation_x=elev_x, elevation_y=elev_y, label_fs=9, tick_fs=8.5)


# ---------------------------------------------------------- Degradation curve
def degradation_chart():
    deg = D["degradation_index"]
    fig, ax = plt.subplots()
    x = deg["distance_km"]

    # subtle elevation motif in background
    ax2 = ax.twinx()
    elev = deg["elevation_m"]
    ax2.fill_between(x, 0, elev, color=T.TEXT_FAINT, alpha=0.08, zorder=1)
    ax2.set_ylim(0, max(elev) * 3.2)
    ax2.axis("off")

    ax.plot(x, deg["vpi_index"], color=T.CYAN, linewidth=1.8, label="VPI", zorder=4)
    ax.plot(x, deg["dmi_index"], color=T.ORANGE, linewidth=1.8, label="DMI", zorder=4)
    ax.plot(x, deg["er_index"], color=T.GREEN, linewidth=1.8, label="ER", zorder=4)
    for arr, c in [(deg["vpi_index"], T.CYAN), (deg["dmi_index"], T.ORANGE), (deg["er_index"], T.GREEN)]:
        ax.scatter([x[0], x[-1]], [arr[0], arr[-1]], color=c, s=13, zorder=5, edgecolors="none")

    style_ax(ax, "Index (0-100)")
    ax.tick_params(labelsize=7.5)
    ax.yaxis.label.set_size(7.8)
    ax.set_ylim(0, 105)
    ax.set_xlim(x[0], x[-1])
    ax.set_xlabel("Distance (km)", color=T.TEXT_MUTED, fontsize=7.8, labelpad=4)
    leg = ax.legend(loc="upper right", frameon=False, fontsize=7.2, labelcolor=T.TEXT_MUTED,
                     handlelength=1.2, handletextpad=0.4, ncol=3, bbox_to_anchor=(1.0, 1.22))
    save(fig, "degradation_curve", 2.95, 1.35)


degradation_chart()


# ---------------------------------------------------------- Position progression
def position_chart():
    pos = D["position_progression"]
    x = pos["distance_km"]
    y = pos["position"]
    fig, ax = plt.subplots()
    ax.plot(x, y, color=T.TEXT, linewidth=2.0, zorder=3)
    ax.fill_between(x, y, max(y) + 8, color=T.TEXT, alpha=0.06, zorder=2)
    ax.scatter([x[0], x[-1]], [y[0], y[-1]], color=T.TEXT, s=18, zorder=4, edgecolors="none")

    best_i = int(np.argmin(y))
    worst_i = int(np.argmax(y))
    ax.scatter([x[best_i]], [y[best_i]], color=T.GREEN, s=30, zorder=5)
    ax.scatter([x[worst_i]], [y[worst_i]], color=T.ORANGE, s=30, zorder=5)

    style_ax(ax, "Race position")
    ax.invert_yaxis()
    ax.set_xlim(x[0], x[-1])
    ax.set_xlabel("Distance (km)", color=T.TEXT_MUTED, fontsize=8.5, labelpad=5)
    save(fig, "position_progression", 5.05, 1.55)


position_chart()

print("charts written to", OUT)
