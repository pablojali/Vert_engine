"""
Builds a small self-contained SVG radar/spider chart (3 axes: VPI, DMI,
ER) overlaying one triangle per analyzed race, colored by distance
bracket. Rendered server-side as plain SVG markup (no JS, no CDN) so it
always works offline and inherits the site's CSS via classes, same as
the existing hex-icon SVGs.

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


def _ratios(vpi, dmi, er) -> list[float]:
    values = (vpi or 0, dmi or 0, er or 0)
    maxes = (VPI_MAX, DMI_MAX, ER_MAX)
    return [max(0.0, min(1.0, v / m)) for v, m in zip(values, maxes)]


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
        for frac in (0.33, 0.66, 1.0)
    )
    axis_lines = "\n".join(
        f'    <line class="radar-axis" x1="{CX}" y1="{CY}" x2="{_point(i, 1.0)[0]:.1f}" y2="{_point(i, 1.0)[1]:.1f}"/>'
        for i in range(3)
    )

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
        f'{labels}\n'
        f'</svg>'
    )
