"""
SACS (Simple Automated Cashflow System) PDF Generator
Matches the actual Windbrook Solutions template:
  - INFLOW circle (green)     — top-left
  - OUTFLOW circle (red)      — top-right
  - PRIVATE RESERVE (blue)    — bottom-center
  - Red filled arrow          — INFLOW → OUTFLOW (labelled with outflow amount)
  - Blue L-shaped arrow       — INFLOW ↓→ PRIVATE RESERVE (labelled with excess)
"""
import math
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.lib.colors import HexColor, white
from reportlab.pdfgen import canvas as rl_canvas

# ── Colours ───────────────────────────────────────────────────────────────────
GREEN_MAIN  = HexColor("#4CAF50")
GREEN_DARK  = HexColor("#2E7D32")
GREEN_ARROW = HexColor("#388E3C")
RED_MAIN    = HexColor("#E53935")
RED_DARK    = HexColor("#B71C1C")
BLUE_MAIN   = HexColor("#1976D2")
BLUE_DARK   = HexColor("#0D47A1")
BLUE_ARROW  = HexColor("#1565C0")
NAVY        = HexColor("#0F2846")
GRAY_TEXT   = HexColor("#374151")
GRAY_LIGHT  = HexColor("#9CA3AF")


def _fmt(n: float) -> str:
    return f"${n:,.0f}"


# ── Path helpers ──────────────────────────────────────────────────────────────

def _circle_path(p, cx, cy, r):
    """Approximate a circle with 4 bezier curves (standard k=0.5523 method)."""
    k = 0.5523
    p.moveTo(cx + r, cy)
    p.curveTo(cx + r,   cy + r*k, cx + r*k, cy + r,   cx,     cy + r)
    p.curveTo(cx - r*k, cy + r,   cx - r,   cy + r*k, cx - r, cy)
    p.curveTo(cx - r,   cy - r*k, cx - r*k, cy - r,   cx,     cy - r)
    p.curveTo(cx + r*k, cy - r,   cx + r,   cy - r*k, cx + r, cy)
    p.close()


# ── Drawing primitives ────────────────────────────────────────────────────────

def _draw_cash_circle(c, cx, cy, r, main_color, floor_color,
                      lines, amount_str, show_floor=True):
    """
    Draw a SACS-style cash circle.
    lines      — list of label strings (e.g. ["INFLOW"] or ["PRIVATE","RESERVE"])
    amount_str — dollar amount shown in white box inside circle
    show_floor — whether to draw the darker floor section
    """
    # Main circle
    c.setFillColor(main_color)
    c.circle(cx, cy, r, fill=1, stroke=0)

    if show_floor:
        # Darker floor section (bottom ~28% of diameter)
        c.saveState()
        clip = c.beginPath()
        _circle_path(clip, cx, cy, r)
        c.clipPath(clip, fill=0, stroke=0)
        floor_h = r * 0.30
        c.setFillColor(floor_color)
        c.rect(cx - r - 1, cy - r - 1, 2 * r + 2, floor_h + 1, fill=1, stroke=0)
        c.restoreState()

        # Dividing line
        floor_top_y = cy - r + r * 0.30
        half_chord  = math.sqrt(max(0, r**2 - (floor_top_y - cy)**2))
        c.setStrokeColor(floor_color)
        c.setLineWidth(0.8)
        c.line(cx - half_chord, floor_top_y, cx + half_chord, floor_top_y)

        # "$1,000 Floor" text
        floor_mid_y = cy - r + (r * 0.30) / 2 - 5
        c.setFillColor(white)
        c.setFont("Helvetica-Oblique", 9)
        c.drawCentredString(cx, floor_mid_y, "$1,000 Floor")

    # Label lines (top portion of circle)
    total_lines = len(lines)
    top_y       = cy + r * 0.55
    line_gap    = 22 if total_lines > 1 else 0
    start_y     = top_y + (total_lines - 1) * line_gap / 2
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 20 if r >= 95 else 16)
    for i, ln in enumerate(lines):
        c.drawCentredString(cx, start_y - i * line_gap, ln)

    # White amount box
    box_w = r * 1.4
    box_h = r * 0.36
    box_x = cx - box_w / 2
    box_y = cy - r * 0.25
    c.setFillColor(white)
    c.roundRect(box_x, box_y, box_w, box_h, 6, fill=1, stroke=0)
    c.setFillColor(main_color)
    c.setFont("Helvetica-Bold", 20 if r >= 95 else 16)
    c.drawCentredString(cx, box_y + box_h * 0.22, amount_str)


def _draw_down_arrow(c, cx, tip_y, shaft_len, color):
    """Solid downward arrow pointing into a circle."""
    sw, hw, hh = 16, 32, 22
    top_y = tip_y + hh + shaft_len
    c.setFillColor(color)
    p = c.beginPath()
    p.moveTo(cx - sw/2, top_y)
    p.lineTo(cx + sw/2, top_y)
    p.lineTo(cx + sw/2, tip_y + hh)
    p.lineTo(cx + hw/2, tip_y + hh)
    p.lineTo(cx,        tip_y)
    p.lineTo(cx - hw/2, tip_y + hh)
    p.lineTo(cx - sw/2, tip_y + hh)
    p.close()
    c.drawPath(p, fill=1, stroke=0)


def _draw_right_arrow(c, x1, x2, cy, shaft_h, color, label, sublabel=None):
    """Solid right-pointing arrow with label."""
    hh = shaft_h        # half-height of shaft
    hw = shaft_h * 2.2  # horizontal length of arrowhead
    sx = x2 - hw        # x where arrowhead starts

    c.setFillColor(color)
    p = c.beginPath()
    p.moveTo(x1, cy + hh)
    p.lineTo(sx, cy + hh)
    p.lineTo(sx, cy + hh * 2.2)
    p.lineTo(x2, cy)
    p.lineTo(sx, cy - hh * 2.2)
    p.lineTo(sx, cy - hh)
    p.lineTo(x1, cy - hh)
    p.close()
    c.drawPath(p, fill=1, stroke=0)

    # Label inside shaft
    mid_x = (x1 + sx) / 2
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(mid_x, cy - 5, label)

    if sublabel:
        c.setFillColor(GRAY_TEXT)
        c.setFont("Helvetica-Oblique", 8)
        c.drawCentredString(mid_x, cy - hh - 14, sublabel)


def _draw_l_arrow(c, vert_x, top_y, corner_y, end_x, color, label):
    """
    Hollow L-shaped arrow:
      — goes DOWN from (vert_x, top_y) to (vert_x, corner_y)
      — turns RIGHT to (end_x, corner_y) with arrowhead
    """
    t  = 14    # pipe thickness (half)
    aw = 20    # arrowhead horizontal length
    ah = 22    # arrowhead half-width

    c.setFillColor(color)
    p = c.beginPath()
    # Outer contour going clockwise:
    p.moveTo(vert_x - t, top_y)              # top-left of vertical
    p.lineTo(vert_x - t, corner_y + t)       # bottom-left outer
    p.lineTo(end_x - aw, corner_y + t)       # right end of bottom
    p.lineTo(end_x - aw, corner_y + ah)      # arrowhead bottom wing
    p.lineTo(end_x,      corner_y)           # arrowhead tip
    p.lineTo(end_x - aw, corner_y - ah)      # arrowhead top wing
    p.lineTo(end_x - aw, corner_y - t)       # right end of top
    p.lineTo(vert_x + t, corner_y - t)       # inner corner
    p.lineTo(vert_x + t, top_y)              # top-right of vertical
    p.close()
    c.drawPath(p, fill=1, stroke=0)

    # Label below the horizontal segment
    mid_x = (vert_x + (end_x - aw)) / 2
    c.setFillColor(color)
    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(mid_x, corner_y - t - 13, label)


# ── Public API ────────────────────────────────────────────────────────────────

def generate_sacs_pdf(client, report, calculations: dict) -> bytes:
    """
    Generate the SACS PDF matching the actual template.

    Args:
        client        — SQLAlchemy Client ORM object
        report        — SQLAlchemy Report ORM object (has .inflow, .outflow,
                        .private_reserve_balance, .quarter, .year, .report_date)
        calculations  — dict from calculations.calculate_report()
    """
    buf = BytesIO()
    W, H = letter  # 612 × 792
    c   = rl_canvas.Canvas(buf, pagesize=letter)

    excess     = calculations["excess"]
    pr_target  = calculations["private_reserve_target"]
    pr_balance = report.private_reserve_balance

    full_name = f"{client.first_name} {client.last_name}"
    if client.is_married and client.spouse_first_name:
        full_name += f" & {client.spouse_first_name} {client.spouse_last_name}"

    # ── Page white background ─────────────────────────────────────────────────
    c.setFillColor(white)
    c.rect(0, 0, W, H, fill=1, stroke=0)

    # ── Header ────────────────────────────────────────────────────────────────
    # Green $ icon
    c.setFillColor(GREEN_MAIN)
    c.setFont("Helvetica-Bold", 38)
    c.drawString(22, H - 52, "$")

    # Title
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 20)
    c.drawCentredString(W / 2, H - 36, "Simple Automated Cashflow System (SACS)")

    # Client name subtitle
    c.setFont("Helvetica-Bold", 13)
    c.setFillColor(GRAY_TEXT)
    c.drawCentredString(W / 2, H - 57, full_name)

    # Salary labels (green, top-left)
    c.setFillColor(GREEN_MAIN)
    c.setFont("Helvetica", 9)
    c.drawString(22, H - 74, f"{_fmt(report.inflow)} — Monthly Inflow")
    c.drawString(22, H - 88, f"{_fmt(report.outflow)} — Monthly Outflow")

    # "X = Monthly Expenses" annotation (top-right)
    c.setFillColor(GRAY_TEXT)
    c.setFont("Helvetica", 8)
    c.drawRightString(W - 22, H - 58, "X = Monthly Expenses")

    # Quarter / date (top-right lower)
    c.setFillColor(GRAY_LIGHT)
    c.setFont("Helvetica", 8)
    c.drawRightString(W - 22, H - 72, f"{report.quarter} {report.year}  |  {report.report_date}")

    # Divider
    c.setStrokeColor(HexColor("#E5E7EB"))
    c.setLineWidth(0.8)
    c.line(18, H - 96, W - 18, H - 96)

    # ── Circle geometry ───────────────────────────────────────────────────────
    r    = 100   # radius for INFLOW / OUTFLOW
    r_pr = 85    # radius for PRIVATE RESERVE

    cy_top = 480  # y-centre for INFLOW / OUTFLOW
    cy_bot = 245  # y-centre for PRIVATE RESERVE

    cx_in  = 162         # INFLOW centre-x
    cx_out = W - 162     # OUTFLOW centre-x  (= 450)
    cx_pr  = W / 2       # PRIVATE RESERVE centre-x (= 306)

    # ── Green down-arrow into INFLOW ──────────────────────────────────────────
    _draw_down_arrow(c, cx_in, cy_top + r + 2, 38, GREEN_ARROW)

    # ── INFLOW circle ─────────────────────────────────────────────────────────
    _draw_cash_circle(c, cx_in, cy_top, r, GREEN_MAIN, GREEN_DARK,
                      ["INFLOW"], _fmt(report.inflow), show_floor=True)

    # ── OUTFLOW circle ────────────────────────────────────────────────────────
    _draw_cash_circle(c, cx_out, cy_top, r, RED_MAIN, RED_DARK,
                      ["OUTFLOW"], _fmt(report.outflow), show_floor=True)

    # ── Red filled arrow INFLOW → OUTFLOW ─────────────────────────────────────
    ax1 = cx_in  + r + 10
    ax2 = cx_out - r - 10
    _draw_right_arrow(c, ax1, ax2, cy_top, 16, RED_MAIN,
                      f"X = {_fmt(report.outflow)}/month*",
                      "Automated transfer on the 28th")

    # ── PRIVATE RESERVE circle ────────────────────────────────────────────────
    _draw_cash_circle(c, cx_pr, cy_bot, r_pr, BLUE_MAIN, BLUE_DARK,
                      ["PRIVATE", "RESERVE"], _fmt(pr_balance), show_floor=False)

    # ── Blue L-arrow INFLOW ↓→ PRIVATE RESERVE ───────────────────────────────
    lx  = cx_in - 36                 # x of vertical segment (left of INFLOW)
    ly0 = cy_top - r - 10            # top of vertical (just below INFLOW)
    lye = cy_bot                     # corner / end y (level with PR centre)
    lx2 = cx_pr - r_pr - 10         # end x (left edge of PR circle)
    _draw_l_arrow(c, lx, ly0, lye, lx2, BLUE_ARROW,
                  f"{_fmt(excess)}/mo*")

    # ── "MONTHLY CASHFLOW" label below PRIVATE RESERVE ───────────────────────
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 13)
    c.drawCentredString(cx_pr, cy_bot - r_pr - 22, "MONTHLY CASHFLOW")

    # Dashed vertical line below label (matches template detail)
    c.setStrokeColor(GRAY_LIGHT)
    c.setLineWidth(0.6)
    c.setDash(3, 3)
    c.line(cx_pr, cy_bot - r_pr - 36, cx_pr, cy_bot - r_pr - 70)
    c.setDash()

    # ── Summary strip at bottom ───────────────────────────────────────────────
    strip_y = 48
    strip_h = 44
    c.setFillColor(HexColor("#F8FAFC"))
    c.setStrokeColor(HexColor("#E5E7EB"))
    c.setLineWidth(0.5)
    c.rect(18, strip_y, W - 36, strip_h, fill=1, stroke=1)

    col_w = (W - 36) / 3
    items = [
        ("Monthly Excess",        _fmt(excess),     GREEN_MAIN if excess >= 0 else RED_MAIN),
        ("Private Reserve",       _fmt(pr_balance),  BLUE_MAIN),
        ("Target",                _fmt(pr_target),   NAVY),
    ]
    for i, (lbl, val, col) in enumerate(items):
        x = 18 + col_w * i + col_w / 2
        c.setFillColor(GRAY_TEXT)
        c.setFont("Helvetica", 7)
        c.drawCentredString(x, strip_y + strip_h - 14, lbl)
        c.setFillColor(col)
        c.setFont("Helvetica-Bold", 11)
        c.drawCentredString(x, strip_y + 8, val)

    # Vertical separators in strip
    c.setStrokeColor(HexColor("#E5E7EB"))
    c.setLineWidth(0.5)
    for i in (1, 2):
        sx = 18 + col_w * i
        c.line(sx, strip_y + 4, sx, strip_y + strip_h - 4)

    # ── Footer ────────────────────────────────────────────────────────────────
    c.setFillColor(GRAY_LIGHT)
    c.setFont("Helvetica", 7)
    c.drawCentredString(W / 2, 26,
        f"Windbrook Solutions  |  {full_name}  |  {report.quarter} {report.year}  |  Confidential")
    c.drawCentredString(W / 2, 14, "* Amounts may be rounded. Floor = $1,000 minimum maintained in each account.")

    c.save()
    return buf.getvalue()
