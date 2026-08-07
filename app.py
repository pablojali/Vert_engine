import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import gpxpy
import re
import io
import json
import unicodedata
import traceback
import requests
from pathlib import Path
from trail_metrics_config import INDEX_CONFIG, SPEED_METRICS, display_metric_documentation
from data.gpx_loader import (
    build_cascading_selector,
    get_gpx_path,
    get_checkpoints,
    get_carrera_info,
    get_carreras,
)

# 1. Page configuration - VertLabs style
st.set_page_config(page_title="VertLabs - Trail Analytics", page_icon="🏃‍♂️", layout="wide")

st.title("🏃‍♂️ VertLabs - Terrain Intelligence Engine v1.0")
st.caption("Analysis backend: GPX geometric segmentation + official runner metrics.")
st.markdown("---")

# Fixed thresholds (hardcoded to keep the app simple).
STRONG_SLOPE_THRESHOLD = 12       # >= 12% strong climb | <= -12% strong descent
MODERATE_SLOPE_MIN = 5            # between 5% and 12% = moderate climb/descent
MODERATE_SLOPE_MAX = 12
ALTITUDE_THRESHOLD = 1800         # meters above sea level

# Consistent color palette shared by the effort map and the bar chart
SLOPE_CATEGORY_COLORS = {
    "Strong Climb (≥12%)": "#ff4b4b",
    "Strong Descent (≤-12%)": "#00bfff",
    "Moderate Climb (5-12%)": "#ffa500",
    "Moderate Descent (-5 to -12%)": "#7dd3fc",
    "Rolling Terrain (-5 to +5%)": "#4ade80",
}
SLOPE_CATEGORY_ORDER = list(SLOPE_CATEGORY_COLORS.keys())


# ============================================================
# 2. ENGINE FUNCTIONS (backend) - no UI logic
# ============================================================

def process_gpx_advanced(file):
    """Parses a GPX and returns a point-by-point DataFrame with
    cumulative distance, elevation, and instantaneous slope."""
    gpx = gpxpy.parse(file)
    points_data = []
    cumulative_distance = 0.0
    previous_point = None

    for track in gpx.tracks:
        for segment in track.segments:
            for point in segment.points:
                if previous_point:
                    dist = point.distance_2d(previous_point)
                    cumulative_distance += dist

                    elevation_change = point.elevation - previous_point.elevation
                    # Avoid division by zero on identical points
                    slope = (elevation_change / dist) * 100 if dist > 0 else 0

                    points_data.append({
                        "Distance (km)": cumulative_distance / 1000.0,
                        "Elevation (m)": point.elevation,
                        "Slope (%)": slope
                    })
                previous_point = point
    return pd.DataFrame(points_data)


def classify_slope(slope):
    """Mutually exclusive categories covering the whole range with no
    gaps: strong -> moderate -> rolling."""
    if slope >= STRONG_SLOPE_THRESHOLD:
        return "Strong Climb (≥12%)"
    elif slope <= -STRONG_SLOPE_THRESHOLD:
        return "Strong Descent (≤-12%)"
    elif slope > MODERATE_SLOPE_MIN:
        return "Moderate Climb (5-12%)"
    elif slope < -MODERATE_SLOPE_MIN:
        return "Moderate Descent (-5 to -12%)"
    else:
        return "Rolling Terrain (-5 to +5%)"


def analyze_race(gpx_file):
    """Full geometric analysis engine: receives the GPX file and returns
    the enriched DataFrame with slope and altitude classification, ready
    to plot/display."""
    df_gpx = process_gpx_advanced(gpx_file)

    df_gpx["Slope Type"] = df_gpx["Slope (%)"].apply(classify_slope)

    # Classification by ALTITUDE (independent of slope: a segment can be
    # "Strong Climb" AND "Above 1800m" at the same time)
    df_gpx["Altitude Zone"] = df_gpx["Elevation (m)"].apply(
        lambda alt: f"Above {ALTITUDE_THRESHOLD}m" if alt > ALTITUDE_THRESHOLD else f"Below {ALTITUDE_THRESHOLD}m"
    )
    return df_gpx


def resample_for_chart(df_gpx, step_m=200):
    """Downsamples the point-by-point GPX (often 10k+ GPS points) into
    fixed-distance bins (default 200m) purely for plotting. This does NOT
    affect any of the underlying analysis/index calculations, which keep
    using the full-resolution df_gpx - only the chart gets lighter."""
    df = df_gpx.copy()
    df["bin"] = (df["Distance (km)"] * 1000 // step_m).astype(int)

    def _dominant_category(series):
        mode = series.mode()
        return mode.iat[0] if not mode.empty else series.iloc[0]

    resampled = df.groupby("bin").agg(**{
        "Distance (km)": ("Distance (km)", "mean"),
        "Elevation (m)": ("Elevation (m)", "mean"),
        "Slope Type": ("Slope Type", _dominant_category),
    }).reset_index(drop=True)
    return resampled


def add_elevation_background(fig, race_df, step_m=200):
    """Adds the race's elevation profile as a subtle background layer on
    an existing Plotly figure, using a secondary (right-side) y-axis, so
    an index line plotted on the primary axis can be visually compared
    against the terrain (e.g. a big final climb dragging VPI down).
    Must be called BEFORE adding the main index trace, so it renders
    behind it."""
    df_chart = resample_for_chart(race_df, step_m=step_m)
    fig.add_trace(go.Scatter(
        x=df_chart["Distance (km)"],
        y=df_chart["Elevation (m)"],
        mode='lines',
        name='Elevation Profile',
        line=dict(color='rgba(160,160,160,0.5)', width=1),
        fill='tozeroy',
        fillcolor='rgba(90,90,90,0.18)',
        yaxis='y2',
        hoverinfo='skip',
        showlegend=False,
    ))
    fig.update_layout(
        yaxis2=dict(
            title="Elevation (m)",
            overlaying="y",
            side="right",
            showgrid=False,
        )
    )


def chart_download_button(fig, filename, key):
    """Renders a small download button right below a Plotly chart that
    exports it as a standalone, interactive HTML snippet (zoom/hover/pan
    all still work) - ready to paste into Blogger's HTML view, or embed
    anywhere else via <iframe>. Uses the CDN version of Plotly.js, so the
    snippet itself is lightweight."""
    html_bytes = fig.to_html(full_html=False, include_plotlyjs="cdn").encode("utf-8")
    st.download_button(
        "📥 Download chart as HTML (for Blogger)",
        data=html_bytes,
        file_name=filename,
        mime="text/html",
        key=key,
    )


def build_full_runner_report_html(runner_info, df_runner, indices, figures, df_segment_degradation, df_summary):
    """Builds a single, self-contained HTML report combining the runner
    card, checkpoints table, performance indices, every chart (VPI, DMI,
    ER, Degradation Curve), and the summary tables - exactly as shown in
    the 'Runner Metrics' tab. Ready to paste directly into Blogger's
    HTML view as one block, with full interactivity (zoom/hover/pan)
    preserved on every chart.

    Plotly.js is only loaded ONCE (via CDN) at the top, and each chart is
    embedded as a lightweight fragment (include_plotlyjs=False) that
    reuses it - instead of loading the library once per chart. Tables
    use VertLabs' own palette (dark slate background, cyan accent) so
    they match the blog's existing theme instead of looking like plain
    unstyled HTML."""

    style_block = """
    <style>
      .vl-report { font-family: -apple-system, 'Segoe UI', Roboto, sans-serif; color: #e2e8f0; }
      .vl-report h2 { color: #22d3ee; margin-bottom: 4px; }
      .vl-report h3 { color: #22d3ee; margin-top: 32px; margin-bottom: 8px;
                       border-bottom: 1px solid #334155; padding-bottom: 6px; }
      .vl-metric { display: inline-block; margin: 0 24px 12px 0; }
      .vl-metric-label { font-size: 13px; color: #94a3b8; }
      .vl-metric-value { font-size: 22px; font-weight: 600; color: #f1f5f9; }
      table.vl-table { border-collapse: collapse; width: 100%; margin-bottom: 8px;
                        font-size: 13px; background-color: #0f172a; }
      table.vl-table th { background-color: #1e293b; color: #22d3ee; text-align: left;
                           padding: 8px 12px; border-bottom: 2px solid #22d3ee;
                           white-space: nowrap; }
      table.vl-table td { padding: 6px 12px; border-bottom: 1px solid #1e293b; color: #e2e8f0; }
      table.vl-table tr:nth-child(even) td { background-color: #16213a; }
      table.vl-table tr:hover td { background-color: #22314f; }
    </style>
    """

    def _metric_html(label, value):
        return (
            f"<div class='vl-metric'>"
            f"<div class='vl-metric-label'>{label}</div>"
            f"<div class='vl-metric-value'>{value}</div>"
            f"</div>"
        )

    def _table_html(df):
        return df.to_html(index=False, border=0, classes="vl-table", na_rep="")

    parts = [
        "<script src='https://cdn.plot.ly/plotly-2.32.0.min.js'></script>",
        style_block,
        "<div class='vl-report'>",
        f"<h2>{runner_info.get('Name') or 'Runner'}</h2>",
        "<div>",
        _metric_html("Finish Time", runner_info.get("Finish Time") or "-"),
        _metric_html("Overall Rank", runner_info.get("Overall Rank") or "-"),
        _metric_html("Category", runner_info.get("Category") or "-"),
        "</div>",
        "<h3>Checkpoints / Split Times</h3>",
        _table_html(df_runner),
        "<h3>🎯 Performance Indices</h3>",
        "<div>",
        _metric_html("VPI", f"{indices.get('VPI')} m/h" if indices.get("VPI") is not None else "N/A"),
        _metric_html("DMI", f"{indices.get('DMI')} km/h" if indices.get("DMI") is not None else "N/A"),
        _metric_html("ER", indices.get("ER") if indices.get("ER") is not None else "N/A"),
        "</div>",
    ]

    for title, fig in figures.items():
        parts.append(f"<h3>{title}</h3>")
        parts.append(fig.to_html(full_html=False, include_plotlyjs=False))

    parts.append("<h3>📉 Degradation Curve by Segment</h3>")
    parts.append(_table_html(df_segment_degradation))
    parts.append("<h3>📋 Full Summary Table</h3>")
    parts.append(_table_html(df_summary))
    parts.append("</div>")

    return "\n".join(parts).encode("utf-8")




def match_checkpoints_with_gpx(df_gpx, checkpoints_km):
    """Receives the already-analyzed GPX DataFrame and a list of checkpoints
    [{'point': int, 'km': float}, ...] and returns a DataFrame with one row
    per segment between consecutive checkpoints: real distance, positive/
    negative elevation change, and average slope, based on the official
    GPX terrain in that km range.

    This is later crossed with the runner's real split times (Tab 2) to
    compute VPI, DMI and ER."""
    sorted_checkpoints = sorted(checkpoints_km, key=lambda c: c["km"])
    rows = []

    for i in range(len(sorted_checkpoints) - 1):
        cp_start = sorted_checkpoints[i]
        cp_end = sorted_checkpoints[i + 1]

        segment = df_gpx[
            (df_gpx["Distance (km)"] >= cp_start["km"]) &
            (df_gpx["Distance (km)"] <= cp_end["km"])
        ]

        if segment.empty:
            elevation_gain = None
            elevation_loss = None
            avg_slope = None
        else:
            elevation_diffs = segment["Elevation (m)"].diff().dropna()
            elevation_gain = elevation_diffs[elevation_diffs > 0].sum()
            elevation_loss = elevation_diffs[elevation_diffs < 0].sum()  # stays negative
            avg_slope = segment["Slope (%)"].mean()

        rows.append({
            "Start Point": cp_start["point"],
            "End Point": cp_end["point"],
            "Start Km": cp_start["km"],
            "End Km": cp_end["km"],
            "Segment Distance (km)": round(cp_end["km"] - cp_start["km"], 3),
            "Elevation Gain (m)": round(elevation_gain, 1) if elevation_gain is not None else None,
            "Elevation Loss (m)": round(elevation_loss, 1) if elevation_loss is not None else None,
            "Average Slope (%)": round(avg_slope, 2) if avg_slope is not None else None,
        })

    return pd.DataFrame(rows)


def parse_time_to_hours(time_str):
    """Converts a 'H:MM:SS' (or 'HH:MM:SS') string into decimal hours.
    If empty/None (e.g. the start checkpoint), treated as 0."""
    if pd.isna(time_str) or time_str is None or str(time_str).strip() == "":
        return 0.0
    parts = [int(p) for p in str(time_str).split(":")]
    while len(parts) < 3:
        parts.insert(0, 0)
    hours, minutes, seconds = parts[-3], parts[-2], parts[-1]
    return hours + minutes / 60 + seconds / 3600


def calculate_total_elevation_gain(full_df_gpx):
    """Total elevation gain of the WHOLE course (not just the segments
    between checkpoints), used for Total_Km_E in the ER index."""
    diffs = full_df_gpx["Elevation (m)"].diff().dropna()
    return diffs[diffs > 0].sum()


def calculate_total_elevation_loss(full_df_gpx):
    """Total elevation loss of the WHOLE course (negative diffs), returned
    as a positive number for display."""
    diffs = full_df_gpx["Elevation (m)"].diff().dropna()
    return abs(diffs[diffs < 0].sum())


def calculate_effort_distribution(full_df_gpx, total_km, total_elevation_gain):
    """Pure course-level version of the split used inside the ER index:
    finds the physical km at which the course reaches 50% of its total
    effort-km (Total_Km_E = distance_km + elevation_gain_m/100), and
    expresses it as a physical-distance ratio (e.g. a front-loaded, very
    steep-at-the-start course reaches 50% of effort by km 40% of the way
    through -> a 40/60 split)."""
    df = full_df_gpx.sort_values("Distance (km)").reset_index(drop=True)
    incremental_dist_km = df["Distance (km)"].diff().fillna(0)
    incremental_gain_m = df["Elevation (m)"].diff().fillna(0).clip(lower=0)
    incremental_effort_km = incremental_dist_km + (incremental_gain_m / 100)

    total_km_e = total_km + (total_elevation_gain / 100)
    half_effort_km = total_km_e / 2

    cumulative_effort_km = incremental_effort_km.cumsum()
    reaches_half = cumulative_effort_km >= half_effort_km

    if not reaches_half.any():
        effort_midpoint_km = total_km
    else:
        effort_midpoint_km = df.loc[reaches_half.idxmax(), "Distance (km)"]

    pct_first_half = (effort_midpoint_km / total_km) * 100 if total_km > 0 else 0
    pct_second_half = 100 - pct_first_half

    return {
        "total_km_e": total_km_e,
        "effort_midpoint_km": effort_midpoint_km,
        "pct_first_half": pct_first_half,
        "pct_second_half": pct_second_half,
    }


def build_time_by_point(df_runner):
    """Maps each checkpoint 'Point' this runner has a recorded split for
    to its accumulated time in decimal hours. A checkpoint the runner has
    NO passing for at all (common at aid stations that don't scan bibs,
    as opposed to timing mats) simply won't appear as a key here - that
    absence is exactly the signal merge_segments_with_runner_times uses
    to fuse the surrounding segments together instead of leaving a gap."""
    return {
        row["Point"]: parse_time_to_hours(row.get("Accumulated Time"))
        for _, row in df_runner.iterrows()
    }


def merge_segments_with_runner_times(df_segments, df_runner):
    """Fuses together consecutive official segments whenever an
    intermediate checkpoint has no recorded time for THIS runner (e.g. an
    aid station that only hands out water/food and never scans bibs).
    Without this, a segment like P0->P12 (a real, steep climb) gets
    silently dropped from every calculation the moment P12 has no time -
    even though the runner's time IS known at P0 and at the next
    checkpoint that does have one (say P16). This merges P0->P12->P16
    into a single P0->P16 segment (summing distance/elevation, and
    recomputing Average Slope as a distance-weighted average of the
    sub-segments), so the climbing/descending effort in that stretch is
    still counted instead of vanishing.

    Returns a new DataFrame with the same columns/shape as df_segments,
    where every row's Start Point and End Point are both guaranteed to
    have a valid runner time (any segment left open at the very end -
    e.g. a DNF with no time at the last known point - is simply dropped,
    same as the pre-existing 'unmatched segment' behavior)."""
    time_by_point = build_time_by_point(df_runner)
    sorted_segments = df_segments.sort_values("Start Km").reset_index(drop=True)

    merged_rows = []
    buffer = None

    for _, seg in sorted_segments.iterrows():
        p_start, p_end = seg["Start Point"], seg["End Point"]
        seg_distance = seg["Segment Distance (km)"] or 0
        seg_gain = seg["Elevation Gain (m)"] or 0
        seg_loss = seg["Elevation Loss (m)"] or 0
        seg_slope = seg["Average Slope (%)"] or 0

        if buffer is None:
            buffer = {
                "Start Point": p_start,
                "Start Km": seg["Start Km"],
                "End Point": p_end,
                "End Km": seg["End Km"],
                "Segment Distance (km)": seg_distance,
                "Elevation Gain (m)": seg_gain,
                "Elevation Loss (m)": seg_loss,
                "_slope_weighted_sum": seg_slope * seg_distance,
                "_distance_sum": seg_distance,
            }
        else:
            buffer["End Point"] = p_end
            buffer["End Km"] = seg["End Km"]
            buffer["Segment Distance (km)"] += seg_distance
            buffer["Elevation Gain (m)"] += seg_gain
            buffer["Elevation Loss (m)"] += seg_loss
            buffer["_slope_weighted_sum"] += seg_slope * seg_distance
            buffer["_distance_sum"] += seg_distance

        if buffer["Start Point"] in time_by_point and p_end in time_by_point:
            avg_slope = (
                buffer["_slope_weighted_sum"] / buffer["_distance_sum"]
                if buffer["_distance_sum"] else None
            )
            merged_rows.append({
                "Start Point": buffer["Start Point"],
                "End Point": buffer["End Point"],
                "Start Km": buffer["Start Km"],
                "End Km": buffer["End Km"],
                "Segment Distance (km)": round(buffer["Segment Distance (km)"], 3),
                "Elevation Gain (m)": round(buffer["Elevation Gain (m)"], 1),
                "Elevation Loss (m)": round(buffer["Elevation Loss (m)"], 1),
                "Average Slope (%)": round(avg_slope, 2) if avg_slope is not None else None,
            })
            buffer = None
        # else: keep extending the buffer through the next segment

    return pd.DataFrame(merged_rows)


def calculate_runner_indices(full_df_gpx, df_segments, df_runner, total_km, total_elevation_gain,
                              distance_weighting_coef=1.0):
    """Crosses the official race segments (df_segments, computed in Tab 1
    from the checkpoints) with the runner's real split times (df_runner)
    to calculate VPI, DMI and ER.

    The crossing is done by checkpoint number ('Point'), which must match
    between both tables. Segments spanning a checkpoint this runner has no
    recorded time for are fused with their neighbors first (see
    merge_segments_with_runner_times) instead of being dropped outright.

    VPI/DMI are aggregated point-by-point (via calculate_indices_by_segment)
    rather than by filtering whole segments on their OWN average slope: a
    fused segment (e.g. a real climb immediately followed by a descent,
    merged together because the checkpoint between them has no runner
    time) can have an average slope well under 12% even though it fully
    contains a genuine steep climb - filtering on that diluted average
    would silently drop the climb from the whole-race VPI. Using the same
    within-segment effort-share method as the per-segment table avoids
    that."""

    if "Point" not in df_runner.columns:
        raise ValueError("The runner table doesn't have a 'Point' column to match checkpoints.")

    original_segment_count = len(df_segments)
    df_segments = merge_segments_with_runner_times(df_segments, df_runner)
    merged_checkpoints_count = max(original_segment_count - len(df_segments), 0)
    time_by_point = build_time_by_point(df_runner)

    crossed_rows = []
    for _, seg in df_segments.iterrows():
        p_start, p_end = seg["Start Point"], seg["End Point"]
        if p_start in time_by_point and p_end in time_by_point:
            runner_time_h = time_by_point[p_end] - time_by_point[p_start]
        else:
            runner_time_h = None
        row = seg.to_dict()
        row["Runner Time (h)"] = runner_time_h
        crossed_rows.append(row)

    df_crossed = pd.DataFrame(crossed_rows)
    unmatched_segments = df_crossed["Runner Time (h)"].isna().sum()

    df_valid = df_crossed.dropna(subset=["Runner Time (h)"]).copy()
    df_valid = df_valid[df_valid["Runner Time (h)"] > 0]

    if df_valid.empty:
        raise ValueError(
            "No checkpoint from the saved race matches the runner's points. "
            "Check that the 'Point' numbers are the same in both tables."
        )

    # --- VPI / DMI: point-by-point effort-share aggregation across ALL
    # segments (already merged), instead of a blunt whole-segment
    # average-slope filter. df_segments here is already merged, so
    # calling calculate_indices_by_segment again is a no-op on top of
    # that merge (idempotent: every boundary already has a valid time).
    df_segment_breakdown = calculate_indices_by_segment(full_df_gpx, df_segments, df_runner)

    valid_climb = df_segment_breakdown.dropna(subset=["VPI Raw (m/h)", "Runner Time (h)", "Climb Effort Share (%)"])
    climb_time_h_rows = valid_climb["Runner Time (h)"] * (valid_climb["Climb Effort Share (%)"] / 100)
    climb_gain_m_rows = valid_climb["VPI Raw (m/h)"] * climb_time_h_rows
    climb_time_h = climb_time_h_rows.sum()
    climb_gain_m = climb_gain_m_rows.sum()
    vpi = (climb_gain_m / climb_time_h) if climb_time_h > 0 else None

    valid_descent = df_segment_breakdown.dropna(subset=["DMI Raw (km/h)", "Runner Time (h)", "Descent Effort Share (%)"])
    descent_time_h_rows = valid_descent["Runner Time (h)"] * (valid_descent["Descent Effort Share (%)"] / 100)
    descent_dist_km_rows = valid_descent["DMI Raw (km/h)"] * descent_time_h_rows
    descent_time_h = descent_time_h_rows.sum()
    descent_dist_km = descent_dist_km_rows.sum()
    dmi = (descent_dist_km / descent_time_h) if descent_time_h > 0 else None

    # --- ER: Endurance Rating (pacing decay between 1st and 2nd half) ---
    total_km_e = total_km + (total_elevation_gain / 100)
    df_valid = df_valid.sort_values("Start Km").reset_index(drop=True)
    df_valid["Effort Km Segment"] = df_valid["Segment Distance (km)"] + (
        df_valid["Elevation Gain (m)"].fillna(0) / 100
    )
    df_valid["Effort Km Accumulated"] = df_valid["Effort Km Segment"].cumsum()
    half_effort_km = total_km_e / 2

    first_half = df_valid[df_valid["Effort Km Accumulated"] <= half_effort_km]
    second_half = df_valid[df_valid["Effort Km Accumulated"] > half_effort_km]

    def _effort_pace(segments):
        time_min = segments["Runner Time (h)"].sum() * 60
        effort_km = segments["Effort Km Segment"].sum()
        return (time_min / effort_km) if effort_km > 0 else None

    pace_1 = _effort_pace(first_half)
    pace_2 = _effort_pace(second_half)

    df_valid["Effort Pace (min/effort-km)"] = (
        (df_valid["Runner Time (h)"] * 60) / df_valid["Effort Km Segment"]
    ).round(2)

    if pace_1 and pace_2 and pace_1 > 0:
        pacing_decay_pct = ((pace_2 / pace_1) - 1) * 100
        er = 100 - (pacing_decay_pct * distance_weighting_coef)
    else:
        pacing_decay_pct = None
        er = None

    result = {
        "VPI": round(vpi, 1) if vpi is not None else None,
        "DMI": round(dmi, 2) if dmi is not None else None,
        "ER": round(er, 1) if er is not None else None,
        "Pacing_Decay_%": round(pacing_decay_pct, 1) if pacing_decay_pct is not None else None,
        "unmatched_segments": int(unmatched_segments),
        "merged_checkpoints": int(merged_checkpoints_count),
        "effort_pace_first_half": round(pace_1, 2) if pace_1 is not None else None,
        "effort_pace_second_half": round(pace_2, 2) if pace_2 is not None else None,
        "half_effort_km": half_effort_km,
    }
    return result, df_valid


def normalize_segment_index(series):
    """Normalizes a per-segment index series against its first valid
    (non-null, non-zero) value, expressed as Segment 1 = 100. Shared by
    both the checkpoint-estimated and the GPX-measured degradation
    tables, so their charts are on the same comparable scale."""
    valid_values = series.dropna()
    if valid_values.empty:
        return pd.Series([None] * len(series), index=series.index)
    baseline = valid_values.iloc[0]
    if not baseline:
        return pd.Series([None] * len(series), index=series.index)
    return ((series / baseline) * 100).round(1)


def calculate_indices_by_segment(full_df_gpx, df_segments, df_runner):
    """Calculates VPI and DMI INDEPENDENTLY for each segment (degradation
    matrix), instead of one global value for the whole race.

    With checkpoints spaced several km apart, a segment's OWN average
    slope rarely crosses ±12% even if it contains real steep walls mixed
    with flatter terrain - requiring the whole segment to qualify leaves
    the table mostly empty. Naively filtering just the steep GPS points
    and dividing by the segment's FULL time (the very first approach)
    dilutes the result, since most of that time was spent on the
    non-qualifying terrain.

    This version splits the difference: it allocates the runner's segment
    time proportionally to EFFORT (distance + elevation gain/100, same
    concept as the ER index) rather than raw distance. Steep climbing
    points get a larger effort-weight per km than flat ones, so this
    isn't just a wash - it estimates how much of the runner's segment
    time was plausibly spent on the qualifying terrain, then computes a
    real speed/vertical-rate on just that portion.

    Finally normalizes both indices against the runner's first valid
    segment (baseline = 100), to plot the degradation curve on a
    comparable 0-100 scale."""

    full_df_gpx = full_df_gpx.sort_values("Distance (km)").reset_index(drop=True)
    incremental_dist_km = full_df_gpx["Distance (km)"].diff()
    incremental_elevation_m = full_df_gpx["Elevation (m)"].diff()
    # Same effort-km definition already used for the ER index: distance +
    # positive elevation gain / 100 (descents don't add an extra term).
    incremental_effort_km = incremental_dist_km + incremental_elevation_m.clip(lower=0) / 100

    # Fuse segments across any checkpoint this runner has no recorded
    # time for (e.g. an aid station that doesn't scan bibs), so that
    # stretch's climb/descent isn't silently dropped from the table.
    df_segments = merge_segments_with_runner_times(df_segments, df_runner)
    time_by_point = build_time_by_point(df_runner)

    sorted_segments = df_segments.sort_values("Start Km").reset_index(drop=True)
    rows = []

    for i, seg in sorted_segments.iterrows():
        p_start, p_end = seg["Start Point"], seg["End Point"]
        km_start, km_end = seg["Start Km"], seg["End Km"]
        avg_slope = seg["Average Slope (%)"]

        if p_start not in time_by_point or p_end not in time_by_point:
            segment_time_h = None
        else:
            segment_time_h = time_by_point[p_end] - time_by_point[p_start]

        vpi_raw, dmi_raw = None, None
        climb_effort_share, descent_effort_share = None, None

        if segment_time_h and segment_time_h > 0:
            segment_mask = (full_df_gpx["Distance (km)"] >= km_start) & (full_df_gpx["Distance (km)"] <= km_end)
            total_effort_km = incremental_effort_km[segment_mask].sum()

            if total_effort_km and total_effort_km > 0:
                # --- VPI: steep-climb points within this segment ---
                climb_mask = segment_mask & (full_df_gpx["Slope (%)"] >= STRONG_SLOPE_THRESHOLD)
                climb_effort_km = incremental_effort_km[climb_mask].sum()
                climb_gain_m = incremental_elevation_m[climb_mask].sum()
                if climb_effort_km and climb_effort_km > 0 and climb_gain_m and climb_gain_m > 0:
                    climb_effort_share = climb_effort_km / total_effort_km
                    climb_time_h = segment_time_h * climb_effort_share
                    vpi_raw = climb_gain_m / climb_time_h if climb_time_h > 0 else None

                # --- DMI: steep-descent points within this segment ---
                descent_mask = segment_mask & (full_df_gpx["Slope (%)"] <= -STRONG_SLOPE_THRESHOLD)
                descent_effort_km = incremental_effort_km[descent_mask].sum()
                descent_dist_km = incremental_dist_km[descent_mask].sum()
                if descent_effort_km and descent_effort_km > 0 and descent_dist_km and descent_dist_km > 0:
                    descent_effort_share = descent_effort_km / total_effort_km
                    descent_time_h = segment_time_h * descent_effort_share
                    dmi_raw = descent_dist_km / descent_time_h if descent_time_h > 0 else None

        rows.append({
            "Segment": f"P{p_start}→P{p_end}",
            "Start Km": km_start,
            "End Km": km_end,
            "Average Slope (%)": avg_slope,
            "Runner Time (h)": round(segment_time_h, 2) if segment_time_h is not None else None,
            "Climb Effort Share (%)": round(climb_effort_share * 100, 1) if climb_effort_share is not None else None,
            "VPI Raw (m/h)": round(vpi_raw, 1) if vpi_raw is not None else None,
            "Descent Effort Share (%)": round(descent_effort_share * 100, 1) if descent_effort_share is not None else None,
            "DMI Raw (km/h)": round(dmi_raw, 2) if dmi_raw is not None else None,
        })

    df_segments_out = pd.DataFrame(rows)

    # Normalization against the runner's first valid segment (Segment 1 = 100)
    df_segments_out["VPI Index (0-100)"] = normalize_segment_index(df_segments_out["VPI Raw (m/h)"])
    df_segments_out["DMI Index (0-100)"] = normalize_segment_index(df_segments_out["DMI Raw (km/h)"])

    return df_segments_out


def process_runner_gpx_with_time(file):
    """Parses a runner's PERSONAL GPX track (e.g. exported from a COROS/
    Garmin watch, which includes a real timestamp on every point) into a
    RAW point-by-point DataFrame with cumulative distance, elevation, and
    REAL elapsed time since the start (in hours).

    Intentionally does NOT compute an instantaneous point-to-point slope
    here: personal watch tracks are usually sampled ~1 point/second, only
    a few meters apart, so raw point-to-point slope is dominated by
    altimeter/GPS noise (the same issue documented for the official GPX).
    Slope is computed later over fixed-distance windows instead - see
    build_runner_slope_windows()."""
    gpx = gpxpy.parse(file)
    points_data = []
    cumulative_distance = 0.0
    previous_point = None
    start_time = None

    for track in gpx.tracks:
        for segment in track.segments:
            for point in segment.points:
                if point.time is None:
                    continue  # skip points with no timestamp
                if start_time is None:
                    start_time = point.time

                if previous_point:
                    dist = point.distance_2d(previous_point)
                    cumulative_distance += dist

                points_data.append({
                    "Distance (km)": cumulative_distance / 1000.0,
                    "Elevation (m)": point.elevation,
                    "Elapsed Time (h)": (point.time - start_time).total_seconds() / 3600,
                })
                previous_point = point

    if not points_data:
        raise ValueError(
            "This GPX has no timestamped points. Make sure it's a recorded "
            "activity track (e.g. from a GPS watch), not just a route/course file."
        )
    return pd.DataFrame(points_data)


def build_runner_slope_windows(runner_gpx_df, window_m=500):
    """Groups the runner's RAW 1-sample/second track into fixed-distance
    windows (default 500m, stable in the 250m-2000m range per VertLabs'
    own findings on the official GPX) and computes, per window:
    - net elevation change and slope over the whole window (cancels out
      point-to-point altimeter noise, unlike a raw instantaneous slope)
    - the REAL elapsed time spent in that window (from the watch's
      timestamps - not estimated)."""
    df = runner_gpx_df.sort_values("Distance (km)").reset_index(drop=True)
    df["window"] = (df["Distance (km)"] * 1000 // window_m).astype(int)

    rows = []
    for _, window_df in df.groupby("window"):
        if len(window_df) < 2:
            continue
        km_start = window_df["Distance (km)"].iloc[0]
        km_end = window_df["Distance (km)"].iloc[-1]
        window_distance_km = km_end - km_start
        if window_distance_km <= 0:
            continue

        elevation_change_m = window_df["Elevation (m)"].iloc[-1] - window_df["Elevation (m)"].iloc[0]
        slope_pct = (elevation_change_m / (window_distance_km * 1000)) * 100

        time_start_h = window_df["Elapsed Time (h)"].iloc[0]
        time_end_h = window_df["Elapsed Time (h)"].iloc[-1]

        rows.append({
            "Window Start Km": km_start,
            "Window End Km": km_end,
            "Window Distance (km)": window_distance_km,
            "Window Elevation Change (m)": elevation_change_m,
            "Window Slope (%)": slope_pct,
            "Window Time (h)": time_end_h - time_start_h,
        })

    return pd.DataFrame(rows)


def calculate_real_indices_by_segment(runner_gpx_df, df_segments, window_m=500):
    """Calculates the REAL (measured, not estimated) VPI and DMI per
    segment, directly from the runner's own timestamped GPX track.

    Slope is evaluated per 500m window (see build_runner_slope_windows),
    not per raw GPS sample, to avoid altimeter-noise saturation. For each
    official segment [Start Km, End Km], sums the real elapsed time and
    elevation change of the windows that individually qualify as steep
    climb/descent and that fall within that segment's km range."""

    windows = build_runner_slope_windows(runner_gpx_df, window_m=window_m)

    sorted_segments = df_segments.sort_values("Start Km").reset_index(drop=True)
    rows = []

    for i, seg in sorted_segments.iterrows():
        p_start, p_end = seg["Start Point"], seg["End Point"]
        km_start, km_end = seg["Start Km"], seg["End Km"]
        effort_km_segment = seg["Segment Distance (km)"] + (seg.get("Elevation Gain (m)") or 0) / 100

        segment_windows = windows[
            (windows["Window Start Km"] >= km_start) & (windows["Window End Km"] <= km_end)
        ]

        if segment_windows.empty:
            rows.append({
                "Segment": f"P{p_start}→P{p_end}",
                "Start Km": km_start,
                "End Km": km_end,
                "Real Time (h)": None,
                "VPI Real (m/h)": None,
                "DMI Real (km/h)": None,
                "Effort Km Segment": effort_km_segment,
                "Effort Pace (min/effort-km)": None,
            })
            continue

        real_segment_time_h = segment_windows["Window Time (h)"].sum()

        climb_windows = segment_windows[segment_windows["Window Slope (%)"] >= STRONG_SLOPE_THRESHOLD]
        climb_gain_m = climb_windows["Window Elevation Change (m)"].sum()
        climb_time_h = climb_windows["Window Time (h)"].sum()
        vpi_real = (climb_gain_m / climb_time_h) if climb_time_h and climb_time_h > 0 and climb_gain_m > 0 else None

        descent_windows = segment_windows[segment_windows["Window Slope (%)"] <= -STRONG_SLOPE_THRESHOLD]
        descent_dist_km = descent_windows["Window Distance (km)"].sum()
        descent_time_h = descent_windows["Window Time (h)"].sum()
        dmi_real = (descent_dist_km / descent_time_h) if descent_time_h and descent_time_h > 0 and descent_dist_km > 0 else None

        effort_pace = (
            (real_segment_time_h * 60) / effort_km_segment
            if effort_km_segment and effort_km_segment > 0 else None
        )

        rows.append({
            "Segment": f"P{p_start}→P{p_end}",
            "Start Km": km_start,
            "End Km": km_end,
            "Real Time (h)": round(real_segment_time_h, 2) if real_segment_time_h is not None else None,
            "VPI Real (m/h)": round(vpi_real, 1) if vpi_real is not None else None,
            "DMI Real (km/h)": round(dmi_real, 2) if dmi_real is not None else None,
            "Effort Km Segment": round(effort_km_segment, 2) if effort_km_segment is not None else None,
            "Effort Pace (min/effort-km)": round(effort_pace, 2) if effort_pace is not None else None,
        })

    return pd.DataFrame(rows)


def interpolate_time_at_km(runner_gpx_df, target_km):
    """Linearly interpolates the runner's REAL elapsed time (from their
    personal GPX) at a given cumulative km, using their own recorded
    distance/time curve. Returns None if target_km is outside the
    recorded range."""
    df = runner_gpx_df.sort_values("Distance (km)")
    if target_km < df["Distance (km)"].iloc[0] or target_km > df["Distance (km)"].iloc[-1]:
        return None
    return float(np.interp(target_km, df["Distance (km)"], df["Elapsed Time (h)"]))


def calculate_global_real_indices(runner_gpx_df, official_df_gpx, total_km, total_elevation_gain,
                                   window_m=500, distance_weighting_coef=1.0):
    """Calculates VPI, DMI and ER for the WHOLE race directly from the
    runner's personal, timestamped GPX - no checkpoint-based estimation
    at all. This is the GPX-only counterpart to calculate_runner_indices
    (which relies on UTMB Live checkpoint times).

    VPI/DMI: aggregate every 500m window across the entire track that
    qualifies as steep climb/descent (see build_runner_slope_windows).
    ER: uses the same effort-km midpoint as the course-level
    calculate_effort_distribution, but measures the runner's REAL elapsed
    time before/after that point (interpolated from their own track)
    instead of estimating it."""

    windows = build_runner_slope_windows(runner_gpx_df, window_m=window_m)

    climb_windows = windows[windows["Window Slope (%)"] >= STRONG_SLOPE_THRESHOLD]
    climb_time_h = climb_windows["Window Time (h)"].sum()
    climb_gain_m = climb_windows["Window Elevation Change (m)"].sum()
    vpi = (climb_gain_m / climb_time_h) if climb_time_h and climb_time_h > 0 and climb_gain_m > 0 else None

    descent_windows = windows[windows["Window Slope (%)"] <= -STRONG_SLOPE_THRESHOLD]
    descent_time_h = descent_windows["Window Time (h)"].sum()
    descent_dist_km = descent_windows["Window Distance (km)"].sum()
    dmi = (descent_dist_km / descent_time_h) if descent_time_h and descent_time_h > 0 and descent_dist_km > 0 else None

    effort_dist = calculate_effort_distribution(official_df_gpx, total_km, total_elevation_gain)
    effort_midpoint_km = effort_dist["effort_midpoint_km"]
    total_km_e = total_km + (total_elevation_gain / 100)
    half_effort_km = total_km_e / 2

    time_at_midpoint_h = interpolate_time_at_km(runner_gpx_df, effort_midpoint_km)
    total_time_h = float(runner_gpx_df["Elapsed Time (h)"].max())

    er, pacing_decay_pct, pace_1, pace_2 = None, None, None, None
    if time_at_midpoint_h is not None:
        time_first_half_h = time_at_midpoint_h
        time_second_half_h = total_time_h - time_at_midpoint_h
        # By construction, both halves represent ~50% of total effort-km
        # each, so the pacing comparison reduces to the real time ratio.
        if time_first_half_h > 0 and time_second_half_h > 0 and half_effort_km > 0:
            pace_1 = (time_first_half_h * 60) / half_effort_km
            pace_2 = (time_second_half_h * 60) / half_effort_km
            pacing_decay_pct = ((pace_2 / pace_1) - 1) * 100
            er = 100 - (pacing_decay_pct * distance_weighting_coef)

    return {
        "VPI": round(vpi, 1) if vpi is not None else None,
        "DMI": round(dmi, 2) if dmi is not None else None,
        "ER": round(er, 1) if er is not None else None,
        "effort_pace_first_half": round(pace_1, 2) if pace_1 is not None else None,
        "effort_pace_second_half": round(pace_2, 2) if pace_2 is not None else None,
        "effort_midpoint_km": effort_midpoint_km,
        "Pacing_Decay_%": round(pacing_decay_pct, 1) if pacing_decay_pct is not None else None,
        "total_time_h": total_time_h,
        "total_distance_km": float(runner_gpx_df["Distance (km)"].max()),
        "total_elevation_gain_m": float(runner_gpx_df["Elevation (m)"].diff().clip(lower=0).sum()),
    }


# Automated timing-data scraping.
# live.utmb.world is a Next.js app: the HTML returned by the server is
# empty and the data is fetched afterwards via JS from an internal API.
# By inspecting the browser's Network tab, we found the real endpoint
# used by the site itself:
#   https://utmblive-api.utmb.world/runners/<ID>?locale=en
# A plain requests.get() is enough: no browser, no Playwright/Chromium,
# no packages.txt needed.

def extract_runner_id(url):
    """Extracts the numeric runner ID from a URL like
    https://live.utmb.world/aranbyutmb/2026/runners/5"""
    match = re.search(r"/runners/(\d+)", url)
    return match.group(1) if match else None


def extract_tenant(url):
    """Extracts 'race_year' from a URL like
    https://live.utmb.world/aranbyutmb/2026/runners/5 -> 'aranbyutmb_2026'
    Required by the API as the X-Tenant header to identify which race
    edition the runner belongs to."""
    match = re.search(r"live\.utmb\.world/([a-zA-Z0-9]+)/(\d{4})/runners/", url)
    if match:
        race, year = match.groups()
        return f"{race}_{year}"
    return None


def fetch_runner_by_tenant_and_bib(tenant, bib):
    """Calls the UTMB Live API directly given a tenant (e.g. 'aranbyutmb_2026')
    and a bib number, without needing a full runner URL. Used both by
    scrape_runner_splits (which derives the tenant from a URL) and by the
    'Top Runners' tab (which reuses one known tenant for several bibs)."""
    api_url = f"https://utmblive-api.utmb.world/runners/{bib}?locale=en"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "*/*",
        "Origin": "https://live.utmb.world",
        "Referer": "https://live.utmb.world/",
        "X-Tenant": tenant,
    }

    response = requests.get(api_url, headers=headers, timeout=15)
    response.raise_for_status()
    data = response.json()

    resume = data.get("resume", {}) or {}
    info = resume.get("info", {}) or {}
    ranking = resume.get("ranking", {}) or {}
    country = data.get("country", {}) or {}

    runner_info = {
        "Name": info.get("fullname"),
        "Bib": resume.get("bib"),
        "Age": info.get("age"),
        "Category": info.get("category"),
        "Club": info.get("club"),
        "Country": country.get("name"),
        "Finish Time": resume.get("raceTime"),
        "Overall Rank": ranking.get("scratch"),
        "Gender Rank": ranking.get("sex"),
        "Category Rank": ranking.get("category"),
        "Status": resume.get("status"),
    }

    passings = (data.get("detail", {}) or {}).get("passings", []) or []
    df_passings = pd.DataFrame(passings)

    # Keep only the useful columns (drop raw/redundant ones like
    # timeSeconds, datetimeIn/Out, and live-prediction fields that don't
    # apply to a finished runner) and rename them in English.
    useful_columns = {
        "pointId": "Point",
        "cumulatedTime": "Accumulated Time",
        "time": "Segment Time",
        "speed": "Speed (km/h)",
        "pace": "Pace (min/km)",
        "rank": "Rank",
        "restTime": "Rest",
    }
    present_columns = [c for c in useful_columns if c in df_passings.columns]
    df_passings = df_passings[present_columns].rename(columns=useful_columns)

    return runner_info, df_passings


def scrape_runner_splits(url):
    runner_id = extract_runner_id(url)
    if not runner_id:
        raise ValueError(
            "Couldn't find the runner ID in that URL. "
            "Make sure it has the format '.../runners/<number>' "
            "(e.g. https://live.utmb.world/aranbyutmb/2026/runners/5)."
        )

    tenant = extract_tenant(url)
    if not tenant:
        raise ValueError(
            "Couldn't identify the race/year in that URL. "
            "Make sure it has the format "
            "'https://live.utmb.world/<race>/<year>/runners/<number>'."
        )

    return fetch_runner_by_tenant_and_bib(tenant, runner_id)


def _seconds_to_hms(seconds):
    """Converts a seconds count (int/float) into 'H:MM:SS'. Used by the
    Livetrail runner endpoints, which report raceTime/restTime in raw
    seconds instead of the pre-formatted strings utmb.world returns."""
    if seconds is None:
        return None
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}"


def extract_livetrail_runner_url_parts(url):
    """Extracts (subdomain, year, bib, race_id) from a Livetrail runner
    URL like:
        https://aranbyutmb.v3.livetrail.net/en/2026/runners/5?raceId=vda
    Returns (None, None, None, None) if the URL doesn't match. race_id
    may be None if the URL has no ?raceId= query param (the caller can
    still supply it manually)."""
    match = re.search(
        r"https?://([a-zA-Z0-9]+)\.v3\.livetrail\.net/[a-z]{2}/(\d{4})/runners/(\d+)",
        url,
    )
    if not match:
        return None, None, None, None
    subdomain, year, bib = match.groups()
    race_id_match = re.search(r"[?&]raceId=([a-zA-Z0-9]+)", url)
    race_id = race_id_match.group(1) if race_id_match else None
    return subdomain, year, bib, race_id


def fetch_runner_by_tenant_and_bib_livetrail(tenant, bib, race_id):
    """Livetrail counterpart of fetch_runner_by_tenant_and_bib. Needs TWO
    requests (confirmed via manual endpoint discovery):
      - /api/events/runners/{bib}            -> name, category, club, status, ranking
      - /api/events/runners/{bib}/detail     -> full passings (pointId, raceTime,
        ranking per checkpoint, restTime)
    Both require the X-Tenant header COMBINED (e.g. "aranbyutmb_2026"),
    NOT split into X-Tenant/X-Year (that variant returns 400 on /detail).
    Origin/Referer are derived from the tenant, same scheme as
    fetch_livetrail_checkpoints."""
    subdomain = tenant.rsplit("_", 1)[0]
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Origin": f"https://{subdomain}.v3.livetrail.net",
        "Referer": f"https://{subdomain}.v3.livetrail.net/",
        "X-Tenant": tenant,
    }

    summary_url = f"https://api.v3.livetrail.net/api/events/runners/{bib}"
    summary_resp = requests.get(summary_url, params={"raceId": race_id}, headers=headers, timeout=15)
    summary_resp.raise_for_status()
    summary = summary_resp.json()

    detail_url = f"https://api.v3.livetrail.net/api/events/runners/{bib}/detail"
    detail_resp = requests.get(detail_url, params={"raceId": race_id}, headers=headers, timeout=15)
    detail_resp.raise_for_status()
    detail = detail_resp.json()

    ranking = summary.get("ranking", {}) or {}
    runner_info = {
        "Name": f"{summary.get('firstName', '')} {summary.get('lastName', '')}".strip() or None,
        "Bib": summary.get("bib"),
        "Age": None,  # not exposed by this endpoint
        "Category": summary.get("category"),
        "Club": summary.get("club"),
        "Country": summary.get("nationality"),  # ISO code only, not full name
        "Finish Time": _seconds_to_hms(summary.get("raceTime")),
        "Overall Rank": ranking.get("scratch"),
        "Gender Rank": ranking.get("sex"),
        "Category Rank": ranking.get("category"),
        "Status": summary.get("status"),
    }

    passings = detail.get("passings", []) or []
    rows = []
    previous_race_time = 0
    for p in sorted(passings, key=lambda x: x.get("raceTime") or 0):
        race_time = p.get("raceTime")
        ranking_p = p.get("ranking") or {}
        segment_seconds = (race_time - previous_race_time) if race_time is not None else None
        rows.append({
            "Point": p.get("pointId"),
            "Accumulated Time": _seconds_to_hms(race_time),
            "Segment Time": _seconds_to_hms(segment_seconds),
            "Speed (km/h)": None,   # not exposed by this endpoint (only by utmb.world)
            "Pace (min/km)": None,  # not exposed by this endpoint (only by utmb.world)
            "Rank": ranking_p.get("scratch"),
            "Rest": _seconds_to_hms(p.get("restTime")),
        })
        if race_time is not None:
            previous_race_time = race_time

    df_passings = pd.DataFrame(rows)
    return runner_info, df_passings


def scrape_runner_splits_livetrail(url, manual_race_id=None):
    """Livetrail counterpart of scrape_runner_splits. Accepts a runner URL
    like 'https://aranbyutmb.v3.livetrail.net/en/2026/runners/5?raceId=vda'.
    If the URL has no ?raceId= (or the person pastes a bare API-style
    link), manual_race_id is used as a fallback."""
    subdomain, year, bib, race_id_from_url = extract_livetrail_runner_url_parts(url)
    if not subdomain:
        raise ValueError(
            "Couldn't parse that URL. Make sure it has the format "
            "'https://<subdomain>.v3.livetrail.net/en/<year>/runners/<bib>?raceId=<race_id>' "
            "(e.g. https://aranbyutmb.v3.livetrail.net/en/2026/runners/5?raceId=vda)."
        )

    race_id = race_id_from_url or manual_race_id
    if not race_id:
        raise ValueError(
            "Couldn't find '?raceId=...' in that URL, and no Race ID was provided "
            "manually. Add it to the URL or fill in the Race ID field."
        )

    tenant = f"{subdomain}_{year}"
    return fetch_runner_by_tenant_and_bib_livetrail(tenant, bib, race_id)


def fetch_livetrail_checkpoints(race_id, tenant, url):
    """
    Downloads the checkpoint list (pointId, name, distance, elevationGain)
    from the Livetrail endpoint. Requires the X-Tenant header, same scheme
    as the utmb.world runner endpoint. Origin/Referer are derived from the
    tenant (e.g. "aranbyutmb_2026" -> "aranbyutmb.v3.livetrail.net"), so it
    works for any race sharing this same provider without touching code.
    """
    subdomain = tenant.rsplit("_", 1)[0]
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Origin": f"https://{subdomain}.v3.livetrail.net",
        "Referer": f"https://{subdomain}.v3.livetrail.net/",
        "X-Tenant": tenant,
    }
    response = requests.get(url, params={"raceId": race_id}, headers=headers, timeout=15)
    response.raise_for_status()
    return response.json()


def build_registry_checkpoints_block(gpx_file, race_slug_api, points):
    """
    Converts the raw Livetrail response into the exact text block pasted
    into data/races_registry.json:

        {
          "gpx_file": "...",
          "race_slug_api": "...",
          "checkpoints": [
            {"id": "0", "nombre": "...", "km": 0.0},
            ...
          ]
        },

    Sorts by ascending distance, uses 'name' (not 'shortName'), and aligns
    the checkpoints array columns in the same manual style already used
    in the existing registry, so copy-pasting doesn't break the visual
    formatting.
    """
    sorted_points = sorted(points, key=lambda p: p["distance"])
    checkpoints = [
        {
            "id": str(p["pointId"]),
            "nombre": p["name"],
            "km": round(p["distance"] / 1000, 1),
        }
        for p in sorted_points
    ]

    id_width = max(len(f'"{cp["id"]}"') for cp in checkpoints) + 1
    nombre_width = max(len(f'"{cp["nombre"]}"') for cp in checkpoints) + 1

    lines = []
    for cp in checkpoints:
        id_str = f'"{cp["id"]}",'.ljust(id_width + 1)
        nombre_str = f'"{cp["nombre"]}",'.ljust(nombre_width + 1)
        lines.append(f'    {{"id": {id_str} "nombre": {nombre_str} "km": {cp["km"]}}}')

    checkpoints_block = ",\n".join(lines)

    return (
        "{\n"
        f'  "gpx_file": "{gpx_file}",\n'
        f'  "race_slug_api": "{race_slug_api}",\n'
        '  "checkpoints": [\n'
        f"{checkpoints_block}\n"
        "  ]\n"
        "},"
    )


def build_summary_table(race_segments_df, df_segment_degradation, df_runner):
    """Builds the unified, Excel-ready summary table: one row per
    checkpoint, combining the official segment geometry (Tab 1), this
    runner's raw split data (from UTMB Live or LiveTrail), and the
    calculated VPI/DMI for that segment. Shared by 'Runner Metrics'
    (single runner) and 'Top Runners' (several runners side by side).

    Some source APIs (confirmed on UTMB Live) omit a column entirely for
    a given runner instead of sending it as 0/null - e.g. 'restTime' can
    be missing altogether when a runner never rested at any checkpoint,
    which drops 'Rest' from df_runner.columns. This function tolerates
    any of the optional runner columns being absent, filling them with
    None instead of raising a KeyError on the merge."""
    df_summary = race_segments_df[[
        "End Point", "Segment Distance (km)", "Elevation Gain (m)",
        "Elevation Loss (m)", "Average Slope (%)", "Start Km", "End Km",
    ]].copy()

    df_summary = df_summary.merge(
        df_segment_degradation[["Start Km", "End Km", "VPI Raw (m/h)", "DMI Raw (km/h)"]],
        on=["Start Km", "End Km"],
        how="left",
    )

    runner_columns_wanted = ["Point", "Speed (km/h)", "Pace (min/km)", "Rank", "Rest", "Segment Time"]
    runner_columns_present = [c for c in runner_columns_wanted if c in df_runner.columns]
    df_summary = df_summary.merge(
        df_runner[runner_columns_present],
        left_on="End Point",
        right_on="Point",
        how="left",
    )

    df_summary = df_summary.rename(columns={
        "End Point": "Checkpoint",
        "Speed (km/h)": "Speed",
        "Pace (min/km)": "Pace",
        "Segment Time": "Time",
        "VPI Raw (m/h)": "VPI",
        "DMI Raw (km/h)": "DMI",
    })

    # Guarantee every expected output column exists, even if the source
    # data for this particular runner was missing one entirely.
    for col in ["Speed", "Pace", "Rank", "Rest", "Time", "VPI", "DMI"]:
        if col not in df_summary.columns:
            df_summary[col] = None

    return df_summary[[
        "Checkpoint", "Segment Distance (km)", "Elevation Gain (m)",
        "Elevation Loss (m)", "Average Slope (%)", "Speed", "Pace",
        "Rank", "Rest", "Time", "VPI", "DMI",
    ]]



# ============================================================
# 3. INTERFACE: three independent tabs
# ============================================================

# In-memory "library" of analyzed races, kept for the duration of the session.
# Structure: { "Race Name": {"df": DataFrame, "total_km": float, ...} }
if 'saved_races' not in st.session_state:
    st.session_state['saved_races'] = {}

# In-memory pool feeding the "Exportar a Web" tab: every runner whose
# VPI/DMI/ER gets computed on the UTMB or LiveTrail tabs is tracked here
# automatically, so the export tab can later write race.json/profile.json
# for the Builder without re-running any analysis. Pure bookkeeping - never
# touches disk on its own, and never affects the tabs that call it.
if 'web_export_pool' not in st.session_state:
    st.session_state['web_export_pool'] = {}

WEB_DATA_DIR = Path(__file__).parent / "data"


def _slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text or "item"


def _find_existing_portrait(athlete_slug: str):
    """Returns the Path to this athlete's existing portrait on disk (any
    of the accepted extensions), or None if they don't have one yet."""
    portrait_dir = WEB_DATA_DIR / "athletes" / athlete_slug / "images"
    for ext in (".jpg", ".jpeg", ".png"):
        candidate = portrait_dir / f"portrait{ext}"
        if candidate.exists():
            return candidate
    return None


def _chart_label(filename: str) -> str:
    """Best-effort friendly label for an uploaded chart HTML, based on
    its filename (matches the file_name= used by chart_download_button
    for the LiveTrail runner charts: vpi_chart_livetrail.html, etc.)."""
    stem = Path(filename).stem.lower()
    if "vpi" in stem:
        return "VPI"
    if "dmi" in stem:
        return "DMI"
    if "degradation" in stem:
        return "Degradation"
    if "er" in stem or "pacing" in stem:
        return "ER"
    return Path(filename).stem.replace("_", " ").replace("-", " ").title()


def _web_export_track_result(race_key, runner_info, indices):
    """Records one runner's already-computed VPI/DMI/ER for a given race
    into st.session_state['web_export_pool'], so the 'Exportar a Web' tab
    can pick it up later. Called right after the existing tabs finish
    calculating indices - wrapped so a bookkeeping error here can never
    break the analysis tab itself."""
    try:
        if not race_key or not runner_info or not indices:
            return
        race_pool = st.session_state['web_export_pool'].setdefault(race_key, {})
        runners = race_pool.setdefault("runners", {})
        name = runner_info.get("Name") or "Runner"
        bib = runner_info.get("Bib")
        runner_key = str(bib) if bib not in (None, "") else _slugify(name)
        position = runner_info.get("Overall Rank")
        try:
            position = int(position)
        except (TypeError, ValueError):
            pass
        runners[runner_key] = {
            "name": name,
            "bib": bib,
            "finish_time": runner_info.get("Finish Time"),
            "position": position,
            "vpi": indices.get("VPI"),
            "dmi": indices.get("DMI"),
            "er": indices.get("ER"),
        }
    except Exception:
        pass


tab_race, tab_runner_lt, tab_gpx, tab_comparison, tab_top, tab_methodology, tab_checkpoints, tab_web_export = st.tabs(
    ["🗺️ Race Analysis", "🏃 Runner Metrics (LiveTrail)", "🛰️ GPX Metrics",
     "⚖️ UTMB vs GPX", "🏆 Top Runners", "📖 Indices & Methodology", "🧩 Checkpoint Fetcher",
     "🌐 Exportar a Web"]
)

# ---------------------------------------------
# TAB 1: Geometric analysis of the official GPX
# ---------------------------------------------
with tab_race:
    st.header("🗺️ Geometric Race Analysis (GPX)")
    st.caption(
        f"Strong slope: ≥{STRONG_SLOPE_THRESHOLD}% climb / ≤-{STRONG_SLOPE_THRESHOLD}% descent · "
        f"Moderate: {MODERATE_SLOPE_MIN}-{MODERATE_SLOPE_MAX}% · "
        f"Altitude: >{ALTITUDE_THRESHOLD}m"
    )

    race_slug, year, distance = build_cascading_selector(st, key_prefix="tab1_selector")

    if not (race_slug and year and distance):
        st.info("👋 Choose race, year and distance above to load the geometric analysis.")
    else:
        try:
            gpx_path = get_gpx_path(race_slug, year, distance)
            gpx_error = None
        except FileNotFoundError as e:
            gpx_path = None
            gpx_error = str(e)

        if gpx_error:
            st.error(f"❌ {gpx_error}")
        else:
            registry_checkpoints = get_checkpoints(race_slug, year, distance)
            registry_info = get_carrera_info(race_slug, year, distance)
            visible_race_name = dict(get_carreras()).get(race_slug, race_slug)

            # --- Confirmation panel (before running the analysis) ---
            with st.container(border=True):
                st.markdown(f"**GPX found:** `{registry_info['gpx_file']}`")
                colA, colB = st.columns(2)
                colA.metric("Checkpoints in registry", len(registry_checkpoints))
                colB.metric("API slug (X-Tenant)", registry_info.get("race_slug_api", race_slug))

                if registry_checkpoints:
                    # Hide the start and finish checkpoints from this preview
                    # table (they're still used for the actual analysis).
                    checkpoints_to_display = registry_checkpoints
                    if len(checkpoints_to_display) > 2:
                        sorted_cps = sorted(checkpoints_to_display, key=lambda c: c["km"])
                        checkpoints_to_display = sorted_cps[1:-1]

                    st.markdown("**Checkpoints:**")
                    st.dataframe(
                        checkpoints_to_display,
                        column_config={
                            "id": "ID",
                            "nombre": "Name",
                            "km": st.column_config.NumberColumn("Km", format="%.2f"),
                        },
                        hide_index=True,
                        use_container_width=True,
                    )
                else:
                    st.warning(
                        "This combination doesn't have checkpoints in the registry yet. "
                        "The geometric analysis still works, but you won't be able to "
                        "calculate VPI/DMI by segment until they're loaded in "
                        "`data/races_registry.json`."
                    )

            use_race = st.button(
                "✅ Use this race for analysis", type="primary", use_container_width=True
            )
            if use_race:
                st.session_state["active_race_tab1"] = (race_slug, year, distance)

            active_race = st.session_state.get("active_race_tab1")

            if not active_race:
                st.info("Click '✅ Use this race for analysis' to run the geometric engine.")
            elif active_race != (race_slug, year, distance):
                st.info(
                    "You selected a different combination than the one currently active. "
                    "Click '✅ Use this race for analysis' to update it."
                )
            else:
                active_race_slug, active_year, active_distance = active_race
                active_gpx_path = get_gpx_path(active_race_slug, active_year, active_distance)
                active_checkpoints = get_checkpoints(active_race_slug, active_year, active_distance)

                with open(active_gpx_path, "r", encoding="utf-8") as f:
                    df_gpx = analyze_race(f)

                # Summary metrics. Each GPX point represents roughly the
                # same average distance (total_km / point count), so we
                # count points per category and convert them to km.
                total_km = df_gpx["Distance (km)"].max()
                km_per_point = total_km / len(df_gpx)

                km_by_category = {
                    category: (df_gpx["Slope Type"] == category).sum() * km_per_point
                    for category in SLOPE_CATEGORY_ORDER
                }
                km_above_altitude = (df_gpx["Altitude Zone"] == f"Above {ALTITUDE_THRESHOLD}m").sum() * km_per_point
                total_elevation_gain = calculate_total_elevation_gain(df_gpx)
                total_elevation_loss = calculate_total_elevation_loss(df_gpx)

                # --- Top row: Distance, Elevation +/-, Above-altitude ---
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Total Distance", f"{total_km:.2f} km")
                col2.metric("Elevation Gain (+)", f"{total_elevation_gain:.0f} m")
                col3.metric("Elevation Loss (−)", f"-{total_elevation_loss:.0f} m")
                col4.metric(f"Above {ALTITUDE_THRESHOLD}m", f"{km_above_altitude:.2f} km")

                # --- Horizontal bar chart: km + % per slope category, same colors as the map ---
                st.markdown("##### Slope Breakdown")
                fig_bars = go.Figure()
                fig_bars.add_trace(go.Bar(
                    x=[km_by_category[c] for c in SLOPE_CATEGORY_ORDER],
                    y=SLOPE_CATEGORY_ORDER,
                    orientation="h",
                    marker_color=[SLOPE_CATEGORY_COLORS[c] for c in SLOPE_CATEGORY_ORDER],
                    text=[
                        f"{km_by_category[c]:.2f} km ({km_by_category[c] / total_km * 100:.1f}%)"
                        for c in SLOPE_CATEGORY_ORDER
                    ],
                    textposition="outside",
                    hovertemplate="%{y}: %{x:.2f} km<extra></extra>",
                ))
                fig_bars.update_layout(
                    template="plotly_dark",
                    xaxis_title="Distance (km)",
                    height=280,
                    margin=dict(l=10, r=10, t=10, b=10),
                    showlegend=False,
                )
                st.plotly_chart(fig_bars, use_container_width=True)
                chart_download_button(fig_bars, "slope_breakdown.html", "dl_slope_bars")

                # --- Effort distribution (same split logic used inside ER) ---
                st.markdown("---")
                st.markdown("##### ⚖️ Effort Distribution")
                st.caption(
                    "Where the course reaches 50% of its total effort-km "
                    "(Total_Km_E = distance + elevation gain / 100) — the same split "
                    "point the ER index uses. A course with heavy early climbing will "
                    "reach 50% of its effort well before the halfway physical point."
                )

                effort_dist = calculate_effort_distribution(df_gpx, total_km, total_elevation_gain)

                fig_effort = go.Figure()
                fig_effort.add_trace(go.Bar(
                    y=["Effort Split"],
                    x=[effort_dist["pct_first_half"]],
                    orientation="h",
                    name=f"First 50% of effort (km 0 → {effort_dist['effort_midpoint_km']:.1f})",
                    marker_color="#22d3ee",
                    text=f"{effort_dist['pct_first_half']:.0f}%",
                    textposition="inside",
                    hovertemplate="First 50%% of effort: %{x:.1f}%% of the course<extra></extra>",
                ))
                fig_effort.add_trace(go.Bar(
                    y=["Effort Split"],
                    x=[effort_dist["pct_second_half"]],
                    orientation="h",
                    name=f"Second 50% of effort (km {effort_dist['effort_midpoint_km']:.1f} → {total_km:.1f})",
                    marker_color="#ffa500",
                    text=f"{effort_dist['pct_second_half']:.0f}%",
                    textposition="inside",
                    hovertemplate="Second 50%% of effort: %{x:.1f}%% of the course<extra></extra>",
                ))
                fig_effort.update_layout(
                    template="plotly_dark",
                    barmode="stack",
                    xaxis_title="% of physical course distance",
                    height=180,
                    margin=dict(l=10, r=10, t=10, b=10),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
                )
                st.plotly_chart(fig_effort, use_container_width=True)
                chart_download_button(fig_effort, "effort_distribution.html", "dl_effort_dist")
                st.caption(
                    f"Split ≈ **{effort_dist['pct_first_half']:.0f}/{effort_dist['pct_second_half']:.0f}** "
                    f"(physical distance to reach 50% of effort vs. remaining distance). "
                    f"Total effort-adjusted distance (Km_E): {effort_dist['total_km_e']:.1f} km."
                )

                # --- Effort map (elevation profile colored by slope category) ---
                st.markdown("---")
                st.subheader("📈 Biomechanical Effort Map")
                st.write("The engine isolated the race segments by slope and altitude:")

                df_chart = resample_for_chart(df_gpx, step_m=200)

                fig = go.Figure()

                fig.add_trace(go.Scatter(
                    x=df_chart["Distance (km)"], y=df_chart["Elevation (m)"],
                    mode='lines', name='Base Profile',
                    line=dict(color='#444444', width=1.5),
                    hovertemplate="Km %{x:.1f}<br>%{y:.0f} m<extra></extra>",
                ))

                for category in SLOPE_CATEGORY_ORDER:
                    color = SLOPE_CATEGORY_COLORS[category]
                    width = 3.5 if "Strong" in category else (3.0 if "Moderate" in category else 2.5)
                    df_layer = df_chart.copy()
                    df_layer.loc[df_layer["Slope Type"] != category, "Elevation (m)"] = None
                    fig.add_trace(go.Scatter(
                        x=df_layer["Distance (km)"], y=df_layer["Elevation (m)"],
                        mode='lines', name=category,
                        line=dict(color=color, width=width),
                        hovertemplate="Km %{x:.1f}<br>%{y:.0f} m<extra></extra>",
                    ))

                fig.add_hline(
                    y=ALTITUDE_THRESHOLD,
                    line_dash="dash",
                    line_color="#a78bfa",
                    annotation_text=f"{ALTITUDE_THRESHOLD}m",
                    annotation_position="top left",
                )

                fig.update_layout(
                    template="plotly_dark",
                    xaxis_title="Distance (km)",
                    yaxis_title="Elevation (m)",
                    height=450,
                    hovermode="closest",
                    xaxis=dict(dtick=5),
                    yaxis=dict(dtick=100),
                )
                st.plotly_chart(fig, use_container_width=True)
                chart_download_button(fig, "biomechanical_effort_map.html", "dl_effort_map")

                with st.expander("View full point-by-point table"):
                    st.dataframe(df_gpx, use_container_width=True)

                st.session_state['df_gpx_analytics'] = df_gpx

                # --- Match registry checkpoints against the GPX ---
                st.markdown("---")
                st.subheader("📍 Official Race Checkpoints")

                valid_checkpoints = []
                invalid_ids = []
                for cp in active_checkpoints:
                    try:
                        valid_checkpoints.append({"point": int(cp["id"]), "km": float(cp["km"])})
                    except (ValueError, TypeError):
                        invalid_ids.append(cp.get("id"))

                if invalid_ids:
                    st.warning(
                        f"Checkpoints with id {invalid_ids} aren't numeric and were excluded "
                        "from matching ('id' must match the UTMB Live 'pointId')."
                    )

                df_segments = None
                if len(valid_checkpoints) >= 2:
                    df_segments = match_checkpoints_with_gpx(df_gpx, valid_checkpoints)
                    st.markdown("##### Matching Preview (segment by segment)")
                    columns_to_show = [c for c in df_segments.columns if c not in ("Start Point", "End Point")]
                    st.dataframe(df_segments[columns_to_show], use_container_width=True)
                else:
                    st.info(
                        "This race has fewer than 2 valid numeric checkpoints in the registry: "
                        "the general geometric analysis is still available, but VPI/DMI by "
                        "segment can't be calculated on the 'Runner Metrics' tab."
                    )

                # --- Auto-save to the library (Tab 2) ---
                saved_race_name = f"{visible_race_name} {active_year} - {active_distance}K"
                st.session_state['saved_races'][saved_race_name] = {
                    "df": df_gpx,
                    "total_km": total_km,
                    "km_by_category": km_by_category,
                    "km_above_altitude": km_above_altitude,
                    "checkpoints_km": valid_checkpoints,
                    "df_segments": df_segments,
                }
                st.success(
                    f"✅ Race loaded as **'{saved_race_name}'** — now available on the "
                    "'Runner Metrics' tab."
                )

        if st.session_state['saved_races']:
            with st.expander(f"📚 Races loaded this session ({len(st.session_state['saved_races'])})"):
                for name in st.session_state['saved_races']:
                    n_checkpoints = len(st.session_state['saved_races'][name].get('checkpoints_km', []))
                    st.write(f"- {name} ({n_checkpoints} checkpoints)")

# ---------------------------------------------
# TAB 2: Runner Metrics via LiveTrail (api.v3.livetrail.net). The
# equivalent UTMB Live-based tab was removed - this is now the single
# path for official runner splits, and the "UTMB vs GPX" tab reads its
# estimate (the "_lt" session_state keys) directly.
# ---------------------------------------------
with tab_runner_lt:
    st.header("🏃 Runner Metrics (LiveTrail)")
    st.caption(
        "Pulls splits and rank directly from Livetrail (api.v3.livetrail.net) - "
        "works for any race timed by Livetrail."
    )

    available_races_lt = st.session_state.get('saved_races', {})
    if not available_races_lt:
        st.warning(
            "⚠️ You haven't loaded any race yet. Go to the "
            "**'🗺️ Race Analysis'** tab, select and analyze a race, and it "
            "will show up here automatically."
        )
        selected_race_lt = None
    else:
        selected_race_lt = st.selectbox(
            "Which race did this runner do?",
            options=list(available_races_lt.keys()),
            key="lt_race_selector",
        )
        race_data_lt_selected = available_races_lt[selected_race_lt]
        st.caption(
            f"Selected race: **{selected_race_lt}** · "
            f"{race_data_lt_selected['total_km']:.1f} km total"
        )

    st.markdown("---")

    runner_url_lt = st.text_input(
        "Runner link (LiveTrail)",
        placeholder="https://aranbyutmb.v3.livetrail.net/en/2026/runners/5?raceId=vda",
        key="lt_runner_url",
    )
    manual_race_id_lt = st.text_input(
        "Race ID (only needed if the URL above has no '?raceId=...')",
        placeholder="vda",
        key="lt_manual_race_id",
    )
    load_button_lt = st.button("🔍 Load runner data (LiveTrail)", use_container_width=True, key="lt_load_button")

    if load_button_lt:
        if not runner_url_lt:
            st.warning("Paste a valid link before clicking the button.")
        else:
            with st.spinner("Connecting to LiveTrail..."):
                try:
                    runner_info_lt, df_runner_lt = scrape_runner_splits_livetrail(
                        runner_url_lt, manual_race_id=manual_race_id_lt or None
                    )
                    error_detail_lt = None
                except Exception:
                    runner_info_lt, df_runner_lt = None, None
                    error_detail_lt = traceback.format_exc()

            if error_detail_lt:
                st.error("❌ An error occurred while trying to fetch the runner data.")
                with st.expander("View technical error detail"):
                    st.code(error_detail_lt, language="python")
            elif df_runner_lt is None or df_runner_lt.empty:
                st.warning(
                    "⚠️ No data table was found at that link. "
                    "Make sure it's the direct URL to the runner's profile, and that "
                    "the race has finished passings recorded."
                )
            else:
                st.success("✅ Runner data fetched successfully (LiveTrail)!")

                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Runner", runner_info_lt.get("Name") or "-")
                c2.metric("Finish Time", runner_info_lt.get("Finish Time") or "-")
                c3.metric("Overall Rank", runner_info_lt.get("Overall Rank") or "-")
                c4.metric("Category", runner_info_lt.get("Category") or "-")
                st.caption(
                    "Note: 'Speed' and 'Pace' per checkpoint aren't exposed by the "
                    "LiveTrail runner endpoint (only by UTMB Live), so those columns "
                    "show blank here - VPI/DMI/ER aren't affected, since they're "
                    "calculated from Accumulated Time, not from these columns."
                )

                st.markdown("##### Checkpoints / Split Times")
                st.dataframe(df_runner_lt, use_container_width=True)

                st.session_state['runner_metrics_df_lt'] = df_runner_lt
                st.session_state['runner_info_lt'] = runner_info_lt
                st.session_state['race_selected_for_runner_lt'] = selected_race_lt

                current_race_data_lt = available_races_lt.get(selected_race_lt, {}) if selected_race_lt else {}
                race_segments_df_lt = current_race_data_lt.get("df_segments")

                st.markdown("---")

                if race_segments_df_lt is None or race_segments_df_lt.empty:
                    st.warning(
                        "⚠️ The selected race doesn't have checkpoints with km loaded yet. "
                        "Go back to the 'Race Analysis' tab, load the checkpoints for that "
                        "race, and reload it here to calculate the indices."
                    )
                else:
                    try:
                        total_race_gain_lt = calculate_total_elevation_gain(current_race_data_lt["df"])
                        indices_lt, df_crossed_lt = calculate_runner_indices(
                            current_race_data_lt["df"],
                            race_segments_df_lt,
                            df_runner_lt,
                            current_race_data_lt["total_km"],
                            total_race_gain_lt,
                        )
                        df_segment_degradation_lt = calculate_indices_by_segment(
                            current_race_data_lt["df"], race_segments_df_lt, df_runner_lt
                        )
                        indices_error_lt = None
                    except Exception as e:
                        indices_lt, df_crossed_lt, df_segment_degradation_lt = None, None, None
                        indices_error_lt = str(e)

                    st.markdown("## 🎯 Performance Indices")
                    if indices_error_lt:
                        st.error(f"❌ Couldn't calculate the indices: {indices_error_lt}")
                    else:
                        if indices_lt["unmatched_segments"] > 0:
                            st.caption(
                                f"⚠️ {indices_lt['unmatched_segments']} race segment(s) had no "
                                "matching checkpoint in the runner's data and were excluded from the calculation."
                            )
                        if indices_lt.get("merged_checkpoints", 0) > 0:
                            st.caption(
                                f"ℹ️ {indices_lt['merged_checkpoints']} checkpoint(s) had no recorded time for "
                                "this runner (common at aid stations that don't scan bibs) and were merged "
                                "into the surrounding segment instead of being dropped."
                            )
                        with st.expander("View crossed segments (race + runner times)"):
                            st.dataframe(df_crossed_lt, use_container_width=True)

                        st.session_state['estimated_degradation_df_lt'] = df_segment_degradation_lt
                        st.session_state['estimated_degradation_race_lt'] = selected_race_lt
                        st.session_state['estimated_global_indices_lt'] = indices_lt
                        _web_export_track_result(selected_race_lt, runner_info_lt, indices_lt)

                        # --- VPI chart ---
                        st.markdown("---")
                        st.markdown("### 🧗 VPI - Vertical Power Index")
                        st.metric(
                            "VPI (whole race)",
                            f"{indices_lt['VPI']} m/h" if indices_lt["VPI"] is not None else "N/A",
                            help="Vertical Power Index: meters of elevation gain per hour on segments with slope ≥12%.",
                        )
                        fig_vpi_lt = go.Figure()
                        add_elevation_background(fig_vpi_lt, current_race_data_lt["df"])
                        fig_vpi_lt.add_trace(go.Scatter(
                            x=df_segment_degradation_lt["End Km"],
                            y=df_segment_degradation_lt["VPI Raw (m/h)"],
                            mode="lines+markers",
                            name="VPI (m/h)",
                            line=dict(color="#22d3ee", width=3),
                            text=df_segment_degradation_lt["Segment"],
                            hovertemplate="%{text}<br>Km %{x:.0f}<br>VPI: %{y:.0f} m/h<extra></extra>",
                        ))
                        fig_vpi_lt.update_layout(
                            template="plotly_dark",
                            xaxis_title="Accumulated Km",
                            yaxis_title="VPI (m/h)",
                            height=380,
                            hovermode="x unified",
                        )
                        st.plotly_chart(fig_vpi_lt, use_container_width=True)
                        chart_download_button(fig_vpi_lt, "vpi_chart_livetrail.html", "dl_vpi_lt")

                        # --- DMI chart ---
                        st.markdown("---")
                        st.markdown("### 📉 DMI - Descent Mastery Index")
                        st.metric(
                            "DMI (whole race)",
                            f"{indices_lt['DMI']} km/h" if indices_lt["DMI"] is not None else "N/A",
                            help="Descent Mastery Index: average speed on segments with slope ≤-12%.",
                        )
                        fig_dmi_lt = go.Figure()
                        add_elevation_background(fig_dmi_lt, current_race_data_lt["df"])
                        fig_dmi_lt.add_trace(go.Scatter(
                            x=df_segment_degradation_lt["End Km"],
                            y=df_segment_degradation_lt["DMI Raw (km/h)"],
                            mode="lines+markers",
                            name="DMI (km/h)",
                            line=dict(color="#ffa500", width=3),
                            text=df_segment_degradation_lt["Segment"],
                            hovertemplate="%{text}<br>Km %{x:.0f}<br>DMI: %{y:.2f} km/h<extra></extra>",
                        ))
                        fig_dmi_lt.update_layout(
                            template="plotly_dark",
                            xaxis_title="Accumulated Km",
                            yaxis_title="DMI (km/h)",
                            height=380,
                            hovermode="x unified",
                        )
                        st.plotly_chart(fig_dmi_lt, use_container_width=True)
                        chart_download_button(fig_dmi_lt, "dmi_chart_livetrail.html", "dl_dmi_lt")

                        # --- ER chart ---
                        st.markdown("---")
                        st.markdown("### 🏆 ER - Endurance Rating - Pacing Curve")
                        m1, pe1, pe2 = st.columns(3)
                        m1.metric(
                            "ER (whole race)",
                            f"{indices_lt['ER']}" if indices_lt["ER"] is not None else "N/A",
                            help="Endurance Rating: 100 = stable pace, lower values indicate fatigue-driven degradation.",
                        )
                        pe1.metric(
                            "First Half Pace",
                            f"{indices_lt['effort_pace_first_half']} min/effort-km"
                            if indices_lt.get("effort_pace_first_half") is not None else "N/A",
                        )
                        pe2.metric(
                            "Second Half Pace",
                            f"{indices_lt['effort_pace_second_half']} min/effort-km"
                            if indices_lt.get("effort_pace_second_half") is not None else "N/A",
                        )

                        fig_er_lt = go.Figure()
                        add_elevation_background(fig_er_lt, current_race_data_lt["df"])
                        fig_er_lt.add_trace(go.Scatter(
                            x=df_crossed_lt["End Km"],
                            y=df_crossed_lt["Effort Pace (min/effort-km)"],
                            mode="lines+markers",
                            name="Effort Pace",
                            line=dict(color="#c084fc", width=3),
                            hovertemplate="Km %{x:.0f}<br>%{y:.2f} min/effort-km<extra></extra>",
                        ))
                        if indices_lt.get("half_effort_km") is not None:
                            reaches_half_effort_lt = df_crossed_lt["Effort Km Accumulated"] >= indices_lt["half_effort_km"]
                            if reaches_half_effort_lt.any():
                                effort_midpoint_km_display_lt = df_crossed_lt.loc[reaches_half_effort_lt, "End Km"].iloc[0]
                            else:
                                effort_midpoint_km_display_lt = current_race_data_lt["total_km"] / 2
                            fig_er_lt.add_vline(
                                x=effort_midpoint_km_display_lt,
                                line_dash="dash",
                                line_color="#a78bfa",
                                annotation_text="50% effort",
                                annotation_position="top",
                            )
                        fig_er_lt.update_layout(
                            template="plotly_dark",
                            xaxis_title="Accumulated Km",
                            yaxis_title="Effort Pace (min/effort-km)",
                            height=380,
                            hovermode="x unified",
                        )
                        st.plotly_chart(fig_er_lt, use_container_width=True)
                        chart_download_button(fig_er_lt, "er_pacing_curve_livetrail.html", "dl_er_lt")

                        # --- Degradation matrix by segment ---
                        st.markdown("---")
                        st.markdown("### 📉 Degradation Curve by Segment")

                        df_segment_degradation_lt = df_segment_degradation_lt.merge(
                            df_crossed_lt[["Start Km", "End Km", "Effort Pace (min/effort-km)"]],
                            on=["Start Km", "End Km"],
                            how="left",
                        )
                        valid_pace_lt = df_segment_degradation_lt["Effort Pace (min/effort-km)"].dropna()
                        if not valid_pace_lt.empty and valid_pace_lt.iloc[0]:
                            pace_baseline_lt = valid_pace_lt.iloc[0]
                            df_segment_degradation_lt["ER Index (0-100)"] = (
                                (pace_baseline_lt / df_segment_degradation_lt["Effort Pace (min/effort-km)"]) * 100
                            ).round(1)
                        else:
                            df_segment_degradation_lt["ER Index (0-100)"] = None

                        st.dataframe(df_segment_degradation_lt, use_container_width=True)

                        fig_degradation_lt = go.Figure()
                        add_elevation_background(fig_degradation_lt, current_race_data_lt["df"])
                        fig_degradation_lt.add_trace(go.Scatter(
                            x=df_segment_degradation_lt["End Km"],
                            y=df_segment_degradation_lt["VPI Index (0-100)"],
                            mode="lines+markers",
                            name="VPI (Climbing)",
                            line=dict(color="#22d3ee", width=3),
                            text=df_segment_degradation_lt["Segment"],
                            hovertemplate="%{text}<br>Km %{x:.0f}<br>VPI Index: %{y:.1f}<extra></extra>",
                        ))
                        fig_degradation_lt.add_trace(go.Scatter(
                            x=df_segment_degradation_lt["End Km"],
                            y=df_segment_degradation_lt["DMI Index (0-100)"],
                            mode="lines+markers",
                            name="DMI (Descent)",
                            line=dict(color="#ffa500", width=3),
                            text=df_segment_degradation_lt["Segment"],
                            hovertemplate="%{text}<br>Km %{x:.0f}<br>DMI Index: %{y:.1f}<extra></extra>",
                        ))
                        fig_degradation_lt.add_trace(go.Scatter(
                            x=df_segment_degradation_lt["End Km"],
                            y=df_segment_degradation_lt["ER Index (0-100)"],
                            mode="lines+markers",
                            name="ER (Endurance)",
                            line=dict(color="#c084fc", width=3),
                            text=df_segment_degradation_lt["Segment"],
                            hovertemplate="%{text}<br>Km %{x:.0f}<br>ER Index: %{y:.1f}<extra></extra>",
                        ))
                        fig_degradation_lt.update_layout(
                            template="plotly_dark",
                            xaxis_title="Accumulated Km",
                            yaxis_title="Index (0-100, Segment 1 = 100)",
                            height=420,
                            hovermode="x unified",
                        )
                        st.plotly_chart(fig_degradation_lt, use_container_width=True)
                        chart_download_button(fig_degradation_lt, "degradation_curve_livetrail.html", "dl_degradation_lt")

                        # --- Full summary table ---
                        st.markdown("---")
                        st.markdown("### 📋 Full Summary Table")

                        df_summary_lt = build_summary_table(race_segments_df_lt, df_segment_degradation_lt, df_runner_lt)
                        st.dataframe(df_summary_lt, use_container_width=True, hide_index=True)

                        # --- Full analysis report ---
                        st.markdown("---")
                        st.markdown("### 📄 Full Analysis Report")
                        full_report_html_lt = build_full_runner_report_html(
                            runner_info=runner_info_lt,
                            df_runner=df_runner_lt,
                            indices=indices_lt,
                            figures={
                                "🧗 VPI - Vertical Power Index": fig_vpi_lt,
                                "📉 DMI - Descent Mastery Index": fig_dmi_lt,
                                "🏆 ER - Endurance Rating - Pacing Curve": fig_er_lt,
                                "📉 Degradation Curve by Segment": fig_degradation_lt,
                            },
                            df_segment_degradation=df_segment_degradation_lt,
                            df_summary=df_summary_lt,
                        )
                        st.download_button(
                            "📄 Download Full Analysis (HTML for Blogger)",
                            data=full_report_html_lt,
                            file_name=f"{(runner_info_lt.get('Name') or 'runner').replace(' ', '_')}_livetrail_full_analysis.html",
                            mime="text/html",
                            type="primary",
                            use_container_width=True,
                            key="dl_full_report_lt",
                        )

# ---------------------------------------------
# TAB 3: GPX Metrics (mirrors Runner Metrics, but measured directly
# from the runner's personal, timestamped GPX instead of UTMB Live)
# ---------------------------------------------
with tab_gpx:
    st.header("🛰️ GPX-Based Runner Metrics")
    st.caption(
        "Same VPI/DMI/ER indices as the 'Runner Metrics' tab, but calculated directly "
        "from the runner's personal GPS watch track (with real timestamps) instead of "
        "the checkpoint-time estimation. No UTMB Live link needed here."
    )

    available_races_gpx = st.session_state.get('saved_races', {})
    if not available_races_gpx:
        st.warning(
            "⚠️ You haven't loaded any race yet. Go to the "
            "**'🗺️ Race Analysis'** tab, select and analyze a race, and it "
            "will show up here automatically."
        )
        selected_race_gpx = None
    else:
        selected_race_gpx = st.selectbox(
            "Which race did this runner do?",
            options=list(available_races_gpx.keys()),
            key="gpx_race_selector",
        )
        race_data_gpx = available_races_gpx[selected_race_gpx]
        st.caption(
            f"Selected race: **{selected_race_gpx}** · "
            f"{race_data_gpx['total_km']:.1f} km total"
        )

    st.markdown("---")

    personal_gpx_file = st.file_uploader(
        "Runner's personal GPX (recorded activity, must include timestamps)",
        type=["gpx", "xml"],
        key="gpx_metrics_uploader",
    )
    calculate_gpx_button = st.button(
        "🛰️ Calculate metrics from this GPX", type="primary", use_container_width=True
    )

    if calculate_gpx_button:
        if personal_gpx_file is None:
            st.warning("Upload a personal GPX file first.")
        elif not selected_race_gpx:
            st.warning("Select a race above first.")
        else:
            current_race_data_gpx = available_races_gpx[selected_race_gpx]
            race_segments_df_gpx = current_race_data_gpx.get("df_segments")

            if race_segments_df_gpx is None or race_segments_df_gpx.empty:
                st.warning(
                    "⚠️ The selected race doesn't have checkpoints with km loaded yet. "
                    "Go back to the 'Race Analysis' tab, load the checkpoints for that "
                    "race, and reload it here."
                )
            else:
                with st.spinner("Parsing personal GPX and calculating metrics..."):
                    try:
                        runner_gpx_df = process_runner_gpx_with_time(personal_gpx_file)
                        total_race_gain_gpx = calculate_total_elevation_gain(current_race_data_gpx["df"])
                        global_indices_gpx = calculate_global_real_indices(
                            runner_gpx_df,
                            current_race_data_gpx["df"],
                            current_race_data_gpx["total_km"],
                            total_race_gain_gpx,
                        )
                        df_segment_gpx = calculate_real_indices_by_segment(runner_gpx_df, race_segments_df_gpx)
                        gpx_error = None
                    except Exception:
                        global_indices_gpx, df_segment_gpx = None, None
                        gpx_error = traceback.format_exc()

                if gpx_error:
                    st.error("❌ Couldn't process this GPX.")
                    with st.expander("View technical error detail"):
                        st.code(gpx_error, language="python")
                else:
                    st.success("✅ Metrics calculated directly from the personal GPX.")

                    # --- Track summary card (no name/bib available from a raw GPX) ---
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Total Distance (GPX)", f"{global_indices_gpx['total_distance_km']:.1f} km")
                    c2.metric("Total Time (GPX)", f"{global_indices_gpx['total_time_h']:.2f} h")
                    c3.metric("Total Elevation Gain (GPX)", f"{global_indices_gpx['total_elevation_gain_m']:.0f} m")

                    st.markdown("### 🎯 Performance Indices (measured)")
                    i1, i2, i3 = st.columns(3)
                    i1.metric(
                        "🧗 VPI - Climbing Efficiency",
                        f"{global_indices_gpx['VPI']} m/h" if global_indices_gpx["VPI"] is not None else "N/A",
                        help="Measured directly from 500m windows across the whole track with slope ≥12%.",
                    )
                    i2.metric(
                        "📉 DMI - Descent Mastery",
                        f"{global_indices_gpx['DMI']} km/h" if global_indices_gpx["DMI"] is not None else "N/A",
                        help="Measured directly from 500m windows across the whole track with slope ≤-12%.",
                    )
                    i3.metric(
                        "🏆 ER - Endurance Rating",
                        f"{global_indices_gpx['ER']}" if global_indices_gpx["ER"] is not None else "N/A",
                        help="Uses the runner's REAL elapsed time before/after the course's effort-km midpoint.",
                    )

                    # --- ER calculation visualized (measured) ---
                    st.markdown("---")
                    st.markdown("### 🏆 Endurance Rating - Pacing Curve (measured)")
                    st.caption(
                        "Effort pace (minutes per effort-km) segment by segment, measured directly "
                        "from the personal GPX. Same split logic as 'Runner Metrics': divided at the "
                        "point where the course reaches 50% of its total effort."
                    )
                    pe1, pe2 = st.columns(2)
                    pe1.metric(
                        "First Half Pace (measured)",
                        f"{global_indices_gpx['effort_pace_first_half']} min/effort-km"
                        if global_indices_gpx.get("effort_pace_first_half") is not None else "N/A",
                    )
                    pe2.metric(
                        "Second Half Pace (measured)",
                        f"{global_indices_gpx['effort_pace_second_half']} min/effort-km"
                        if global_indices_gpx.get("effort_pace_second_half") is not None else "N/A",
                    )

                    df_segment_gpx_sorted = df_segment_gpx.sort_values("Start Km").reset_index(drop=True)
                    df_segment_gpx_sorted["Effort Km Accumulated"] = df_segment_gpx_sorted["Effort Km Segment"].cumsum()

                    fig_er_gpx = go.Figure()
                    fig_er_gpx.add_trace(go.Scatter(
                        x=df_segment_gpx_sorted["End Km"],
                        y=df_segment_gpx_sorted["Effort Pace (min/effort-km)"],
                        mode="lines+markers",
                        name="Effort Pace (measured)",
                        line=dict(color="#c084fc", width=3),
                        hovertemplate="Km %{x:.0f}<br>%{y:.2f} min/effort-km<extra></extra>",
                    ))
                    if global_indices_gpx.get("effort_midpoint_km") is not None:
                        fig_er_gpx.add_vline(
                            x=global_indices_gpx["effort_midpoint_km"],
                            line_dash="dash",
                            line_color="#a78bfa",
                            annotation_text="50% effort",
                            annotation_position="top",
                        )
                    fig_er_gpx.update_layout(
                        template="plotly_dark",
                        xaxis_title="Accumulated Km",
                        yaxis_title="Effort Pace (min/effort-km)",
                        height=380,
                        hovermode="x unified",
                    )
                    st.plotly_chart(fig_er_gpx, use_container_width=True)
                    chart_download_button(fig_er_gpx, "gpx_er_pacing_curve.html", "dl_er_gpx")

                    # --- Degradation curve by segment (measured) ---
                    st.markdown("---")
                    st.markdown("### 📉 Degradation Curve by Segment (measured)")

                    df_segment_gpx["VPI Index (0-100)"] = normalize_segment_index(df_segment_gpx["VPI Real (m/h)"])
                    df_segment_gpx["DMI Index (0-100)"] = normalize_segment_index(df_segment_gpx["DMI Real (km/h)"])

                    st.dataframe(df_segment_gpx, use_container_width=True)

                    fig_gpx_degradation = go.Figure()
                    fig_gpx_degradation.add_trace(go.Scatter(
                        x=df_segment_gpx["End Km"],
                        y=df_segment_gpx["VPI Index (0-100)"],
                        mode="lines+markers",
                        name="VPI (Climbing)",
                        line=dict(color="#22d3ee", width=3),
                        text=df_segment_gpx["Segment"],
                        hovertemplate="%{text}<br>Km %{x:.0f}<br>VPI Index: %{y:.1f}<extra></extra>",
                    ))
                    fig_gpx_degradation.add_trace(go.Scatter(
                        x=df_segment_gpx["End Km"],
                        y=df_segment_gpx["DMI Index (0-100)"],
                        mode="lines+markers",
                        name="DMI (Descent)",
                        line=dict(color="#ffa500", width=3),
                        text=df_segment_gpx["Segment"],
                        hovertemplate="%{text}<br>Km %{x:.0f}<br>DMI Index: %{y:.1f}<extra></extra>",
                    ))
                    fig_gpx_degradation.update_layout(
                        template="plotly_dark",
                        xaxis_title="Accumulated Km",
                        yaxis_title="Index (0-100, Segment 1 = 100)",
                        height=420,
                        hovermode="x unified",
                    )
                    st.plotly_chart(fig_gpx_degradation, use_container_width=True)
                    chart_download_button(fig_gpx_degradation, "gpx_degradation_curve.html", "dl_gpx_degradation")

                    # Saved so the 'UTMB vs GPX' tab can compare against the estimate
                    st.session_state['real_degradation_df'] = df_segment_gpx
                    st.session_state['real_metrics_race'] = selected_race_gpx
                    st.session_state['real_global_indices'] = global_indices_gpx

# ---------------------------------------------
# TAB 4: UTMB vs GPX comparison (pulls results already computed in
# 'Runner Metrics' and 'GPX Metrics' - no new upload needed here)
# ---------------------------------------------
with tab_comparison:
    st.header("⚖️ LiveTrail Estimate vs GPX Measurement")
    st.caption(
        "Compares the checkpoint-based estimate (from 'Runner Metrics (LiveTrail)') "
        "against the GPX-measured values (from 'GPX Metrics') for the same runner and "
        "race. Load both tabs first for the same race."
    )

    estimated_df = st.session_state.get('estimated_degradation_df_lt')
    estimated_race = st.session_state.get('estimated_degradation_race_lt')
    estimated_global = st.session_state.get('estimated_global_indices_lt')

    real_df = st.session_state.get('real_degradation_df')
    real_race = st.session_state.get('real_metrics_race')
    real_global = st.session_state.get('real_global_indices')

    if estimated_df is None or real_df is None:
        missing = []
        if estimated_df is None:
            missing.append("**'Runner Metrics (LiveTrail)'** (checkpoint-based estimate)")
        if real_df is None:
            missing.append("**'GPX Metrics'** (personal GPX measurement)")
        st.info(
            "Still missing data from: " + " and ".join(missing) +
            ". Load the runner there first, then come back here."
        )
    elif estimated_race != real_race:
        st.info(
            f"The estimate in memory is for **'{estimated_race}'** and the GPX "
            f"measurement is for **'{real_race}'**. Reload both tabs with the same "
            "race selected to compare them."
        )
    else:
        st.markdown(f"**Race:** {estimated_race}")

        st.markdown("### 🎯 Global Indices")
        g1, g2, g3 = st.columns(3)
        g1.metric(
            "🧗 VPI",
            f"Est: {estimated_global['VPI']} vs Real: {real_global['VPI']} m/h"
            if estimated_global.get('VPI') is not None and real_global.get('VPI') is not None else "N/A",
        )
        g2.metric(
            "📉 DMI",
            f"Est: {estimated_global['DMI']} vs Real: {real_global['DMI']} km/h"
            if estimated_global.get('DMI') is not None and real_global.get('DMI') is not None else "N/A",
        )
        g3.metric(
            "🏆 ER",
            f"Est: {estimated_global['ER']} vs Real: {real_global['ER']}"
            if estimated_global.get('ER') is not None and real_global.get('ER') is not None else "N/A",
        )

        st.markdown("---")
        st.markdown("### 📊 Segment by Segment")

        df_comparison = pd.merge(
            real_df[["Segment", "Real Time (h)", "VPI Real (m/h)", "DMI Real (km/h)"]],
            estimated_df[["Segment", "Runner Time (h)", "VPI Raw (m/h)", "DMI Raw (km/h)"]],
            on="Segment",
            how="outer",
        )
        df_comparison["VPI Diff (m/h)"] = (
            df_comparison["VPI Real (m/h)"] - df_comparison["VPI Raw (m/h)"]
        ).round(1)
        df_comparison["DMI Diff (km/h)"] = (
            df_comparison["DMI Real (km/h)"] - df_comparison["DMI Raw (km/h)"]
        ).round(2)

        st.dataframe(df_comparison, use_container_width=True)

        valid_vpi_diff = df_comparison["VPI Diff (m/h)"].dropna()
        valid_dmi_diff = df_comparison["DMI Diff (km/h)"].dropna()
        c1, c2 = st.columns(2)
        if not valid_vpi_diff.empty:
            c1.metric(
                "Average VPI error",
                f"{valid_vpi_diff.abs().mean():.1f} m/h",
                help="Mean absolute difference between the estimated and real VPI across segments where both exist.",
            )
        if not valid_dmi_diff.empty:
            c2.metric(
                "Average DMI error",
                f"{valid_dmi_diff.abs().mean():.2f} km/h",
                help="Mean absolute difference between the estimated and real DMI across segments where both exist.",
            )

# ---------------------------------------------
# TAB 5: Top Runners (same unified summary table as 'Runner Metrics',
# but for several bibs at once, ready to compare side by side)
# ---------------------------------------------
with tab_top:
    st.header("🏆 Top Runners Comparison")
    st.caption(
        "Fetches the same unified summary table as 'Runner Metrics' for several bibs at "
        "once (e.g. the top 10), so you can paste them side by side into Excel without "
        "loading each runner one at a time."
    )

    available_races_top = st.session_state.get('saved_races', {})
    if not available_races_top:
        st.warning(
            "⚠️ You haven't loaded any race yet. Go to the "
            "**'🗺️ Race Analysis'** tab, select and analyze a race, and it "
            "will show up here automatically."
        )
        selected_race_top = None
    else:
        selected_race_top = st.selectbox(
            "Which race are these runners in?",
            options=list(available_races_top.keys()),
            key="top_race_selector",
        )

    st.markdown("---")
    example_url = st.text_input(
        "Example runner URL from this race (any bib works, just to identify the race/year)",
        placeholder="https://live.utmb.world/aranbyutmb/2026/runners/5",
        key="top_example_url",
    )
    bib_list_raw = st.text_area(
        "Bib numbers to fetch (one per line or comma-separated, e.g. the top 10)",
        placeholder="5\n12\n8\n23\n...",
        key="top_bib_list",
    )
    fetch_top_button = st.button("🏆 Fetch all bibs", type="primary", use_container_width=True)

    if fetch_top_button:
        if not selected_race_top:
            st.warning("Select a race above first.")
        elif not example_url:
            st.warning("Paste an example runner URL first (needed to identify the race/year).")
        elif not bib_list_raw.strip():
            st.warning("Enter at least one bib number.")
        else:
            tenant = extract_tenant(example_url)
            if not tenant:
                st.error(
                    "❌ Couldn't identify the race/year from that URL. Make sure it has the "
                    "format 'https://live.utmb.world/<race>/<year>/runners/<number>'."
                )
            else:
                bibs = [b.strip() for b in re.split(r"[,\n]+", bib_list_raw) if b.strip()]
                race_data_top = available_races_top[selected_race_top]
                race_segments_df_top = race_data_top.get("df_segments")

                if race_segments_df_top is None or race_segments_df_top.empty:
                    st.warning(
                        "⚠️ The selected race doesn't have checkpoints with km loaded yet. "
                        "Go back to the 'Race Analysis' tab and load them first."
                    )
                else:
                    results = {}
                    errors = {}
                    progress = st.progress(0.0, text="Fetching runners...")

                    for i, bib in enumerate(bibs):
                        try:
                            runner_info_bib, df_runner_bib = fetch_runner_by_tenant_and_bib(tenant, bib)
                            df_segment_degradation_bib = calculate_indices_by_segment(
                                race_data_top["df"], race_segments_df_top, df_runner_bib
                            )
                            df_summary_bib = build_summary_table(
                                race_segments_df_top, df_segment_degradation_bib, df_runner_bib
                            )
                            label = f"{runner_info_bib.get('Name') or ('Bib ' + str(bib))} (Bib {bib})"
                            results[label] = df_summary_bib
                        except Exception:
                            errors[bib] = traceback.format_exc()
                        progress.progress((i + 1) / len(bibs), text=f"Fetching runners... ({i + 1}/{len(bibs)})")

                    progress.empty()

                    if errors:
                        with st.expander(f"⚠️ {len(errors)} bib(s) failed"):
                            for bib, err in errors.items():
                                st.markdown(f"**Bib {bib}:**")
                                st.code(err, language="python")

                    if not results:
                        st.error("❌ Couldn't fetch any of the bibs entered.")
                    else:
                        st.success(f"✅ Fetched {len(results)} of {len(bibs)} runner(s).")

                        for label, df_summary_bib in results.items():
                            st.markdown(f"##### {label}")
                            st.dataframe(df_summary_bib, use_container_width=True, hide_index=True)

                        # --- Combined Excel download: shared geometry once, then each
                        # runner's own columns side by side (no repeated Checkpoint/
                        # Segment Distance/Elevation/Slope columns per runner) ---
                        shared_columns = [
                            "Checkpoint", "Segment Distance (km)", "Elevation Gain (m)",
                            "Elevation Loss (m)", "Average Slope (%)",
                        ]
                        runner_columns = ["Speed", "Pace", "Rank", "Rest", "Time", "VPI", "DMI"]

                        first_df_summary = next(iter(results.values()))
                        df_shared = first_df_summary[shared_columns]

                        excel_buffer = io.BytesIO()
                        with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
                            sheet_name = "Top Runners"

                            # Shared geometry block (once)
                            pd.DataFrame({"Race Segment Geometry": []}).to_excel(
                                writer, sheet_name=sheet_name, startrow=0, startcol=0, index=False
                            )
                            df_shared.to_excel(
                                writer, sheet_name=sheet_name, startrow=1, startcol=0, index=False
                            )

                            # One block per runner, right after the shared columns
                            startcol = len(shared_columns) + 1
                            for label, df_summary_bib in results.items():
                                pd.DataFrame({label: []}).to_excel(
                                    writer, sheet_name=sheet_name, startrow=0, startcol=startcol, index=False
                                )
                                df_summary_bib[runner_columns].to_excel(
                                    writer, sheet_name=sheet_name, startrow=1, startcol=startcol, index=False
                                )
                                startcol += len(runner_columns) + 1

                        st.download_button(
                            "📥 Download combined Excel (shared geometry + each runner side by side)",
                            data=excel_buffer.getvalue(),
                            file_name=f"{selected_race_top.replace(' ', '_')}_top_runners.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True,
                        )

                        # --- Position progression chart ---
                        st.markdown("---")
                        st.markdown("### 📈 Position Progression")
                        st.caption(
                            "Each runner's rank at every checkpoint, connected across the race. "
                            "The Y axis puts 1st place at the top, counting down to the largest "
                            "(worst) position at the bottom."
                        )

                        checkpoint_to_km = dict(zip(
                            race_segments_df_top["End Point"], race_segments_df_top["End Km"]
                        ))

                        fig_positions = go.Figure()
                        add_elevation_background(fig_positions, race_data_top["df"])

                        worst_rank_seen = 0
                        for label, df_summary_bib in results.items():
                            df_plot = df_summary_bib[["Checkpoint", "Rank"]].dropna(subset=["Rank"]).copy()
                            df_plot["Km"] = df_plot["Checkpoint"].map(checkpoint_to_km)
                            df_plot = df_plot.dropna(subset=["Km"]).sort_values("Km")
                            if df_plot.empty:
                                continue
                            worst_rank_seen = max(worst_rank_seen, df_plot["Rank"].astype(float).max())
                            fig_positions.add_trace(go.Scatter(
                                x=df_plot["Km"],
                                y=df_plot["Rank"],
                                mode="lines+markers",
                                name=label,
                                hovertemplate=f"{label}<br>Km %{{x:.0f}}<br>Position: %{{y}}<extra></extra>",
                            ))

                        fig_positions.update_layout(
                            template="plotly_dark",
                            xaxis_title="Accumulated Km",
                            yaxis_title="Position",
                            height=480,
                            hovermode="closest",
                            yaxis=dict(
                                autorange=False,
                                range=[worst_rank_seen + 1, 0],
                                dtick=2,
                                showgrid=False,
                            ),
                        )
                        st.plotly_chart(fig_positions, use_container_width=True)
                        chart_download_button(fig_positions, "position_progression.html", "dl_positions")

                        # --- VPI progression chart ---
                        st.markdown("---")
                        st.markdown("### 🧗 VPI Progression")
                        st.caption(
                            "Each runner's VPI (m/h) at every checkpoint with steep climbing "
                            "terrain, connected across the race. Higher is better, so the axis "
                            "keeps the largest values at the top."
                        )

                        fig_vpi_top = go.Figure()
                        add_elevation_background(fig_vpi_top, race_data_top["df"])

                        max_vpi_seen = 0
                        for label, df_summary_bib in results.items():
                            df_plot = df_summary_bib[["Checkpoint", "VPI"]].dropna(subset=["VPI"]).copy()
                            df_plot["Km"] = df_plot["Checkpoint"].map(checkpoint_to_km)
                            df_plot = df_plot.dropna(subset=["Km"]).sort_values("Km")
                            if df_plot.empty:
                                continue
                            max_vpi_seen = max(max_vpi_seen, df_plot["VPI"].astype(float).max())
                            fig_vpi_top.add_trace(go.Scatter(
                                x=df_plot["Km"],
                                y=df_plot["VPI"],
                                mode="lines+markers",
                                name=label,
                                hovertemplate=f"{label}<br>Km %{{x:.0f}}<br>VPI: %{{y:.0f}} m/h<extra></extra>",
                            ))

                        fig_vpi_top.update_layout(
                            template="plotly_dark",
                            xaxis_title="Accumulated Km",
                            yaxis_title="VPI (m/h)",
                            height=480,
                            hovermode="closest",
                            yaxis=dict(
                                autorange=False,
                                range=[0, max_vpi_seen * 1.05 if max_vpi_seen else 1],
                                dtick=50,
                                showgrid=False,
                            ),
                        )
                        st.plotly_chart(fig_vpi_top, use_container_width=True)
                        chart_download_button(fig_vpi_top, "vpi_progression.html", "dl_vpi_top")

                        # --- DMI progression chart ---
                        st.markdown("---")
                        st.markdown("### 📉 DMI Progression")
                        st.caption(
                            "Each runner's DMI (km/h) at every checkpoint with steep descending "
                            "terrain, connected across the race. Higher is better, so the axis "
                            "keeps the largest values at the top."
                        )

                        fig_dmi_top = go.Figure()
                        add_elevation_background(fig_dmi_top, race_data_top["df"])

                        max_dmi_seen = 0
                        for label, df_summary_bib in results.items():
                            df_plot = df_summary_bib[["Checkpoint", "DMI"]].dropna(subset=["DMI"]).copy()
                            df_plot["Km"] = df_plot["Checkpoint"].map(checkpoint_to_km)
                            df_plot = df_plot.dropna(subset=["Km"]).sort_values("Km")
                            if df_plot.empty:
                                continue
                            max_dmi_seen = max(max_dmi_seen, df_plot["DMI"].astype(float).max())
                            fig_dmi_top.add_trace(go.Scatter(
                                x=df_plot["Km"],
                                y=df_plot["DMI"],
                                mode="lines+markers",
                                name=label,
                                hovertemplate=f"{label}<br>Km %{{x:.0f}}<br>DMI: %{{y:.2f}} km/h<extra></extra>",
                            ))

                        fig_dmi_top.update_layout(
                            template="plotly_dark",
                            xaxis_title="Accumulated Km",
                            yaxis_title="DMI (km/h)",
                            height=480,
                            hovermode="closest",
                            yaxis=dict(
                                autorange=False,
                                range=[0, max_dmi_seen * 1.05 if max_dmi_seen else 1],
                                dtick=1,
                                showgrid=False,
                            ),
                        )
                        st.plotly_chart(fig_dmi_top, use_container_width=True)
                        chart_download_button(fig_dmi_top, "dmi_progression.html", "dl_dmi_top")

with tab_methodology:
    st.header("📖 Indices & Calculation Methodology")
    st.caption(
        "Definitions, geometric criteria and formulas for VertLabs' proprietary indices. "
        "These indices cross the official GPX terrain (the 'Race Analysis' tab) with the "
        "runner's real split times (the 'Runner Metrics' tab)."
    )

    st.markdown("### 📐 Performance Indices")
    for index_key in INDEX_CONFIG:
        cfg = INDEX_CONFIG[index_key]
        with st.expander(f"{cfg['icon']} {cfg['name']} ({index_key})", expanded=False):
            st.markdown(display_metric_documentation(index_key))

    st.markdown("---")
    st.markdown("### ⚡ Speed Metrics")
    for metric_key, cfg in SPEED_METRICS.items():
        with st.expander(cfg['name'], expanded=False):
            st.markdown(f"""
            * **Description:** {cfg['description']}
            * **Data Source:** {cfg['source']}
            * **Formula:** `{cfg['formula']}`
            * **Unit:** {cfg['unit']}
            """)

# ---------------------------------------------
# TAB 7: Checkpoint Fetcher (Livetrail) - generates the exact block to
# paste into data/races_registry.json for a new race/edition
# ---------------------------------------------
with tab_checkpoints:
    st.header("🧩 Checkpoint Fetcher (Livetrail)")
    st.caption(
        "Descarga la lista de checkpoints (id, nombre, km) de cualquier carrera que use "
        "Livetrail como proveedor de cronometraje, y genera el bloque listo para pegar "
        "en `data/races_registry.json`."
    )

    with st.form("checkpoint_fetcher_form"):
        col1, col2 = st.columns(2)
        with col1:
            cf_race_id = st.text_input(
                "Race ID (raceId)", value="vda",
                help="El slug de la carrera dentro del tenant, ej: 'vda' para Val d'Aran.",
            )
            cf_tenant = st.text_input(
                "X-Tenant", value="aranbyutmb_2026",
                help="Formato raceslug_year, ej: 'aranbyutmb_2026'.",
            )
            cf_url = st.text_input(
                "Request URL (endpoint de Livetrail)",
                value="https://api.v3.livetrail.net/api/events/points",
                help="La Request URL exacta vista en DevTools > Network (sin el query string).",
            )
        with col2:
            cf_gpx_file = st.text_input(
                "gpx_file (ruta relativa)",
                value="data/gpx/<carrera>/<anio>/<ARCHIVO>.gpx",
                help="Ruta al GPX oficial que vas a subir/ya subiste para esta carrera.",
            )
            cf_race_slug_api = st.text_input(
                "race_slug_api", value="",
                help="Normalmente igual al Race ID (se autocompleta si lo dejas vacío).",
            )

        cf_submit = st.form_submit_button("🧩 Fetch checkpoints", type="primary", use_container_width=True)

    if cf_submit:
        if not cf_race_id or not cf_tenant or not cf_url:
            st.warning("Completa al menos Race ID, X-Tenant y Request URL.")
        else:
            with st.spinner("Consultando Livetrail..."):
                try:
                    raw_points = fetch_livetrail_checkpoints(cf_race_id, cf_tenant, cf_url)
                    cf_error = None
                except Exception:
                    raw_points = None
                    cf_error = traceback.format_exc()

            if cf_error:
                st.error("❌ No se pudo obtener la lista de checkpoints.")
                with st.expander("Ver detalle técnico del error"):
                    st.code(cf_error, language="python")
            elif not raw_points:
                st.warning("⚠️ La respuesta llegó vacía. Revisa el Race ID y el X-Tenant.")
            else:
                effective_slug = cf_race_slug_api.strip() or cf_race_id

                st.success(f"✅ {len(raw_points)} checkpoints encontrados para raceId='{cf_race_id}'.")

                # Preview en tabla, ordenada por distancia
                preview_rows = [
                    {
                        "id": p["pointId"],
                        "nombre": p["name"],
                        "km": round(p["distance"] / 1000, 1),
                        "altitud (m)": p.get("altitude"),
                        "ganancia acum. (m)": p.get("elevationGain"),
                    }
                    for p in sorted(raw_points, key=lambda x: x["distance"])
                ]
                st.dataframe(preview_rows, use_container_width=True, hide_index=True)

                registry_block = build_registry_checkpoints_block(
                    cf_gpx_file, effective_slug, raw_points
                )

                st.markdown("##### 📋 Bloque listo para pegar en `races_registry.json`")
                st.code(registry_block, language="json")

                st.download_button(
                    "📥 Descargar como .json",
                    data=registry_block.encode("utf-8"),
                    file_name=f"{cf_race_id}_checkpoints.json",
                    mime="application/json",
                    use_container_width=True,
                )

# ---------------------------------------------
# TAB 9: Export to the public web (Builder input)
#
# Writes race.json / data/athletes/<slug>/profile.json in the format
# builder/generators expects (see Claude.md section 4). Never computes
# anything itself - it only serializes VPI/DMI/ER that the UTMB/LiveTrail
# tabs already calculated this session (tracked via _web_export_track_result).
# ---------------------------------------------
with tab_web_export:
    st.header("🌐 Exportar a Web")
    st.caption(
        "Convierte los resultados ya calculados en la pestaña 'Runner Metrics (LiveTrail)' "
        "en `race.json` + `profile.json`, en el formato que espera el Builder "
        "(`vertlabs.run`). No recalcula nada: solo serializa lo que ya está en pantalla."
    )

    export_pool = st.session_state.get('web_export_pool', {})

    if not export_pool:
        st.info(
            "⚠️ Todavía no calculaste ningún índice esta sesión. Andá a "
            "**'🏃 Runner Metrics (LiveTrail)'**, cargá al menos un corredor, "
            "y va a aparecer acá automáticamente."
        )
    else:
        pool_key = st.selectbox(
            "Carrera a exportar",
            options=list(export_pool.keys()),
            help="Estas son las carreras para las que ya calculaste VPI/DMI/ER en esta sesión.",
        )
        runners_pool = export_pool[pool_key].get("runners", {})
        race_lib_data = st.session_state.get('saved_races', {}).get(pool_key, {})

        st.markdown(f"**{len(runners_pool)} corredor(es) listos para exportar:**")
        st.dataframe(
            [
                {"Bib": r.get("bib"), "Nombre": r.get("name"), "Pos": r.get("position"),
                 "Tiempo": r.get("finish_time"), "VPI": r.get("vpi"), "DMI": r.get("dmi"), "ER": r.get("er")}
                for r in runners_pool.values()
            ],
            use_container_width=True, hide_index=True,
        )

        # --- Best-effort defaults parsed from "{name} {year} - {distance}K" ---
        default_name, default_year, default_distance = pool_key, "", ""
        m = re.match(r"^(.*?)\s+(\d{4})\s*-\s*([\d.]+)K$", pool_key)
        if m:
            default_name, default_year, default_distance = m.group(1), m.group(2), m.group(3)
        default_total_km = race_lib_data.get("total_km")

        st.markdown("---")
        st.markdown("##### Metadata de la carrera (no calculada por el Engine, se completa a mano)")

        with st.form("web_export_form"):
            col1, col2 = st.columns(2)
            with col1:
                race_name = st.text_input("Nombre de la carrera", value=default_name)
                race_year = st.text_input("Año", value=default_year)
                race_distance_km = st.number_input(
                    "Distancia (km)", value=float(default_total_km) if default_total_km else 0.0, step=1.0,
                )
                race_elevation_gain_m = st.number_input("Desnivel positivo (m)", value=0.0, step=100.0)
                race_date = st.text_input("Fecha (YYYY-MM-DD)", value="")
            with col2:
                race_location = st.text_input("Ubicación", value="")
                race_folder = st.text_input(
                    "Carpeta (data/races/<esto>/...)",
                    value=_slugify(default_name) or "carrera",
                    help="Elegí el nombre que quieras: solo define dónde vive el JSON en el repo, no la URL pública.",
                )
                race_distance_folder = st.text_input(
                    "Carpeta distancia (.../<esto>/race.json)",
                    value=f"{default_distance}k" if default_distance else "distancia",
                )
                race_slug = st.text_input(
                    "Slug público (vertlabs.run/races/<esto>/)",
                    value=_slugify(f"{default_name}-{default_year}") if default_year else _slugify(default_name),
                )

            st.markdown("---")
            hero_upload = st.file_uploader(
                "Imagen hero (opcional)", type=["jpg", "jpeg", "png"],
                help="Si no subís nada, podés dejar el archivo a mano después en images/hero.jpg.",
            )
            elevation_upload = st.file_uploader(
                "Perfil de elevación (opcional): imagen o HTML interactivo de Plotly",
                type=["jpg", "jpeg", "png", "html"],
                help=(
                    "Para el interactivo: en la pestaña 'Race Analysis', el botón "
                    "'📥 Download chart as HTML' del gráfico de elevación. Se embebe "
                    "como iframe en la página de la carrera (zoom/hover funcionan)."
                ),
            )

            st.markdown("---")
            st.markdown("##### Fotos y gráficos por corredor (opcional)")
            st.caption(
                "Los gráficos HTML son los mismos que bajás con los botones "
                "'📥 Download chart as HTML' al final de 'Runner Metrics (LiveTrail)' "
                "(VPI, DMI, ER, Degradation) - subí los que quieras, se muestran "
                "interactivos al lado del corredor en la página de la carrera."
            )
            runner_uploads = {}
            for runner_key, r in runners_pool.items():
                athlete_slug = _slugify(r["name"])
                with st.expander(f"{r['name']} (Bib {r.get('bib') or '-'})"):
                    existing_portrait = _find_existing_portrait(athlete_slug)
                    if existing_portrait:
                        st.image(str(existing_portrait), caption="Foto actual", width=120)
                    portrait_upload = st.file_uploader(
                        "Foto (reemplaza la actual si subís una nueva)",
                        type=["jpg", "jpeg", "png"], key=f"portrait_{runner_key}",
                    )
                    report_upload = st.file_uploader(
                        "Informe de rendimiento completo (el HTML de 'Download Full Analysis') - "
                        "se linkea desde el nombre de esta carrera en la página del corredor",
                        type=["html"], key=f"report_{runner_key}",
                    )
                    charts_upload = st.file_uploader(
                        "Otros gráficos HTML de este corredor (podés subir varios) - se muestran "
                        "embebidos al lado del corredor en la página de la carrera",
                        type=["html"], accept_multiple_files=True, key=f"charts_{runner_key}",
                    )
                    runner_uploads[runner_key] = {
                        "portrait": portrait_upload, "report": report_upload, "charts": charts_upload,
                    }

            export_submit = st.form_submit_button(
                "📤 Exportar carrera + corredores a data/", type="primary", use_container_width=True
            )

        if export_submit:
            if not race_slug or not race_year or not race_folder or not race_distance_folder:
                st.error("Completá al menos slug, año, carpeta y carpeta de distancia.")
            else:
                try:
                    def _save_upload(upload, dest_dir: Path, base_name: str):
                        """Saves a Streamlit UploadedFile as base_name + its
                        original extension inside dest_dir. Returns the
                        extension (with dot), or None if nothing was uploaded."""
                        if upload is None:
                            return None
                        ext = Path(upload.name).suffix.lower() or ".jpg"
                        dest_dir.mkdir(parents=True, exist_ok=True)
                        (dest_dir / f"{base_name}{ext}").write_bytes(upload.getvalue())
                        return ext

                    race_dir = WEB_DATA_DIR / "races" / race_folder / race_year / race_distance_folder
                    race_dir.mkdir(parents=True, exist_ok=True)

                    # --- Merge with whatever race.json already exists at this
                    # folder/year/distance path, so re-exporting the same race
                    # (e.g. with more runners loaded in a later session) always
                    # widens it instead of risking a full overwrite that drops
                    # runners not in memory this time around. ---
                    existing_race_path = race_dir / "race.json"
                    existing_race_json = (
                        json.loads(existing_race_path.read_text(encoding="utf-8"))
                        if existing_race_path.exists() else {}
                    )
                    existing_athletes_by_slug = {
                        a["slug"]: a for a in existing_race_json.get("athletes", [])
                    }

                    hero_ext = _save_upload(hero_upload, race_dir / "images", "hero")
                    elevation_ext = _save_upload(elevation_upload, race_dir / "charts", "elevation_profile")

                    if hero_ext:
                        hero_image = f"/media/races/{race_slug}/images/hero{hero_ext}"
                    else:
                        hero_image = existing_race_json.get("hero_image") or f"/media/races/{race_slug}/images/hero.jpg"

                    if elevation_ext:
                        elevation_profile_image = f"/media/races/{race_slug}/charts/elevation_profile{elevation_ext}"
                    else:
                        elevation_profile_image = (
                            existing_race_json.get("elevation_profile_image")
                            or f"/media/races/{race_slug}/charts/elevation_profile.png"
                        )

                    portrait_uploads_by_slug = {}
                    report_by_slug = {}
                    athletes_payload = []
                    for runner_key, r in runners_pool.items():
                        athlete_slug = _slugify(r["name"])
                        uploads = runner_uploads.get(runner_key, {})
                        portrait_uploads_by_slug[athlete_slug] = uploads.get("portrait")
                        existing_athlete = existing_athletes_by_slug.get(athlete_slug, {})
                        runner_dir = race_dir / "charts" / "runners" / athlete_slug

                        report_ext = _save_upload(uploads.get("report"), runner_dir, "report")
                        if report_ext:
                            report_path = f"/media/races/{race_slug}/charts/runners/{athlete_slug}/report{report_ext}"
                        else:
                            report_path = existing_athlete.get("report")
                        report_by_slug[athlete_slug] = report_path

                        charts_payload = list(existing_athlete.get("charts", []))
                        for chart_file in uploads.get("charts") or []:
                            runner_dir.mkdir(parents=True, exist_ok=True)
                            safe_name = _slugify(Path(chart_file.name).stem) + ".html"
                            (runner_dir / safe_name).write_bytes(chart_file.getvalue())
                            chart_entry = {
                                "label": _chart_label(chart_file.name),
                                "file": f"/media/races/{race_slug}/charts/runners/{athlete_slug}/{safe_name}",
                            }
                            # Replace an existing chart with the same file name (re-upload),
                            # otherwise add it as a new one.
                            charts_payload = [c for c in charts_payload if c["file"] != chart_entry["file"]]
                            charts_payload.append(chart_entry)

                        athletes_payload.append({
                            "slug": athlete_slug,
                            "name": r["name"],
                            "bib": r.get("bib"),
                            "finish_time": r.get("finish_time"),
                            "position": r.get("position"),
                            "vpi": r.get("vpi"),
                            "dmi": r.get("dmi"),
                            "er": r.get("er"),
                            "report": report_path,
                            "charts": charts_payload,
                        })

                    # Upsert: this export's runners replace their old entry (if
                    # any); runners not touched this round (e.g. loaded in a
                    # previous session, not currently in memory) are kept as-is.
                    merged_athletes_by_slug = dict(existing_athletes_by_slug)
                    for a in athletes_payload:
                        merged_athletes_by_slug[a["slug"]] = a

                    race_json = {
                        "slug": race_slug,
                        "name": race_name,
                        "year": int(race_year),
                        "distance_km": race_distance_km or None,
                        "elevation_gain_m": race_elevation_gain_m or None,
                        "date": race_date or None,
                        "location": race_location or None,
                        "hero_image": hero_image,
                        "elevation_profile_image": elevation_profile_image,
                        "athletes": list(merged_athletes_by_slug.values()),
                    }

                    (race_dir / "race.json").write_text(
                        json.dumps(race_json, ensure_ascii=False, indent=2), encoding="utf-8"
                    )
                    written_paths = [str((race_dir / "race.json").relative_to(WEB_DATA_DIR.parent))]
                    if hero_ext:
                        written_paths.append(str((race_dir / "images" / f"hero{hero_ext}").relative_to(WEB_DATA_DIR.parent)))
                    if elevation_ext:
                        written_paths.append(str((race_dir / "charts" / f"elevation_profile{elevation_ext}").relative_to(WEB_DATA_DIR.parent)))
                    n_charts_uploaded = sum(len(uploads_.get("charts") or []) for uploads_ in runner_uploads.values())
                    if n_charts_uploaded:
                        written_paths.append(f"({n_charts_uploaded} gráfico(s) de corredor)")
                    n_reports_uploaded = sum(1 for u in runner_uploads.values() if u.get("report") is not None)
                    if n_reports_uploaded:
                        written_paths.append(f"({n_reports_uploaded} informe(s) completo(s) de corredor)")

                    # --- One profile.json per athlete, merged with whatever
                    # already exists on disk so career history accumulates
                    # across export runs instead of being overwritten. ---
                    for athlete in athletes_payload:
                        athlete_dir = WEB_DATA_DIR / "athletes" / athlete["slug"]
                        athlete_dir.mkdir(parents=True, exist_ok=True)
                        profile_path = athlete_dir / "profile.json"

                        if profile_path.exists():
                            profile = json.loads(profile_path.read_text(encoding="utf-8"))
                        else:
                            profile = {
                                "slug": athlete["slug"],
                                "name": athlete["name"],
                                "country": None,
                                "portrait": f"/media/athletes/{athlete['slug']}/images/portrait.jpg",
                                "races": [],
                            }

                        portrait_ext = _save_upload(
                            portrait_uploads_by_slug.get(athlete["slug"]), athlete_dir / "images", "portrait"
                        )
                        if portrait_ext:
                            profile["portrait"] = f"/media/athletes/{athlete['slug']}/images/portrait{portrait_ext}"
                            written_paths.append(
                                str((athlete_dir / "images" / f"portrait{portrait_ext}").relative_to(WEB_DATA_DIR.parent))
                            )

                        profile["races"] = [
                            race_entry for race_entry in profile.get("races", [])
                            if race_entry.get("race_slug") != race_slug
                        ]
                        profile["races"].append({
                            "race_slug": race_slug,
                            "race_name": race_name,
                            "year": int(race_year),
                            "position": athlete["position"],
                            "finish_time": athlete["finish_time"],
                            "vpi": athlete["vpi"],
                            "dmi": athlete["dmi"],
                            "er": athlete["er"],
                            "report": athlete.get("report"),
                        })

                        def _avg(key):
                            values = [r[key] for r in profile["races"] if r.get(key) is not None]
                            return round(sum(values) / len(values), 1) if values else None

                        profile["career_avg"] = {
                            "vpi": _avg("vpi"),
                            "dmi": _avg("dmi"),
                            "er": _avg("er"),
                        }

                        profile_path.write_text(
                            json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8"
                        )
                        written_paths.append(str(profile_path.relative_to(WEB_DATA_DIR.parent)))

                    st.success(f"✅ Exportado. {len(written_paths)} archivo(s) escrito(s):")
                    st.code("\n".join(written_paths))
                    missing = []
                    if not hero_ext:
                        missing.append("hero (images/hero.jpg)")
                    if not elevation_ext:
                        missing.append("elevation_profile (charts/elevation_profile.png)")
                    athletes_without_portrait = [
                        a["name"] for a in athletes_payload
                        if not portrait_uploads_by_slug.get(a["slug"]) and not _find_existing_portrait(a["slug"])
                    ]
                    if athletes_without_portrait:
                        missing.append(f"portrait de: {', '.join(athletes_without_portrait)}")
                    if missing:
                        st.caption(
                            f"Falta subir a mano: {'; '.join(missing)}. "
                            "Después corré `python publish.py` para regenerar el sitio."
                        )
                    else:
                        st.caption("Todas las imágenes están listas. Corré `python publish.py` para regenerar el sitio.")
                except Exception:
                    st.error("❌ No se pudo exportar.")
                    with st.expander("Ver detalle técnico del error"):
                        st.code(traceback.format_exc(), language="python")