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

Pagination: orders are laid out one per row at a fixed font size; an order
whose text doesn't fit the ORDERS column width wraps onto a second (and
if needed third+) row, indented, with DATE/TIME left blank on those
continuation rows. If the orders (plus a trailing signature line, and a
height/weight reminder line if a weight-based medication landed on that
page) don't fit in NUM_ROWS rows, a new page is started -- and every page
gets its own signature line (and its own height/weight reminder, if a
weight-based med's order is on that particular page).
"""

import os

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.pdfbase.pdfmetrics import stringWidth

import layout as L

ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
TEMPLATE_IMAGE_PATH = os.path.join(ASSETS_DIR, "template_preview.png")

SIGNATURE_BLANK = "_" * 34
HEIGHT_WEIGHT_TEXT = (
    "PLEASE DOCUMENT PATIENT HEIGHT AND WEIGHT     "
    "Height: ____________     Weight: ____________"
)


def _fit_single_line(text, max_width, font_name, start_size, min_size=6.0):
    """Shrink `text` (no wrapping) until it fits `max_width`. Used only for
    the synthesized signature / height-weight lines and the DATE/TIME
    columns, which must always occupy exactly one row."""
    size = start_size
    while size > min_size and stringWidth(text, font_name, size) > max_width:
        size -= 0.5
    return size, text


def _wrap_order_text(text, full_width, cont_width, font_name, size):
    """Word-wrap `text` at a fixed font size into physical lines -- the
    first against `full_width`, any further lines against the narrower
    `cont_width` (they'll be drawn indented). Returns a list of 1+ line
    strings. A single word wider than the available width is truncated
    with an ellipsis rather than overflowing the column or looping."""
    if stringWidth(text, font_name, size) <= full_width:
        return [text]

    def _truncate_to_fit(word, width):
        if stringWidth(word, font_name, size) <= width:
            return word
        while word and stringWidth(word + "...", font_name, size) > width:
            word = word[:-1]
        return (word + "...") if word else "..."

    words = text.split(" ")
    lines = []
    current = ""
    width_limit = full_width
    for word in words:
        candidate = (current + " " + word).strip()
        if stringWidth(candidate, font_name, size) <= width_limit:
            current = candidate
        elif not current:
            lines.append(_truncate_to_fit(word, width_limit))
            current = ""
        else:
            lines.append(current)
            current = word
            width_limit = cont_width
            if stringWidth(current, font_name, size) > width_limit:
                lines.append(_truncate_to_fit(current, width_limit))
                current = ""
    if current:
        lines.append(current)
    return lines


class OrderEntry:
    """One order to print: its display text, whether it requires the
    height/weight reminder to appear on whichever page it lands on, an
    optional group tag (e.g. "medications") used to keep a whole contiguous
    run of same-group orders together on one page (see KEEP_TOGETHER_GROUPS),
    and an optional bold flag for a banner-style entry (e.g. the AOP
    declaration line) that's shrink-to-fit on a single row rather than
    wrapped/indented like a normal order."""

    def __init__(self, text, requires_weight=False, group=None, bold=False):
        self.text = text
        self.requires_weight = requires_weight
        self.group = group
        self.bold = bold


# Groups that should never be split across a page boundary: a contiguous
# run of orders sharing one of these group tags either fits together on
# the current page, or the whole run starts fresh on the next page. Falls
# back to normal per-order splitting only if the run alone is too long to
# ever fit on an empty page (see _build_units).
KEEP_TOGETHER_GROUPS = {"medications"}


class Row:
    """One physical printable row on the form."""

    def __init__(self, text, date_str="", time_str="", bold=False, indent=False):
        self.text = text
        self.date_str = date_str
        self.time_str = time_str
        self.bold = bold
        self.indent = indent


def _orders_col_widths():
    full = L.COL_RIGHT - L.COL_NOTED_ORDERS_DIV - 2 * L.CELL_TEXT_PAD_X
    cont = full - L.ORDER_CONTINUATION_INDENT
    return full, cont


def _expand_order(entry, date_str, time_str):
    if entry.bold:
        # Banner-style entry (e.g. the AOP declaration line): always exactly
        # one row, shrink-to-fit rather than wrapped/indented.
        return [Row(text=entry.text, date_str=date_str, time_str=time_str, bold=True)]

    full_width, cont_width = _orders_col_widths()
    lines = _wrap_order_text(entry.text, full_width, cont_width, L.FONT_NAME, L.ORDER_FONT_SIZE)
    rows = []
    for i, line_text in enumerate(lines):
        rows.append(Row(
            text=line_text,
            date_str=date_str if i == 0 else "",
            time_str=time_str if i == 0 else "",
            indent=(i > 0),
        ))
    return rows


def _build_units(order_entries, order_date_str, order_time_str, sig_rows):
    """Groups consecutive entries that share a KEEP_TOGETHER_GROUPS tag into
    one atomic pagination unit -- (rows, requires_weight) -- so the whole
    run either lands together on one page or moves together to the next.
    A run too long to ever fit on an empty page falls back to one unit per
    entry (nothing physically fits otherwise; see max_fittable below)."""
    max_fittable = L.NUM_ROWS - 1 - sig_rows  # worst case tail: height/weight line + signature block

    units = []
    i, n = 0, len(order_entries)
    while i < n:
        entry = order_entries[i]
        if entry.group in KEEP_TOGETHER_GROUPS:
            run = [entry]
            j = i + 1
            while j < n and order_entries[j].group == entry.group:
                run.append(order_entries[j])
                j += 1
            run_rows = [_expand_order(e, order_date_str, order_time_str) for e in run]
            total_rows = sum(len(r) for r in run_rows)
            if total_rows <= max_fittable:
                units.append((
                    [row for rows in run_rows for row in rows],
                    any(e.requires_weight for e in run),
                ))
            else:
                for e, rows in zip(run, run_rows):
                    units.append((rows, e.requires_weight))
            i = j
        else:
            units.append((_expand_order(entry, order_date_str, order_time_str), entry.requires_weight))
            i += 1
    return units


def _paginate(order_entries, order_date_str, order_time_str, physician_name, nurse_name=None):
    """Returns a list of pages; each page is a list of Row (already
    including that page's height/weight reminder, if needed, and its own
    trailing signature block). Normally that block is a single physician
    signature line; if `nurse_name` is not None (an AOP order sheet), it's
    instead an Ordering Nurse line (with that name) plus a blank Physician
    line to be filled in later."""
    sig_rows = 2 if nurse_name is not None else 1
    units = _build_units(order_entries, order_date_str, order_time_str, sig_rows)

    pages = []
    current_rows = []
    current_has_weight = False

    def close_page():
        page_rows = list(current_rows)
        if current_has_weight:
            page_rows.append(Row(HEIGHT_WEIGHT_TEXT, order_date_str, order_time_str, bold=True))
        if nurse_name is not None:
            nurse_text = "Ordering Nurse: {}   {}".format(SIGNATURE_BLANK, nurse_name or "")
            page_rows.append(Row(nurse_text, "", "", bold=True))
            phys_text = "Physician: {}".format(SIGNATURE_BLANK)
            page_rows.append(Row(phys_text, "", "", bold=True))
        else:
            sig_text = "Signature: {}   {}".format(SIGNATURE_BLANK, physician_name or "")
            page_rows.append(Row(sig_text, "", "", bold=True))
        pages.append(page_rows)

    for rows, requires_weight in units:
        prospective_weight = current_has_weight or requires_weight
        tail = sig_rows + (1 if prospective_weight else 0)
        if current_rows and (len(current_rows) + len(rows) + tail) > L.NUM_ROWS:
            close_page()
            current_rows = []
            current_has_weight = False
        current_rows.extend(rows)
        if requires_weight:
            current_has_weight = True

    close_page()
    return pages


def generate_pdf(
    out_path,
    patient_name,
    csn,
    physician_name,
    orders,
    order_date_str,
    order_time_str,
    include_background=False,
    calibration=None,
    nurse_name=None,
):
    """
    orders: list of dicts, each {"text": str, "requires_weight": bool,
            "group": str or None, "bold": bool}. text is a plain-language,
            already-formatted order string (e.g. "Acetaminophen 650 mg PO
            Q6H", "CT Head - Indication: r/o bleed"). Long text wraps onto
            an indented continuation row rather than shrinking to fit,
            unless "bold" is set (a banner-style entry, e.g. an AOP
            declaration line), which is shrink-to-fit on one row instead.
            A signature line (and, on any page containing a weight-based
            med, a height/weight reminder line) is appended automatically
            to every page. Entries sharing a group tag in
            KEEP_TOGETHER_GROUPS (e.g. "medications") are kept together on
            one page rather than being split across a page boundary.
    nurse_name: if not None, every page's signature block becomes an
            Ordering Nurse line (with this name) plus a blank Physician
            line, instead of the usual single physician signature line
            (used for AOP/nurse-protocol order sheets).
    """
    cal = calibration or L.load_calibration()

    entries = [
        OrderEntry(o["text"], o.get("requires_weight", False), o.get("group"), o.get("bold", False))
        for o in orders
    ]
    pages = _paginate(entries, order_date_str, order_time_str, physician_name, nurse_name)

    c = canvas.Canvas(out_path, pagesize=letter)

    for page_rows in pages:
        if include_background and os.path.exists(TEMPLATE_IMAGE_PATH):
            c.drawImage(
                TEMPLATE_IMAGE_PATH, 0, 0,
                width=L.PAGE_WIDTH, height=L.PAGE_HEIGHT,
                preserveAspectRatio=False, mask="auto",
            )

        _draw_patient_block(c, patient_name, csn, cal)
        _draw_order_rows(c, page_rows, cal)

        c.showPage()

    c.save()
    return out_path


def _draw_patient_block(c, patient_name, csn, cal):
    x = L.apply_x(L.PATIENT_BLOCK_X, cal)
    c.setFont(L.FONT_NAME_BOLD, L.PATIENT_FONT_SIZE)
    c.drawString(x, L.PATIENT_NAME_Y + cal.get("offset_y", 0.0), "Patient: {}".format(patient_name or ""))
    c.drawString(x, L.PATIENT_CSN_Y + cal.get("offset_y", 0.0), "CSN: {}".format(csn or ""))


def _draw_order_rows(c, page_rows, cal):
    date_col_width = L.COL_DATE_TIME_DIV - L.COL_LEFT - 2 * L.CELL_TEXT_PAD_X
    time_col_width = L.COL_TIME_NOTED_DIV - L.COL_DATE_TIME_DIV - 2 * L.CELL_TEXT_PAD_X
    full_width, _cont_width = _orders_col_widths()

    for i, row in enumerate(page_rows):
        row_bottom = L.row_bottom(i, cal)
        baseline = row_bottom + L.CELL_TEXT_PAD_Y

        if row.date_str:
            fsize, dtext = _fit_single_line(row.date_str, date_col_width, L.FONT_NAME, L.DATE_TIME_FONT_SIZE)
            c.setFont(L.FONT_NAME, fsize)
            c.drawString(L.apply_x(L.COL_LEFT + L.CELL_TEXT_PAD_X, cal), baseline, dtext)
        if row.time_str:
            fsize, ttext = _fit_single_line(row.time_str, time_col_width, L.FONT_NAME, L.DATE_TIME_FONT_SIZE)
            c.setFont(L.FONT_NAME, fsize)
            c.drawString(L.apply_x(L.COL_DATE_TIME_DIV + L.CELL_TEXT_PAD_X, cal), baseline, ttext)

        font = L.FONT_NAME_BOLD if row.bold else L.FONT_NAME
        indent_extra = L.ORDER_CONTINUATION_INDENT if row.indent else 0.0
        ox = L.apply_x(L.COL_NOTED_ORDERS_DIV + L.CELL_TEXT_PAD_X + indent_extra, cal)

        if row.bold:
            # Signature / height-weight lines: synthesized by us, always
            # exactly one row -- shrink to fit rather than wrap.
            fsize, text = _fit_single_line(row.text, full_width, font, L.ORDER_FONT_SIZE)
            c.setFont(font, fsize)
            c.drawString(ox, baseline, text)
        else:
            # Regular order rows are pre-wrapped to fit at a fixed size.
            c.setFont(font, L.ORDER_FONT_SIZE)
            c.drawString(ox, baseline, row.text)


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
