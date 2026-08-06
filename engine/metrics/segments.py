"""
Shared helpers for VPI/DMI/ER calculation. Ported verbatim from app.py
(same behavior, no Streamlit dependency, no I/O). The Builder never
imports from here - only the Engine/export path does.
"""
import pandas as pd

STRONG_SLOPE_THRESHOLD = 12  # >= 12% strong climb | <= -12% strong descent


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
