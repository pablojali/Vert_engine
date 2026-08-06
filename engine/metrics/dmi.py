"""
Descent Mastery Index (DMI): km/h on strong-descent terrain
(slope <= -12%).

The real computation is shared with VPI/ER (they're derived from the
same segment crossing of official GPX segments x runner split times),
so this is a thin accessor over calculate_runner_indices rather than a
reimplementation - see indices.py for the actual logic.
"""
from .indices import calculate_runner_indices


def calculate_dmi(full_df_gpx, df_segments, df_runner, total_km, total_elevation_gain,
                   distance_weighting_coef=1.0):
    """Returns the DMI (km/h) for one runner on one race, or None if it
    couldn't be computed (no strong-descent segments with a valid time)."""
    result, _ = calculate_runner_indices(
        full_df_gpx, df_segments, df_runner, total_km, total_elevation_gain,
        distance_weighting_coef,
    )
    return result["DMI"]
