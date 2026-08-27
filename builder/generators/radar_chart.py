"""
Builds a small self-contained SVG radar/spider chart (3 axes: VPI, DMI,
ER) overlaying one triangle per analyzed race, colored by distance
bracket. Rendered server-side as plain SVG markup (no JS, no CDN) so it
always works offline and inherits the site's CSS via classes, same as
the existing hex-icon SVGs.

The three metrics are on different scales (m/h, km/h, 0-100 score), so
each axis is plotted against its own [min, max] window instead of a
shared 0-based scale - a tighter window than the metric's full possible
range, chosen so real differences between races are visible instead of
compressed into a sliver near the edge. Each of the 3 grid rings is
labeled with that axis's actual value at that ring (e.g. 900/1200/1500
for VPI), since the three axes don't share a scale. A value outside the
window just clamps to the nearest edge (center or outer ring) instead
of over/underflowing the chart.
"""
import math

# (min, max) per axis - the "interesting" band where real races differ,
# not the metric's full theoretical range. Tune here only; nothing else
# needs to change to shift these.
AXIS_RANGE = {
    "vpi": (600, 1500),   # m/h on >=12% climbs
    "dmi": (6, 15),       # km/h on <=-12% descents
    "er": (40, 100),      # 0-100 score
}

AXES = ("vpi", "dmi", "er")
RING_FRACTIONS = (1 / 3, 2 / 3, 1.0)
CX, CY, R = 110, 110, 80

# Distance brackets requested for the overlay: >120K red, 80-120K green,
# <=80K orange. Unknown distance falls back to a neutral/muted stroke
# instead of silently guessing a bracket.
LONG_KM = 120
MID_KM = 80


def _bracket_color(distance_km) -> str:
    if distance_km is None:
        return "var(--color-muted)"
    if distance_km > LONG_KM:
        return "var(--color-dist-long)"
    if distance_km > MID_KM:
        return "var(--color-dist-mid)"
    return "var(--color-dist-short)"


def _angle(i: int) -> float:
    return math.radians(-90 + i * 120)


def _point(i: int, ratio: float) -> tuple[float, float]:
    ang = _angle(i)
    return CX + R * ratio * math.cos(ang), CY + R * ratio * math.sin(ang)


def _fmt_points(pts) -> str:
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)


def _ratio(axis: str, value) -> float:
    lo, hi = AXIS_RANGE[axis]
    if value is None:
        return 0.0
    return max(0.0, min(1.0, (value - lo) / (hi - lo)))


def _ratios(vpi, dmi, er) -> list[float]:
    return [_ratio("vpi", vpi), _ratio("dmi", dmi), _ratio("er", er)]


def build_radar_svg(races: list[dict]) -> str | None:
    """races: dicts with vpi/dmi/er (all required, already filtered by the
    caller - see athlete_generator.py's eligibility check) and optional
    distance_km. One outlined triangle per race, overlaid on the same
    3-axis grid - not a single averaged shape. Returns None if `races`
    is empty."""
    if not races:
        return None

    grid_rings = "\n".join(
        f'    <polygon class="radar-grid" points="{_fmt_points(_point(i, frac) for i in range(3))}"/>'
        for frac in RING_FRACTIONS
    )
    axis_lines = "\n".join(
        f'    <line class="radar-axis" x1="{CX}" y1="{CY}" x2="{_point(i, 1.0)[0]:.1f}" y2="{_point(i, 1.0)[1]:.1f}"/>'
        for i in range(3)
    )

    # Ring value labels: each axis has its own scale, so each ring shows a
    # different number per axis (e.g. VPI's outer ring is 1500, DMI's is
    # 15) - offset slightly off the axis line so the number doesn't sit
    # on top of it.
    tick_labels = []
    for i, axis in enumerate(AXES):
        lo, hi = AXIS_RANGE[axis]
        perp = _angle(i) + math.pi / 2
        for frac in RING_FRACTIONS:
            x, y = _point(i, frac)
            tx, ty = x + 7 * math.cos(perp), y + 7 * math.sin(perp)
            value = round(lo + frac * (hi - lo))
            tick_labels.append(f'    <text class="radar-tick" x="{tx:.1f}" y="{ty:.1f}" text-anchor="middle">{value}</text>')

    race_polygons = []
    for race in races:
        ratios = _ratios(race.get("vpi"), race.get("dmi"), race.get("er"))
        points = _fmt_points(_point(i, ratios[i]) for i in range(3))
        color = _bracket_color(race.get("distance_km"))
        race_polygons.append(
            f'    <polygon class="radar-data" points="{points}" '
            f'style="fill:none;stroke:{color};stroke-width:2;stroke-opacity:0.85"/>'
        )

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
        f'<svg viewBox="0 0 220 220" class="radar-chart" role="img" aria-label="VPI/DMI/ER radar chart, one outline per analyzed race">\n'
        f'{grid_rings}\n'
        f'{axis_lines}\n'
        + "\n".join(race_polygons) + "\n"
        + "\n".join(tick_labels) + "\n"
        f'{labels}\n'
        f'</svg>'
    )
