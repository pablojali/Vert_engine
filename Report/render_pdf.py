"""
VertLabs — Athlete Performance Report PDF renderer
----------------------------------------------------
data (Engine JSON) -> interpretation model -> visual components -> PDF

Usage:
    python3 render_pdf.py data/wayne_walsh_lavaredo120k_2026.json output/report.pdf
"""
import sys
import json
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader

import theme as T
import components as K
import interpretation as I

CHARTS = "/home/claude/vertlabs_pdf/charts"


def register_fonts():
    base = "/home/claude/vertlabs_pdf/fonts_ttf"
    mono = "/usr/share/fonts/truetype/jetbrains-mono"
    pdfmetrics.registerFont(TTFont("Inter", f"{base}/Inter-Regular.ttf"))
    pdfmetrics.registerFont(TTFont("Inter-Medium", f"{base}/Inter-Medium.ttf"))
    pdfmetrics.registerFont(TTFont("Inter-SemiBold", f"{base}/Inter-SemiBold.ttf"))
    pdfmetrics.registerFont(TTFont("Inter-Bold", f"{base}/Inter-Bold.ttf"))
    pdfmetrics.registerFont(TTFont("Inter-Black", f"{base}/Inter-Black.ttf"))
    pdfmetrics.registerFont(TTFont("JetBrainsMono", f"{mono}/JetBrainsMono-Medium.ttf"))


def img(name):
    return ImageReader(f"{CHARTS}/{name}.png")


# ================================================================= PAGE 1
def page1(c, data, model):
    K.draw_page_background(c)
    div_y = K.draw_header(c, 1)
    x = T.MARGIN
    w = T.CONTENT_W
    y = div_y - 34

    K.draw_label(c, x, y, "ATHLETE PERFORMANCE REPORT", color=T.TEXT_FAINT, size=8.2)
    y -= 30
    c.setFont(T.FONT_BLACK, 30)
    c.setFillColor(HexColor(T.TEXT))
    c.drawString(x, y, data["athlete"]["name"])
    y -= 22
    race = data["race"]
    c.setFont(T.FONT_SEMIBOLD, 14)
    c.setFillColor(HexColor(T.TEXT))
    c.drawString(x, y, race["name"])
    y -= 17
    c.setFont(T.FONT_MED, 9.5)
    c.setFillColor(HexColor(T.TEXT_MUTED))
    c.drawString(x, y, f"{race['distance_label']}  ·  {race['elevation_gain_label']}  ·  {race['year']}")

    y -= 30
    K.hline(c, x, x + w, y, color=T.LINE)
    y -= 42

    res = data["result"]
    items = [
        ("FINISH", res["finish_time"]),
        ("OVERALL", f"#{res['overall_rank']}"),
    ]
    if res.get("category"):
        pass
    items.append(("CATEGORY", data["athlete"]["category"]))
    if res.get("category_rank"):
        items.append(("CATEGORY RANK", f"#{res['category_rank']}"))
    K.draw_result_strip(c, x, y, w, items)

    y -= 78
    K.hline(c, x, x + w, y, color=T.LINE)

    # --- performance triangle (left) + athlete profile (right) -----------
    panel_top = y - 64
    panel_h = 372
    panel_y = panel_top - panel_h
    left_w = w * 0.46
    right_x = x + left_w + 26
    right_w = w - left_w - 26

    K.rounded_panel(c, x, panel_y, left_w, panel_h, r=10)
    K.draw_topo_motif(c, x, panel_y, left_w, panel_h, seed=3, n=4, alpha=0.045)
    K.draw_label(c, x + 18, panel_y + panel_h - 24, "PERFORMANCE TRIANGLE", size=7.6)
    tri_cx = x + left_w / 2
    tri_cy = panel_y + panel_h / 2 + 34
    m = data["metrics"]
    K.draw_performance_triangle(c, tri_cx, tri_cy, 98,
                                 m["vpi"]["index"], m["dmi"]["index"], m["er"]["index"])

    # raw value strip under triangle
    ry = panel_y + 40
    labels = [
        (f"{m['vpi']['raw']} {m['vpi']['unit']}", "VERTICAL POWER", T.CYAN),
        (f"{m['dmi']['raw']} {m['dmi']['unit']}", "DESCENT MASTERY", T.ORANGE),
        (f"{m['er']['raw']}", "ENDURANCE", T.GREEN),
    ]
    col_w = left_w / 3
    for i, (val, lab, col) in enumerate(labels):
        cxp = x + col_w * i + col_w / 2
        c.setFont(T.FONT_BOLD, 12.5)
        c.setFillColor(HexColor(col))
        c.drawCentredString(cxp, ry, val)
        c.setFont(T.FONT_MED, 6.6)
        c.setFillColor(HexColor(T.TEXT_MUTED))
        c.drawCentredString(cxp, ry - 11, lab)

    # profile panel (right)
    K.rounded_panel(c, right_x, panel_y, right_w, panel_h, r=10)
    py = panel_y + panel_h - 26
    K.draw_label(c, right_x + 18, py, "ATHLETE PROFILE", size=7.6)
    py -= 22
    c.setFont(T.FONT_BOLD, 13.5)
    c.setFillColor(HexColor(T.TEXT))
    for line in K.wrap_text(c, model["profile_classification"], T.FONT_BOLD, 13.5, right_w - 36):
        c.drawString(right_x + 18, py, line)
        py -= 16
    py -= 6

    profile_body = (
        f"Strongest on {I.DIMENSION_LABELS[model['strongest'][0]][2].lower()} terrain "
        f"(index {model['strongest'][1]}/100), with {I.DIMENSION_LABELS[model['weakest'][0]][2].lower()} "
        f"the limiting dimension (index {model['weakest'][1]}/100). {model['fatigue_sentence']}"
    )
    py = K.draw_paragraph(c, right_x + 18, py, profile_body, T.FONT_REG, 9.2, 14.4, right_w - 36,
                           color=T.TEXT_MUTED)
    py -= 22
    K.hline(c, right_x + 18, right_x + right_w - 18, py, color=T.LINE_SOFT)
    py -= 28

    rows = [
        ("PRIMARY STRENGTH", model["primary_strength"], T.CYAN),
        ("LIMITING FACTOR", model["limiting_factor"], T.ORANGE),
        ("RACE CHARACTER", model["race_character"], T.TEXT),
    ]
    for lab, val, col in rows:
        K.draw_label(c, right_x + 18, py, lab, color=T.TEXT_FAINT, size=7.2)
        py -= 15
        c.setFont(T.FONT_SEMIBOLD, 10)
        c.setFillColor(HexColor(col))
        lines = K.wrap_text(c, val, T.FONT_SEMIBOLD, 10, right_w - 36)
        for line in lines[:2]:
            c.drawString(right_x + 18, py, line)
            py -= 13.5
        py -= 16

    K.draw_footer(c, data["athlete"]["name"], data["race"]["name"])


# ================================================================= PAGE 2
def page2(c, data, model):
    K.draw_page_background(c)
    div_y = K.draw_header(c, 2)
    x = T.MARGIN
    w = T.CONTENT_W
    y = div_y - 32

    c.setFont(T.FONT_BLACK, 20)
    c.setFillColor(HexColor(T.TEXT))
    c.drawString(x, y, "PERFORMANCE & FATIGUE")
    y -= 30

    # ---- three dimension rows, stacked, each with mountain-profile chart ----
    row_h = 106
    row_gap = 13
    left_w = 152
    chart_gap = 18
    chart_w = w - left_w - chart_gap

    dims = [
        ("VPI", "VERTICAL POWER INDEX", f"{data['metrics']['vpi']['raw']} m/h", T.CYAN,
         "vpi_progression", data["vpi_half"], "vpi"),
        ("DMI", "DESCENT MASTERY INDEX", f"{data['metrics']['dmi']['raw']} km/h", T.ORANGE,
         "dmi_progression", data["dmi_half"], "dmi"),
        ("ER", "ENDURANCE RATING", f"{data['metrics']['er']['raw']}", T.GREEN,
         "pace_progression", data["effort_pace_half"], "er"),
    ]

    for code, full, raw, color, chart_name, half, key in dims:
        row_y = y - row_h
        K.rounded_panel(c, x, row_y, w, row_h, r=9)
        pad = 16

        # left info block
        c.setFont(T.FONT_BOLD, 14)
        c.setFillColor(HexColor(color))
        c.drawString(x + pad, row_y + row_h - 24, code)
        c.setFont(T.FONT_MED, 6.6)
        c.setFillColor(HexColor(T.TEXT_MUTED))
        c.drawString(x + pad, row_y + row_h - 34, full)

        c.setFont(T.FONT_BOLD, 19)
        c.setFillColor(HexColor(T.TEXT))
        c.drawString(x + pad, row_y + row_h - 58, raw)

        if key == "er":
            f_val, s_val = half["first_min_km"], half["second_min_km"]
            unit = " min/km"
            deg = half["change_pct"]
            deg_word = "PACE CHANGE"
        else:
            f_val, s_val = half["first"], half["second"]
            unit = " m/h" if key == "vpi" else " km/h"
            deg = half["degradation_pct"]
            deg_word = "DEGRADATION"

        ty = row_y + 34
        c.setFont(T.FONT_MED, 6.2)
        c.setFillColor(HexColor(T.TEXT_FAINT))
        c.drawString(x + pad, ty, "1ST HALF")
        c.setFont(T.FONT_SEMIBOLD, 8.4)
        c.setFillColor(HexColor(T.TEXT))
        c.drawString(x + pad, ty - 11, f"{f_val}{unit}")

        c.setFont(T.FONT_MED, 6.2)
        c.setFillColor(HexColor(T.TEXT_FAINT))
        c.drawString(x + pad + 76, ty, "2ND HALF")
        c.setFont(T.FONT_SEMIBOLD, 8.4)
        c.setFillColor(HexColor(T.TEXT))
        c.drawString(x + pad + 76, ty - 11, f"{s_val}{unit}")

        c.setFont(T.FONT_MED, 6.4)
        c.setFillColor(HexColor(T.TEXT_FAINT))
        c.drawString(x + pad, row_y + 12, f"{deg_word}  {deg:+.1f}%")

        # right chart — mountain profile with metric line
        K.vline(c, x + left_w, row_y + 14, row_y + row_h - 14, color=T.LINE_SOFT)
        cimg_pad = 14
        cimg_h = row_h - 2 * cimg_pad
        cimg_w = chart_w - cimg_pad
        c.drawImage(img(chart_name), x + left_w + chart_gap, row_y + cimg_pad,
                    width=cimg_w, height=cimg_h, preserveAspectRatio=False, mask="auto")

        y = row_y - row_gap

    y -= 12
    K.hline(c, x, x + w, y, color=T.LINE)
    y -= 26

    c.setFont(T.FONT_BOLD, 13)
    c.setFillColor(HexColor(T.TEXT))
    c.drawString(x, y, "DEGRADATION CURVE")
    c.setFont(T.FONT_MED, 7.4)
    c.setFillColor(HexColor(T.TEXT_FAINT))
    c.drawRightString(x + w, y, "NORMALIZED INDEX · NOT RAW VALUES")
    y -= 14

    # ---- two-column section: smaller degradation chart | stacked KPI cards ----
    section_h = 150
    col_gap = 16
    left_col_w = w * 0.58
    right_col_w = w - left_col_w - col_gap
    sec_top = y

    chart_h = section_h - 10
    c.drawImage(img("degradation_curve"), x, sec_top - chart_h, width=left_col_w, height=chart_h,
                preserveAspectRatio=False, mask="auto")

    kpi_x = x + left_col_w + col_gap
    kpi_h = 42
    kpi_gap = 9
    kpi_y = sec_top
    kpi_defs = [
        ("VPI DEGRADATION", f"{data['vpi_half']['degradation_pct']:+.1f}", T.CYAN),
        ("DMI DEGRADATION", f"{data['dmi_half']['degradation_pct']:+.1f}", T.ORANGE),
        ("EFFORT PACE CHANGE", f"{data['effort_pace_half']['change_pct']:+.1f}", T.GREEN),
    ]
    for lab, val, col in kpi_defs:
        kpi_y -= kpi_h
        K.rounded_panel(c, kpi_x, kpi_y, right_col_w, kpi_h, r=8)
        K.draw_label(c, kpi_x + 12, kpi_y + kpi_h - 15, lab, color=T.TEXT_MUTED, size=6.4)
        c.setFont(T.FONT_BOLD, 15)
        c.setFillColor(HexColor(col))
        c.drawString(kpi_x + 12, kpi_y + 9, val)
        c.setFont(T.FONT_MED, 8)
        c.setFillColor(HexColor(T.TEXT_MUTED))
        vw = c.stringWidth(val, T.FONT_BOLD, 15)
        c.drawString(kpi_x + 12 + vw + 3, kpi_y + 11, "%")
        kpi_y -= kpi_gap

    y = sec_top - section_h - 22
    K.rounded_panel(c, x, y - 40, w, 40, r=8, fill=T.PANEL)
    c.setFont(T.FONT_SEMIBOLD, 8)
    c.setFillColor(HexColor(T.TEXT_MUTED))
    c.drawString(x + 16, y - 16, "FATIGUE SIGNAL")
    c.setFont(T.FONT_BOLD, 12)
    c.setFillColor(HexColor(T.TEXT))
    c.drawString(x + 16, y - 32, model["fatigue_level"])
    c.setFont(T.FONT_REG, 8.4)
    c.setFillColor(HexColor(T.TEXT_MUTED))
    lines = K.wrap_text(c, model["fatigue_sentence"], T.FONT_REG, 8.4, w - 230)
    ty = y - 16
    for line in lines[:2]:
        c.drawString(x + 160, ty, line)
        ty -= 11

    K.draw_footer(c, data["athlete"]["name"], data["race"]["name"])


# ================================================================= PAGE 3
def page3(c, data, model):
    K.draw_page_background(c)
    div_y = K.draw_header(c, 3)
    x = T.MARGIN
    w = T.CONTENT_W
    y = div_y - 32

    c.setFont(T.FONT_BLACK, 20)
    c.setFillColor(HexColor(T.TEXT))
    c.drawString(x, y, "THE RACE, EXPLAINED BY DATA")
    y -= 26

    pos = data["position_summary"]
    chart_h = 118
    y -= 6
    c.drawImage(img("position_progression"), x, y - chart_h, width=w, height=chart_h,
                preserveAspectRatio=False, mask="auto")
    y -= chart_h + 16

    stats = [
        ("BEST POSITION", f"#{pos['best_position']}", T.GREEN),
        ("WORST POSITION", f"#{pos['worst_position']}", T.ORANGE),
        ("LARGEST GAIN", f"+{pos['largest_gain']['places']}", T.GREEN),
        ("LARGEST LOSS", f"-{pos['largest_loss']['places']}", T.ORANGE),
        ("FINAL POSITION", f"#{pos['final_position']}", T.TEXT),
    ]
    sw = w / len(stats)
    for i, (lab, val, col) in enumerate(stats):
        sx = x + i * sw
        K.draw_label(c, sx, y, lab, color=T.TEXT_FAINT, size=6.4)
        c.setFont(T.FONT_BOLD, 13.5)
        c.setFillColor(HexColor(col))
        c.drawString(sx, y - 15, val)
    y -= 40
    K.hline(c, x, x + w, y, color=T.LINE)
    y -= 24

    # race story — 3 moments
    story = model["race_story"]
    moments = [("01", "OPENING", story["opening"], T.CYAN),
               ("02", "TURNING POINT", story["turning_point"], T.ORANGE),
               ("03", "CLOSING", story["closing"], T.GREEN)]

    for num, title, body, col in moments:
        c.setFont(T.FONT_BLACK, 15)
        c.setFillColor(HexColor(T.LINE))
        c.drawString(x, y, num)
        c.setFont(T.FONT_BOLD, 10.5)
        c.setFillColor(HexColor(col))
        c.drawString(x + 26, y, title)
        y -= 14
        y = K.draw_paragraph(c, x + 26, y, body, T.FONT_REG, 8.6, 12, w - 26, color=T.TEXT_MUTED)
        y -= 14

    y -= 4
    K.hline(c, x, x + w, y, color=T.LINE)
    y -= 22

    c.setFont(T.FONT_BOLD, 11.5)
    c.setFillColor(HexColor(T.TEXT))
    c.drawString(x, y, "KEY SEGMENTS")
    y -= 18

    headers = ["SEGMENT", "DIST (KM)", "SLOPE", "VPI", "DMI", "ER IDX", "SIGNAL"]
    col_x = [x, x + 132, x + 190, x + 228, x + 264, x + 300, x + 340]
    c.setFont(T.FONT_SEMIBOLD, 6.6)
    c.setFillColor(HexColor(T.TEXT_FAINT))
    for hx, htext in zip(col_x, headers):
        c.drawString(hx, y, htext)
    y -= 8
    K.hline(c, x, x + w, y, color=T.LINE)
    y -= 15

    role_colors = {
        "BEST CLIMB": T.CYAN, "WORST CLIMB": T.CYAN,
        "BEST DESCENT": T.ORANGE, "WORST DESCENT": T.ORANGE,
        "LARGEST DEGRADATION": T.TEXT, "BEST RECOVERY": T.GREEN,
    }

    for seg in data["segments"]:
        col = role_colors.get(seg["role"], T.TEXT)
        c.setFont(T.FONT_SEMIBOLD, 6.6)
        c.setFillColor(HexColor(col))
        c.drawString(col_x[0], y + 9, seg["role"])

        c.setFont(T.FONT_MED, 7.8)
        c.setFillColor(HexColor(T.TEXT))
        name_lines = K.wrap_text(c, seg["name"], T.FONT_MED, 7.8, 128)
        c.drawString(col_x[0], y - 2, name_lines[0])

        c.setFont(T.FONT_REG, 7.4)
        c.setFillColor(HexColor(T.TEXT_MUTED))
        c.drawString(col_x[1], y + 3, seg["distance_km"])
        c.drawString(col_x[2], y + 3, f"{seg['avg_slope_pct']:+.1f}%")
        c.drawString(col_x[3], y + 3, f"{seg['vpi_m_h']}" if seg["vpi_m_h"] else "—")
        c.drawString(col_x[4], y + 3, f"{seg['dmi_km_h']}" if seg["dmi_km_h"] else "—")

        if seg["reliable"]:
            c.setFillColor(HexColor(T.TEXT))
            c.drawString(col_x[5], y + 3, str(seg["er_index"]))
        else:
            c.setFillColor(HexColor(T.TEXT_FAINT))
            c.drawString(col_x[5], y + 3, "low n")

        sig_lines = K.wrap_text(c, seg["signal"], T.FONT_REG, 6.9, w - col_x[6] + x)
        c.setFont(T.FONT_REG, 6.9)
        c.setFillColor(HexColor(T.TEXT_MUTED))
        for li, line in enumerate(sig_lines[:2]):
            c.drawString(col_x[6], y + 3 - li * 8, line)

        y -= 30
        K.hline(c, x, x + w, y + 12, color=T.LINE_SOFT)

    K.draw_footer(c, data["athlete"]["name"], data["race"]["name"])


# ================================================================= PAGE 4
def page4(c, data, model):
    K.draw_page_background(c)
    div_y = K.draw_header(c, 4)
    x = T.MARGIN
    w = T.CONTENT_W
    y = div_y - 32

    c.setFont(T.FONT_BLACK, 20)
    c.setFillColor(HexColor(T.TEXT))
    c.drawString(x, y, "VERTICAL TRAIL LABS ASSESSMENT")
    y -= 30

    K.draw_label(c, x, y, "ATHLETE PERFORMANCE SUMMARY", size=7.6)
    y -= 18
    y = K.draw_paragraph(c, x, y, model["summary_paragraph"], T.FONT_REG, 9.4, 14.6, w,
                          color=T.TEXT)
    y -= 26
    K.hline(c, x, x + w, y, color=T.LINE)
    y -= 30

    K.draw_label(c, x, y, "PERFORMANCE SIGNATURE", size=7.6)
    y -= 24
    m = data["metrics"]
    bar_w = w
    bar_h = 14
    K.draw_metric_bar(c, x, y - bar_h, bar_w, bar_h, "CLIMBING · VPI",
                       "", f"{m['vpi']['raw']} m/h", m["vpi"]["index"], T.CYAN)
    y -= bar_h + 34
    K.draw_metric_bar(c, x, y - bar_h, bar_w, bar_h, "DESCENDING · DMI",
                       "", f"{m['dmi']['raw']} km/h", m["dmi"]["index"], T.ORANGE)
    y -= bar_h + 34
    K.draw_metric_bar(c, x, y - bar_h, bar_w, bar_h, "ENDURANCE · ER",
                       "", f"{m['er']['raw']}", m["er"]["index"], T.GREEN)
    y -= bar_h + 26

    K.hline(c, x, x + w, y, color=T.LINE)
    y -= 28

    K.draw_label(c, x, y, "KEY TAKEAWAYS", size=7.6)
    y -= 20
    for i, tk in enumerate(model["key_takeaways"]):
        c.setFont(T.FONT_BLACK, 11)
        c.setFillColor(HexColor(T.LINE))
        c.drawString(x, y, f"{i+1:02d}")
        y = K.draw_paragraph(c, x + 26, y, tk, T.FONT_REG, 8.6, 11.6, w - 26, color=T.TEXT_MUTED)
        y -= 10

    y -= 12
    K.hline(c, x, x + w, y, color=T.LINE)
    y -= 24

    K.draw_label(c, x, y, "METHODOLOGY", size=7.6)
    y -= 20
    meth_w = (w - 24) / 3
    items = [
        ("VPI", "Vertical Power Index", "Uphill efficiency on steep climbing terrain.", T.CYAN),
        ("DMI", "Descent Mastery Index", "Downhill speed and technical efficiency.", T.ORANGE),
        ("ER", "Endurance Rating", "Terrain-adjusted endurance and fatigue resistance.", T.GREEN),
    ]
    for i, (code, name, desc, col) in enumerate(items):
        mx = x + i * (meth_w + 12)
        c.setFont(T.FONT_BOLD, 11)
        c.setFillColor(HexColor(col))
        c.drawString(mx, y, code)
        c.setFont(T.FONT_SEMIBOLD, 7.6)
        c.setFillColor(HexColor(T.TEXT))
        c.drawString(mx, y - 13, name)
        c.setFont(T.FONT_REG, 7.2)
        c.setFillColor(HexColor(T.TEXT_MUTED))
        for li, line in enumerate(K.wrap_text(c, desc, T.FONT_REG, 7.2, meth_w)):
            c.drawString(mx, y - 26 - li * 9.5, line)

    y -= 58
    K.hline(c, x, x + w, y, color=T.LINE_SOFT)
    y -= 14
    c.setFont(T.FONT_REG, 6.8)
    c.setFillColor(HexColor(T.TEXT_FAINT))
    c.drawString(x, y, "Raw metrics retain their original units. Normalized indices are used for visual comparison.")

    c.setFont(T.FONT_BOLD, 9)
    c.setFillColor(HexColor(T.TEXT))
    c.drawRightString(x + w, y + 2, "STOP GUESSING, START MEASURING.")

    K.draw_footer(c, data["athlete"]["name"], data["race"]["name"])


# ================================================================= main
def build(data_path, out_path):
    with open(data_path) as f:
        data = json.load(f)
    model = I.build_report_model(data)

    register_fonts()
    c = canvas.Canvas(out_path, pagesize=(T.PAGE_W, T.PAGE_H))
    c.setTitle(f"{data['athlete']['name']} — {data['race']['name']} — VertLabs Athlete Report")
    c.setAuthor("Vertical Trail Labs")

    page1(c, data, model); c.showPage()
    page2(c, data, model); c.showPage()
    page3(c, data, model); c.showPage()
    page4(c, data, model); c.showPage()

    c.save()
    print("written", out_path)


if __name__ == "__main__":
    data_path = sys.argv[1] if len(sys.argv) > 1 else "data/wayne_walsh_lavaredo120k_2026.json"
    out_path = sys.argv[2] if len(sys.argv) > 2 else "output/report.pdf"
    build(data_path, out_path)
