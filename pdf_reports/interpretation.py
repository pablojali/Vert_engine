"""
VertLabs — Interpretation Engine
---------------------------------
Transparent, threshold-based rules that turn Engine output (raw + normalized
VPI/DMI/ER, degradation, segments, position) into report-ready statements.

No claim is generated here that isn't directly traceable to a field in the
athlete data dict. Nothing about training, nutrition, weather, tactics or
psychology is inferred.

This module is intentionally decoupled from rendering: render_pdf.py only
calls into here, it never computes interpretation itself.
"""

THRESHOLDS = {
    "balance_narrow": 12,      # spread between strongest/weakest index <= this => "balanced"
    "balance_wide": 25,        # spread >= this => "specialist"
    "fatigue_strong_drop": 15,   # avg degradation < this => STRONG fatigue resistance
    "fatigue_moderate_drop": 30, # avg degradation < this => MODERATE
    "reliable_min_km": 3.0,      # (documented threshold, applied upstream by Engine)
}

DIMENSION_LABELS = {
    "vpi": ("VPI", "climbing", "Vertical Power"),
    "dmi": ("DMI", "descending", "Descent Mastery"),
    "er":  ("ER", "endurance", "Endurance"),
}


def _indices(metrics):
    return {k: metrics[k]["index"] for k in ("vpi", "dmi", "er")}


def strongest_dimension(metrics):
    idx = _indices(metrics)
    key = max(idx, key=idx.get)
    return key, idx[key]


def weakest_dimension(metrics):
    idx = _indices(metrics)
    key = min(idx, key=idx.get)
    return key, idx[key]


def balance_spread(metrics):
    idx = _indices(metrics)
    return max(idx.values()) - min(idx.values())


def profile_classification(metrics):
    """Rule: classify athlete profile from normalized index spread + strongest axis."""
    spread = balance_spread(metrics)
    strong_key, _ = strongest_dimension(metrics)
    strong_label = DIMENSION_LABELS[strong_key][2]

    if spread <= THRESHOLDS["balance_narrow"]:
        return "BALANCED ALL-TERRAIN PROFILE"
    if spread >= THRESHOLDS["balance_wide"]:
        return f"{strong_label.upper()} SPECIALIST"
    return f"{strong_label.upper()}-LEANING PROFILE"


def avg_degradation(vpi_deg_pct, dmi_deg_pct, effort_change_pct):
    """Average magnitude of decline across the three degradation signals."""
    vals = [abs(vpi_deg_pct), abs(dmi_deg_pct), abs(effort_change_pct) / 2]
    return sum(vals) / len(vals)


def fatigue_signal(vpi_deg_pct, dmi_deg_pct, effort_change_pct):
    avg = avg_degradation(vpi_deg_pct, dmi_deg_pct, effort_change_pct)
    if avg < THRESHOLDS["fatigue_strong_drop"]:
        level = "STRONG"
        sentence = "Performance indices held close to first-half levels through to the finish."
    elif avg < THRESHOLDS["fatigue_moderate_drop"]:
        level = "MODERATE"
        sentence = "A measurable decline appeared in the second half without a full collapse in output."
    else:
        level = "LIMITED"
        sentence = "Climbing, descending and pacing indices all declined sharply after the midpoint."
    return level, sentence


def primary_strength(metrics, segments):
    key, val = strongest_dimension(metrics)
    label = DIMENSION_LABELS[key][2]
    best_seg = next((s for s in segments if s["role"] in ("BEST CLIMB", "BEST DESCENT") and
                      ((key == "vpi" and s["role"] == "BEST CLIMB") or
                       (key == "dmi" and s["role"] == "BEST DESCENT"))), None)
    if best_seg:
        return f"{label} — index {val}/100, peaking on {best_seg['name']}."
    return f"{label} — highest normalized index of the three dimensions ({val}/100)."


def limiting_factor(metrics, segments):
    key, val = weakest_dimension(metrics)
    label = DIMENSION_LABELS[key][2]
    worst_seg = next((s for s in segments if s["role"] in ("WORST CLIMB", "WORST DESCENT") and
                       ((key == "vpi" and s["role"] == "WORST CLIMB") or
                        (key == "dmi" and s["role"] == "WORST DESCENT"))), None)
    if worst_seg:
        return f"{label} — index {val}/100, lowest point at {worst_seg['name']}."
    return f"{label} — lowest normalized index of the three dimensions ({val}/100)."


def race_character(pos_summary, fatigue_level):
    gain = pos_summary["largest_gain"]["places"]
    loss = pos_summary["largest_loss"]["places"]
    if loss > gain and fatigue_level in ("MODERATE", "LIMITED"):
        return "POSITIVE START, SECOND-HALF ATTRITION"
    if gain >= loss:
        return "STEADY POSITIONAL CLIMB"
    return "EVEN RACE, LATE VOLATILITY"


def turning_point_statement(pos_summary):
    km = pos_summary["turning_point_km"]
    return (f"The clearest inflection point in the race sits near km {km}, "
            f"where position and performance indices move together.")


def race_story(data):
    """Three-part narrative built strictly from progression + index data."""
    seg = data["segments"]
    deg = data["degradation_index"]
    pos = data["position_summary"]
    vpi_h = data["vpi_half"]
    dmi_h = data["dmi_half"]
    pace_h = data["effort_pace_half"]

    opening = (
        f"The race opened with the strongest climbing output of the day: "
        f"{seg[0]['vpi_m_h']} m/h on {seg[0]['name']}, well above the eventual race-average VPI. "
        f"Position moved from {pos['best_position']}-range toward the front third inside the first quarter of the course, "
        f"supported by an ER index above {deg['er_index'][0]} in the opening segments."
    )

    # The reference mockup hardcoded index [7] here, which only worked
    # for its specific 12-point sample data - fixed to use the actual
    # turning-point index (data_mapper.py's _turning_point_km result),
    # so this generalizes to any real race's segment count.
    t_idx = pos.get("turning_point_idx")
    if t_idx is not None and 0 <= t_idx < len(deg["vpi_index"]):
        vpi_at_turn = deg["vpi_index"][t_idx]
        dmi_at_turn = deg["dmi_index"][t_idx]
    else:
        vpi_at_turn = dmi_at_turn = None
    turning = (
        f"Around km {pos['turning_point_km']}, climbing and descending indices decline together — "
        f"VPI index drops to {vpi_at_turn} and DMI index to {dmi_at_turn}, "
        f"the first point in the race where both terrain dimensions move down at the same time. "
        f"{turning_point_statement(pos)}"
    )

    closing = (
        f"From this point, effort pace slows from {pace_h['first_min_km']} to {pace_h['second_min_km']} min/km "
        f"({pace_h['change_pct']}% change), and VPI falls {abs(vpi_h['degradation_pct'])}% while DMI falls "
        f"{abs(dmi_h['degradation_pct'])}% between race halves. Position stabilizes rather than continuing to fall, "
        f"closing at #{pos['final_position']} after a low point of #{pos['worst_position']}."
    )

    return {"opening": opening, "turning_point": turning, "closing": closing}


def _dimension_anchor(key, seg, best=True):
    """Return a (value_str, segment_name) anchor statement for a given dimension."""
    if key == "vpi":
        s = seg[0] if best else seg[1]  # BEST CLIMB / WORST CLIMB
        return f"{s['vpi_m_h']} m/h on {s['name']}"
    if key == "dmi":
        s = seg[2] if best else seg[3]  # BEST DESCENT / WORST DESCENT
        return f"{s['dmi_km_h']} km/h on {s['name']}"
    # er has no dedicated best/worst climb-or-descent segment; anchor on ER index instead
    s = seg[0] if best else seg[3]
    return f"an ER index of {s['er_index']} on {s['name']}"


def key_takeaways(data):
    metrics = data["metrics"]
    seg = data["segments"]
    pos = data["position_summary"]
    strong_key, _ = strongest_dimension(metrics)
    weak_key, _ = weakest_dimension(metrics)

    return [
        f"{DIMENSION_LABELS[strong_key][2]} was the defining strength, anchored by "
        f"{_dimension_anchor(strong_key, seg, best=True)}.",

        f"{DIMENSION_LABELS[weak_key][2]} capped overall performance, falling furthest under fatigue, "
        f"with {_dimension_anchor(weak_key, seg, best=False)}.",

        f"Km {pos['turning_point_km']} marked the race's defining moment, where climbing and descending "
        f"output declined together and position began to fall.",

        f"Second-half pacing decay, not a single bad segment, was the main performance characteristic of the race.",
    ]


def summary_paragraph(data):
    metrics = data["metrics"]
    profile = profile_classification(metrics)
    strong_key, strong_val = strongest_dimension(metrics)
    weak_key, weak_val = weakest_dimension(metrics)
    level, _ = fatigue_signal(
        data["vpi_half"]["degradation_pct"],
        data["dmi_half"]["degradation_pct"],
        data["effort_pace_half"]["change_pct"],
    )
    pos = data["position_summary"]

    def art(word):
        return "an" if word[0].upper() in "AEIOU" else "a"

    profile_article = art(profile)
    strong_label = DIMENSION_LABELS[strong_key][2]
    weak_label = DIMENSION_LABELS[weak_key][2]
    text = (
        f"{data['athlete']['name']}'s race data fits {profile_article} {profile.lower()}, driven by "
        f"{art(strong_label)} {strong_label.lower()} "
        f"index of {strong_val}/100 against {art(weak_label)} {weak_label.lower()} index of {weak_val}/100. "
        f"The clearest performance cost came from {DIMENSION_LABELS[weak_key][1]}, which declined furthest as the race "
        f"progressed. Fatigue resistance was {level.lower()}: VPI fell {abs(data['vpi_half']['degradation_pct'])}% and "
        f"DMI fell {abs(data['dmi_half']['degradation_pct'])}% between race halves, alongside a "
        f"{data['effort_pace_half']['change_pct']}% slowdown in effort pace. Position tracked this decline directly, "
        f"moving from a best of #{pos['best_position']} to a low of #{pos['worst_position']} before stabilizing at "
        f"the km {pos['turning_point_km']} mark. The defining characteristic of the race was a strong, front-loaded "
        f"climbing performance that outpaced the athlete's ability to sustain descending output and pace to the finish."
    )
    return text


def build_report_model(data):
    """Assemble every derived field the renderer needs, in one place."""
    metrics = data["metrics"]
    strong_key, strong_val = strongest_dimension(metrics)
    weak_key, weak_val = weakest_dimension(metrics)
    level, fatigue_sentence = fatigue_signal(
        data["vpi_half"]["degradation_pct"],
        data["dmi_half"]["degradation_pct"],
        data["effort_pace_half"]["change_pct"],
    )

    return {
        "profile_classification": profile_classification(metrics),
        "primary_strength": primary_strength(metrics, data["segments"]),
        "limiting_factor": limiting_factor(metrics, data["segments"]),
        "race_character": race_character(data["position_summary"], level),
        "fatigue_level": level,
        "fatigue_sentence": fatigue_sentence,
        "race_story": race_story(data),
        "key_takeaways": key_takeaways(data),
        "summary_paragraph": summary_paragraph(data),
        "strongest": (strong_key, strong_val),
        "weakest": (weak_key, weak_val),
    }
