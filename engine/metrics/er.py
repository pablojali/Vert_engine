"""
Endurance Rating (ER): 100 minus the pacing decay (%) between the first
and second half of the race, measured in effort-kilometers
(distance_km + elevation_gain_m / 100) rather than raw distance.

The real computation is shared with VPI/DMI (they're derived from the
same segment crossing of official GPX segments x runner split times),
so this is a thin accessor over calculate_runner_indices rather than a
reimplementation - see indices.py for the actual logic.
"""
from .indices import calculate_runner_indices


def calculate_er(full_df_gpx, df_segments, df_runner, total_km, total_elevation_gain,
                  distance_weighting_coef=1.0):
    """Returns the ER (0-100 score) for one runner on one race, or None
    if pacing decay couldn't be computed (missing first or second half)."""
    result, _ = calculate_runner_indices(
        full_df_gpx, df_segments, df_runner, total_km, total_elevation_gain,
        distance_weighting_coef,
    )
    return result["ER"]
