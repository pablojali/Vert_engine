"""
Maps real Engine data (runner_info, indices, and the DataFrames cached
in app.py's pdf_report_pool) into the dict shape render_pdf.py /
interpretation.py expect - the field-by-field mapping agreed in
checkpoints 1-2 of Report/Contexto.txt.

Two fields the reference mockup has that the Engine genuinely cannot
provide today are deliberately OMITTED rather than invented:
  - result.overall_field / category_field: LiveTrail's runner endpoint
    never exposes field size, only rank (confirmed by reading
    fetch_runner_by_tenant_and_bib_livetrail in app.py).
  - race.circuit (e.g. "UTMB World Series"): not tracked anywhere.

Everything else is either read straight from already-computed Engine
fields, or derived here with an explicit, documented rule - see each
function's docstring. Nothing is generated freely; every sentence
interpretation.py produces still traces back to one of these fields.
"""
import re
import math

import numpy as np
import pandas as pd
import requests

# Same fixed axis bands the public site's own VTL Performance Profile
# triangle already uses (builder/generators/radar_chart.py in the
# vertlabs-web builder) - NOT a percentile against other analyzed
# runners (that data doesn't exist without scraping the whole field).
# "Index" here means "where this value sits in VTL's own typical range
# for that metric", exactly what vertlabs.run already shows visitors.
AXIS_RANGE = {
    "vpi": (600, 1500),
    "dmi": (6, 15),
    "er": (40, 100),
}

RACE_KEY_RE = re.compile(r"^(.*?)\s+(\d{4})\s*-\s*([\d.]+)K$")

# df_seg's "Segment" column is a bare "P{start}→P{end}" point-ID string
# (app.py's calculate_runner_indices/calculate_indices_by_segment) - not
# informative in the printed report (real user feedback: "los puntos de
# paso... P18 > P22 no dice nada, hay que ponerle el nombre que tiene
# asociado en el checkpoint"). The point IDs sometimes arrive as pandas
# float64 (a NaN elsewhere in the same column promotes the whole column
# from int to float), which prints as "P22.0->P24.0" - real user report
# after the first fix shipped - so the trailing ".0" must be tolerated,
# not just the bare-integer form.
SEGMENT_RE = re.compile(r"^P(\d+(?:\.\d+)?)→P(\d+(?:\.\d+)?)$")


class MissingReportData(Exception):
    """Raised when the cached session data isn't enough to build a
    report - e.g. too few segments for a meaningful chart. Caught by
    the Streamlit tab and shown as a clear message instead of crashing
    or drawing a broken PDF."""


def _axis_index(key: str, value) -> int:
    if value is None:
        return 0
    lo, hi = AXIS_RANGE[key]
    ratio = max(0.0, min(1.0, (value - lo) / (hi - lo)))
    return round(ratio * 100)


def _parse_race_key(race_key: str) -> dict:
    m = RACE_KEY_RE.match(race_key.strip())
    if not m:
        return {"name": race_key, "year": None, "distance_k": None}
    name, year, distance_k = m.groups()
    return {"name": name.strip(), "year": int(year), "distance_k": float(distance_k)}


def _elevation_gain_label(total_elevation_gain: float) -> str:
    return f"{total_elevation_gain:,.0f} D+"


def _nan_to_none(value):
    return None if (value is None or (isinstance(value, float) and math.isnan(value))) else value


def _fetch_image_bytes(url):
    """Best-effort fetch for the athlete portrait / country flag - both
    come from external CDNs (LiveTrail/Cloudinary, flagcdn.com) that the
    report has no control over, so a timeout or a missing image must
    never break PDF generation. Returns None on any failure; the
    renderer simply skips drawing that image when this is None."""
    if not url:
        return None
    try:
        resp = requests.get(url, timeout=6)
        resp.raise_for_status()
        return resp.content
    except Exception:
        return None


def _flag_url(iso_code):
    """Same rule as app.py's _country_flag_url - duplicated rather than
    imported since app.py runs as __main__ under `streamlit run` (see
    build_report_data's docstring)."""
    if not iso_code or len(iso_code) != 2 or not iso_code.isalpha():
        return None
    return f"https://flagcdn.com/w80/{iso_code.lower()}.png"


def _segment_display_name(segment_label: str, point_to_name: dict) -> str:
    """Replaces a bare 'P18→P22' label with the real checkpoint names
    ('Bassa d'Oles → Artiga de Lin') when the race's registry has a name
    for both endpoints; falls back to the raw point-ID label rather than
    guessing when a name is missing."""
    m = SEGMENT_RE.match(segment_label)
    if not m:
        return segment_label
    start_name = point_to_name.get(int(float(m.group(1))))
    end_name = point_to_name.get(int(float(m.group(2))))
    if start_name and end_name:
        return f"{start_name} → {end_name}"
    return segment_label


def _segment_progression(df_seg: pd.DataFrame, value_col: str) -> tuple[list, list]:
    """One (distance_km, value) pair per segment with a finite
    value_col - segments where this runner has no qualifying terrain
    for that metric are skipped rather than plotted as a fake zero.
    Filters on np.isfinite(), not just .dropna(): a segment with a
    near-zero effort-km (e.g. two checkpoints at almost the same km)
    can produce +/-inf from a division, which dropna() does NOT catch -
    matplotlib then fails with "Axis limits cannot be NaN or Inf" on
    real data (confirmed live on a real runner's Effort Pace column)."""
    finite = df_seg[df_seg[value_col].apply(lambda v: pd.notna(v) and np.isfinite(v))]
    return finite["End Km"].round(1).tolist(), finite[value_col].tolist()


def _position_progression(df_runner: pd.DataFrame, checkpoints_km: list[dict]) -> dict:
    """Builds (distance_km, position) from df_runner's 'Rank' column,
    using the race's own checkpoint-to-km mapping (the runner table
    itself only has checkpoint 'Point' IDs, not km)."""
    point_to_km = {c["point"]: c["km"] for c in checkpoints_km}
    rows = [
        (point_to_km[p], r)
        for p, r in zip(df_runner["Point"], df_runner["Rank"])
        if p in point_to_km and pd.notna(r)
    ]
    rows.sort(key=lambda pr: pr[0])
    return {
        "distance_km": [round(km, 1) for km, _ in rows],
        "position": [int(r) for _, r in rows],
    }


def _position_summary(pos_progression: dict, turning_point_km, turning_point_idx) -> dict:
    positions = pos_progression["position"]
    km = pos_progression["distance_km"]
    if len(positions) < 2:
        raise MissingReportData("Not enough ranked checkpoints to build a position summary.")

    best_i = positions.index(min(positions))
    worst_i = positions.index(max(positions))

    largest_gain = {"places": 0, "segment": ""}
    largest_loss = {"places": 0, "segment": ""}
    for i in range(1, len(positions)):
        delta = positions[i - 1] - positions[i]  # positive = moved up (fewer = better)
        label = f"Km {km[i-1]:.0f} → Km {km[i]:.0f}"
        if delta > largest_gain["places"]:
            largest_gain = {"places": delta, "segment": label}
        if -delta > largest_loss["places"]:
            largest_loss = {"places": -delta, "segment": label}

    return {
        "best_position": positions[best_i],
        "worst_position": positions[worst_i],
        "final_position": positions[-1],
        "largest_gain": largest_gain or {"places": 0, "segment": ""},
        "largest_loss": largest_loss or {"places": 0, "segment": ""},
        "turning_point_km": turning_point_km,
        "turning_point_idx": turning_point_idx,
    }


def _turning_point_km(df_seg: pd.DataFrame):
    """Rule (confirmed with the user): the segment with the largest
    COMBINED drop in VPI Index + DMI Index versus the immediately
    preceding segment - the first point where both terrain dimensions
    decline together. Returns (km, positional_index) where the index is
    a position into df_seg ITSELF (the caller already sorted + reset
    its index) - NOT into some separately filtered/reindexed subset, so
    it lines up with degradation_index's arrays (built from the same
    df_seg via .tolist(), same row order) for interpretation.py's
    race_story() to look up directly. Returns (None, None) if fewer
    than 2 segments have both indices (no meaningful 'together' to
    detect)."""
    vpi_idx = df_seg["VPI Index (0-100)"]
    dmi_idx = df_seg["DMI Index (0-100)"]
    drop = -(vpi_idx.diff() + dmi_idx.diff())  # positive = a combined decline from the previous row
    drop = drop.dropna()  # diff() is NaN on row 0 and wherever either index is missing
    if drop.empty:
        return None, None
    worst_pos = drop.idxmax()
    return round(df_seg.loc[worst_pos, "End Km"]), int(worst_pos)


def _segment_role_rows(df_seg: pd.DataFrame, turning_point_idx, point_to_name: dict) -> list[dict]:
    """Derives the 'Key Segments' table roles - none of these are a
    stored field, each is the segment with the max/min of the relevant
    already-computed raw value:
      BEST/WORST CLIMB   -> max/min VPI Raw (m/h)
      BEST/WORST DESCENT -> max/min DMI Raw (km/h)
      LARGEST DEGRADATION -> the same segment _turning_point_km flags
      BEST RECOVERY -> the last segment where the combined VPI+DMI
        Index ticked UP versus the previous one (a real stabilization
        near the finish), falling back to the last valid segment if
        the runner's indices declined monotonically with no recovery.

    Order matters and is NOT incidental: interpretation.py's
    _dimension_anchor() indexes this list positionally (seg[0]=BEST
    CLIMB, seg[1]=WORST CLIMB, seg[2]=BEST DESCENT, seg[3]=WORST
    DESCENT) rather than by role, to stay unmodified from the reference
    mockup. Raises MissingReportData instead of silently reordering or
    omitting one of those 4 if this runner has zero qualifying climb or
    descent segments - that would make interpretation.py silently
    anchor a claim to the wrong segment."""
    df_seg = df_seg.sort_values("End Km").reset_index(drop=True)

    def _row(idx, role):
        r = df_seg.loc[idx]
        # Rounded defensively even though calculate_indices_by_segment()
        # already rounds these upstream - the fixed-width table layout
        # (components.py, unchanged from the reference) assumes short
        # values and visibly overlaps columns if handed a long float.
        vpi = _nan_to_none(r["VPI Raw (m/h)"])
        vpi = round(vpi, 1) if vpi is not None else None
        dmi = _nan_to_none(r["DMI Raw (km/h)"])
        dmi = round(dmi, 2) if dmi is not None else None
        er_idx = _nan_to_none(r.get("ER Index (0-100)"))
        reliable = bool(r["VPI Reliable"]) if role in ("BEST CLIMB", "WORST CLIMB") else (
            bool(r["DMI Reliable"]) if role in ("BEST DESCENT", "WORST DESCENT") else
            bool(r["VPI Reliable"]) and bool(r["DMI Reliable"])
        )
        return {
            "role": role,
            "name": _segment_display_name(r["Segment"], point_to_name),
            "distance_km": f"{r['Start Km']:.1f} - {r['End Km']:.1f}",
            "avg_slope_pct": float(r["Average Slope (%)"]),
            "vpi_m_h": vpi,
            "dmi_km_h": dmi,
            "er_index": round(er_idx) if er_idx is not None else None,
            "reliable": reliable,
            "signal": _segment_signal(role, r),
        }

    valid_vpi = df_seg.dropna(subset=["VPI Raw (m/h)"])
    valid_dmi = df_seg.dropna(subset=["DMI Raw (km/h)"])
    if valid_vpi.empty or valid_dmi.empty:
        raise MissingReportData(
            "This runner has no segment with a qualifying climb or descent (>=12% slope) - "
            "not enough data for the Key Segments table and race-story anchors."
        )

    rows = [
        _row(valid_vpi["VPI Raw (m/h)"].idxmax(), "BEST CLIMB"),
        _row(valid_vpi["VPI Raw (m/h)"].idxmin(), "WORST CLIMB"),
        _row(valid_dmi["DMI Raw (km/h)"].idxmax(), "BEST DESCENT"),
        _row(valid_dmi["DMI Raw (km/h)"].idxmin(), "WORST DESCENT"),
    ]
    if turning_point_idx is not None:
        rows.append(_row(turning_point_idx, "LARGEST DEGRADATION"))

    recovery_idx = _best_recovery_index(df_seg)
    if recovery_idx is not None:
        rows.append(_row(recovery_idx, "BEST RECOVERY"))

    return rows


def _best_recovery_index(df_seg: pd.DataFrame):
    """Positional index into df_seg itself (same contract as
    _turning_point_km - see its docstring) - deliberately does NOT
    dropna+reset_index into a separate frame, since idxmax()/diff() on
    a plain dropna() (no reset) already preserve df_seg's own row
    labels, which the caller uses directly via df_seg.loc[idx]."""
    valid = df_seg.dropna(subset=["VPI Index (0-100)", "DMI Index (0-100)"])
    if len(valid) < 2:
        return None
    combined = (valid["VPI Index (0-100)"] + valid["DMI Index (0-100)"]).sort_index()
    upticks = combined.diff()
    recovery_candidates = upticks[upticks > 0]
    if not recovery_candidates.empty:
        return recovery_candidates.index[-1]
    return combined.index[-1]


def _segment_signal(role: str, row) -> str:
    """One fixed sentence per role, same 'threshold -> fixed phrase'
    pattern as interpretation.py - never freely generated."""
    templates = {
        "BEST CLIMB": "Strongest climbing output of the race on this segment.",
        "WORST CLIMB": "Climbing output dropped furthest below this runner's own race average here.",
        "BEST DESCENT": "Fastest technical descent of the race on this segment.",
        "WORST DESCENT": "Descent speed dropped furthest below this runner's own race average here.",
        "LARGEST DEGRADATION": "Sharpest simultaneous drop in climbing and descending indices in the race.",
        "BEST RECOVERY": "Climbing and descending indices ticked back up here rather than continuing to fall.",
    }
    return templates.get(role, "")


def build_report_data(race_key: str, runner_bundle: dict, race_data: dict, total_elevation_gain: float,
                       field_comparison_note: str = "") -> dict:
    """race_key: the 'Name Year - DistanceK' string used in saved_races /
    pdf_report_pool. runner_bundle: one entry of
    pdf_report_pool[race_key][runner_key]. race_data: saved_races[race_key].
    total_elevation_gain: caller-computed via app.py's own
    calculate_total_elevation_gain(race_data["df"]) - passed in rather
    than imported here, since app.py runs as __main__ under
    `streamlit run` and importing it as a module from inside this
    package would re-execute the whole Streamlit script a second time.

    field_comparison_note: free text, typed by hand in the Streamlit tab.
    The Engine has no access to the full race field's results (LiveTrail
    only exposes rank, and only for runners the user chose to analyze
    this session) - real user feedback confirmed there's no reliable way
    to compute "vs the rest of the field" automatically, so this is a
    deliberate manual field rather than a derived one. Left out of the
    PDF entirely when blank.

    Raises MissingReportData with a clear reason if there isn't enough
    data to build a meaningful report - the Streamlit tab shows that
    message instead of generating a broken/empty PDF."""
    runner_info = runner_bundle["runner_info"]
    indices = runner_bundle["indices"]
    df_runner = runner_bundle["df_runner"]
    df_seg = runner_bundle["df_segment_degradation"].sort_values("End Km").reset_index(drop=True)
    df_crossed = runner_bundle["df_crossed"]

    if len(df_seg) < 2:
        raise MissingReportData(
            f"Only {len(df_seg)} segment(s) calculated for this runner - not enough for a "
            "meaningful progression chart (need at least 2)."
        )

    race_meta = _parse_race_key(race_key)

    vpi_dist, vpi_val = _segment_progression(df_seg, "VPI Raw (m/h)")
    dmi_dist, dmi_val = _segment_progression(df_seg, "DMI Raw (km/h)")
    pace_dist, pace_val = _segment_progression(df_seg, "Effort Pace (min/effort-km)")
    if len(vpi_dist) < 2 or len(dmi_dist) < 2 or len(pace_dist) < 2:
        raise MissingReportData(
            "Not enough qualifying segments to plot VPI, DMI and effort pace progressions "
            "(each needs at least 2 valid points)."
        )

    turning_point_km, turning_point_idx = _turning_point_km(df_seg)
    pos_progression = _position_progression(df_runner, race_data["checkpoints_km"])
    position_summary = _position_summary(pos_progression, turning_point_km, turning_point_idx)

    point_to_name = {
        c["point"]: c.get("name") for c in race_data["checkpoints_km"] if c.get("name")
    }

    # Elevation motif for the chart backgrounds - sampled from the
    # race's own GPX at each segment's End Km, nearest match. Purely
    # decorative (same role it plays in the reference mockup).
    gpx_df = race_data["df"]
    elevation_m = [
        float(gpx_df.iloc[(gpx_df["Distance (km)"] - km).abs().idxmin()]["Elevation (m)"])
        for km in df_seg["End Km"]
    ]

    # --- vpi_half / dmi_half: same effort-km-weighted first/second-half
    # split calculate_runner_indices() already uses for ER (df_crossed's
    # "Effort Km Accumulated"), applied to VPI Raw / DMI Raw instead of
    # pace - not a plain-distance approximation. ---
    half_effort_km = indices.get("half_effort_km")
    merged = df_seg.merge(
        df_crossed[["Start Km", "End Km", "Effort Km Accumulated", "Runner Time (h)"]],
        on=["Start Km", "End Km"], how="left", suffixes=("", "_crossed"),
    )
    if half_effort_km is None or merged["Effort Km Accumulated"].isna().all():
        raise MissingReportData("Missing effort-km data needed to split VPI/DMI into race halves.")

    first_half = merged[merged["Effort Km Accumulated"] <= half_effort_km]
    second_half = merged[merged["Effort Km Accumulated"] > half_effort_km]

    def _time_weighted_avg(df_half, value_col, time_col="Runner Time (h)"):
        valid = df_half.dropna(subset=[value_col, time_col])
        if valid.empty or valid[time_col].sum() == 0:
            return None
        return (valid[value_col] * valid[time_col]).sum() / valid[time_col].sum()

    vpi_first = _time_weighted_avg(first_half, "VPI Raw (m/h)")
    vpi_second = _time_weighted_avg(second_half, "VPI Raw (m/h)")
    dmi_first = _time_weighted_avg(first_half, "DMI Raw (km/h)")
    dmi_second = _time_weighted_avg(second_half, "DMI Raw (km/h)")

    def _pct_change(first, second):
        if not first:
            return None
        return round(((second / first) - 1) * 100, 1) if second is not None else None

    vpi_half = {
        "first": round(vpi_first, 1) if vpi_first is not None else None,
        "second": round(vpi_second, 1) if vpi_second is not None else None,
        "degradation_pct": _pct_change(vpi_first, vpi_second) or 0.0,
    }
    dmi_half = {
        "first": round(dmi_first, 2) if dmi_first is not None else None,
        "second": round(dmi_second, 2) if dmi_second is not None else None,
        "degradation_pct": _pct_change(dmi_first, dmi_second) or 0.0,
    }
    effort_pace_half = {
        "first_min_km": indices.get("effort_pace_first_half"),
        "second_min_km": indices.get("effort_pace_second_half"),
        "change_pct": indices.get("Pacing_Decay_%") or 0.0,
    }

    data = {
        "athlete": {
            "name": runner_info.get("Name") or "Runner",
            "category": runner_info.get("Category"),
            "nationality": runner_info.get("Country"),
            "portrait_bytes": _fetch_image_bytes(runner_info.get("Picture URL")),
            "flag_bytes": _fetch_image_bytes(_flag_url(runner_info.get("Country"))),
        },
        "race": {
            "name": race_meta["name"],
            "distance_label": f"{race_meta['distance_k']:.0f}K" if race_meta["distance_k"] else "—",
            "elevation_gain_label": _elevation_gain_label(total_elevation_gain),
            "year": race_meta["year"] or "—",
        },
        "result": {
            "finish_time": runner_info.get("Finish Time") or "—",
            "overall_rank": runner_info.get("Overall Rank"),
            "category_rank": runner_info.get("Category Rank"),
        },
        "metrics": {
            "vpi": {
                "raw": round(indices["VPI"], 1) if indices.get("VPI") is not None else None,
                "unit": "m/h", "index": _axis_index("vpi", indices.get("VPI")),
            },
            "dmi": {
                "raw": round(indices["DMI"], 2) if indices.get("DMI") is not None else None,
                "unit": "km/h", "index": _axis_index("dmi", indices.get("DMI")),
            },
            "er": {
                "raw": round(indices["ER"], 1) if indices.get("ER") is not None else None,
                "unit": "pts", "index": _axis_index("er", indices.get("ER")),
            },
        },
        "vpi_progression": {"distance_km": vpi_dist, "value_m_h": vpi_val},
        "dmi_progression": {"distance_km": dmi_dist, "value_km_h": dmi_val},
        "effort_pace_progression": {"distance_km": pace_dist, "pace_min_km": pace_val},
        "degradation_index": {
            # pandas NaN (not None) on purpose here - fed straight into
            # matplotlib, which renders a NaN as a gap in the line
            # instead of erroring on a mixed-type list.
            "distance_km": df_seg["End Km"].round(1).tolist(),
            "vpi_index": df_seg["VPI Index (0-100)"].tolist(),
            "dmi_index": df_seg["DMI Index (0-100)"].tolist(),
            "er_index": df_seg["ER Index (0-100)"].tolist(),
            "elevation_m": elevation_m,
        },
        "vpi_half": vpi_half,
        "dmi_half": dmi_half,
        "effort_pace_half": effort_pace_half,
        "segments": _segment_role_rows(df_seg, turning_point_idx, point_to_name),
        "position_progression": pos_progression,
        "position_summary": position_summary,
        "field_comparison_note": (field_comparison_note or "").strip(),
    }
    return data
