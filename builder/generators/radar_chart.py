"""
Builds a small self-contained SVG radar/spider chart (3 axes: VPI, DMI,
ER) for an athlete's career averages. Rendered server-side as plain SVG
markup (no JS, no CDN) so it always works offline and inherits the
site's CSS via classes, same as the existing hex-icon SVGs.

The three metrics are on different scales (m/h, km/h, 0-100 score), so
each axis is normalized against a fixed reference ceiling before being
plotted. These ceilings are a rough "very strong performance" reference,
not a hard limit - a value above the ceiling is just clamped to the
edge of the chart.
"""
import math

VPI_MAX = 1200  # m/h on >=12% climbs
DMI_MAX = 15    # km/h on <=-12% descents
ER_MAX = 100    # already a 0-100 score

AXES = ("vpi", "dmi", "er")
CX, CY, R = 110, 110, 80


def _angle(i: int) -> float:
    return math.radians(-90 + i * 120)


def _point(i: int, ratio: float) -> tuple[float, float]:
    ang = _angle(i)
    return CX + R * ratio * math.cos(ang), CY + R * ratio * math.sin(ang)


def _fmt_points(pts) -> str:
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)


def build_radar_svg(vpi, dmi, er) -> str | None:
    """Returns an inline <svg> string, or None if there's no data yet."""
    if vpi is None and dmi is None and er is None:
        return None

    values = (vpi or 0, dmi or 0, er or 0)
    maxes = (VPI_MAX, DMI_MAX, ER_MAX)
    ratios = [max(0.0, min(1.0, v / m)) for v, m in zip(values, maxes)]

    grid_rings = "\n".join(
        f'    <polygon class="radar-grid" points="{_fmt_points(_point(i, frac) for i in range(3))}"/>'
        for frac in (0.33, 0.66, 1.0)
    )
    axis_lines = "\n".join(
        f'    <line class="radar-axis" x1="{CX}" y1="{CY}" x2="{_point(i, 1.0)[0]:.1f}" y2="{_point(i, 1.0)[1]:.1f}"/>'
        for i in range(3)
    )
    data_polygon = _fmt_points(_point(i, ratios[i]) for i in range(3))

    label_r = R + 24
    label_anchors = ("middle", "start", "end")
    label_dy = (-4, 4, 4)
    labels = "\n".join(
        f'    <text class="radar-label radar-label-{AXES[i]}" x="{CX + label_r * math.cos(_angle(i)):.1f}" '
        f'y="{CY + label_r * math.sin(_angle(i)) + label_dy[i]:.1f}" text-anchor="{label_anchors[i]}">'
        f'{AXES[i].upper()}</text>'
        for i in range(3)
    )

    return (
        f'<svg viewBox="0 0 220 220" class="radar-chart" role="img" aria-label="VPI/DMI/ER radar chart">\n'
        f'{grid_rings}\n'
        f'{axis_lines}\n'
        f'    <polygon class="radar-data" points="{data_polygon}"/>\n'
        f'{labels}\n'
        f'</svg>'
    )
