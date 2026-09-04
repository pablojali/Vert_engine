"""Generate all chart PNGs used in the report, at high DPI, transparent bg.

Adapted from Report/make_charts.py (the mockup) to run fully in memory -
returns a dict of {chart_name: BytesIO} instead of writing files to a
hardcoded /home/claude/... path, so it works unmodified on Streamlit
Community Cloud (no local disk assumptions, no state left behind
between report generations).
"""
import io
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np

from . import theme as T

FONTS_DIR = Path(__file__).parent / "fonts"

_fonts_registered = False


def _register_matplotlib_fonts():
    global _fonts_registered
    if _fonts_registered:
        return
    for f in fm.findSystemFonts(fontpaths=[str(FONTS_DIR)]):
        fm.fontManager.addfont(f)
    plt.rcParams["font.family"] = "Inter"
    _fonts_registered = True


def _style_ax(ax, ylabel=None):
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


def _save(fig, w, h) -> io.BytesIO:
    fig.set_size_inches(w, h)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=300, transparent=True, bbox_inches="tight", pad_inches=0.04)
    plt.close(fig)
    buf.seek(0)
    return buf


def _line_chart(dist, values, color, ylabel, w=4.55, h=0.92, fill=True,
                 elevation_x=None, elevation_y=None, label_fs=10, tick_fs=9.5):
    fig, ax = plt.subplots()

    if elevation_x is not None and len(elevation_x) == len(elevation_y) and max(elevation_y or [0]) > 0:
        ax2 = ax.twinx()
        ax2.fill_between(elevation_x, 0, elevation_y, color=T.TEXT_FAINT, alpha=0.10, zorder=1)
        ax2.set_ylim(0, max(elevation_y) * 3.4)
        ax2.axis("off")

    ax.plot(dist, values, color=color, linewidth=2.0, solid_capstyle="round", zorder=3)
    ax.scatter([dist[0], dist[-1]], [values[0], values[-1]], color=color, s=14, zorder=4, edgecolors="none")
    if fill:
        ax.fill_between(dist, values, min(values) - (max(values) - min(values)) * 0.15,
                         color=color, alpha=0.10, zorder=2)
    _style_ax(ax, ylabel)
    ax.tick_params(labelsize=tick_fs)
    ax.yaxis.label.set_size(label_fs)
    ax.set_xlim(dist[0], dist[-1])
    pad = (max(values) - min(values)) * 0.22 or 1
    ax.set_ylim(min(values) - pad, max(values) + pad)
    ax.set_xlabel("Distance (km)", color=T.TEXT_MUTED, fontsize=label_fs, labelpad=4)
    return _save(fig, w, h)


def _degradation_chart(deg, w=2.95, h=1.35):
    x = deg["distance_km"]
    fig, ax = plt.subplots()

    elev = deg.get("elevation_m")
    if elev and max(elev) > 0:
        ax2 = ax.twinx()
        ax2.fill_between(x, 0, elev, color=T.TEXT_FAINT, alpha=0.08, zorder=1)
        ax2.set_ylim(0, max(elev) * 3.2)
        ax2.axis("off")

    ax.plot(x, deg["vpi_index"], color=T.CYAN, linewidth=2.2, label="VPI", zorder=4)
    ax.plot(x, deg["dmi_index"], color=T.ORANGE, linewidth=2.2, label="DMI", zorder=4)
    ax.plot(x, deg["er_index"], color=T.GREEN, linewidth=2.2, label="ER", zorder=4)
    for arr, c in [(deg["vpi_index"], T.CYAN), (deg["dmi_index"], T.ORANGE), (deg["er_index"], T.GREEN)]:
        ax.scatter([x[0], x[-1]], [arr[0], arr[-1]], color=c, s=22, zorder=5, edgecolors="none")

    _style_ax(ax, "Index (0-100)")
    ax.tick_params(labelsize=10)
    ax.yaxis.label.set_size(11)
    ax.set_ylim(0, 105)
    ax.set_xlim(x[0], x[-1])
    ax.set_xlabel("Distance (km)", color=T.TEXT_MUTED, fontsize=11, labelpad=6)
    ax.legend(loc="upper right", frameon=False, fontsize=10, labelcolor=T.TEXT_MUTED,
              handlelength=1.4, handletextpad=0.5, ncol=3, bbox_to_anchor=(1.0, 1.16))
    return _save(fig, w, h)


def _position_chart(pos):
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

    _style_ax(ax, "Race position")
    ax.invert_yaxis()
    ax.set_xlim(x[0], x[-1])
    ax.set_xlabel("Distance (km)", color=T.TEXT_MUTED, fontsize=8.5, labelpad=5)
    return _save(fig, 5.05, 1.55)


def build_charts(data: dict, progression_wh=(4.55, 0.92), degradation_wh=(2.95, 1.35)) -> dict:
    """Returns {name: BytesIO} for every PNG render_pdf.py embeds -
    vpi_progression, dmi_progression, pace_progression, degradation_curve,
    position_progression.

    progression_wh / degradation_wh let the caller size these charts to
    match the actual box they'll be drawn into (render_pdf.py's page2/
    page3 layout constants) so the PNG renders at native resolution
    instead of being stretched to fill a bigger box than it was drawn
    for - real user feedback that the charts looked too small/cramped
    led to enlarging their page layout, so the source render must grow
    with it or the enlarged charts come out blurry."""
    _register_matplotlib_fonts()

    elev_x = data["degradation_index"]["distance_km"]
    elev_y = data["degradation_index"]["elevation_m"]
    pw, ph = progression_wh

    charts = {}
    charts["vpi_progression"] = _line_chart(
        data["vpi_progression"]["distance_km"], data["vpi_progression"]["value_m_h"],
        T.CYAN, "VPI (m/h)", w=pw, h=ph, elevation_x=elev_x, elevation_y=elev_y,
    )
    charts["dmi_progression"] = _line_chart(
        data["dmi_progression"]["distance_km"], data["dmi_progression"]["value_km_h"],
        T.ORANGE, "DMI (km/h)", w=pw, h=ph, elevation_x=elev_x, elevation_y=elev_y,
    )
    charts["pace_progression"] = _line_chart(
        data["effort_pace_progression"]["distance_km"], data["effort_pace_progression"]["pace_min_km"],
        T.GREEN, "Pace (min/km)", w=pw, h=ph, elevation_x=elev_x, elevation_y=elev_y,
    )
    charts["degradation_curve"] = _degradation_chart(data["degradation_index"],
                                                       w=degradation_wh[0], h=degradation_wh[1])
    charts["position_progression"] = _position_chart(data["position_progression"])
    return charts
