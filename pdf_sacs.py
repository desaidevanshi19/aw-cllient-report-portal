"""
SACS (Simple Automated Cash Flow System) PDF Generator
Produces a 2-page PDF:
  Page 1 — Cash flow bubble diagram  (Inflow → Outflow → Private Reserve)
  Page 2 — Private Reserve summary detail
"""
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.lib.colors import HexColor, white, black
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph
from reportlab.pdfbase import pdfmetrics

# ── Brand colours ─────────────────────────────────────────────────────────────
NAVY       = HexColor("#0F2846")
GREEN      = HexColor("#16A34A")
GREEN_LIGHT= HexColor("#DCFCE7")
GREEN_DARK = HexColor("#15803D")
RED        = HexColor("#DC2626")
RED_LIGHT  = HexColor("#FEE2E2")
RED_DARK   = HexColor("#B91C1C")
BLUE       = HexColor("#2563EB")
BLUE_LIGHT = HexColor("#DBEAFE")
BLUE_DARK  = HexColor("#1D4ED8")
GRAY_LIGHT = HexColor("#F3F4F6")
GRAY_MID   = HexColor("#9CA3AF")
GRAY_DARK  = HexColor("#374151")
BORDER     = HexColor("#E5E7EB")


def _fmt(n: float) -> str:
    """Format number as currency string."""
    return f"${n:,.0f}"


def _draw_header(c: rl_canvas.Canvas, client, report, width: float, height: float):
    """Dark navy header bar at the top of every page."""
    bar_h = 56
    c.setFillColor(NAVY)
    c.rect(0, height - bar_h, width, bar_h, fill=1, stroke=0)

    # Company name (left)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(24, height - 22, "Windbrook Solutions")
    c.setFont("Helvetica", 8)
    c.setFillColor(HexColor("#93C5FD"))
    c.drawString(24, height - 38, "Confidential — Not for Distribution")

    # Client name (centre)
    full_name = f"{client.first_name} {client.last_name}"
    if client.is_married and client.spouse_first_name:
        full_name += f" & {client.spouse_first_name} {client.spouse_last_name}"
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(width / 2, height - 26, full_name)

    # Quarter / date (right)
    c.setFont("Helvetica-Bold", 11)
    c.drawRightString(width - 24, height - 22, f"{report.quarter} {report.year}")
    c.setFont("Helvetica", 8)
    c.setFillColor(HexColor("#93C5FD"))
    c.drawRightString(width - 24, height - 38, f"Report Date: {report.report_date}")


def _draw_bubble(
    c: rl_canvas.Canvas,
    cx: float, cy: float, r: float,
    fill_color, border_color,
    label: str, amount: str,
    sub_label: str = "",
):
    """Draw a coloured circle with centred label and amount."""
    # Shadow
    c.setFillColor(HexColor("#D1D5DB"))
    c.circle(cx + 3, cy - 3, r, fill=1, stroke=0)
    # Main circle
    c.setFillColor(fill_color)
    c.setStrokeColor(border_color)
    c.setLineWidth(2)
    c.circle(cx, cy, r, fill=1, stroke=1)
    # Label
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(cx, cy + r * 0.25, label)
    # Amount
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(cx, cy - r * 0.10, amount)
    # Sub-label
    if sub_label:
        c.setFont("Helvetica", 8)
        c.setFillColor(HexColor("#BFDBFE") if fill_color == BLUE else HexColor("#FCA5A5") if fill_color == RED else HexColor("#86EFAC"))
        c.drawCentredString(cx, cy - r * 0.38, sub_label)


def _draw_arrow(c: rl_canvas.Canvas, x1, y, x2, color, label="", strikethrough=False):
    """Horizontal arrow between two x positions."""
    c.setStrokeColor(color)
    c.setFillColor(color)
    c.setLineWidth(3)
    c.line(x1, y, x2 - 8, y)
    # Arrowhead
    p = c.beginPath()
    p.moveTo(x2, y)
    p.lineTo(x2 - 10, y + 5)
    p.lineTo(x2 - 10, y - 5)
    p.close()
    c.drawPath(p, fill=1, stroke=0)
    if label:
        c.setFont("Helvetica-Bold", 8)
        mid = (x1 + x2) / 2
        c.drawCentredString(mid, y + 7, label)
    if strikethrough:
        # Red X
        c.setStrokeColor(RED_DARK)
        c.setLineWidth(2)
        mid = (x1 + x2) / 2
        c.line(mid - 8, y - 8, mid + 8, y + 8)
        c.line(mid + 8, y - 8, mid - 8, y + 8)


def _draw_summary_box(c: rl_canvas.Canvas, x, y, w, h, title, rows):
    """
    Draw a grey summary card.
    rows = list of (label, value, value_color)
    """
    c.setFillColor(GRAY_LIGHT)
    c.setStrokeColor(BORDER)
    c.setLineWidth(1)
    c.roundRect(x, y, w, h, 6, fill=1, stroke=1)
    # Title bar
    c.setFillColor(NAVY)
    c.roundRect(x, y + h - 26, w, 26, 6, fill=1, stroke=0)
    # Clip the bottom corners of title bar
    c.setFillColor(NAVY)
    c.rect(x, y + h - 26, w, 13, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(x + w / 2, y + h - 17, title.upper())
    # Rows
    row_h = (h - 32) / max(len(rows), 1)
    for i, (label, value, vcolor) in enumerate(rows):
        ry = y + h - 32 - (i + 1) * row_h + row_h * 0.3
        c.setFillColor(GRAY_DARK)
        c.setFont("Helvetica", 8)
        c.drawString(x + 10, ry, label)
        c.setFillColor(vcolor if vcolor else GRAY_DARK)
        c.setFont("Helvetica-Bold", 9)
        c.drawRightString(x + w - 10, ry, value)


# ── Public API ────────────────────────────────────────────────────────────────

def generate_sacs_pdf(client, report, calculations: dict) -> bytes:
    """
    Generate the SACS PDF and return raw bytes.

    Args:
        client  — SQLAlchemy Client ORM object
        report  — SQLAlchemy Report ORM object
        calculations — dict from calculations.calculate_report()
    """
    buf = BytesIO()
    W, H = letter  # 612 × 792
    c = rl_canvas.Canvas(buf, pagesize=letter)

    excess     = calculations["excess"]
    pr_target  = calculations["private_reserve_target"]
    pr_balance = report.private_reserve_balance

    # ── PAGE 1: Cash Flow Diagram ─────────────────────────────────────────────
    _draw_header(c, client, report, W, H)

    # Section title
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(W / 2, H - 80, "Simple Automated Cash Flow System")
    c.setFillColor(GRAY_MID)
    c.setFont("Helvetica", 9)
    c.drawCentredString(W / 2, H - 96, "Monthly Cash Flow Overview")

    # Divider
    c.setStrokeColor(BORDER)
    c.setLineWidth(1)
    c.line(40, H - 104, W - 40, H - 104)

    # Three main bubbles
    bubble_y = H - 290
    bubble_r = 82
    spacing  = 170
    cx1 = W / 2 - spacing        # Inflow
    cx2 = W / 2                  # Outflow
    cx3 = W / 2 + spacing        # Private Reserve

    _draw_bubble(c, cx1, bubble_y, bubble_r, GREEN, GREEN_DARK,
                 "MONTHLY INFLOW", _fmt(report.inflow), "Monthly Salary")

    _draw_bubble(c, cx2, bubble_y, bubble_r, RED, RED_DARK,
                 "MONTHLY OUTFLOW", _fmt(report.outflow), "Expense Budget")

    _draw_bubble(c, cx3, bubble_y, bubble_r, BLUE, BLUE_DARK,
                 "PRIVATE RESERVE", _fmt(pr_balance), "Current Balance")

    # Arrows
    gap = 10
    _draw_arrow(c, cx1 + bubble_r + gap, bubble_y + 12, cx2 - bubble_r - gap, GREEN,
                label="Salary Deposit")
    _draw_arrow(c, cx2 + bubble_r + gap, bubble_y + 12, cx3 - bubble_r - gap, BLUE,
                label=f"Excess {_fmt(excess)}")
    # Strike-through on outflow arrow (money going out)
    _draw_arrow(c, cx1 + bubble_r + gap, bubble_y - 12, cx2 - bubble_r - gap, RED,
                strikethrough=True)

    # Floor note
    c.setFillColor(GRAY_MID)
    c.setFont("Helvetica-Oblique", 8)
    c.drawCentredString(W / 2, bubble_y - bubble_r - 22,
                        "* $1,000 floor balance maintained in each bank account")

    # ── Summary cards (lower section) ────────────────────────────────────────
    card_y  = 80
    card_h  = 150
    card_w  = 160
    gap_c   = 20
    total_w = 3 * card_w + 2 * gap_c
    start_x = (W - total_w) / 2

    excess_color = GREEN if excess >= 0 else RED
    excess_str   = (f"+{_fmt(excess)}" if excess >= 0 else _fmt(excess))

    _draw_summary_box(c, start_x, card_y, card_w, card_h, "Cash Flow", [
        ("Monthly Inflow",  _fmt(report.inflow),   GREEN),
        ("Monthly Outflow", _fmt(report.outflow),  RED),
        ("Monthly Excess",  excess_str,             excess_color),
    ])

    _draw_summary_box(c, start_x + card_w + gap_c, card_y, card_w, card_h, "Private Reserve", [
        ("Current Balance", _fmt(pr_balance),      BLUE),
        ("Target Balance",  _fmt(pr_target),       NAVY),
        ("Status", "✓ On Track" if pr_balance >= pr_target else "Below Target",
         GREEN if pr_balance >= pr_target else RED),
    ])

    _draw_summary_box(c, start_x + 2 * (card_w + gap_c), card_y, card_w, card_h, "Annualised", [
        ("Annual Inflow",   _fmt(report.inflow * 12),  GREEN),
        ("Annual Outflow",  _fmt(report.outflow * 12), RED),
        ("Annual Excess",   _fmt(excess * 12),          excess_color),
    ])

    # Footer
    c.setFillColor(GRAY_MID)
    c.setFont("Helvetica", 7)
    c.drawCentredString(W / 2, 28,
        f"Windbrook Solutions  |  {client.first_name} {client.last_name}  |  "
        f"{report.quarter} {report.year}  |  Confidential")

    # ── PAGE 2: Private Reserve Detail ───────────────────────────────────────
    c.showPage()
    _draw_header(c, client, report, W, H)

    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(W / 2, H - 80, "Private Reserve Detail")
    c.setStrokeColor(BORDER)
    c.line(40, H - 94, W - 40, H - 94)

    detail_rows = [
        ("Monthly Inflow (take-home salary)",    _fmt(report.inflow),     GRAY_DARK),
        ("Monthly Outflow (agreed expense budget)", _fmt(report.outflow),  GRAY_DARK),
        ("Monthly Excess (Inflow – Outflow)",    excess_str,               excess_color),
        ("",                                      "",                       GRAY_DARK),
        ("Private Reserve Current Balance",       _fmt(pr_balance),         BLUE),
        ("Private Reserve Target (6× expenses)",  _fmt(pr_target),          NAVY),
        ("Difference (Balance – Target)",
            _fmt(pr_balance - pr_target),
            GREEN if pr_balance >= pr_target else RED),
    ]

    row_y = H - 130
    for label, value, vcolor in detail_rows:
        if not label:
            c.setStrokeColor(BORDER)
            c.line(60, row_y + 8, W - 60, row_y + 8)
            row_y -= 14
            continue
        c.setFillColor(GRAY_DARK)
        c.setFont("Helvetica", 10)
        c.drawString(60, row_y, label)
        c.setFillColor(vcolor)
        c.setFont("Helvetica-Bold", 10)
        c.drawRightString(W - 60, row_y, value)
        row_y -= 28

    # Large target progress bar
    bar_x, bar_y, bar_w, bar_bh = 60, row_y - 60, W - 120, 28
    pct = min(pr_balance / pr_target, 1.0) if pr_target > 0 else 0
    c.setFillColor(GRAY_LIGHT)
    c.setStrokeColor(BORDER)
    c.roundRect(bar_x, bar_y, bar_w, bar_bh, 4, fill=1, stroke=1)
    c.setFillColor(GREEN if pct >= 1.0 else BLUE)
    c.roundRect(bar_x, bar_y, bar_w * pct, bar_bh, 4, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(bar_x + bar_w / 2, bar_y + 9, f"{pct * 100:.0f}% funded")

    # Footer
    c.setFillColor(GRAY_MID)
    c.setFont("Helvetica", 7)
    c.drawCentredString(W / 2, 28,
        f"Windbrook Solutions  |  {client.first_name} {client.last_name}  |  "
        f"{report.quarter} {report.year}  |  Confidential")

    c.save()
    return buf.getvalue()
