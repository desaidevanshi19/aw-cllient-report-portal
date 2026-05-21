"""
TCC (Total Client Chart) PDF Generator — Faithful to the actual template.

Layout (landscape letter: 792 × 612):
  ┌─────────────────────────────────────────────────────────────────────┐
  │ NAME: ___   DATE: ___                                               │
  ├──────────────────────┬──────────────────┬──────────────────────────┤
  │  [C1 Ret Total box]  │  GRAND TOTAL box │  [C2 Ret Total box]      │
  │  [Client 1 oval]     │  [Liab summ box] │  [Client 2 oval]         │
  │  account ovals …     │                  │  account ovals …         │
  │  RETIREMENT          │                  │  RETIREMENT              │
  ├──────────────────────┤──────────────────┤──────────────────────────┤
  │  NON RETIREMENT      │  [Trust oval]    │  NON RETIREMENT          │
  │  account ovals …     │  [Liab detail]   │  bank account ovals …    │
  │                      │  [Non-Ret Total] │                          │
  └──────────────────────┴──────────────────┴──────────────────────────┘
"""
from io import BytesIO
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.colors import HexColor, white, black
from reportlab.pdfgen import canvas as rl_canvas

# ── Colours (matching real template) ─────────────────────────────────────────
GREEN_OVAL   = HexColor("#5A8A3C")   # client circle fill
GREEN_BORDER = HexColor("#3A6A20")   # client circle border / account oval border
GREEN_LIGHT  = HexColor("#8DB86B")   # lighter green for account border
CHARCOAL     = HexColor("#404040")   # dark summary boxes
LIAB_GRAY    = HexColor("#B0B0B0")   # liabilities box fill
LIAB_BORDER  = HexColor("#888888")
RED_NOTE     = HexColor("#CC0000")
TEXT_DARK    = HexColor("#1A1A1A")
TEXT_MID     = HexColor("#444444")
TEXT_LIGHT   = HexColor("#888888")
PAGE_BG      = HexColor("#FFFFFF")
BORDER_LINE  = HexColor("#CCCCCC")


ACCT_LABELS = {
    "ira": "IRA", "roth_ira": "ROTH IRA", "401k": "401K", "pension": "Pension",
    "brokerage": "Brokerage", "joint": "Schwab JT TEN", "checking": "Checking",
    "savings": "Savings", "trust": "Family Trust", "mortgage": "Mortgage",
    "auto_loan": "Auto Loan", "other": "Other",
}


def _fmt(n: float) -> str:
    return f"${n:,.2f}"


def _fmt0(n: float) -> str:
    return f"${n:,.0f}"


# ── Drawing primitives ────────────────────────────────────────────────────────

def _oval(c, cx, cy, rw, rh, fill_color, border_color, lw=1.5):
    """Draw a filled ellipse centred at (cx, cy)."""
    c.setFillColor(fill_color)
    c.setStrokeColor(border_color)
    c.setLineWidth(lw)
    c.ellipse(cx - rw, cy - rh, cx + rw, cy + rh, fill=1, stroke=1)


def _client_oval(c, cx, cy, rw, rh, label, name, age, dob, ssn_last4):
    """Green filled client info oval."""
    _oval(c, cx, cy, rw, rh, GREEN_OVAL, GREEN_BORDER, lw=2.5)
    # Label (e.g. "Client 1")
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(cx, cy + rh * 0.45, label)
    # Name / details
    c.setFont("Helvetica", 7)
    line_h = rh * 0.28
    c.drawCentredString(cx, cy + rh * 0.10, f"Age")
    c.drawCentredString(cx, cy - rh * 0.15, f"DOB")
    c.drawCentredString(cx, cy - rh * 0.40, f"SSN")
    c.setFont("Helvetica-Bold", 7)
    c.drawCentredString(cx, cy + rh * 0.10 - 9, age or "—")
    c.drawCentredString(cx, cy - rh * 0.15 - 9, dob or "—")
    c.drawCentredString(cx, cy - rh * 0.40 - 9, f"···{ssn_last4}" if ssn_last4 else "—")


def _account_oval(c, cx, cy, rw, rh, acct_name, last4, balance, report_date,
                  cash_bal=None, stale=False):
    """White oval with green border — one account."""
    _oval(c, cx, cy, rw, rh, white, GREEN_LIGHT, lw=1.2)

    # ACCT # header
    c.setFillColor(TEXT_MID)
    c.setFont("Helvetica", 6)
    acct_str = f"ACCT # {last4}" if last4 else "ACCT #"
    c.drawCentredString(cx, cy + rh * 0.60, acct_str)

    # Account name
    c.setFont("Helvetica-Bold", 7.5)
    c.setFillColor(TEXT_DARK)
    # Word-wrap simple: if name > 16 chars split
    words = acct_name.split()
    if len(acct_name) <= 16 or len(words) <= 1:
        c.drawCentredString(cx, cy + rh * 0.28, acct_name)
        name_bottom = cy + rh * 0.28
    else:
        mid = len(words) // 2
        l1 = " ".join(words[:mid])
        l2 = " ".join(words[mid:])
        c.drawCentredString(cx, cy + rh * 0.42, l1)
        c.drawCentredString(cx, cy + rh * 0.18, l2)
        name_bottom = cy + rh * 0.18

    # Balance
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(TEXT_DARK)
    bal_y = name_bottom - 14
    bal_str = _fmt(balance) + (" *" if stale else "")
    c.drawCentredString(cx, bal_y, bal_str)

    # Date
    c.setFont("Helvetica", 6)
    c.setFillColor(TEXT_LIGHT)
    c.drawCentredString(cx, bal_y - 10, f"a/o {report_date}")

    # Optional cash sub-circle
    if cash_bal is not None:
        sub_r = min(rw, rh) * 0.30
        sub_cx, sub_cy = cx, cy - rh * 0.62
        _oval(c, sub_cx, sub_cy, sub_r * 1.4, sub_r, white, GREEN_LIGHT, lw=0.8)
        c.setFillColor(TEXT_DARK)
        c.setFont("Helvetica-Bold", 6)
        c.drawCentredString(sub_cx, sub_cy + 2, _fmt0(cash_bal))
        c.setFont("Helvetica", 5.5)
        c.setFillColor(TEXT_LIGHT)
        c.drawCentredString(sub_cx, sub_cy - 7, "Cash")


def _summary_box(c, x, y, w, h, title, amount, text_color=white, fill=CHARCOAL):
    """Dark charcoal summary pill."""
    c.setFillColor(fill)
    c.setStrokeColor(HexColor("#2A2A2A"))
    c.setLineWidth(0.5)
    c.roundRect(x, y, w, h, 4, fill=1, stroke=1)
    c.setFillColor(text_color)
    c.setFont("Helvetica", 7)
    c.drawCentredString(x + w / 2, y + h - 13, title)
    c.setFont("Helvetica-Bold", 11)
    c.drawCentredString(x + w / 2, y + 5, amount)


def _liabilities_box(c, x, y, w, h, items):
    """Light gray liabilities detail box."""
    c.setFillColor(HexColor("#D8D8D8"))
    c.setStrokeColor(LIAB_BORDER)
    c.setLineWidth(0.8)
    c.roundRect(x, y, w, h, 3, fill=1, stroke=1)
    c.setFillColor(TEXT_DARK)
    c.setFont("Helvetica-Bold", 7)
    c.drawString(x + 6, y + h - 12, "Liabilities:")
    row_h = max((h - 16) / max(len(items), 1), 9)
    for i, (name, amount) in enumerate(items):
        ry = y + h - 16 - (i + 0.7) * row_h
        c.setFont("Helvetica", 6.5)
        c.drawString(x + 6, ry, name)
        c.drawRightString(x + w - 6, ry, amount)


def _quad_label(c, x, y, text, align="left"):
    """Small caps quadrant label."""
    c.setFillColor(GREEN_OVAL)
    c.setFont("Helvetica-Bold", 7)
    if align == "right":
        c.drawRightString(x, y, text)
    else:
        c.drawString(x, y, text)


def _place_ovals_in_zone(c, accounts, balances_map, report_date,
                          zone_x, zone_y, zone_w, zone_h,
                          oval_rw=58, oval_rh=48):
    """
    Lay out account ovals in a grid within a zone.
    Returns list of (cx, cy) placed.
    """
    if not accounts:
        return
    n = len(accounts)
    cols = min(n, 3)
    rows = (n + cols - 1) // cols
    cell_w = zone_w / cols
    cell_h = zone_h / rows

    for i, (acc, _) in enumerate(accounts):
        col = i % cols
        row = i // cols
        cx = zone_x + cell_w * (col + 0.5)
        cy = zone_y + zone_h - cell_h * (row + 0.5)
        bal = balances_map.get(acc.id, 0.0)

        cash_bal = None
        for rb in acc.report_balances:
            if hasattr(rb, "cash_balance") and rb.cash_balance is not None:
                cash_bal = rb.cash_balance
                break

        label = acc.account_name or ACCT_LABELS.get(acc.account_type, acc.account_type.upper())
        _account_oval(c, cx, cy, oval_rw, oval_rh,
                      label, acc.last4, bal, report_date,
                      cash_bal=cash_bal)


# ── Public API ────────────────────────────────────────────────────────────────

def generate_tcc_pdf(client, report, balances_by_account_id: dict, calculations: dict) -> bytes:
    """
    Generate the TCC PDF matching the real Windbrook Solutions template.
    Returns raw PDF bytes.
    """
    buf = BytesIO()
    W, H = landscape(letter)   # 792 × 612
    c = rl_canvas.Canvas(buf, pagesize=landscape(letter))

    # ── Sort accounts by category ────────────────────────────────────────────
    c1_ret, c2_ret, non_ret, bank_accts, trusts, liabilities = [], [], [], [], [], []
    for acc in client.accounts:
        bal = balances_by_account_id.get(acc.id, 0.0)
        entry = (acc, bal)
        if acc.category == "retirement":
            (c1_ret if acc.owner == "client1" else c2_ret).append(entry)
        elif acc.category == "non_retirement":
            non_ret.append(entry)
        elif acc.category == "bank":
            bank_accts.append(entry)
        elif acc.category == "trust":
            trusts.append(entry)
        elif acc.category == "liability":
            liabilities.append(entry)

    # ── Page background ──────────────────────────────────────────────────────
    c.setFillColor(white)
    c.rect(0, 0, W, H, fill=1, stroke=0)

    # Outer border
    c.setStrokeColor(BORDER_LINE)
    c.setLineWidth(1)
    c.rect(8, 8, W - 16, H - 16, fill=0, stroke=1)

    # ── Header strip ─────────────────────────────────────────────────────────
    HEADER_H = 38
    c.setFillColor(white)
    c.setFont("Helvetica", 8)
    c.setFillColor(TEXT_DARK)
    c.drawString(16, H - 18, f"NAME     {client.first_name} {client.last_name}")
    c.line(80, H - 19, 220, H - 19)
    c.drawString(16, H - 30, f"DATE     {report.report_date}")
    c.line(80, H - 31, 220, H - 31)

    # ── Zone geometry ────────────────────────────────────────────────────────
    BODY_TOP  = H - HEADER_H        # y of body top  (~574)
    BODY_BOT  = 16                  # y of body bottom
    BODY_H    = BODY_TOP - BODY_BOT # ~558

    CENTER_W  = 190                 # width of center column
    LEFT_W    = (W - CENTER_W) / 2  # ~301
    RIGHT_W   = LEFT_W

    LEFT_X    = 8
    CENTER_X  = LEFT_X + LEFT_W     # ~309
    RIGHT_X   = CENTER_X + CENTER_W # ~499

    H_DIV     = BODY_BOT + BODY_H * 0.48  # horizontal divider y (~284)

    # ── Dividing lines ───────────────────────────────────────────────────────
    c.setStrokeColor(BORDER_LINE)
    c.setLineWidth(0.8)
    # Horizontal
    c.line(LEFT_X, H_DIV, W - 8, H_DIV)
    # Vertical left boundary of center column
    c.line(CENTER_X, BODY_BOT, CENTER_X, BODY_TOP)
    # Vertical right boundary of center column
    c.line(RIGHT_X, BODY_BOT, RIGHT_X, BODY_TOP)

    rdate = report.report_date

    # ── TOP-LEFT: Client 1 retirement ────────────────────────────────────────
    # Quadrant label
    _quad_label(c, LEFT_X + 10, H_DIV + 8, "RETIREMENT")

    # Client 1 oval (positioned upper-center of left quadrant)
    c1_cx = LEFT_X + LEFT_W * 0.52
    c1_cy = BODY_TOP - 75
    _client_oval(c, c1_cx, c1_cy, 65, 56,
                 "Client 1",
                 f"{client.first_name} {client.last_name}",
                 "—", client.dob, client.ssn_last4)

    # Client 1 Retirement Total box (left of client oval)
    box_w, box_h = 130, 38
    _summary_box(c, LEFT_X + 12, c1_cy - box_h / 2 + 8, box_w, box_h,
                 "Client 1 Retirement Only",
                 _fmt(calculations["client1_retirement_total"]))

    # Client 1 account ovals (below client oval, in lower part of top-left quadrant)
    zone1 = dict(
        zone_x=LEFT_X + 8,
        zone_y=H_DIV + 16,
        zone_w=LEFT_W - 16,
        zone_h=(BODY_TOP - 145) - (H_DIV + 16),
        oval_rw=54, oval_rh=44,
    )
    _place_ovals_in_zone(c, c1_ret, balances_by_account_id, rdate, **zone1)

    # ── TOP-RIGHT: Client 2 retirement ───────────────────────────────────────
    _quad_label(c, RIGHT_X + LEFT_W - 10, H_DIV + 8, "RETIREMENT", align="right")

    c2_cx = RIGHT_X + LEFT_W * 0.48
    c2_cy = BODY_TOP - 75
    if client.is_married and client.spouse_first_name:
        _client_oval(c, c2_cx, c2_cy, 65, 56,
                     "Client 2",
                     f"{client.spouse_first_name} {client.spouse_last_name}",
                     "—", client.spouse_dob, client.spouse_ssn_last4)

    # Client 2 Retirement Total box (right of client oval)
    _summary_box(c, RIGHT_X + LEFT_W - 12 - box_w, c2_cy - box_h / 2 + 8,
                 box_w, box_h,
                 "Client 2 Retirement Only",
                 _fmt(calculations["client2_retirement_total"]))

    zone2 = dict(
        zone_x=RIGHT_X + 8,
        zone_y=H_DIV + 16,
        zone_w=RIGHT_W - 16,
        zone_h=(BODY_TOP - 145) - (H_DIV + 16),
        oval_rw=54, oval_rh=44,
    )
    _place_ovals_in_zone(c, c2_ret, balances_by_account_id, rdate, **zone2)

    # ── CENTER-TOP: Grand Total + Liabilities summary ─────────────────────────
    gt_w, gt_h = CENTER_W - 20, 42
    gt_x = CENTER_X + 10
    gt_y = BODY_TOP - gt_h - 12
    _summary_box(c, gt_x, gt_y, gt_w, gt_h,
                 "GRAND TOTAL", _fmt(calculations["grand_total"]))

    # Liabilities summary box (below grand total)
    ls_w, ls_h = CENTER_W - 20, 32
    ls_x = CENTER_X + 10
    ls_y = gt_y - ls_h - 8
    c.setFillColor(HexColor("#C0C0C0"))
    c.setStrokeColor(LIAB_BORDER)
    c.setLineWidth(0.8)
    c.roundRect(ls_x, ls_y, ls_w, ls_h, 3, fill=1, stroke=1)
    c.setFillColor(TEXT_DARK)
    c.setFont("Helvetica", 7)
    c.drawCentredString(CENTER_X + CENTER_W / 2,
                        ls_y + ls_h - 12,
                        f"Liabilities: {_fmt(calculations['liabilities_total'])}")
    c.setFont("Helvetica", 6.5)
    c.setFillColor(TEXT_MID)
    c.drawCentredString(CENTER_X + CENTER_W / 2, ls_y + 6, f"a/o {rdate}")

    # ── BOTTOM-LEFT: Non-retirement accounts ─────────────────────────────────
    _quad_label(c, LEFT_X + 10, H_DIV - 12, "NON RETIREMENT")

    zone3 = dict(
        zone_x=LEFT_X + 8,
        zone_y=BODY_BOT + 8,
        zone_w=LEFT_W - 16,
        zone_h=H_DIV - BODY_BOT - 20,
        oval_rw=54, oval_rh=44,
    )
    _place_ovals_in_zone(c, non_ret, balances_by_account_id, rdate, **zone3)

    # ── BOTTOM-RIGHT: Bank / Pinnacle accounts ────────────────────────────────
    _quad_label(c, RIGHT_X + LEFT_W - 10, H_DIV - 12, "NON RETIREMENT", align="right")

    zone4 = dict(
        zone_x=RIGHT_X + 8,
        zone_y=BODY_BOT + 8,
        zone_w=RIGHT_W - 16,
        zone_h=H_DIV - BODY_BOT - 20,
        oval_rw=54, oval_rh=44,
    )
    _place_ovals_in_zone(c, bank_accts, balances_by_account_id, rdate, **zone4)

    # ── CENTER-BOTTOM: Trust, Liabilities detail, Non-ret total ──────────────
    center_bot_h = H_DIV - BODY_BOT - 16
    center_mid_y = BODY_BOT + center_bot_h / 2 + 8

    # Trust oval (upper center-bottom)
    if trusts:
        trust_acc, trust_bal = trusts[0]
        trust_label = trust_acc.account_name or "Family Trust"
        if client.is_married and client.spouse_first_name:
            trust_label = f"{client.first_name} and\n{client.spouse_first_name}\n{trust_label}"
        t_cx = CENTER_X + CENTER_W / 2
        t_cy = H_DIV - 60
        _oval(c, t_cx, t_cy, 68, 52, white, GREEN_LIGHT, lw=1.2)
        c.setFillColor(TEXT_DARK)
        c.setFont("Helvetica-Bold", 6.5)
        lines = trust_label.split("\n")
        line_y = t_cy + 16 + (len(lines) - 1) * 8
        for ln in lines:
            c.drawCentredString(t_cx, line_y, ln)
            line_y -= 10
        c.setFont("Helvetica-Bold", 8)
        c.drawCentredString(t_cx, t_cy - 14, _fmt(trust_bal))
        c.setFont("Helvetica", 6)
        c.setFillColor(TEXT_LIGHT)
        c.drawCentredString(t_cx, t_cy - 24, f"a/o {rdate}")

    # Liabilities detail box
    if liabilities:
        liab_items = [
            (acc.account_name or ACCT_LABELS.get(acc.account_type, "Liability"),
             _fmt(balances_by_account_id.get(acc.id, 0.0)))
            for acc, _ in liabilities
        ]
        ld_h = min(16 + len(liab_items) * 11, center_bot_h * 0.55)
        ld_w = CENTER_W - 20
        ld_x = CENTER_X + 10
        ld_y = BODY_BOT + 30
        _liabilities_box(c, ld_x, ld_y, ld_w, ld_h, liab_items)

    # Non-retirement total (bottom center)
    nr_w, nr_h = CENTER_W - 20, 28
    nr_x = CENTER_X + 10
    nr_y = BODY_BOT + 8
    _summary_box(c, nr_x, nr_y, nr_w, nr_h,
                 "NON RETIREMENT TOTAL",
                 _fmt(calculations["non_retirement_total"]))

    # ── Footer note ──────────────────────────────────────────────────────────
    c.setFillColor(RED_NOTE)
    c.setFont("Helvetica-Oblique", 6.5)
    c.drawRightString(W - 16, BODY_BOT + 2,
                      "* Indicates we do not have up to date information")

    c.save()
    return buf.getvalue()
