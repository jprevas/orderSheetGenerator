"""
Generates a print-ready PDF that overlays patient info, orders, and a
signature line directly onto the pre-printed "Physician Orders" paper
form, at the coordinates measured in layout.py.

Two render modes:
  - Final (include_background=False): only the dynamic text is drawn.
    This is what you print on the actual pre-printed hospital forms.
  - Preview (include_background=True): the scanned form image is drawn
    behind the text so you can eyeball alignment on screen (e.g. on a
    Mac with no access to the paper stock) before printing for real.
"""

import os

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.pdfbase.pdfmetrics import stringWidth

import layout as L

ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
TEMPLATE_IMAGE_PATH = os.path.join(ASSETS_DIR, "template_preview.png")

SIGNATURE_BLANK = "_" * 34


def _fit_lines(text, max_width, font_name, start_size, min_size=6.0, max_lines=2):
    """Return (font_size, [lines]) so that `text` fits within max_width,
    shrinking font size first, then falling back to wrapping onto up to
    `max_lines` lines at the minimum size."""
    size = start_size
    while size > min_size and stringWidth(text, font_name, size) > max_width:
        size -= 0.5
    if stringWidth(text, font_name, size) <= max_width or max_lines <= 1:
        return size, [text]

    # Word-wrap at the minimum usable size.
    size = max(size, min_size)
    words = text.split(" ")
    lines = []
    current = ""
    for word in words:
        candidate = (current + " " + word).strip()
        if stringWidth(candidate, font_name, size) <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
        if len(lines) == max_lines - 1:
            break
    if current:
        lines.append(current)
    remaining_words = words[len(" ".join(lines).split(" ")):]
    if remaining_words:
        lines[-1] = lines[-1].rstrip() + "..."
    return size, lines[:max_lines]


class OrderLine:
    """One printable row: an order (with date/time) or the signature line."""

    def __init__(self, text, date_str="", time_str="", is_signature=False):
        self.text = text
        self.date_str = date_str
        self.time_str = time_str
        self.is_signature = is_signature


def build_pages(order_lines):
    """Split a flat list of OrderLine into pages of NUM_ROWS each."""
    pages = []
    for i in range(0, len(order_lines), L.NUM_ROWS):
        pages.append(order_lines[i:i + L.NUM_ROWS])
    return pages or [[]]


def generate_pdf(
    out_path,
    patient_name,
    csn,
    physician_name,
    order_texts,
    order_date_str,
    order_time_str,
    include_background=False,
    calibration=None,
):
    """
    order_texts: list of plain-language order strings, already formatted
                 (e.g. "Acetaminophen 650 mg PO", "CT Head w/o Contrast -
                 Indication: r/o bleed"). The signature line is appended
                 automatically.
    """
    cal = calibration or L.load_calibration()

    lines = [OrderLine(t, order_date_str, order_time_str) for t in order_texts]
    sig_text = "Signature: {}   {}".format(SIGNATURE_BLANK, physician_name or "")
    lines.append(OrderLine(sig_text, "", "", is_signature=True))

    pages = build_pages(lines)

    c = canvas.Canvas(out_path, pagesize=letter)

    for page_lines in pages:
        if include_background and os.path.exists(TEMPLATE_IMAGE_PATH):
            c.drawImage(
                TEMPLATE_IMAGE_PATH, 0, 0,
                width=L.PAGE_WIDTH, height=L.PAGE_HEIGHT,
                preserveAspectRatio=False, mask="auto",
            )

        _draw_patient_block(c, patient_name, csn, cal)
        _draw_order_rows(c, page_lines, cal)

        c.showPage()

    c.save()
    return out_path


def _draw_patient_block(c, patient_name, csn, cal):
    x = L.apply_x(L.PATIENT_BLOCK_X, cal)
    c.setFont(L.FONT_NAME_BOLD, L.PATIENT_FONT_SIZE)
    c.drawString(x, L.PATIENT_NAME_Y + cal.get("offset_y", 0.0), "Patient: {}".format(patient_name or ""))
    c.drawString(x, L.PATIENT_CSN_Y + cal.get("offset_y", 0.0), "CSN: {}".format(csn or ""))


def _draw_order_rows(c, page_lines, cal):
    date_col_width = L.COL_DATE_TIME_DIV - L.COL_LEFT - 2 * L.CELL_TEXT_PAD_X
    time_col_width = L.COL_TIME_NOTED_DIV - L.COL_DATE_TIME_DIV - 2 * L.CELL_TEXT_PAD_X
    orders_col_width = L.COL_RIGHT - L.COL_NOTED_ORDERS_DIV - 2 * L.CELL_TEXT_PAD_X

    for i, line in enumerate(page_lines):
        row_bottom = L.row_bottom(i, cal)
        row_top = L.row_top(i, cal)
        row_h = row_top - row_bottom
        baseline = row_bottom + L.CELL_TEXT_PAD_Y

        # DATE / TIME columns (blank for the signature row).
        if line.date_str:
            c.setFont(L.FONT_NAME, L.DATE_TIME_FONT_SIZE)
            fsize, dlines = _fit_lines(line.date_str, date_col_width, L.FONT_NAME, L.DATE_TIME_FONT_SIZE, max_lines=1)
            c.setFont(L.FONT_NAME, fsize)
            c.drawString(L.apply_x(L.COL_LEFT + L.CELL_TEXT_PAD_X, cal), baseline, dlines[0])
        if line.time_str:
            fsize, tlines = _fit_lines(line.time_str, time_col_width, L.FONT_NAME, L.DATE_TIME_FONT_SIZE, max_lines=1)
            c.setFont(L.FONT_NAME, fsize)
            c.drawString(L.apply_x(L.COL_DATE_TIME_DIV + L.CELL_TEXT_PAD_X, cal), baseline, tlines[0])

        # ORDERS column (bold label prefix for the signature line).
        font = L.FONT_NAME_BOLD if line.is_signature else L.FONT_NAME
        fsize, olines = _fit_lines(line.text, orders_col_width, font, L.ORDER_FONT_SIZE, max_lines=2)
        c.setFont(font, fsize)
        ox = L.apply_x(L.COL_NOTED_ORDERS_DIV + L.CELL_TEXT_PAD_X, cal)
        if len(olines) == 1:
            c.drawString(ox, baseline, olines[0])
        else:
            # Two lines: stack them within the row, smaller leading.
            leading = max(fsize + 1.0, row_h / 2.0)
            c.drawString(ox, baseline + leading / 2.0, olines[0])
            c.drawString(ox, baseline - leading / 2.0 + (leading - fsize), olines[1])


def generate_calibration_test_page(out_path, calibration=None):
    """Prints row numbers and column markers at every computed position so
    the offsets can be sanity-checked against a real blank form (hold the
    printed test page up to the light against the paper form, or print it
    directly on a spare form)."""
    cal = calibration or L.load_calibration()
    c = canvas.Canvas(out_path, pagesize=letter)

    _draw_patient_block(c, "TEST PATIENT", "CSN-TEST", cal)

    for i in range(L.NUM_ROWS):
        rb = L.row_bottom(i, cal)
        baseline = rb + L.CELL_TEXT_PAD_Y
        c.setFont(L.FONT_NAME, 8)
        c.drawString(L.apply_x(L.COL_LEFT + L.CELL_TEXT_PAD_X, cal), baseline, "D{}".format(i + 1))
        c.drawString(L.apply_x(L.COL_DATE_TIME_DIV + L.CELL_TEXT_PAD_X, cal), baseline, "T{}".format(i + 1))
        c.drawString(
            L.apply_x(L.COL_NOTED_ORDERS_DIV + L.CELL_TEXT_PAD_X, cal),
            baseline,
            "Row {} - order text baseline".format(i + 1),
        )

    c.showPage()
    c.save()
    return out_path