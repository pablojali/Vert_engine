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
import uuid
import os
import shutil
import subprocess
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import redirect_stdout
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from data import gpx_loader
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

# Per-segment VPI/DMI reliability flags (see docs/05-known-issues.md,
# "VPI/DMI inflado en tramos con terreno corto e irregular"). The
# checkpoint-to-checkpoint effort-share time allocation in
# calculate_indices_by_segment() is only an estimate - it gets noisy
# when the qualifying climb/descent is a short, steep sliver of a much
# longer segment. Flag those instead of hiding them: a segment is
# marked unreliable when its effort-share is too thin to trust, or the
# resulting rate is past what's physically plausible on real terrain.
LOW_EFFORT_SHARE_THRESHOLD = 15   # % - below this, the time estimate rests on too little of the segment
VPI_PLAUSIBILITY_CEILING = 1500   # m/h - beyond real sustained climbing rates on trail
DMI_PLAUSIBILITY_CEILING = 20     # km/h - beyond real sustained technical-descent running speed

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
    # Some GPX files have points with no <ele> reading (gaps in the
    # device/course's altitude data) - carry the last known elevation
    # forward instead of crashing on None arithmetic.
    last_known_elevation = 0.0

    for track in gpx.tracks:
        for segment in track.segments:
            for point in segment.points:
                elevation = point.elevation if point.elevation is not None else last_known_elevation
                if previous_point:
                    dist = point.distance_2d(previous_point)
                    cumulative_distance += dist

                    elevation_change = elevation - last_known_elevation
                    # Avoid division by zero on identical points
                    slope = (elevation_change / dist) * 100 if dist > 0 else 0

                    points_data.append({
                        "Distance (km)": cumulative_distance / 1000.0,
                        "Elevation (m)": elevation,
                        "Slope (%)": slope
                    })
                previous_point = point
                last_known_elevation = elevation
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


def _ascii_filename(text: str) -> str:
    """Strips accents/non-ASCII characters from a piece of a download
    filename (e.g. a runner's name going into file_name= for
    st.download_button). Browsers can silently fail a download - no
    Python traceback, no server-side error - when the Content-Disposition
    header isn't plain ASCII, so this only touches the filename, never
    the runner's name as shown inside the report itself."""
    return unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode("ascii")


def _build_reports_zip(html_by_filename: dict) -> bytes:
    """Zips a batch of already-built report HTML strings into one
    in-memory .zip (filename -> HTML content), so a bulk fetch (Top
    Runners, Engine Live) can offer a single-click download of everything
    that worked, alongside the existing one-by-one buttons for anyone who
    only wants a couple."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for filename, html in html_by_filename.items():
            zf.writestr(filename, html)
    return buf.getvalue()


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

    return "\n".join(parts)




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

        # A segment's VPI/DMI estimate is flagged (not dropped) when the
        # effort-share the whole rate is built on is too thin to trust, or
        # the resulting rate is past what's physically plausible - almost
        # always a short/steep climb or descent tucked inside a much
        # longer, gentler checkpoint segment. See the constants above and
        # docs/05-known-issues.md.
        vpi_reliable = None
        if vpi_raw is not None:
            vpi_reliable = not (
                (climb_effort_share is not None and climb_effort_share * 100 < LOW_EFFORT_SHARE_THRESHOLD)
                or vpi_raw > VPI_PLAUSIBILITY_CEILING
            )
        dmi_reliable = None
        if dmi_raw is not None:
            dmi_reliable = not (
                (descent_effort_share is not None and descent_effort_share * 100 < LOW_EFFORT_SHARE_THRESHOLD)
                or dmi_raw > DMI_PLAUSIBILITY_CEILING
            )

        rows.append({
            "Segment": f"P{p_start}→P{p_end}",
            "Start Km": km_start,
            "End Km": km_end,
            "Average Slope (%)": avg_slope,
            "Runner Time (h)": round(segment_time_h, 2) if segment_time_h is not None else None,
            "Climb Effort Share (%)": round(climb_effort_share * 100, 1) if climb_effort_share is not None else None,
            "VPI Raw (m/h)": round(vpi_raw, 1) if vpi_raw is not None else None,
            "VPI Reliable": vpi_reliable,
            "Descent Effort Share (%)": round(descent_effort_share * 100, 1) if descent_effort_share is not None else None,
            "DMI Raw (km/h)": round(dmi_raw, 2) if dmi_raw is not None else None,
            "DMI Reliable": dmi_reliable,
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


def _livetrail_picture_url(picture_id):
    """Builds the runner's photo URL from the opaque "picture" ID LiveTrail's
    runner summary endpoint returns. Confirmed against a real example the
    user pulled from the LiveTrail site itself (this sandbox has no network
    access to LiveTrail to verify it independently): the photos are hosted
    on UTMB World's Cloudinary account, keyed by that same ID, e.g.
    https://res.cloudinary.com/utmb-world/image/upload/q_auto/f_auto/c_scale,w_300/c_fill,g_auto/v1/worldseries/Members/<picture_id>
    Returns None if the runner has no picture ID (not every runner has a photo)."""
    if not picture_id:
        return None
    return (
        "https://res.cloudinary.com/utmb-world/image/upload/"
        f"q_auto/f_auto/c_scale,w_300/c_fill,g_auto/v1/worldseries/Members/{picture_id}"
    )


def _country_flag_url(iso_code):
    """Builds a small flag image URL for a 2-letter ISO country code via the
    free flagcdn.com CDN. Used instead of the Unicode flag emoji (regional-
    indicator-symbol pairs) because Windows browsers don't ship flag glyphs
    by default and fall back to showing the two bare letters in little
    boxes - which reads exactly like the country code never changed at
    all. Returns None if the code doesn't look like a plain 2-letter code."""
    if not iso_code or len(iso_code) != 2 or not iso_code.isalpha():
        return None
    return f"https://flagcdn.com/w40/{iso_code.lower()}.png"


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
    """Pulls one runner's info + full checkpoint passings from LiveTrail
    given a tenant and bib. Needs TWO requests (confirmed via manual
    endpoint discovery):
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
        "Picture URL": _livetrail_picture_url(summary.get("picture")),
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
    """Accepts a runner URL like
    'https://aranbyutmb.v3.livetrail.net/en/2026/runners/5?raceId=vda'.
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


def parse_livetrail_url(url: str) -> dict:
    """Best-effort extraction of the X-Tenant and Race ID from a Livetrail
    live-results URL, so the Checkpoint Fetcher doesn't require digging
    through DevTools for those two values. Different Livetrail frontends
    encode this differently, so tries a few known shapes in order:
      - query/hash params 'e=' (tenant) and 'c=' or 'raceId=' (race id)
      - <subdomain>.v3.livetrail.net + a 4-digit year found anywhere in
        the URL, combined into "<subdomain>_<year>" (matches the tenant
        format fetch_livetrail_checkpoints already expects), used when
        there's no explicit 'e=' param
    Returns {} (never raises, no partial/guessed values) for whatever it
    can't confidently read - callers keep the tenant/race ID fields
    manually editable as a fallback."""
    if not url:
        return {}
    url = url.strip()
    parsed = urlparse(url)
    query_string = parsed.query
    if not query_string and "?" in parsed.fragment:
        query_string = parsed.fragment.split("?", 1)[1]
    params = parse_qs(query_string)

    result = {}
    for key in ("raceId", "c", "race"):
        if params.get(key):
            result["race_id"] = params[key][0]
            break

    if params.get("e"):
        result["tenant"] = params["e"][0]
    else:
        subdomain_match = re.match(r"([a-z0-9-]+)\.v3\.livetrail\.net", parsed.netloc, re.I)
        year_match = re.search(r"(20\d{2})", url)
        if subdomain_match and year_match:
            result["tenant"] = f"{subdomain_match.group(1)}_{year_match.group(1)}"

    return result


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


def build_runner_analysis_bundle(race_df, race_segments_df, df_runner, total_km, total_gain):
    """Computes every index/table/chart the 'Runner Metrics (LiveTrail)'
    tab shows for one runner - no Streamlit calls, so the single-runner
    tab (which renders each piece with its own markdown/metric/chart
    widgets) and a bulk fetch (which only needs the finished figures/
    tables to build a downloadable report, with nothing rendered on
    screen) can share this one computation instead of two copies
    drifting apart over time.

    Raises whatever calculate_runner_indices/calculate_indices_by_segment
    raise - callers wrap this in their own try/except to match their
    existing error handling.

    Returns a dict:
      indices, df_crossed, df_segment_degradation (VPI/DMI/ER Index
      columns + Effort Pace merged in, same shape the individual tab
      already displays), df_summary, and figures - a dict of the 4
      go.Figure objects keyed exactly as build_full_runner_report_html
      expects for its own 'figures' param."""
    indices, df_crossed = calculate_runner_indices(race_df, race_segments_df, df_runner, total_km, total_gain)
    df_segment_degradation = calculate_indices_by_segment(race_df, race_segments_df, df_runner)

    fig_vpi = go.Figure()
    add_elevation_background(fig_vpi, race_df)
    fig_vpi.add_trace(go.Scatter(
        x=df_segment_degradation["End Km"], y=df_segment_degradation["VPI Raw (m/h)"],
        mode="lines+markers", name="VPI (m/h)", line=dict(color="#22d3ee", width=3),
        text=df_segment_degradation["Segment"],
        hovertemplate="%{text}<br>Km %{x:.0f}<br>VPI: %{y:.0f} m/h<extra></extra>",
    ))
    vpi_flagged = df_segment_degradation[df_segment_degradation["VPI Reliable"] == False]  # noqa: E712 (pandas bool mask, not Python bool)
    if not vpi_flagged.empty:
        fig_vpi.add_trace(go.Scatter(
            x=vpi_flagged["End Km"], y=vpi_flagged["VPI Raw (m/h)"],
            mode="markers", name="Approximate (irregular terrain)",
            marker=dict(color="#f85149", size=13, symbol="diamond", line=dict(width=2, color="#0d1117")),
            text=vpi_flagged["Segment"],
            hovertemplate=(
                "%{text}<br>Km %{x:.0f}<br>VPI: %{y:.0f} m/h"
                "<br>⚠ Approximate value — short/irregular terrain within this checkpoint segment"
                "<extra></extra>"
            ),
        ))
    fig_vpi.update_layout(
        template="plotly_dark", xaxis_title="Accumulated Km", yaxis_title="VPI (m/h)",
        height=380, hovermode="x unified",
    )

    fig_dmi = go.Figure()
    add_elevation_background(fig_dmi, race_df)
    fig_dmi.add_trace(go.Scatter(
        x=df_segment_degradation["End Km"], y=df_segment_degradation["DMI Raw (km/h)"],
        mode="lines+markers", name="DMI (km/h)", line=dict(color="#ffa500", width=3),
        text=df_segment_degradation["Segment"],
        hovertemplate="%{text}<br>Km %{x:.0f}<br>DMI: %{y:.2f} km/h<extra></extra>",
    ))
    dmi_flagged = df_segment_degradation[df_segment_degradation["DMI Reliable"] == False]  # noqa: E712
    if not dmi_flagged.empty:
        fig_dmi.add_trace(go.Scatter(
            x=dmi_flagged["End Km"], y=dmi_flagged["DMI Raw (km/h)"],
            mode="markers", name="Approximate (irregular terrain)",
            marker=dict(color="#f85149", size=13, symbol="diamond", line=dict(width=2, color="#0d1117")),
            text=dmi_flagged["Segment"],
            hovertemplate=(
                "%{text}<br>Km %{x:.0f}<br>DMI: %{y:.2f} km/h"
                "<br>⚠ Approximate value — short/irregular terrain within this checkpoint segment"
                "<extra></extra>"
            ),
        ))
    fig_dmi.update_layout(
        template="plotly_dark", xaxis_title="Accumulated Km", yaxis_title="DMI (km/h)",
        height=380, hovermode="x unified",
    )

    fig_er = go.Figure()
    add_elevation_background(fig_er, race_df)
    fig_er.add_trace(go.Scatter(
        x=df_crossed["End Km"], y=df_crossed["Effort Pace (min/effort-km)"],
        mode="lines+markers", name="Effort Pace", line=dict(color="#c084fc", width=3),
        hovertemplate="Km %{x:.0f}<br>%{y:.2f} min/effort-km<extra></extra>",
    ))
    if indices.get("half_effort_km") is not None:
        reaches_half_effort = df_crossed["Effort Km Accumulated"] >= indices["half_effort_km"]
        if reaches_half_effort.any():
            effort_midpoint_km_display = df_crossed.loc[reaches_half_effort, "End Km"].iloc[0]
        else:
            effort_midpoint_km_display = total_km / 2
        fig_er.add_vline(
            x=effort_midpoint_km_display, line_dash="dash", line_color="#a78bfa",
            annotation_text="50% effort", annotation_position="top",
        )
    fig_er.update_layout(
        template="plotly_dark", xaxis_title="Accumulated Km", yaxis_title="Effort Pace (min/effort-km)",
        height=380, hovermode="x unified",
    )

    df_segment_degradation = df_segment_degradation.merge(
        df_crossed[["Start Km", "End Km", "Effort Pace (min/effort-km)"]],
        on=["Start Km", "End Km"], how="left",
    )
    valid_pace = df_segment_degradation["Effort Pace (min/effort-km)"].dropna()
    if not valid_pace.empty and valid_pace.iloc[0]:
        pace_baseline = valid_pace.iloc[0]
        df_segment_degradation["ER Index (0-100)"] = (
            (pace_baseline / df_segment_degradation["Effort Pace (min/effort-km)"]) * 100
        ).round(1)
    else:
        df_segment_degradation["ER Index (0-100)"] = None

    fig_degradation = go.Figure()
    add_elevation_background(fig_degradation, race_df)
    fig_degradation.add_trace(go.Scatter(
        x=df_segment_degradation["End Km"], y=df_segment_degradation["VPI Index (0-100)"],
        mode="lines+markers", name="VPI (Climbing)", line=dict(color="#22d3ee", width=3),
        text=df_segment_degradation["Segment"],
        hovertemplate="%{text}<br>Km %{x:.0f}<br>VPI Index: %{y:.1f}<extra></extra>",
    ))
    fig_degradation.add_trace(go.Scatter(
        x=df_segment_degradation["End Km"], y=df_segment_degradation["DMI Index (0-100)"],
        mode="lines+markers", name="DMI (Descent)", line=dict(color="#ffa500", width=3),
        text=df_segment_degradation["Segment"],
        hovertemplate="%{text}<br>Km %{x:.0f}<br>DMI Index: %{y:.1f}<extra></extra>",
    ))
    fig_degradation.add_trace(go.Scatter(
        x=df_segment_degradation["End Km"], y=df_segment_degradation["ER Index (0-100)"],
        mode="lines+markers", name="ER (Endurance)", line=dict(color="#c084fc", width=3),
        text=df_segment_degradation["Segment"],
        hovertemplate="%{text}<br>Km %{x:.0f}<br>ER Index: %{y:.1f}<extra></extra>",
    ))
    fig_degradation.update_layout(
        template="plotly_dark", xaxis_title="Accumulated Km",
        yaxis_title="Index (0-100, Segment 1 = 100)", height=420, hovermode="x unified",
    )

    df_summary = build_summary_table(race_segments_df, df_segment_degradation, df_runner)

    return {
        "indices": indices,
        "df_crossed": df_crossed,
        "df_segment_degradation": df_segment_degradation,
        "df_summary": df_summary,
        "figures": {
            "🧗 VPI - Vertical Power Index": fig_vpi,
            "📉 DMI - Descent Mastery Index": fig_dmi,
            "🏆 ER - Endurance Rating - Pacing Curve": fig_er,
            "📉 Degradation Curve by Segment": fig_degradation,
        },
    }


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
ENGINE_ROOT = Path(__file__).parent
PUBLISH_CONFIG_PATH = ENGINE_ROOT / ".local_publish_config.json"
PUBLISH_KEEP_ENTRIES = {".git", "Backup from Blogger", "README.md"}


def _load_publish_config() -> dict:
    if PUBLISH_CONFIG_PATH.exists():
        try:
            return json.loads(PUBLISH_CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_publish_config(cfg: dict) -> None:
    PUBLISH_CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def _github_token() -> str | None:
    """Reads an optional GitHub Personal Access Token from Streamlit
    secrets (Settings > Secrets in the Streamlit Cloud dashboard, key
    GITHUB_TOKEN). Returns None (never raises) when no secrets file
    exists at all - true on a Codespace, which doesn't need this since
    it already has push-capable git credentials ambient in the
    container. Only a fresh container with no such ambient credentials
    (Streamlit Cloud, a brand new VPS) needs this configured."""
    try:
        return st.secrets.get("GITHUB_TOKEN")
    except Exception:
        return None


def _authed_github_url(owner_repo: str) -> str:
    """https://github.com/<owner_repo>.git, with the token from secrets
    embedded for auth if one's configured; otherwise the plain URL,
    relying on whatever ambient git credentials the environment has."""
    token = _github_token()
    if token:
        return f"https://{token}@github.com/{owner_repo}.git"
    return f"https://github.com/{owner_repo}.git"


def _redact_token(text: str) -> str:
    """Strips a configured GitHub token out of git command output
    before it's ever written into a log shown in the UI (st.code) -
    git error messages routinely echo back the remote URL, which would
    otherwise leak the token straight into the page."""
    token = _github_token()
    if token and text:
        return text.replace(token, "***")
    return text


# A full site push (~1600 files) can legitimately take a couple of
# minutes with no progress feedback in between - generous on purpose, so
# this is a safety net against a genuine hang (bad/expired credentials,
# a stalled connection), not a performance limit on a real slow-but-
# working push.
GIT_SUBPROCESS_TIMEOUT_S = 300


def _git_env() -> dict:
    """GIT_TERMINAL_PROMPT=0 makes git fail immediately ('terminal
    prompts disabled') instead of blocking forever on a username/password
    prompt that can never be answered in this headless context - the
    failure mode when GITHUB_TOKEN isn't configured (or has expired) and
    the fallback plain HTTPS remote needs credentials nobody can type."""
    return {**os.environ, "GIT_TERMINAL_PROMPT": "0"}


def _run_git(repo_dir: Path, *args: str) -> subprocess.CompletedProcess:
    # -c user.name/user.email override (not depend on) any global git
    # config, so auto-commits from the Publish button work the same on
    # a fresh container (Streamlit Cloud, a new Codespace, a VPS...)
    # that's never had `git config --global` run on it, without needing
    # a terminal there to set that up by hand.
    config_args = ["-c", "user.name=VertLabs Engine", "-c", "user.email=engine@vertlabs.run"]
    try:
        r = subprocess.run(
            ["git", *config_args, *args], cwd=str(repo_dir), capture_output=True, text=True,
            timeout=GIT_SUBPROCESS_TIMEOUT_S, env=_git_env(),
        )
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(
            args=["git", *args], returncode=1, stdout="",
            stderr=(
                f"git {' '.join(args)} no respondió en {GIT_SUBPROCESS_TIMEOUT_S}s - "
                "probablemente credenciales (GITHUB_TOKEN) faltantes/vencidas o un problema de red. "
                "Se abortó en vez de quedar colgado indefinidamente."
            ),
        )
    r.stdout = _redact_token(r.stdout)
    r.stderr = _redact_token(r.stderr)
    return r


def _configure_git_push_auth(repo_dir: Path, owner_repo: str) -> None:
    """Points 'origin' at an authenticated URL if a GITHUB_TOKEN secret
    is configured, so the next push doesn't need to prompt for
    credentials. A no-op when no token is set (nothing to change; the
    environment's ambient git credentials, if any, keep being used as
    before)."""
    token = _github_token()
    if not token:
        return
    _run_git(repo_dir, "remote", "set-url", "origin", _authed_github_url(owner_repo))


def _sync_output_to_web_repo(web_repo_dir: Path) -> None:
    """Mirrors Vert_engine/output/ into the vertlabs-web checkout.

    Copies/overwrites the fresh content FIRST and only removes stale
    leftovers afterward (instead of wiping everything up front) - if this
    gets interrupted partway (Codespace hang, closed browser tab), the
    working tree still ends up with old+new content mixed rather than
    half-deleted with nothing to replace it."""
    output_dir = ENGINE_ROOT / "output"
    output_entries = {e.name for e in output_dir.iterdir()}

    for entry in output_dir.iterdir():
        dest = web_repo_dir / entry.name
        if dest.exists():
            if dest.is_dir():
                shutil.rmtree(dest)
            else:
                dest.unlink()
        if entry.is_dir():
            shutil.copytree(entry, dest)
        else:
            shutil.copy2(entry, dest)

    for entry in web_repo_dir.iterdir():
        if entry.name in PUBLISH_KEEP_ENTRIES or entry.name in output_entries:
            continue
        if entry.is_dir():
            shutil.rmtree(entry)
        else:
            entry.unlink()


def _backup_engine_data() -> tuple[bool, str]:
    """Commits+pushes Vert_engine's own data/ to GitHub. Runs before the
    site is even built, so a Codespace dying or hanging right after this
    never loses race/athlete data again - only ever the site rebuild,
    which is a 2-minute redo, not a from-scratch data re-entry."""
    r = _run_git(ENGINE_ROOT, "add", "data/")
    log = r.stdout + r.stderr
    r = _run_git(ENGINE_ROOT, "diff", "--cached", "--quiet")
    if r.returncode == 0:
        return True, log + "Sin cambios en data/ - nada para respaldar.\n"
    r = _run_git(ENGINE_ROOT, "commit", "-m", "Backup de datos desde el botón Publicar")
    log += r.stdout + r.stderr
    if r.returncode != 0:
        return False, "Falló el respaldo de data/ (commit):\n" + log

    r = _run_git(ENGINE_ROOT, "rev-parse", "--abbrev-ref", "HEAD")
    current_branch = r.stdout.strip() or "HEAD"
    _configure_git_push_auth(ENGINE_ROOT, "pablojali/Vert_engine")
    r = _run_git(ENGINE_ROOT, "push", "-u", "origin", current_branch)
    log += r.stdout + r.stderr
    if r.returncode != 0:
        return False, "Falló el respaldo de data/ (push):\n" + log
    return True, log


def _ensure_web_repo(web_repo_dir: Path) -> tuple[bool, str]:
    """Clones vertlabs-web into web_repo_dir if it isn't there yet.

    A hand-set-up Codespace usually has both repos cloned side by side
    already, but a fresh container (Streamlit Cloud, a brand new
    Codespace, a VPS) only has Vert_engine - vertlabs-web simply doesn't
    exist on disk there until something clones it. Does that once,
    automatically, instead of failing with 'not a valid repo'."""
    if web_repo_dir.is_dir() and (web_repo_dir / ".git").is_dir():
        return True, ""
    web_repo_dir.parent.mkdir(parents=True, exist_ok=True)
    try:
        r = subprocess.run(
            ["git", "clone", _authed_github_url("pablojali/vertlabs-web"), str(web_repo_dir)],
            capture_output=True, text=True, timeout=GIT_SUBPROCESS_TIMEOUT_S, env=_git_env(),
        )
    except subprocess.TimeoutExpired:
        return False, (
            f"git clone no respondió en {GIT_SUBPROCESS_TIMEOUT_S}s - "
            "probablemente credenciales (GITHUB_TOKEN) faltantes/vencidas o un problema de red."
        )
    return r.returncode == 0, _redact_token(r.stdout) + _redact_token(r.stderr)


class _TeeStdout:
    """Stand-in for io.StringIO() as a redirect_stdout() target: buffers
    everything written (same full-log behavior as before), and also
    calls on_line(line) for each complete line - used to stream
    publish.py's own section-header prints live to a st.status() while
    it's running, instead of only ever seeing them in the log after the
    (possibly slow) call already returned."""
    def __init__(self, on_line):
        self._buf = io.StringIO()
        self._on_line = on_line
        self._partial = ""

    def write(self, s: str) -> int:
        self._buf.write(s)
        self._partial += s
        while "\n" in self._partial:
            line, self._partial = self._partial.split("\n", 1)
            if line.strip():
                self._on_line(line.strip())
        return len(s)

    def flush(self) -> None:
        pass

    def getvalue(self) -> str:
        return self._buf.getvalue()


def _publish_to_branch(web_repo_dir: Path, branch: str, commit_message: str, status=None) -> tuple[bool, str]:
    """Backs up data/ first, then builds the site (equivalent to
    `python publish.py`), mirrors output/ into the vertlabs-web checkout,
    and pushes it to the given branch. Returns (ok, log) - never raises,
    so the caller can show the failure in the UI instead of crashing the
    Streamlit app.

    status: an optional st.status() context (or anything with a
    .write(str) method) - when given, each real step writes a line to it
    as it happens, so a slow publish (a full site push is ~1600 files)
    shows live progress instead of one static spinner for several
    minutes straight, which reads as a hang even when it's working."""
    def _step(msg: str) -> None:
        if status is not None:
            status.write(msg)

    _step("📦 Respaldando `data/`...")
    backup_ok, backup_log = _backup_engine_data()
    log_lines = [f"--- Respaldo de data/ ---\n{backup_log}"]
    if not backup_ok:
        return False, "\n".join(log_lines)

    _step("🏗️ Generando el sitio (HTML/CSS/JS desde `data/`)...")
    try:
        import publish as publish_module
        # publish.py already prints its own section headers ("1/8 Cargando
        # posts...", etc., once per locale) - previously these were only
        # ever seen in the collapsed "Ver detalle" log AFTER the whole
        # (possibly slow) call returned. Tee just those header lines live
        # to status, so a slow generation shows WHICH of the 8 steps it's
        # stuck on instead of one opaque "Generando el sitio..." for
        # however many minutes. Skips the much chattier per-page "  ✓ ..."
        # lines (hundreds/thousands of those at real scale) - still
        # captured in the full log below, just not streamed one by one.
        header_prefixes = ("===",) + tuple(f"{n}/8" for n in range(1, 9))
        tee = _TeeStdout(on_line=lambda line: _step(f"　{line}") if line.startswith(header_prefixes) else None)
        with redirect_stdout(tee):
            publish_module.main()
        log_lines.append(tee.getvalue())
    except Exception:
        return False, "Falló la generación del sitio (publish.py):\n" + traceback.format_exc()

    _step("📂 Preparando el checkout local de `vertlabs-web`...")
    clone_ok, clone_log = _ensure_web_repo(web_repo_dir)
    if clone_log:
        log_lines.append(f"--- Clonando vertlabs-web ---\n{clone_log}")
    if not clone_ok:
        return False, "No se pudo clonar vertlabs-web:\n" + "\n".join(log_lines)

    _step("🔄 Copiando el sitio generado al checkout...")
    _sync_output_to_web_repo(web_repo_dir)

    _step(f"🌿 Cambiando a la rama '{branch}'...")
    r = _run_git(web_repo_dir, "fetch", "origin", branch)
    log_lines.append(r.stdout + r.stderr)
    r = _run_git(web_repo_dir, "checkout", "-B", branch, f"origin/{branch}")
    if r.returncode != 0:
        r = _run_git(web_repo_dir, "checkout", "-B", branch)
    log_lines.append(r.stdout + r.stderr)

    r = _run_git(web_repo_dir, "add", "-A")
    log_lines.append(r.stdout + r.stderr)

    r = _run_git(web_repo_dir, "diff", "--cached", "--quiet")
    if r.returncode == 0:
        log_lines.append("Sin cambios respecto al último publish - nada para commitear.")
    else:
        _step("📝 Armando el commit...")
        r = _run_git(web_repo_dir, "commit", "-m", commit_message)
        log_lines.append(r.stdout + r.stderr)
        if r.returncode != 0:
            return False, "Falló el commit:\n" + "\n".join(log_lines)

    # Push unconditionally - even with no new commit, the branch might not
    # exist on origin yet (first publish to it), and Cloudflare Pages only
    # picks up branches it can see on the remote.
    _step("☁️ Subiendo a GitHub (un push grande puede tardar varios minutos)...")
    _configure_git_push_auth(web_repo_dir, "pablojali/vertlabs-web")
    r = _run_git(web_repo_dir, "push", "-u", "origin", branch)
    log_lines.append(r.stdout + r.stderr)
    if r.returncode != 0:
        return False, "Falló el push:\n" + "\n".join(log_lines)

    _step("✅ Listo.")
    return True, "\n".join(log_lines)


with st.sidebar:
    st.markdown("## 🚀 Publicar sitio")
    st.caption(
        "Genera el sitio (como `python publish.py`) y lo sube a `vertlabs-web`. "
        "Disponible desde cualquier pestaña."
    )

    _publish_cfg = _load_publish_config()
    _default_web_dir = _publish_cfg.get("vertlabs_web_dir") or str(ENGINE_ROOT.parent / "vertlabs-web")
    web_repo_dir_str = st.text_input(
        "Carpeta local de vertlabs-web", value=_default_web_dir, key="publish_web_repo_dir",
        help="La carpeta donde tenés clonado el repo vertlabs-web en esta máquina.",
    )

    st.markdown("#### Vista previa (staging)")
    st.caption("Cloudflare Pages genera una URL de preview para la rama 'staging' automáticamente.")
    if st.button("📤 Publicar a Staging", use_container_width=True, key="publish_staging_btn"):
        _save_publish_config({"vertlabs_web_dir": web_repo_dir_str})
        with st.status("Publicando a 'staging'...", expanded=True) as status:
            ok, log = _publish_to_branch(
                Path(web_repo_dir_str).expanduser(), "staging", "Publish desde el Engine (staging)",
                status=status,
            )
            status.update(
                label="✅ Publicado en 'staging'." if ok else "❌ Falló la publicación a staging.",
                state="complete" if ok else "error",
            )
        with st.expander("Ver detalle"):
            st.code(log or "(sin salida)")

    st.markdown("#### Producción")
    confirm_prod = st.checkbox("Confirmo publicar en PRODUCCIÓN (vertlabs.run)", key="publish_confirm_prod")
    if st.button(
        "✅ Promover a Producción", use_container_width=True, disabled=not confirm_prod, key="publish_prod_btn"
    ):
        _save_publish_config({"vertlabs_web_dir": web_repo_dir_str})
        with st.status("Publicando a producción...", expanded=True) as status:
            ok, log = _publish_to_branch(
                Path(web_repo_dir_str).expanduser(), "main", "Publish desde el Engine (producción)",
                status=status,
            )
            status.update(
                label="✅ Publicado en 'main'." if ok else "❌ Falló la publicación a producción.",
                state="complete" if ok else "error",
            )
        with st.expander("Ver detalle"):
            st.code(log or "(sin salida)")


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


def _find_existing_image(dir_path: Path, base_name: str):
    """Same idea as _find_existing_portrait, generalized to any base_name
    (used for the event icon, which lives one level up from a distance -
    e.g. data/races/val-d-aran-by-utmb/2026/images/icon.jpg, shared by
    every distance under that event)."""
    for ext in (".jpg", ".jpeg", ".png"):
        candidate = dir_path / f"{base_name}{ext}"
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


def _parse_gender_from_category(category):
    """LiveTrail's category code ends in an age-group + gender suffix
    (French convention, confirmed against real data for this project:
    'SE H' = Senior Homme, 'SE F' = Senior Femme). Only trusts that exact
    confirmed suffix ('H'/'F' as the last whitespace-separated token) -
    anything else (different race software, unexpected format) is left
    as unknown rather than guessed."""
    if not category:
        return None
    tokens = str(category).strip().split()
    if not tokens:
        return None
    last = tokens[-1].upper()
    if last == "H":
        return "M"
    if last == "F":
        return "F"
    return None


def _web_export_track_result(race_key, runner_info, indices, report_html=None):
    """Records one runner's already-computed VPI/DMI/ER for a given race
    into st.session_state['web_export_pool'], so the 'Exportar a Web' tab
    can pick it up later. Called right after the existing tabs finish
    calculating indices - wrapped so a bookkeeping error here can never
    break the analysis tab itself.

    report_html is optional - when the caller already built the runner's
    Full Analysis Report HTML (build_full_runner_report_html's output,
    the same string the per-runner download button hands out), it's
    stashed here as a plain string so 'Exportar a Web' can just write it
    to disk at export time - no manual download/re-upload needed, and no
    need to carry heavy DataFrame/Figure objects through session_state to
    regenerate it later."""
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
        gender_rank = runner_info.get("Gender Rank")
        try:
            gender_rank = int(gender_rank)
        except (TypeError, ValueError):
            pass
        runners[runner_key] = {
            "name": name,
            "bib": bib,
            "finish_time": runner_info.get("Finish Time"),
            "position": position,
            "gender_rank": gender_rank,
            "vpi": indices.get("VPI"),
            "dmi": indices.get("DMI"),
            "er": indices.get("ER"),
            "pace_first_half": indices.get("effort_pace_first_half"),
            "pace_second_half": indices.get("effort_pace_second_half"),
            "country": runner_info.get("Country"),
            "gender": _parse_gender_from_category(runner_info.get("Category")),
            "picture_url": runner_info.get("Picture URL"),
            "_report_html": report_html,
        }
    except Exception:
        pass


# ---------------------------------------------
# Shared block-editor engine, used by both the race Analysis Editor and
# the Posts editor: an ordered list of content blocks (text/html/image/
# top10), addable/reorderable/deletable, backed by st.session_state.
# Kept generic (order_key + key_prefix passed in) so the two editors don't
# collide and don't duplicate this ~90-line widget dance.
# ---------------------------------------------
BLOCK_TYPE_LABELS = {"text": "📝 Texto", "html": "🧩 HTML", "image": "🖼️ Imagen", "top10": "🏆 Top 10"}


def _init_block_order(order_key: str, loaded_blocks: list[dict]) -> None:
    if order_key in st.session_state:
        return
    order = []
    for b in loaded_blocks:
        bid = str(uuid.uuid4())
        order.append((bid, b["type"]))
        st.session_state[f"block_initial_{bid}"] = b
    st.session_state[order_key] = order


def _render_block_editor_ui(order_key: str, key_prefix: str, images_dir: Path, athlete_options: dict) -> None:
    order = st.session_state[order_key]
    athlete_names_by_slug = {v: k for k, v in athlete_options.items() if v}

    if not order:
        st.caption("Todavía no hay bloques. Agregá el primero abajo.")

    for idx, (bid, btype) in enumerate(order):
        initial = st.session_state.get(f"block_initial_{bid}", {})
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([6, 1, 1, 1])
            c1.markdown(f"**{idx + 1}. {BLOCK_TYPE_LABELS.get(btype, btype)}**")
            if c2.button("↑", key=f"{key_prefix}_up_{bid}", disabled=(idx == 0), help="Subir"):
                order[idx - 1], order[idx] = order[idx], order[idx - 1]
                st.session_state[order_key] = order
                st.rerun()
            if c3.button("↓", key=f"{key_prefix}_down_{bid}", disabled=(idx == len(order) - 1), help="Bajar"):
                order[idx + 1], order[idx] = order[idx], order[idx + 1]
                st.session_state[order_key] = order
                st.rerun()
            if c4.button("🗑️", key=f"{key_prefix}_del_{bid}", help="Borrar bloque"):
                order.pop(idx)
                st.session_state[order_key] = order
                st.rerun()

            if btype == "text":
                st.text_input(
                    "Título (opcional)", value=initial.get("title", ""), key=f"{key_prefix}_text_title_{bid}",
                    placeholder="Título (opcional) — ej. 'Performance by athlete'",
                )
                st.text_area(
                    "Texto (dejá una línea en blanco entre párrafos)",
                    value=initial.get("content", ""), height=150, key=f"{key_prefix}_text_{bid}",
                    label_visibility="collapsed",
                )
            elif btype == "html":
                st.text_area(
                    "HTML / gráfico embebido (ej. el fragmento de 'Download chart as HTML')",
                    value=initial.get("content", ""), height=200, key=f"{key_prefix}_html_{bid}",
                    label_visibility="collapsed",
                )
            elif btype == "image":
                existing_src = initial.get("src")
                if existing_src:
                    local_path = images_dir / Path(existing_src).name
                    if local_path.exists():
                        st.image(str(local_path), caption="Imagen actual", width=240)
                st.file_uploader(
                    "Reemplazar imagen (opcional si ya hay una)",
                    type=["jpg", "jpeg", "png"], key=f"{key_prefix}_image_upload_{bid}",
                )
                st.text_input(
                    "Pie de foto (opcional)", value=initial.get("caption", ""), key=f"{key_prefix}_image_caption_{bid}"
                )
            elif btype == "top10":
                st.text_input(
                    "Título del bloque", value=initial.get("title", "Top 10"), key=f"{key_prefix}_top10_title_{bid}"
                )
                saved_slugs = initial.get("slugs", [])
                cols = st.columns(2)
                for i in range(10):
                    saved_slug = saved_slugs[i] if i < len(saved_slugs) else None
                    default_name = athlete_names_by_slug.get(saved_slug, "— (vacío) —")
                    options = list(athlete_options.keys())
                    default_index = options.index(default_name) if default_name in options else 0
                    cols[i % 2].selectbox(
                        f"Puesto {i + 1}", options, index=default_index, key=f"{key_prefix}_top10_pos_{bid}_{i}",
                    )

    st.markdown("---")
    add_col1, add_col2 = st.columns([3, 1])
    new_block_label = add_col1.selectbox(
        "Tipo de bloque a agregar", list(BLOCK_TYPE_LABELS.values()),
        key=f"{key_prefix}_new_block_type", label_visibility="collapsed",
    )
    if add_col2.button("➕ Agregar bloque", use_container_width=True, key=f"{key_prefix}_add_block_btn"):
        new_type = {v: k for k, v in BLOCK_TYPE_LABELS.items()}[new_block_label]
        new_id = str(uuid.uuid4())
        order.append((new_id, new_type))
        st.session_state[f"block_initial_{new_id}"] = {}
        st.session_state[order_key] = order
        st.rerun()


def _collect_blocks_from_state(
    order_key: str, key_prefix: str, images_dir: Path, images_url_prefix: str, athlete_options: dict
) -> list[dict]:
    order = st.session_state[order_key]
    blocks = []
    for bid, btype in order:
        if btype == "text":
            blocks.append({
                "type": "text",
                "title": st.session_state.get(f"{key_prefix}_text_title_{bid}", ""),
                "content": st.session_state.get(f"{key_prefix}_text_{bid}", ""),
            })
        elif btype == "html":
            blocks.append({"type": "html", "content": st.session_state.get(f"{key_prefix}_html_{bid}", "")})
        elif btype == "image":
            initial = st.session_state.get(f"block_initial_{bid}", {})
            src = initial.get("src")
            upload = st.session_state.get(f"{key_prefix}_image_upload_{bid}")
            if upload is not None:
                images_dir.mkdir(parents=True, exist_ok=True)
                ext = Path(upload.name).suffix.lower() or ".jpg"
                fname = f"{bid}{ext}"
                (images_dir / fname).write_bytes(upload.getvalue())
                src = f"{images_url_prefix}/{fname}"
            blocks.append({
                "type": "image", "src": src,
                "caption": st.session_state.get(f"{key_prefix}_image_caption_{bid}", ""),
            })
        elif btype == "top10":
            slugs = []
            for i in range(10):
                picked_name = st.session_state.get(f"{key_prefix}_top10_pos_{bid}_{i}")
                slug = athlete_options.get(picked_name)
                if slug:
                    slugs.append(slug)
            blocks.append({
                "type": "top10",
                "title": st.session_state.get(f"{key_prefix}_top10_title_{bid}", "Top 10"),
                "slugs": slugs,
            })
    return blocks


tab_race, tab_runner_lt, tab_gpx, tab_comparison, tab_top, tab_engine_live, tab_checkpoints, tab_web_export, tab_posts = st.tabs(
    ["🗺️ Race Analysis", "🏃 Runner Metrics (LiveTrail)", "🛰️ GPX Metrics",
     "⚖️ UTMB vs GPX", "🏆 Top Runners", "📡 Engine Live", "🧩 Checkpoint Fetcher",
     "🌐 Exportar a Web", "📰 Posts"]
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

    # --- Fetch happens only on the button click, but the result is stashed
    # in session_state and rendered below unconditionally - a download
    # button always triggers a Streamlit rerun, and if the fetched data only
    # existed inside "if load_button_lt:" it would vanish on that rerun
    # (since the button no longer reads as clicked), forcing a re-fetch. ---
    if load_button_lt:
        if not runner_url_lt:
            st.session_state['lt_fetch_warning'] = "Paste a valid link before clicking the button."
        else:
            st.session_state['lt_fetch_warning'] = None
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
                st.session_state['lt_fetch_error'] = error_detail_lt
                st.session_state['runner_metrics_df_lt'] = None
            elif df_runner_lt is None or df_runner_lt.empty:
                st.session_state['lt_fetch_error'] = "empty"
                st.session_state['runner_metrics_df_lt'] = None
            else:
                st.session_state['lt_fetch_error'] = None
                st.session_state['runner_metrics_df_lt'] = df_runner_lt
                st.session_state['runner_info_lt'] = runner_info_lt

    lt_fetch_warning = st.session_state.get('lt_fetch_warning')
    lt_fetch_error = st.session_state.get('lt_fetch_error')
    df_runner_lt = st.session_state.get('runner_metrics_df_lt')
    runner_info_lt = st.session_state.get('runner_info_lt')

    if lt_fetch_warning:
        st.warning(lt_fetch_warning)
    elif lt_fetch_error == "empty":
        st.warning(
            "⚠️ No data table was found at that link. "
            "Make sure it's the direct URL to the runner's profile, and that "
            "the race has finished passings recorded."
        )
    elif lt_fetch_error:
        st.error("❌ An error occurred while trying to fetch the runner data.")
        with st.expander("View technical error detail"):
            st.code(lt_fetch_error, language="python")
    elif df_runner_lt is not None:
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
                analysis_lt = build_runner_analysis_bundle(
                    current_race_data_lt["df"], race_segments_df_lt, df_runner_lt,
                    current_race_data_lt["total_km"], total_race_gain_lt,
                )
                indices_lt = analysis_lt["indices"]
                df_crossed_lt = analysis_lt["df_crossed"]
                df_segment_degradation_lt = analysis_lt["df_segment_degradation"]
                df_summary_lt = analysis_lt["df_summary"]
                figures_lt = analysis_lt["figures"]
                indices_error_lt = None
            except Exception as e:
                indices_lt, df_crossed_lt, df_segment_degradation_lt = None, None, None
                df_summary_lt, figures_lt = None, None
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
                try:
                    full_report_html_lt = build_full_runner_report_html(
                        runner_info=runner_info_lt,
                        df_runner=df_runner_lt,
                        indices=indices_lt,
                        figures=figures_lt,
                        df_segment_degradation=df_segment_degradation_lt,
                        df_summary=df_summary_lt,
                    )
                except Exception:
                    # A report-generation hiccup shouldn't hide the indices/
                    # charts below, which already computed fine.
                    full_report_html_lt = None
                _web_export_track_result(
                    selected_race_lt, runner_info_lt, indices_lt, report_html=full_report_html_lt,
                )

                fig_vpi_lt = figures_lt["🧗 VPI - Vertical Power Index"]
                fig_dmi_lt = figures_lt["📉 DMI - Descent Mastery Index"]
                fig_er_lt = figures_lt["🏆 ER - Endurance Rating - Pacing Curve"]
                fig_degradation_lt = figures_lt["📉 Degradation Curve by Segment"]

                # --- VPI chart ---
                st.markdown("---")
                st.markdown("### 🧗 VPI - Vertical Power Index")
                st.metric(
                    "VPI (whole race)",
                    f"{indices_lt['VPI']} m/h" if indices_lt["VPI"] is not None else "N/A",
                    help="Vertical Power Index: meters of elevation gain per hour on segments with slope ≥12%.",
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
                st.plotly_chart(fig_er_lt, use_container_width=True)
                chart_download_button(fig_er_lt, "er_pacing_curve_livetrail.html", "dl_er_lt")

                # --- Degradation matrix by segment ---
                st.markdown("---")
                st.markdown("### 📉 Degradation Curve by Segment")
                st.dataframe(df_segment_degradation_lt, use_container_width=True)
                st.plotly_chart(fig_degradation_lt, use_container_width=True)
                chart_download_button(fig_degradation_lt, "degradation_curve_livetrail.html", "dl_degradation_lt")

                # --- Full summary table ---
                st.markdown("---")
                st.markdown("### 📋 Full Summary Table")
                st.dataframe(df_summary_lt, use_container_width=True, hide_index=True)

                # --- Full analysis report (already built above, right after
                # the export-pool bookkeeping, so it doubles as this download
                # and as the auto-attached report 'Exportar a Web' picks up) ---
                st.markdown("---")
                st.markdown("### 📄 Full Analysis Report")
                if full_report_html_lt is None:
                    st.warning("⚠️ No se pudo generar el informe completo para este corredor.")
                else:
                    st.download_button(
                        "📄 Download Full Analysis (HTML for Blogger)",
                        data=full_report_html_lt,
                        file_name=f"{_ascii_filename(runner_info_lt.get('Name') or 'runner').replace(' ', '_')}_livetrail_full_analysis.html",
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

    # --- Computed only on the button click, but stashed in session_state and
    # rendered below unconditionally - a chart download button always
    # triggers a Streamlit rerun, and results kept only inside
    # "if calculate_gpx_button:" would vanish on that rerun, forcing the GPX
    # to be recalculated (or re-uploaded) from scratch. ---
    if calculate_gpx_button:
        if personal_gpx_file is None:
            st.session_state['gpx_warning'] = "Upload a personal GPX file first."
        elif not selected_race_gpx:
            st.session_state['gpx_warning'] = "Select a race above first."
        else:
            st.session_state['gpx_warning'] = None
            current_race_data_gpx = available_races_gpx[selected_race_gpx]
            race_segments_df_gpx = current_race_data_gpx.get("df_segments")

            if race_segments_df_gpx is None or race_segments_df_gpx.empty:
                st.session_state['gpx_warning'] = (
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
                        df_segment_gpx["VPI Index (0-100)"] = normalize_segment_index(df_segment_gpx["VPI Real (m/h)"])
                        df_segment_gpx["DMI Index (0-100)"] = normalize_segment_index(df_segment_gpx["DMI Real (km/h)"])
                        gpx_error = None
                    except Exception:
                        global_indices_gpx, df_segment_gpx = None, None
                        gpx_error = traceback.format_exc()

                if gpx_error:
                    st.session_state['gpx_error'] = gpx_error
                    st.session_state['real_global_indices'] = None
                else:
                    st.session_state['gpx_error'] = None
                    st.session_state['real_degradation_df'] = df_segment_gpx
                    st.session_state['real_metrics_race'] = selected_race_gpx
                    st.session_state['real_global_indices'] = global_indices_gpx

    gpx_warning = st.session_state.get('gpx_warning')
    gpx_error = st.session_state.get('gpx_error')
    global_indices_gpx = st.session_state.get('real_global_indices')
    df_segment_gpx = st.session_state.get('real_degradation_df')

    if gpx_warning:
        st.warning(gpx_warning)
    elif gpx_error:
        st.error("❌ Couldn't process this GPX.")
        with st.expander("View technical error detail"):
            st.code(gpx_error, language="python")
    elif global_indices_gpx is not None:
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

    def _top_parse_url():
        parsed = parse_livetrail_url(st.session_state.get("top_livetrail_url", ""))
        if parsed.get("tenant"):
            st.session_state["top_tenant_input"] = parsed["tenant"]
        if parsed.get("race_id"):
            st.session_state["top_race_id_input"] = parsed["race_id"]

    st.text_input(
        "LiveTrail link of any runner in this race (to identify tenant/race ID)",
        key="top_livetrail_url", on_change=_top_parse_url,
        placeholder="https://aranbyutmb.v3.livetrail.net/en/2026/runners/5?raceId=vda",
    )
    col_top_tenant, col_top_race_id = st.columns(2)
    with col_top_tenant:
        top_tenant = st.text_input("X-Tenant", key="top_tenant_input", help="Auto-filled from the link above.")
    with col_top_race_id:
        top_race_id = st.text_input("Race ID", key="top_race_id_input", help="Auto-filled from the link above.")

    bib_list_raw = st.text_area(
        "Bib numbers to fetch (one per line or comma-separated)",
        placeholder="5\n12\n8\n23\n...",
        key="top_bib_list",
    )
    fetch_top_button = st.button("🏆 Fetch all bibs", type="primary", use_container_width=True)

    MAX_BIBS_PER_FETCH = 200

    # --- Fetch happens only on the button click, but everything it produces
    # (results/reports/the race snapshot used) is stashed in session_state
    # and rendered below unconditionally. Every download button here
    # (per-runner report, Excel, 3 charts) triggers a Streamlit rerun, and
    # if the fetched bibs only existed inside "if fetch_top_button:" they'd
    # vanish on that rerun - forcing all bibs to be re-fetched from
    # scratch just to click a second download. ---
    if fetch_top_button:
        bibs = [b.strip() for b in re.split(r"[,\n]+", bib_list_raw) if b.strip()]

        if not selected_race_top:
            st.session_state['top_warning'] = "Select a race above first."
        elif not top_tenant or not top_race_id:
            st.session_state['top_warning'] = "Paste a LiveTrail link above first (or fill in X-Tenant/Race ID by hand)."
        elif not bibs:
            st.session_state['top_warning'] = "Enter at least one bib number."
        elif len(bibs) > MAX_BIBS_PER_FETCH:
            st.session_state['top_warning'] = (
                f"⚠️ That's {len(bibs)} bibs - narrow it down to {MAX_BIBS_PER_FETCH} or fewer per fetch "
                "(likely a typo, e.g. a year instead of a bib number)."
            )
        else:
            st.session_state['top_warning'] = None
            race_data_top = available_races_top[selected_race_top]
            race_segments_df_top = race_data_top.get("df_segments")

            if race_segments_df_top is None or race_segments_df_top.empty:
                st.session_state['top_warning'] = (
                    "⚠️ The selected race doesn't have checkpoints with km loaded yet. "
                    "Go back to the 'Race Analysis' tab and load them first."
                )
            else:
                total_race_gain_top = calculate_total_elevation_gain(race_data_top["df"])
                results = {}
                reports = {}
                errors = {}
                progress = st.progress(0.0, text="Fetching runners...")

                for i, bib in enumerate(bibs):
                    try:
                        runner_info_bib, df_runner_bib = fetch_runner_by_tenant_and_bib_livetrail(
                            top_tenant, bib, top_race_id
                        )
                        analysis_bib = build_runner_analysis_bundle(
                            race_data_top["df"], race_segments_df_top, df_runner_bib,
                            race_data_top["total_km"], total_race_gain_top,
                        )
                        label = f"{runner_info_bib.get('Name') or ('Bib ' + str(bib))} (Bib {bib})"
                        results[label] = analysis_bib["df_summary"]
                        try:
                            report_html_bib = build_full_runner_report_html(
                                runner_info=runner_info_bib,
                                df_runner=df_runner_bib,
                                indices=analysis_bib["indices"],
                                figures=analysis_bib["figures"],
                                df_segment_degradation=analysis_bib["df_segment_degradation"],
                                df_summary=analysis_bib["df_summary"],
                            )
                        except Exception:
                            # A report-generation hiccup for this one runner
                            # shouldn't sink their whole fetch - they still get
                            # their VPI/DMI/ER, just without an auto-attached
                            # report (same as before this existed).
                            report_html_bib = None
                        reports[label] = {
                            "runner_info": runner_info_bib,
                            "indices": analysis_bib["indices"],
                            "report_html": report_html_bib,
                        }
                        _web_export_track_result(
                            selected_race_top, runner_info_bib, analysis_bib["indices"],
                            report_html=report_html_bib,
                        )
                    except Exception:
                        errors[bib] = traceback.format_exc()
                    progress.progress((i + 1) / len(bibs), text=f"Fetching runners... ({i + 1}/{len(bibs)})")

                progress.empty()

                st.session_state['top_bibs_requested'] = len(bibs)
                st.session_state['top_errors'] = errors
                st.session_state['top_results'] = results or None
                st.session_state['top_reports'] = reports
                st.session_state['top_race_used'] = selected_race_top
                st.session_state['top_race_data_used'] = race_data_top

    top_warning = st.session_state.get('top_warning')
    top_errors = st.session_state.get('top_errors') or {}
    results = st.session_state.get('top_results')
    reports = st.session_state.get('top_reports') or {}
    top_bibs_requested = st.session_state.get('top_bibs_requested') or 0
    selected_race_top_used = st.session_state.get('top_race_used')
    race_data_top = st.session_state.get('top_race_data_used')

    if top_warning:
        st.warning(top_warning)
    else:
        if top_errors:
            with st.expander(f"⚠️ {len(top_errors)} bib(s) failed"):
                for bib, err in top_errors.items():
                    st.markdown(f"**Bib {bib}:**")
                    st.code(err, language="python")

        if results is None and top_errors:
            st.error("❌ Couldn't fetch any of the bibs entered.")
        elif results:
            race_segments_df_top = race_data_top.get("df_segments")
            st.success(
                f"✅ Fetched {len(results)} of {top_bibs_requested} runner(s), all loaded into the "
                "export pool - go straight to '🌐 Exportar a Web' to save them, no need to "
                "revisit them one by one."
            )

            # --- Quick copy/paste table: one row per runner, just the
            # global numbers (no per-checkpoint breakdown) - select the
            # cells and Ctrl+C straight into Excel, no download needed. ---
            st.markdown("##### 📋 Quick Copy Table")
            quick_copy_rows = [
                {
                    "Photo": report_data["runner_info"].get("Picture URL"),
                    "Runner": label,
                    "Status": report_data["runner_info"].get("Status"),
                    "Finish Time": report_data["runner_info"].get("Finish Time"),
                    "Country": _country_flag_url(report_data["runner_info"].get("Country")),
                    "VPI": report_data["indices"].get("VPI"),
                    "DMI": report_data["indices"].get("DMI"),
                    "ER": report_data["indices"].get("ER"),
                    "Pace 1st Half (min/effort-km)": report_data["indices"].get("effort_pace_first_half"),
                    "Pace 2nd Half (min/effort-km)": report_data["indices"].get("effort_pace_second_half"),
                }
                for label, report_data in reports.items()
            ]
            st.dataframe(
                quick_copy_rows,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Photo": st.column_config.ImageColumn("Photo"),
                    "Country": st.column_config.ImageColumn("Country"),
                },
            )

            # --- Abandonments: LiveTrail reports "WITHDRAWN" in the
            # runner's own status field for a confirmed DNF (confirmed
            # against a real case) - checked case-insensitively since
            # other statuses (RUNNING, FINISHER, etc.) haven't all been
            # seen yet and casing isn't guaranteed. Anyone else with no
            # Finish Time is flagged separately as "sin confirmar" (could
            # be a live race still in progress, not necessarily a DNF). ---
            withdrawn = [
                label for label, report_data in reports.items()
                if str(report_data["runner_info"].get("Status") or "").strip().upper() == "WITHDRAWN"
            ]
            no_finish_unconfirmed = [
                label for label, report_data in reports.items()
                if label not in withdrawn and not report_data["runner_info"].get("Finish Time")
            ]
            if withdrawn:
                st.error(f"🚩 {len(withdrawn)} abandono(s) (WITHDRAWN): " + ", ".join(withdrawn))
            if no_finish_unconfirmed:
                st.warning(
                    f"⚠️ {len(no_finish_unconfirmed)} corredor(es) sin tiempo de llegada y sin status "
                    "WITHDRAWN (puede seguir en carrera): " + ", ".join(no_finish_unconfirmed)
                )

            # checkpoint_to_km_top: used below by the position-progression
            # charts to map a checkpoint number back to its accumulated km.
            checkpoint_to_km_top = dict(zip(
                race_segments_df_top["End Point"], race_segments_df_top["End Km"]
            ))

            for label, df_summary_bib in results.items():
                st.markdown(f"##### {label}")
                st.dataframe(df_summary_bib, use_container_width=True, hide_index=True)

            # --- Full Analysis Report per runner: a single ZIP with
            # everything that worked, plus one download button each for
            # anyone who only wants a couple - not either/or. ---
            st.markdown("---")
            st.markdown("### 📄 Full Analysis Reports")
            st.caption("One HTML report per runner, same as 'Download Full Analysis' in Runner Metrics.")

            reports_ready = {
                label: report_data for label, report_data in reports.items() if report_data.get("report_html")
            }
            if reports_ready:
                zip_html_by_filename = {
                    f"{_ascii_filename(report_data['runner_info'].get('Name') or label).replace(' ', '_')}"
                    "_livetrail_full_analysis.html": report_data["report_html"]
                    for label, report_data in reports_ready.items()
                }
                st.download_button(
                    f"📦 Descargar los {len(reports_ready)} informes (ZIP)",
                    data=_build_reports_zip(zip_html_by_filename),
                    file_name=f"{_ascii_filename(selected_race_top_used or 'race').replace(' ', '_')}_full_analysis_reports.zip",
                    mime="application/zip",
                    type="primary",
                    use_container_width=True,
                    key="dl_top_reports_zip",
                )

            for i, (label, report_data) in enumerate(reports.items()):
                if not report_data.get("report_html"):
                    st.caption(f"⚠️ {label}: no se pudo generar su informe.")
                    continue
                st.download_button(
                    f"📄 {label}",
                    data=report_data["report_html"],
                    file_name=(
                        f"{_ascii_filename(report_data['runner_info'].get('Name') or label).replace(' ', '_')}"
                        "_livetrail_full_analysis.html"
                    ),
                    mime="text/html",
                    use_container_width=True,
                    key=f"dl_top_report_{i}",
                )

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
                file_name=f"{_ascii_filename(selected_race_top_used).replace(' ', '_')}_top_runners.xlsx",
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

            fig_positions = go.Figure()
            add_elevation_background(fig_positions, race_data_top["df"])

            worst_rank_seen = 0
            for label, df_summary_bib in results.items():
                df_plot = df_summary_bib[["Checkpoint", "Rank"]].dropna(subset=["Rank"]).copy()
                df_plot["Km"] = df_plot["Checkpoint"].map(checkpoint_to_km_top)
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
                df_plot["Km"] = df_plot["Checkpoint"].map(checkpoint_to_km_top)
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
                df_plot["Km"] = df_plot["Checkpoint"].map(checkpoint_to_km_top)
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

# ---------------------------------------------
# TAB 6: Engine Live - race-wide analysis across a wide bib range (up to
# 1000), separate from the hand-curated Top Runners flow. Doesn't feed
# the web export pool and doesn't build per-runner reports/charts - just
# the indices needed for aggregate leaderboards, so a big range fetches
# as fast as it can and doesn't clutter Exportar a Web with hundreds of
# runners nobody asked to publish. Goal: surface performances outside the
# podium (a runner's own dedicated analysis already lives in Athletes),
# not replace the manually-curated Top 10.
# ---------------------------------------------
ENGINE_LIVE_MAX_WORKERS = 10


def _fetch_and_score_engine_live_bib(bib, tenant, race_id, full_df_gpx, df_segments, total_km, total_gain):
    """One bib's worth of work for Engine Live's bulk scan: both LiveTrail
    requests (summary + detail - both are needed, see
    fetch_runner_by_tenant_and_bib_livetrail's docstring: Status/Overall
    Rank only exist on the summary endpoint, the per-checkpoint
    Point/Rank/Accumulated Time only on the detail one) plus the index
    calculation. Runs inside a thread pool since this is I/O-bound
    (network round-trips dominate, not the pandas math), so a wide bib
    range fetches in parallel instead of one bib at a time."""
    runner_info_bib, df_runner_bib = fetch_runner_by_tenant_and_bib_livetrail(tenant, bib, race_id)
    indices_bib, _ = calculate_runner_indices(full_df_gpx, df_segments, df_runner_bib, total_km, total_gain)
    ranks_bib = df_runner_bib["Rank"].dropna() if "Rank" in df_runner_bib.columns else None
    first_rank = int(ranks_bib.iloc[0]) if ranks_bib is not None and not ranks_bib.empty else None
    try:
        final_rank = int(runner_info_bib.get("Overall Rank"))
    except (TypeError, ValueError):
        final_rank = None
    positions_change = (
        first_rank - final_rank if first_rank is not None and final_rank is not None else None
    )
    return {
        "Bib": runner_info_bib.get("Bib") or bib,
        "Runner": runner_info_bib.get("Name") or f"Bib {bib}",
        "Status": runner_info_bib.get("Status"),
        "Finish Time": runner_info_bib.get("Finish Time"),
        "First CP Rank": first_rank,
        "Final Rank": final_rank,
        "Positions +/-": positions_change,
        "VPI": indices_bib.get("VPI"),
        "DMI": indices_bib.get("DMI"),
        "ER": indices_bib.get("ER"),
    }


with tab_engine_live:
    st.header("📡 Engine Live")
    st.caption(
        "Análisis del campo completo de una carrera: le pasás un rango amplio de dorsales "
        "y te trae quién subió/bajó más puestos, los mejores VPI/DMI/ER, y quién tuvo un "
        "gran rendimiento pero abandonó - pensado para encontrar historias fuera del podio, "
        "no para reemplazar el Top 10 curado a mano (eso sigue en '🏆 Top Runners')."
    )

    MAX_LIVE_BIBS = 1000

    available_races_live = st.session_state.get('saved_races', {})
    if not available_races_live:
        st.warning(
            "⚠️ You haven't loaded any race yet. Go to the "
            "**'🗺️ Race Analysis'** tab, select and analyze a race, and it "
            "will show up here automatically."
        )
        selected_race_live = None
    else:
        selected_race_live = st.selectbox(
            "Which race?", options=list(available_races_live.keys()), key="live_race_selector",
        )

    st.markdown("---")

    def _live_parse_url():
        parsed = parse_livetrail_url(st.session_state.get("live_livetrail_url", ""))
        if parsed.get("tenant"):
            st.session_state["live_tenant_input"] = parsed["tenant"]
        if parsed.get("race_id"):
            st.session_state["live_race_id_input"] = parsed["race_id"]

    st.text_input(
        "LiveTrail link of any runner in this race (to identify tenant/race ID)",
        key="live_livetrail_url", on_change=_live_parse_url,
        placeholder="https://aranbyutmb.v3.livetrail.net/en/2026/runners/5?raceId=vda",
    )
    col_live_tenant, col_live_race_id = st.columns(2)
    with col_live_tenant:
        live_tenant = st.text_input("X-Tenant", key="live_tenant_input", help="Auto-filled from the link above.")
    with col_live_race_id:
        live_race_id = st.text_input("Race ID", key="live_race_id_input", help="Auto-filled from the link above.")

    col_live_from, col_live_to = st.columns(2)
    with col_live_from:
        live_bib_from = st.number_input("Bib from", min_value=1, step=1, value=1, key="live_bib_from")
    with col_live_to:
        live_bib_to = st.number_input("Bib to", min_value=1, step=1, value=100, key="live_bib_to")

    st.caption(
        f"Hasta {MAX_LIVE_BIBS} dorsales por corrida. Un rango grande puede tardar varios "
        "minutos - se hacen 2 pedidos a LiveTrail por corredor, y no todo dorsal en el rango "
        "va a estar asignado (es normal, no es un error)."
    )

    fetch_live_button = st.button("📡 Analizar carrera", type="primary", use_container_width=True)

    # --- Same session_state-driven rendering as every other bulk-fetch tab
    # in this app: the Excel download button below triggers a Streamlit
    # rerun like any other, and results kept only inside
    # "if fetch_live_button:" would vanish on that rerun. ---
    if fetch_live_button:
        bib_count = int(live_bib_to) - int(live_bib_from) + 1 if live_bib_to >= live_bib_from else 0
        if not selected_race_live:
            st.session_state['live_warning'] = "Select a race above first."
        elif not live_tenant or not live_race_id:
            st.session_state['live_warning'] = "Paste a LiveTrail link above first (or fill in X-Tenant/Race ID by hand)."
        elif bib_count <= 0:
            st.session_state['live_warning'] = "'Bib to' debe ser mayor o igual a 'Bib from'."
        elif bib_count > MAX_LIVE_BIBS:
            st.session_state['live_warning'] = f"Ese rango tiene {bib_count} dorsales - achicalo a {MAX_LIVE_BIBS} o menos."
        else:
            st.session_state['live_warning'] = None
            race_data_live = available_races_live[selected_race_live]
            race_segments_df_live = race_data_live.get("df_segments")

            if race_segments_df_live is None or race_segments_df_live.empty:
                st.session_state['live_warning'] = (
                    "⚠️ The selected race doesn't have checkpoints with km loaded yet. "
                    "Go back to the 'Race Analysis' tab and load them first."
                )
            else:
                total_race_gain_live = calculate_total_elevation_gain(race_data_live["df"])
                bibs_live = [str(b) for b in range(int(live_bib_from), int(live_bib_to) + 1)]
                live_rows = []
                live_not_found = 0
                progress = st.progress(0.0, text="Analizando...")
                completed_live = 0

                # Parallel fetch: each bib is 2 sequential LiveTrail
                # requests (summary + detail, both required - see
                # _fetch_and_score_engine_live_bib's docstring), but bibs
                # are independent of each other, so a wide range fetches
                # ENGINE_LIVE_MAX_WORKERS bibs at a time instead of one by
                # one. This is the actual lever for a faster scan, not
                # cutting either request - both feed fields this tab uses.
                with ThreadPoolExecutor(max_workers=ENGINE_LIVE_MAX_WORKERS) as executor:
                    futures = {
                        executor.submit(
                            _fetch_and_score_engine_live_bib, bib, live_tenant, live_race_id,
                            race_data_live["df"], race_segments_df_live,
                            race_data_live["total_km"], total_race_gain_live,
                        ): bib
                        for bib in bibs_live
                    }
                    for future in as_completed(futures):
                        completed_live += 1
                        try:
                            live_rows.append(future.result())
                        except Exception:
                            # Most misses in a wide bib range are simply
                            # bibs nobody registered under, not real
                            # errors - no per-bib traceback log here
                            # (would just be noise for a 1000-bib scan),
                            # just a running count.
                            live_not_found += 1
                        progress.progress(
                            completed_live / len(bibs_live),
                            text=f"Analizando... ({completed_live}/{len(bibs_live)})",
                        )

                progress.empty()
                st.session_state['live_rows'] = live_rows or None
                st.session_state['live_not_found'] = live_not_found
                st.session_state['live_bibs_requested'] = len(bibs_live)

    live_warning = st.session_state.get('live_warning')
    live_rows = st.session_state.get('live_rows')
    live_not_found = st.session_state.get('live_not_found') or 0
    live_bibs_requested = st.session_state.get('live_bibs_requested') or 0

    if live_warning:
        st.warning(live_warning)
    elif live_rows:
        st.success(
            f"✅ {len(live_rows)} de {live_bibs_requested} dorsales con datos "
            f"({live_not_found} sin datos - normal en un rango amplio)."
        )

        withdrawn_live = [
            r for r in live_rows if str(r.get("Status") or "").strip().upper() == "WITHDRAWN"
        ]
        if withdrawn_live:
            st.error(f"🚩 {len(withdrawn_live)} abandono(s) (WITHDRAWN) en este rango.")

        def _leaderboard(rows, key, reverse, n):
            return sorted((r for r in rows if r.get(key) is not None), key=lambda r: r[key], reverse=reverse)[:n]

        st.markdown("### 🚀📉 Movers")
        col_gain, col_loss = st.columns(2)
        with col_gain:
            st.markdown("**Top 3 - subieron más puestos**")
            top_gainers_live = _leaderboard(live_rows, "Positions +/-", True, 3)
            if top_gainers_live:
                for r in top_gainers_live:
                    st.markdown(f"- **{r['Runner']}** (Bib {r['Bib']}) — +{r['Positions +/-']} puestos")
            else:
                st.caption("Sin datos suficientes.")
        with col_loss:
            st.markdown("**Top 3 - bajaron más puestos**")
            top_losers_live = _leaderboard(live_rows, "Positions +/-", False, 3)
            if top_losers_live:
                for r in top_losers_live:
                    st.markdown(f"- **{r['Runner']}** (Bib {r['Bib']}) — {r['Positions +/-']} puestos")
            else:
                st.caption("Sin datos suficientes.")

        st.markdown("### 🏆 Mejores índices del rango")
        col_vpi, col_dmi, col_er = st.columns(3)
        with col_vpi:
            st.markdown("**Top 5 VPI**")
            for r in _leaderboard(live_rows, "VPI", True, 5):
                st.markdown(f"- **{r['Runner']}** — {r['VPI']} m/h")
        with col_dmi:
            st.markdown("**Top 5 DMI**")
            for r in _leaderboard(live_rows, "DMI", True, 5):
                st.markdown(f"- **{r['Runner']}** — {r['DMI']} km/h")
        with col_er:
            st.markdown("**Top 5 ER**")
            for r in _leaderboard(live_rows, "ER", True, 5):
                st.markdown(f"- **{r['Runner']}** — {r['ER']}")

        st.markdown("### 💎 Gran motor, no llegó")
        st.caption(
            "Mejor VPI y DMI entre quienes abandonaron (WITHDRAWN) - candidatos a mirar de cerca "
            "aunque no hayan terminado."
        )
        if withdrawn_live:
            col_wvpi, col_wdmi = st.columns(2)
            with col_wvpi:
                st.markdown("**Mejor VPI entre abandonos**")
                wd_vpi_top = _leaderboard(withdrawn_live, "VPI", True, 3)
                if wd_vpi_top:
                    for r in wd_vpi_top:
                        st.markdown(f"- **{r['Runner']}** (Bib {r['Bib']}) — {r['VPI']} m/h")
                else:
                    st.caption("Sin datos de VPI entre los abandonos.")
            with col_wdmi:
                st.markdown("**Mejor DMI entre abandonos**")
                wd_dmi_top = _leaderboard(withdrawn_live, "DMI", True, 3)
                if wd_dmi_top:
                    for r in wd_dmi_top:
                        st.markdown(f"- **{r['Runner']}** (Bib {r['Bib']}) — {r['DMI']} km/h")
                else:
                    st.caption("Sin datos de DMI entre los abandonos.")
        else:
            st.caption("No hay abandonos (WITHDRAWN) en este rango.")
    elif live_rows is None and live_bibs_requested:
        st.error("❌ Ningún dorsal del rango devolvió datos.")

# ---------------------------------------------
# TAB 7: Checkpoint Fetcher (Livetrail) - generates the exact block to
# paste into data/races_registry.json for a new race/edition
# ---------------------------------------------
with tab_checkpoints:
    st.header("🧩 Checkpoint Fetcher (Livetrail)")
    st.caption(
        "Pegá el link de resultados en vivo de Livetrail para autocompletar el tenant y el "
        "race ID, bajá los checkpoints, y guardalos directo en `data/races_registry.json` - "
        "sin copiar/pegar JSON a mano. También te deja la carpeta del GPX creada y lista."
    )

    def _cf_parse_url():
        parsed = parse_livetrail_url(st.session_state.get("cf_url_input", ""))
        if parsed.get("tenant"):
            st.session_state["cf_tenant_input"] = parsed["tenant"]
        if parsed.get("race_id"):
            st.session_state["cf_race_id_input"] = parsed["race_id"]

    CF_NEW_RACE_OPTION = "+ Carrera nueva"

    def _cf_sync_slug_from_nombre():
        # Only auto-slugify while creating a brand new race - once an
        # existing one is picked below, the slug is locked to that race's
        # real key so editing the display name can't quietly re-derive a
        # DIFFERENT slug and fork off a duplicate top-level entry (this is
        # exactly how the Monterosa duplicate happened: two slightly
        # different slugs for the same event, "MonteRosa" vs
        # "monterosa-walserwaeg-by-utmb", each keeping its own checkpoints).
        if st.session_state.get("cf_existing_race_select", CF_NEW_RACE_OPTION) == CF_NEW_RACE_OPTION:
            st.session_state["cf_carrera_slug_input"] = _slugify(st.session_state.get("cf_carrera_nombre_input", ""))

    st.text_input(
        "Link de Livetrail (resultados en vivo)", key="cf_url_input", on_change=_cf_parse_url,
        placeholder="https://aranbyutmb.v3.livetrail.net/?e=aranbyutmb_2026&c=vda",
        help="El link que abrís normalmente para ver resultados en vivo de esta carrera.",
    )

    existing_carreras_cf = get_carreras()  # [(slug, nombre_visible), ...]
    carrera_nombre_by_slug_cf = dict(existing_carreras_cf)
    carrera_options_cf = [CF_NEW_RACE_OPTION] + [slug for slug, _ in existing_carreras_cf]

    def _cf_apply_existing_race():
        picked = st.session_state.get("cf_existing_race_select")
        if picked and picked != CF_NEW_RACE_OPTION:
            st.session_state["cf_carrera_nombre_input"] = carrera_nombre_by_slug_cf[picked]
            st.session_state["cf_carrera_slug_input"] = picked

    st.selectbox(
        "¿Sumás una distancia o actualizás el GPX de una carrera que ya existe, o es una carrera nueva?",
        options=carrera_options_cf,
        format_func=lambda s: s if s == CF_NEW_RACE_OPTION else f"{carrera_nombre_by_slug_cf[s]} ({s})",
        key="cf_existing_race_select",
        on_change=_cf_apply_existing_race,
        help="Elegí la carrera existente para completar el nombre y el slug automáticamente - evita crear "
             "una entrada duplicada en el registry por escribir el slug distinto a como ya estaba guardado.",
    )
    cf_using_existing_race = st.session_state.get("cf_existing_race_select", CF_NEW_RACE_OPTION) != CF_NEW_RACE_OPTION

    col1, col2 = st.columns(2)
    with col1:
        cf_race_id = st.text_input(
            "Race ID (raceId)", key="cf_race_id_input",
            help="Se autocompleta del link. El slug de la carrera dentro del tenant, ej: 'vda'.",
        )
        cf_tenant = st.text_input(
            "X-Tenant", key="cf_tenant_input",
            help="Se autocompleta del link. Formato raceslug_year, ej: 'aranbyutmb_2026'.",
        )
        cf_endpoint = st.text_input(
            "Request URL (endpoint de Livetrail)",
            value="https://api.v3.livetrail.net/api/events/points", key="cf_endpoint_input",
        )
        cf_race_slug_api = st.text_input(
            "race_slug_api (opcional)", key="cf_race_slug_api_input",
            help="Normalmente igual al Race ID (se autocompleta si lo dejas vacío).",
        )
    with col2:
        cf_carrera_nombre = st.text_input(
            "Nombre visible de la carrera", key="cf_carrera_nombre_input", on_change=_cf_sync_slug_from_nombre,
            help='Ej: "Val d\'Aran by UTMB"',
        )
        cf_carrera_slug = st.text_input(
            "Slug interno (clave del registry)", key="cf_carrera_slug_input",
            help="Se sugiere solo del nombre. Ej: 'aran', 'lavaredo'.",
            disabled=cf_using_existing_race,
        )
        cf_anio = st.text_input("Año", key="cf_anio_input", help="Ej: 2026")
        cf_distancia = st.text_input(
            "Distancia (clave)", key="cf_distancia_input",
            help="Solo el número, ej: '163', '110', '80'.",
        )

    if st.button("🧩 Fetch checkpoints", type="primary", use_container_width=True, key="cf_fetch_btn"):
        if not cf_race_id or not cf_tenant or not cf_endpoint:
            st.warning("Completa al menos Race ID, X-Tenant y Request URL (pegá el link de arriba, o cargalos a mano).")
        else:
            with st.spinner("Consultando Livetrail..."):
                try:
                    raw_points = fetch_livetrail_checkpoints(cf_race_id, cf_tenant, cf_endpoint)
                    st.session_state["cf_raw_points"] = raw_points
                    st.session_state["cf_fetch_error"] = None
                except Exception:
                    st.session_state["cf_raw_points"] = None
                    st.session_state["cf_fetch_error"] = traceback.format_exc()

    cf_fetch_error = st.session_state.get("cf_fetch_error")
    cf_raw_points = st.session_state.get("cf_raw_points")

    if cf_fetch_error:
        st.error("❌ No se pudo obtener la lista de checkpoints.")
        with st.expander("Ver detalle técnico del error"):
            st.code(cf_fetch_error, language="python")
    elif cf_raw_points is not None and not cf_raw_points:
        st.warning("⚠️ La respuesta llegó vacía. Revisa el Race ID y el X-Tenant.")
    elif cf_raw_points:
        st.success(f"✅ {len(cf_raw_points)} checkpoints encontrados para raceId='{cf_race_id}'.")

        preview_rows = [
            {
                "id": p["pointId"],
                "nombre": p["name"],
                "km": round(p["distance"] / 1000, 1),
                "altitud (m)": p.get("altitude"),
                "ganancia acum. (m)": p.get("elevationGain"),
            }
            for p in sorted(cf_raw_points, key=lambda x: x["distance"])
        ]
        st.dataframe(preview_rows, use_container_width=True, hide_index=True)

        if not (cf_carrera_slug and cf_carrera_nombre and cf_anio and cf_distancia):
            st.info("Completá slug, nombre, año y distancia arriba para poder guardar esto en el registry.")
        else:
            gpx_dir_rel = f"data/gpx/{cf_carrera_slug}/{cf_anio}"
            cf_gpx_upload = st.file_uploader(
                "GPX oficial de la carrera (opcional acá - también lo podés subir después a mano)",
                type=["gpx"], key="cf_gpx_upload",
            )
            if cf_gpx_upload is not None:
                cf_gpx_filename = cf_gpx_upload.name
                st.caption(f"Se va a guardar como `{cf_gpx_filename}`.")
            else:
                cf_gpx_filename = st.text_input(
                    "Nombre del archivo GPX (lo subís después a mano con este nombre)",
                    value=f"{cf_distancia}.gpx", key="cf_gpx_filename_input",
                )
            gpx_file_rel = f"{gpx_dir_rel}/{cf_gpx_filename}"
            effective_slug = cf_race_slug_api.strip() or cf_race_id

            checkpoints = [
                {"id": str(p["pointId"]), "nombre": p["name"], "km": round(p["distance"] / 1000, 1)}
                for p in sorted(cf_raw_points, key=lambda x: x["distance"])
            ]
            new_entry = {"gpx_file": gpx_file_rel, "race_slug_api": effective_slug, "checkpoints": checkpoints}

            registry_path = WEB_DATA_DIR / "races_registry.json"
            registry = json.loads(registry_path.read_text(encoding="utf-8")) if registry_path.exists() else {}
            already_exists = (
                cf_carrera_slug in registry
                and cf_anio in registry.get(cf_carrera_slug, {}).get("anios", {})
                and cf_distancia in registry.get(cf_carrera_slug, {}).get("anios", {}).get(cf_anio, {})
            )

            st.markdown("##### 📋 Esto se va a guardar en el registry")
            st.code(json.dumps(new_entry, ensure_ascii=False, indent=2), language="json")

            if already_exists:
                st.warning(
                    f"⚠️ Ya existe una entrada para '{cf_carrera_slug}' / {cf_anio} / {cf_distancia}K "
                    "en el registry. Guardar la va a sobreescribir."
                )

            if st.button(
                "💾 Guardar en el registry y crear carpeta del GPX",
                type="primary", use_container_width=True, key="cf_save_btn",
            ):
                registry.setdefault(cf_carrera_slug, {})["nombre"] = cf_carrera_nombre
                registry[cf_carrera_slug].setdefault("anios", {}).setdefault(cf_anio, {})[cf_distancia] = new_entry
                registry_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")

                gpx_dir_abs = WEB_DATA_DIR / "gpx" / cf_carrera_slug / cf_anio
                gpx_dir_abs.mkdir(parents=True, exist_ok=True)
                if cf_gpx_upload is not None:
                    (gpx_dir_abs / cf_gpx_filename).write_bytes(cf_gpx_upload.getvalue())

                gpx_loader.load_registry.cache_clear()

                if cf_gpx_upload is not None:
                    st.success(
                        f"✅ Guardado: {cf_carrera_slug} / {cf_anio} / {cf_distancia}K, con el GPX incluido. "
                        "Ya podés elegir esta carrera en '🗺️ Race Analysis'."
                    )
                else:
                    st.success(
                        f"✅ Guardado: {cf_carrera_slug} / {cf_anio} / {cf_distancia}K. "
                        f"Subí el GPX oficial a `{gpx_dir_rel}` cuando lo tengas "
                        "y ya vas a poder elegir esta carrera en '🗺️ Race Analysis'."
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
                 "Tiempo": r.get("finish_time"), "VPI": r.get("vpi"), "DMI": r.get("dmi"), "ER": r.get("er"),
                 "Informe": "✅" if r.get("_report_html") else "—"}
                for r in runners_pool.values()
            ],
            use_container_width=True, hide_index=True,
        )
        st.caption(
            "Informe ✅ = se va a adjuntar automáticamente al exportar, sin necesidad de subirlo a mano."
        )

        # --- Best-effort defaults parsed from "{name} {year} - {distance}K" ---
        default_name, default_year, default_distance = pool_key, "", ""
        m = re.match(r"^(.*?)\s+(\d{4})\s*-\s*([\d.]+)K$", pool_key)
        if m:
            default_name, default_year, default_distance = m.group(1), m.group(2), m.group(3)
        default_total_km = race_lib_data.get("total_km")

        # --- Find an already-published race folder for this same (year,
        # distance) AND a recognizably similar name, regardless of what its
        # top-level folder is named. The race's freeform "name" (used to
        # slugify a folder guess) can vary slightly between sessions - e.g.
        # "Lavaredo Ultra Trail by UTMB" vs "Lavaredo Ultra Trail" - and
        # re-slugifying it then silently creates a second top-level folder
        # for the same real-world event. Matching on (year, distance) ALONE
        # is not enough - unrelated races routinely share a round distance
        # (e.g. two different events both having a "120k"), so the name
        # must also share at least one non-generic word before two folders
        # are treated as the same event. ---
        # English generic words, plus grammatical connectors from the
        # languages these races are actually named in (French/Italian/
        # Spanish/German) - e.g. "du" alone matched "Marathon DU Mont
        # Blanc" against "Trail DU Saint-Jacques by UTMB", two unrelated
        # races that only shared that one French preposition.
        _GENERIC_RACE_WORDS = {
            "by", "utmb", "ultra", "trail", "race", "the", "of",
            "du", "de", "des", "la", "le", "les", "et", "l",  # French
            "di", "del", "della", "dei", "delle", "e", "il", "lo", "i", "gli",  # Italian
            "y", "el", "los", "las",  # Spanish
            "und", "der", "die", "das", "von", "im", "am",  # German
        }

        def _name_tokens(text: str) -> set:
            return set(_slugify(text or "").split("-")) - _GENERIC_RACE_WORDS

        def _find_existing_race_folder(year: str, distance_folder: str, distance_km, race_name: str) -> str | None:
            if not year:
                return None
            name_tokens = _name_tokens(race_name)
            if not name_tokens:
                return None
            for f in sorted((WEB_DATA_DIR / "races").glob(f"*/{year}/*/race.json")):
                try:
                    existing = json.loads(f.read_text(encoding="utf-8"))
                except Exception:
                    continue
                same_distance_folder = distance_folder and f.parent.name == distance_folder
                same_distance_km = (
                    distance_km and existing.get("distance_km")
                    and abs(float(existing["distance_km"]) - float(distance_km)) < 1.0
                )
                if not (same_distance_folder or same_distance_km):
                    continue
                if name_tokens & _name_tokens(existing.get("name")):
                    return f.parent.parent.parent.name
            return None

        _slugified_name_guess = _slugify(default_name) or "carrera"
        _existing_folder_match = _find_existing_race_folder(
            default_year, f"{default_distance}k" if default_distance else "", default_total_km, default_name,
        )
        default_race_folder = _existing_folder_match or _slugified_name_guess
        if _existing_folder_match and _existing_folder_match != _slugified_name_guess:
            st.warning(
                f"⚠️ Ya existe una carrera publicada para {default_year} · "
                f"{default_distance}K en la carpeta `data/races/{_existing_folder_match}/` "
                f"(el nombre de esta sesión hubiera sugerido `{_slugified_name_guess}`, una carpeta "
                "distinta). Precargué la carpeta existente abajo para no duplicar el evento - "
                "no la cambies salvo que sepas que es una carrera realmente nueva."
            )

        # --- If this same race was already exported before (same guessed
        # folder/year/distance), pre-fill the metadata fields from the
        # existing race.json instead of blanking them out. Re-exporting an
        # already-published race (e.g. with more runners) shouldn't require
        # retyping location/date/etc. every time. ---
        guessed_race_dir = (
            WEB_DATA_DIR / "races" / default_race_folder
            / (default_year or "") / (f"{default_distance}k" if default_distance else "distancia")
        )
        guessed_race_path = guessed_race_dir / "race.json"
        existing_race_for_prefill = (
            json.loads(guessed_race_path.read_text(encoding="utf-8")) if guessed_race_path.exists() else {}
        )
        guessed_event_icon = _find_existing_image(guessed_race_dir.parent / "images", "icon")

        st.markdown("---")
        st.markdown("##### Metadata de la carrera (no calculada por el Engine, se completa a mano)")
        if existing_race_for_prefill:
            st.caption(
                "📎 Ya existe una carrera exportada en esa carpeta/año/distancia - "
                "los campos de abajo se precargaron con lo que ya estaba guardado."
            )

        with st.form("web_export_form"):
            col1, col2 = st.columns(2)
            with col1:
                race_name = st.text_input("Nombre de la carrera", value=existing_race_for_prefill.get("name") or default_name)
                race_year = st.text_input("Año", value=default_year)
                race_distance_km = st.number_input(
                    "Distancia (km)",
                    value=float(existing_race_for_prefill.get("distance_km") or default_total_km or 0.0), step=1.0,
                )
                race_elevation_gain_m = st.number_input(
                    "Desnivel positivo (m)",
                    value=float(existing_race_for_prefill.get("elevation_gain_m") or 0.0), step=100.0,
                )
                race_date = st.text_input("Fecha (YYYY-MM-DD)", value=existing_race_for_prefill.get("date") or "")
            with col2:
                race_location = st.text_input("Ubicación", value=existing_race_for_prefill.get("location") or "")
                race_folder = st.text_input(
                    "Carpeta (data/races/<esto>/...)",
                    value=default_race_folder,
                    help="Elegí el nombre que quieras: solo define dónde vive el JSON en el repo, no la URL pública.",
                )
                race_distance_folder = st.text_input(
                    "Carpeta distancia (.../<esto>/race.json)",
                    value=f"{default_distance}k" if default_distance else "distancia",
                )
                race_slug = st.text_input(
                    "Slug público (vertlabs.run/races/<esto>/)",
                    value=existing_race_for_prefill.get("slug")
                    or (_slugify(f"{default_name}-{default_year}") if default_year else _slugify(default_name)),
                )

            st.markdown("---")
            hero_upload = st.file_uploader(
                "Imagen hero (opcional)", type=["jpg", "jpeg", "png"],
                help="Si no subís nada, podés dejar el archivo a mano después en images/hero.jpg.",
            )
            if guessed_event_icon:
                st.image(str(guessed_event_icon), caption="Ícono actual del evento", width=120)
            event_icon_upload = st.file_uploader(
                "Ícono del evento (opcional)", type=["jpg", "jpeg", "png"],
                help=(
                    "Se usa como miniatura en la grilla de /races/ para el EVENTO completo "
                    "(no para esta distancia sola) - compartido entre todas sus distancias, "
                    "así que con subirlo una vez alcanza."
                ),
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

                    event_icon_ext = _save_upload(event_icon_upload, race_dir.parent / "images", "icon")

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
                    elif existing_race_json.get("hero_image"):
                        hero_image = existing_race_json.get("hero_image")
                    elif (race_dir / "images" / "hero.jpg").exists():
                        hero_image = f"/media/races/{race_slug}/images/hero.jpg"
                    else:
                        hero_image = None

                    if elevation_ext:
                        elevation_profile_image = f"/media/races/{race_slug}/charts/elevation_profile{elevation_ext}"
                    elif existing_race_json.get("elevation_profile_image"):
                        elevation_profile_image = existing_race_json.get("elevation_profile_image")
                    elif (race_dir / "charts" / "elevation_profile.png").exists():
                        elevation_profile_image = f"/media/races/{race_slug}/charts/elevation_profile.png"
                    else:
                        elevation_profile_image = None

                    portrait_uploads_by_slug = {}
                    report_by_slug = {}
                    athletes_payload = []
                    runner_country_by_slug = {}
                    runner_gender_by_slug = {}
                    runner_picture_url_by_slug = {}
                    auto_report_paths = []
                    auto_report_failures = []
                    for runner_key, r in runners_pool.items():
                        athlete_slug = _slugify(r["name"])
                        uploads = runner_uploads.get(runner_key, {})
                        portrait_uploads_by_slug[athlete_slug] = uploads.get("portrait")
                        runner_country_by_slug[athlete_slug] = r.get("country")
                        runner_gender_by_slug[athlete_slug] = r.get("gender")
                        runner_picture_url_by_slug[athlete_slug] = r.get("picture_url")
                        existing_athlete = existing_athletes_by_slug.get(athlete_slug, {})
                        runner_dir = race_dir / "charts" / "runners" / athlete_slug

                        report_ext = _save_upload(uploads.get("report"), runner_dir, "report")
                        if report_ext:
                            report_path = f"/media/races/{race_slug}/charts/runners/{athlete_slug}/report{report_ext}"
                        else:
                            # No manual upload this round - if this runner was just
                            # (re)fetched this session, its Full Analysis Report HTML
                            # was already built then (same string the per-runner
                            # download button hands out) - just write it to disk, no
                            # regeneration needed. Always prefer it over an older saved
                            # report: a fresh fetch usually means updated numbers, and
                            # an old report can be pointing at a stale path from a
                            # since-renamed race slug/folder. Only when nothing was
                            # fetched this round do we fall back to whatever was saved.
                            report_html = r.get("_report_html")
                            report_path = None
                            if report_html:
                                try:
                                    runner_dir.mkdir(parents=True, exist_ok=True)
                                    (runner_dir / "report.html").write_text(report_html, encoding="utf-8")
                                    report_path = f"/media/races/{race_slug}/charts/runners/{athlete_slug}/report.html"
                                    auto_report_paths.append(
                                        str((runner_dir / "report.html").relative_to(WEB_DATA_DIR.parent))
                                    )
                                except Exception:
                                    auto_report_failures.append(f"{r['name']}: {traceback.format_exc(limit=1)}")
                            if not report_path:
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
                            "gender_rank": r.get("gender_rank"),
                            "gender": r.get("gender"),
                            "vpi": r.get("vpi"),
                            "dmi": r.get("dmi"),
                            "er": r.get("er"),
                            "pace_first_half": r.get("pace_first_half"),
                            "pace_second_half": r.get("pace_second_half"),
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
                    if event_icon_ext:
                        written_paths.append(
                            str((race_dir.parent / "images" / f"icon{event_icon_ext}").relative_to(WEB_DATA_DIR.parent))
                        )
                    if elevation_ext:
                        written_paths.append(str((race_dir / "charts" / f"elevation_profile{elevation_ext}").relative_to(WEB_DATA_DIR.parent)))
                    n_charts_uploaded = sum(len(uploads_.get("charts") or []) for uploads_ in runner_uploads.values())
                    if n_charts_uploaded:
                        written_paths.append(f"({n_charts_uploaded} gráfico(s) de corredor)")
                    n_reports_uploaded = sum(1 for u in runner_uploads.values() if u.get("report") is not None)
                    if n_reports_uploaded:
                        written_paths.append(f"({n_reports_uploaded} informe(s) completo(s) de corredor)")
                    if auto_report_paths:
                        written_paths.append(f"({len(auto_report_paths)} informe(s) generado(s) automáticamente)")

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
                            existing_portrait_path = _find_existing_portrait(athlete["slug"])
                            profile = {
                                "slug": athlete["slug"],
                                "name": athlete["name"],
                                "country": None,
                                "gender": None,
                                "portrait": (
                                    f"/media/athletes/{athlete['slug']}/images/{existing_portrait_path.name}"
                                    if existing_portrait_path else None
                                ),
                                "races": [],
                            }

                        fetched_country = runner_country_by_slug.get(athlete["slug"])
                        if fetched_country:
                            profile["country"] = fetched_country

                        fetched_gender = runner_gender_by_slug.get(athlete["slug"])
                        if fetched_gender:
                            profile["gender"] = fetched_gender

                        portrait_ext = _save_upload(
                            portrait_uploads_by_slug.get(athlete["slug"]), athlete_dir / "images", "portrait"
                        )
                        if portrait_ext:
                            profile["portrait"] = f"/media/athletes/{athlete['slug']}/images/portrait{portrait_ext}"
                            written_paths.append(
                                str((athlete_dir / "images" / f"portrait{portrait_ext}").relative_to(WEB_DATA_DIR.parent))
                            )
                        elif not profile.get("portrait"):
                            # No manual upload this round and no existing portrait -
                            # auto-fetch the photo LiveTrail already has for this bib,
                            # so most runners never need a manual photo upload at all.
                            picture_url = runner_picture_url_by_slug.get(athlete["slug"])
                            if picture_url:
                                try:
                                    picture_resp = requests.get(picture_url, timeout=15)
                                    picture_resp.raise_for_status()
                                    portrait_dir = athlete_dir / "images"
                                    portrait_dir.mkdir(parents=True, exist_ok=True)
                                    (portrait_dir / "portrait.jpg").write_bytes(picture_resp.content)
                                    profile["portrait"] = f"/media/athletes/{athlete['slug']}/images/portrait.jpg"
                                    written_paths.append(
                                        str((portrait_dir / "portrait.jpg").relative_to(WEB_DATA_DIR.parent))
                                    )
                                except Exception:
                                    pass  # best-effort - a manual upload always still works

                        profile["races"] = [
                            race_entry for race_entry in profile.get("races", [])
                            if race_entry.get("race_slug") != race_slug
                        ]
                        profile["races"].append({
                            "race_slug": race_slug,
                            "race_name": race_name,
                            "year": int(race_year),
                            "distance_km": race_distance_km or None,
                            "position": athlete["position"],
                            "gender_rank": athlete.get("gender_rank"),
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
                    if auto_report_failures:
                        with st.expander(f"⚠️ {len(auto_report_failures)} informe(s) no se pudieron generar automáticamente"):
                            for failure in auto_report_failures:
                                st.code(failure, language="python")
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
                            "Después usá el botón '🚀 Publicar sitio' de la barra lateral."
                        )
                    else:
                        st.caption("Todas las imágenes están listas. Usá el botón '🚀 Publicar sitio' de la barra lateral.")
                except Exception:
                    st.error("❌ No se pudo exportar.")
                    with st.expander("Ver detalle técnico del error"):
                        st.code(traceback.format_exc(), language="python")

# ---------------------------------------------
with tab_posts:
    st.header("📰 Editor de Posts")
    st.caption(
        "Artículos separados de las carreras: pre-race, análisis de métricas, o cualquier otra cosa "
        "que quieras publicar. Podés asociarlos a una carrera (opcional) - si lo hacés, aparece en la "
        "página de esa carrera y de su evento. El carousel de la home siempre muestra los posts más "
        "recientes, sin necesidad de elegir nada."
    )

    _existing_posts_for_edit = sorted(WEB_DATA_DIR.glob("posts/*/post.json"))
    _post_edit_options = {"— Nuevo post —": None}
    for _p in _existing_posts_for_edit:
        _d = json.loads(_p.read_text(encoding="utf-8"))
        _post_edit_options[f"{_d.get('title') or _p.parent.name} ({_p.parent.name})"] = _p.parent.name

    def _load_post_for_edit():
        chosen_slug = _post_edit_options.get(st.session_state.get("post_edit_select"))
        if chosen_slug:
            data = json.loads((WEB_DATA_DIR / "posts" / chosen_slug / "post.json").read_text(encoding="utf-8"))
            st.session_state["post_title_input"] = data.get("title", "")
            st.session_state["post_slug_input"] = chosen_slug

    st.selectbox(
        "📂 Editar post existente", list(_post_edit_options.keys()), key="post_edit_select",
        on_change=_load_post_for_edit,
        help="Elegí un post ya publicado para cargarlo y seguir editándolo, en vez de escribir su título/slug a mano.",
    )

    def _sync_post_slug_from_title():
        st.session_state["post_slug_input"] = _slugify(st.session_state.get("post_title_input", ""))

    post_title = st.text_input("Título del post", key="post_title_input", on_change=_sync_post_slug_from_title)
    post_slug = st.text_input(
        "Slug (define la URL /posts/<esto>/ y dónde se guarda)", key="post_slug_input",
    )

    if not post_slug:
        st.info("Escribí un título (o directamente un slug) para empezar.")
    else:
        post_dir = WEB_DATA_DIR / "posts" / post_slug
        post_path = post_dir / "post.json"
        existing_post = json.loads(post_path.read_text(encoding="utf-8")) if post_path.exists() else {}
        if existing_post:
            st.caption(f"📎 Ya existe un post en '{post_slug}' - se precargó lo que ya estaba guardado.")

        col1, col2 = st.columns(2)
        with col1:
            post_category = st.text_input(
                "Categoría", value=existing_post.get("category") or "", key="post_category_input",
                placeholder="ej. Pre-race, Análisis de métricas",
            )
            post_date = st.text_input("Fecha (YYYY-MM-DD)", value=existing_post.get("date") or "", key="post_date_input")
        with col2:
            _existing_races_for_posts = sorted(WEB_DATA_DIR.glob("races/**/race.json"))
            race_options = {"— Ninguna —": None}
            for p in _existing_races_for_posts:
                d = json.loads(p.read_text(encoding="utf-8"))
                race_options[f"{d.get('name')} {d.get('year')} — {p.parent.name} ({d.get('slug')})"] = d.get("slug")
            default_race_label = next(
                (k for k, v in race_options.items() if v == existing_post.get("race_slug")), "— Ninguna —"
            )
            race_label = st.selectbox(
                "Carrera asociada (opcional)", list(race_options.keys()),
                index=list(race_options.keys()).index(default_race_label), key="post_race_select",
            )
            post_race_slug = race_options[race_label]

        cover_existing = existing_post.get("cover_image")
        if cover_existing:
            local_cover = post_dir / "images" / Path(cover_existing).name
            if local_cover.exists():
                st.image(str(local_cover), caption="Imagen de portada actual", width=280)
        cover_upload = st.file_uploader(
            "Imagen de portada (opcional)", type=["jpg", "jpeg", "png"], key="post_cover_upload"
        )

        athlete_options = {"— (vacío) —": None}
        if post_race_slug:
            race_json_path = next(
                (p for p in _existing_races_for_posts
                 if json.loads(p.read_text(encoding="utf-8")).get("slug") == post_race_slug), None,
            )
            if race_json_path:
                race_json = json.loads(race_json_path.read_text(encoding="utf-8"))
                for a in race_json.get("athletes", []):
                    athlete_options[f"{a['name']} (#{a.get('bib') or '-'})"] = a["slug"]

        order_key = f"post_order_{post_slug}"
        if order_key not in st.session_state:
            _init_block_order(order_key, existing_post.get("blocks", []))

        st.markdown("---")
        _render_block_editor_ui(order_key, f"post_{post_slug}", post_dir / "images" / "content", athlete_options)

        st.markdown("---")
        if st.button("💾 Guardar post", type="primary", use_container_width=True, key="post_save_btn"):
            new_blocks = _collect_blocks_from_state(
                order_key, f"post_{post_slug}", post_dir / "images" / "content",
                f"/media/posts/{post_slug}/images/content", athlete_options,
            )
            post_dir.mkdir(parents=True, exist_ok=True)

            cover_image = cover_existing
            if cover_upload is not None:
                images_dir = post_dir / "images"
                images_dir.mkdir(parents=True, exist_ok=True)
                ext = Path(cover_upload.name).suffix.lower() or ".jpg"
                (images_dir / f"cover{ext}").write_bytes(cover_upload.getvalue())
                cover_image = f"/media/posts/{post_slug}/images/cover{ext}"

            post_json = {
                "slug": post_slug,
                "title": post_title or post_slug,
                "date": post_date or None,
                "category": post_category or None,
                "race_slug": post_race_slug,
                "cover_image": cover_image,
                "blocks": new_blocks,
            }
            post_path.write_text(json.dumps(post_json, ensure_ascii=False, indent=2), encoding="utf-8")
            st.success("✅ Post guardado. Usá el botón '🚀 Publicar sitio' de la barra lateral para subirlo.")