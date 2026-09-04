"""Reusable low-level drawing components shared by every page."""
import io
import math
from pathlib import Path
from reportlab.lib.colors import HexColor, Color
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas as canvas_mod
from . import theme as T

LOGO_PATH = Path(__file__).parent / "logo.png"
_logo_reader = None


def _logo_image() -> ImageReader:
    global _logo_reader
    if _logo_reader is None:
        _logo_reader = ImageReader(str(LOGO_PATH))
    return _logo_reader


def hex_alpha(hexcolor, alpha):
    c = HexColor(hexcolor)
    return Color(c.red, c.green, c.blue, alpha=alpha)


# ---------------------------------------------------------------- page frame
def draw_page_background(c):
    c.setFillColor(HexColor(T.BG))
    c.rect(0, 0, T.PAGE_W, T.PAGE_H, fill=1, stroke=0)


def draw_topo_motif(c, x, y, w, h, seed=1, n=5, alpha=0.05):
    """Subtle nested topographic-line motif, used sparingly as texture."""
    import random
    rnd = random.Random(seed)
    c.saveState()
    p = c.beginPath()
    c.setStrokeColor(hex_alpha(T.TEXT, alpha))
    c.setLineWidth(0.6)
    for i in range(n):
        pts = []
        steps = 24
        base_y = y + h * (i + 1) / (n + 1)
        for s in range(steps + 1):
            px = x + w * s / steps
            wob = math.sin(s / 3.2 + i * 1.7 + rnd.random()) * (h / (n * 3.2))
            pts.append((px, base_y + wob))
        path = c.beginPath()
        path.moveTo(*pts[0])
        for px, py in pts[1:]:
            path.lineTo(px, py)
        c.drawPath(path, stroke=1, fill=0)
    c.restoreState()


# ---------------------------------------------------------------- header
def draw_header(c, page_index, page_total=5):
    top = T.PAGE_H - T.MARGIN
    x = T.MARGIN

    # Real VertLabs hexagon mark (assets/img/logo.png) instead of a
    # hand-drawn placeholder glyph - square aspect, drawn at a fixed
    # height with mask="auto" to keep its transparent background.
    mark_size = 24
    my = top - mark_size + 4
    c.drawImage(_logo_image(), x, my, width=mark_size, height=mark_size,
                preserveAspectRatio=True, mask="auto")

    tx = x + mark_size + 10
    c.setFillColor(HexColor(T.TEXT))
    c.setFont(T.FONT_BOLD, 15.5)
    c.drawString(tx, top - 8, "VERTICAL TRAIL LABS")
    c.setFillColor(HexColor(T.TEXT_MUTED))
    c.setFont(T.FONT_MED, 7.6)
    c.drawString(tx, top - 19, "TERRAIN INTELLIGENCE ENGINE")

    # right-aligned page index
    c.setFont(T.FONT_MONO, 8.5)
    c.setFillColor(HexColor(T.TEXT_FAINT))
    label = f"{page_index:02d} / {page_total:02d}"
    c.drawRightString(T.PAGE_W - T.MARGIN, top - 8, label)
    c.setFont(T.FONT_MED, 7.6)
    c.setFillColor(HexColor(T.TEXT_MUTED))
    c.drawRightString(T.PAGE_W - T.MARGIN, top - 19, "ATHLETE PERFORMANCE REPORT")

    # divider
    div_y = top - mark_size - 10
    c.setStrokeColor(HexColor(T.LINE))
    c.setLineWidth(0.9)
    c.line(T.MARGIN, div_y, T.PAGE_W - T.MARGIN, div_y)
    return div_y


def draw_image_bytes(c, x, y, w, h, image_bytes, border=True, round_corners=False):
    """Draws an image fetched as raw bytes over HTTP (athlete portrait,
    country flag) inside a bordered box, centered/cropped to fill it.
    These come from external CDNs with no alpha channel, so no mask is
    applied (unlike the logo). Callers should skip calling this entirely
    when image_bytes is None (fetch failed or the athlete has none) -
    there is nothing to fall back to that wouldn't misrepresent data."""
    img = ImageReader(io.BytesIO(image_bytes))
    c.saveState()
    if round_corners:
        p = c.beginPath()
        p.roundRect(x, y, w, h, min(w, h) * 0.12)
        c.clipPath(p, stroke=0, fill=0)
    c.drawImage(img, x, y, width=w, height=h, preserveAspectRatio=True, anchor="c", mask=None)
    c.restoreState()
    if border:
        c.setStrokeColor(HexColor(T.LINE))
        c.setLineWidth(0.9)
        if round_corners:
            c.roundRect(x, y, w, h, min(w, h) * 0.12, fill=0, stroke=1)
        else:
            c.rect(x, y, w, h, fill=0, stroke=1)


def draw_footer(c, athlete_name, race_name):
    y = 26
    c.setStrokeColor(HexColor(T.LINE_SOFT))
    c.setLineWidth(0.7)
    c.line(T.MARGIN, y + 14, T.PAGE_W - T.MARGIN, y + 14)
    c.setFont(T.FONT_MED, 7)
    c.setFillColor(HexColor(T.TEXT_FAINT))
    c.drawString(T.MARGIN, y, f"{athlete_name.upper()}  ·  {race_name.upper()}")
    c.drawRightString(T.PAGE_W - T.MARGIN, y, "STOP GUESSING, START MEASURING.")


# ---------------------------------------------------------------- text utils
def draw_label(c, x, y, text, color=T.TEXT_MUTED, size=7.6, tracking=0.6, font=None):
    c.setFont(font or T.FONT_SEMIBOLD, size)
    c.setFillColor(HexColor(color))
    _draw_tracked(c, x, y, text.upper(), size, tracking)


def _draw_tracked(c, x, y, text, size, tracking):
    cx = x
    for ch in text:
        c.drawString(cx, y, ch)
        cx += c.stringWidth(ch, c._fontname, size) + tracking


def wrap_text(c, text, font, size, max_w):
    words = text.split()
    lines, cur = [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if c.stringWidth(trial, font, size) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def draw_paragraph(c, x, y, text, font, size, leading, max_w, color=T.TEXT_MUTED):
    c.setFont(font, size)
    c.setFillColor(HexColor(color))
    lines = wrap_text(c, text, font, size, max_w)
    for i, line in enumerate(lines):
        c.drawString(x, y - i * leading, line)
    return y - len(lines) * leading


# ---------------------------------------------------------------- shapes
def rounded_panel(c, x, y, w, h, r=8, fill=T.PANEL, stroke=T.LINE, lw=0.9):
    c.setFillColor(HexColor(fill))
    if stroke:
        c.setStrokeColor(HexColor(stroke))
        c.setLineWidth(lw)
    c.roundRect(x, y, w, h, r, fill=1, stroke=1 if stroke else 0)


def vline(c, x, y1, y2, color=T.LINE, w=0.8):
    c.setStrokeColor(HexColor(color))
    c.setLineWidth(w)
    c.line(x, y1, x, y2)


def hline(c, x1, x2, y, color=T.LINE, w=0.8):
    c.setStrokeColor(HexColor(color))
    c.setLineWidth(w)
    c.line(x1, y, x2, y)


# ---------------------------------------------------------------- result strip
def draw_result_strip(c, x, y, w, items):
    """items: list of (label, value) tuples, drawn in equal columns."""
    n = len(items)
    col_w = w / n
    for i, (label, value) in enumerate(items):
        cx = x + i * col_w
        if i > 0:
            vline(c, cx, y - 2, y + 40, color=T.LINE)
        draw_label(c, cx + (16 if i > 0 else 0), y + 30, label, color=T.TEXT_MUTED, size=7.4)
        c.setFont(T.FONT_BOLD, 19)
        c.setFillColor(HexColor(T.TEXT))
        c.drawString(cx + (16 if i > 0 else 0), y + 8, str(value))


# ---------------------------------------------------------------- KPI card
def draw_kpi_card(c, x, y, w, h, label, value, unit, color=T.TEXT, sub=None):
    rounded_panel(c, x, y, w, h)
    pad = 12
    draw_label(c, x + pad, y + h - 18, label, color=T.TEXT_MUTED, size=7.2)
    c.setFont(T.FONT_BOLD, 20)
    c.setFillColor(HexColor(color))
    val_str = str(value)
    c.drawString(x + pad, y + h - 40, val_str)
    vw = c.stringWidth(val_str, T.FONT_BOLD, 20)
    if unit:
        c.setFont(T.FONT_MED, 9)
        c.setFillColor(HexColor(T.TEXT_MUTED))
        c.drawString(x + pad + vw + 4, y + h - 36, unit)
    if sub:
        c.setFont(T.FONT_REG, 7.6)
        c.setFillColor(HexColor(T.TEXT_FAINT))
        c.drawString(x + pad, y + 10, sub)


# ---------------------------------------------------------------- performance triangle
def draw_performance_triangle(c, cx, cy, radius, vpi_idx, dmi_idx, er_idx, axis_range):
    """
    Radar-style triangle. Vertices 120 deg apart:
      top = VPI (cyan), bottom-right = DMI (orange), bottom-left = ER (green)
    Geometry uses NORMALIZED 0-100 ratios internally, but each of the 3
    rings is labeled with that axis's own real value (e.g. VPI's rings
    read 900/1200/1500 m/h) instead of a bare 33/66/100 - same
    axis_range bands and ring fractions as the public site's own VTL
    Performance Profile triangle (builder/generators/radar_chart.py),
    so the two look and read the same way.
    """
    angles = {"vpi": 90, "dmi": 90 - 120, "er": 90 - 240}  # degrees, standard math orientation
    ring_fractions = (1 / 3, 2 / 3, 1.0)

    def pt(angle_deg, r):
        a = math.radians(angle_deg)
        return (cx + r * math.cos(a), cy + r * math.sin(a))

    c.saveState()
    for frac in ring_fractions:
        r = radius * frac
        p = c.beginPath()
        v = pt(angles["vpi"], r)
        d = pt(angles["dmi"], r)
        e = pt(angles["er"], r)
        p.moveTo(*v)
        p.lineTo(*d)
        p.lineTo(*e)
        p.close()
        c.setStrokeColor(HexColor(T.LINE))
        c.setLineWidth(0.7 if frac < 1.0 else 1.0)
        c.drawPath(p, stroke=1, fill=0)

    # spokes
    outer = {k: pt(a, radius) for k, a in angles.items()}
    for k, (px, py) in outer.items():
        c.setStrokeColor(HexColor(T.LINE))
        c.setLineWidth(0.7)
        c.line(cx, cy, px, py)

    # per-ring value labels, offset perpendicular to each axis so they
    # don't sit directly on the spoke line
    c.setFont(T.FONT_MONO, 6.3)
    c.setFillColor(HexColor(T.TEXT_FAINT))
    for k, angle_deg in angles.items():
        lo, hi = axis_range[k]
        perp = math.radians(angle_deg) + math.pi / 2
        for frac in ring_fractions:
            px, py = pt(angle_deg, radius * frac)
            tx = px + 8 * math.cos(perp)
            ty = py + 8 * math.sin(perp)
            value = round(lo + frac * (hi - lo))
            c.drawCentredString(tx, ty - 2, str(value))

    # athlete polygon
    va = pt(angles["vpi"], radius * vpi_idx / 100)
    da = pt(angles["dmi"], radius * dmi_idx / 100)
    ea = pt(angles["er"], radius * er_idx / 100)
    poly = c.beginPath()
    poly.moveTo(*va)
    poly.lineTo(*da)
    poly.lineTo(*ea)
    poly.close()
    c.setFillColor(hex_alpha(T.CYAN, 0.13))
    c.setStrokeColor(HexColor(T.TEXT))
    c.setLineWidth(1.6)
    c.drawPath(poly, fill=1, stroke=1)

    # vertex dots
    for (px, py), col in [(va, T.CYAN), (da, T.ORANGE), (ea, T.GREEN)]:
        c.setFillColor(HexColor(col))
        c.circle(px, py, 3.6, fill=1, stroke=0)
        c.setFillColor(HexColor(T.BG))
        c.circle(px, py, 1.3, fill=1, stroke=0)

    # axis end-labels
    label_r = radius + 20
    labels = {"vpi": ("VPI", T.CYAN), "dmi": ("DMI", T.ORANGE), "er": ("ER", T.GREEN)}
    for k, (txt, col) in labels.items():
        lx, ly = pt(angles[k], label_r)
        c.setFont(T.FONT_BOLD, 11)
        c.setFillColor(HexColor(col))
        c.drawCentredString(lx, ly - 4, txt)
    c.restoreState()


# ---------------------------------------------------------------- horizontal bar
def draw_metric_bar(c, x, y, w, h, label_left, label_right, raw_value, index_value, color, axis_range=None):
    """Bar length reflects index_value (0-100, the same VTL axis-range
    ratio the triangle uses) - but the fill no longer prints that
    abstract number on top of it (real user feedback: "no me gusta lo
    de index VPI 43/100, eso que es?"). Instead, when axis_range=(lo, hi)
    is given, the two endpoints are labeled below the bar so what the
    fill length actually means is self-evident."""
    draw_label(c, x, y + h + 12, label_left, color=T.TEXT_MUTED, size=8)
    c.setFont(T.FONT_BOLD, 12)
    c.setFillColor(HexColor(T.TEXT))
    c.drawRightString(x + w, y + h + 13.5, raw_value)

    rounded_panel(c, x, y, w, h, r=h / 2, fill=T.LINE_SOFT, stroke=None)
    fill_w = max(w * index_value / 100, h)
    c.setFillColor(HexColor(color))
    c.roundRect(x, y, fill_w, h, h / 2, fill=1, stroke=0)

    if axis_range is not None:
        lo, hi = axis_range
        c.setFont(T.FONT_MONO, 6.8)
        c.setFillColor(HexColor(T.TEXT_FAINT))
        c.drawString(x, y - 10, str(round(lo)))
        c.drawRightString(x + w, y - 10, str(round(hi)))
