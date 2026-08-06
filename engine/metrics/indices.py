"""
Core VPI/DMI/ER calculation, ported verbatim from app.py's
calculate_indices_by_segment / calculate_runner_indices (same behavior,
no Streamlit dependency, no I/O - pure functions over pandas DataFrames
already assembled by the Engine/scrapers).

This module never imports anything from builder/ and never writes
files. The "Exportar a Web" tab in app.py is the only caller that turns
its output into race.json / profile.json.
"""
import pandas as pd

from .segments import (
    STRONG_SLOPE_THRESHOLD,
    build_time_by_point,
    merge_segments_with_runner_times,
    normalize_segment_index,
)


def calculate_indices_by_segment(full_df_gpx, df_segments, df_runner):
    """Calculates VPI and DMI INDEPENDENTLY for each segment (degradation
    matrix), instead of one global value for the whole race.

    With checkpoints spaced several km apart, a segment's OWN average
    slope rarely crosses +-12% even if it contains real steep walls mixed
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


def calculate_runner_indices(full_df_gpx, df_segments, df_runner, total_km, total_elevation_gain,
                              distance_weighting_coef=1.0):
    """Crosses the official race segments (df_segments, computed from the
    checkpoints) with the runner's real split times (df_runner) to
    calculate VPI, DMI and ER.

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
