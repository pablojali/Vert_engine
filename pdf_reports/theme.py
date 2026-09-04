"""VertLabs shared visual constants."""

# Brand palette - warm, calm cream (not black, not stark white; see
# 2026-09 feedback: "no quiero un fondo negro, debe ser un color
# tranquilo, tipo crema"). Accent hues keep the same cyan/orange/green
# identity as the dark theme, deepened for legibility on a light page.
BG          = "#F4EFE2"   # page background (warm cream)
PANEL       = "#FBF8F0"   # slightly lifted panel background
LINE        = "#DCD3BC"   # thin borders / dividers
LINE_SOFT   = "#E8E0CC"
TEXT        = "#26241C"   # primary text (warm near-black, not pure black)
TEXT_MUTED  = "#6E6650"
TEXT_FAINT  = "#9A9178"

CYAN   = "#0E7C8A"   # VPI — Vertical Power
ORANGE = "#C96A1F"   # DMI — Descent Mastery
GREEN  = "#2F8F55"   # ER  — Endurance

GRID   = "#E3DAC2"

FONT_REG      = "Inter"
FONT_MED      = "Inter-Medium"
FONT_SEMIBOLD = "Inter-SemiBold"
FONT_BOLD     = "Inter-Bold"
FONT_BLACK    = "Inter-Black"
FONT_MONO     = "JetBrainsMono"

PAGE_W, PAGE_H = 595.28, 841.89  # A4 in points
MARGIN = 42
CONTENT_W = PAGE_W - 2 * MARGIN
