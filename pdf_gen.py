import io
import os

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.pdfbase.pdfmetrics import stringWidth
from pypdf import PdfReader, PdfWriter

import layout as L

ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
TEMPLATE_PDF_PATH = os.path.join(ASSETS_DIR, "physician_orders.pdf")

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
    physician_name,
    orders,
    order_date_str,
    order_time_str,
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

    There is no patient name/CSN block -- affix a patient ID sticker to the
    "PATIENT ID LABEL" box on the printed sheet instead.
    """
    entries = [
        OrderEntry(o["text"], o.get("requires_weight", False), o.get("group"), o.get("bold", False))
        for o in orders
    ]
    pages = _paginate(entries, order_date_str, order_time_str, physician_name, nurse_name)

    overlay_buffer = io.BytesIO()
    c = canvas.Canvas(overlay_buffer, pagesize=letter)

    for page_rows in pages:
        _draw_order_rows(c, page_rows)
        c.showPage()

    c.save()
    _write_with_template(overlay_buffer, out_path)
    return out_path


def _write_with_template(overlay_buffer, out_path):
    """Merges each page of `overlay_buffer` (a ready-to-save reportlab
    Canvas's output) onto its own copy of the blank form template and
    writes the result to `out_path`. Falls back to writing the overlay
    alone if the template asset is missing."""
    overlay_buffer.seek(0)

    if not os.path.exists(TEMPLATE_PDF_PATH):
        with open(out_path, "wb") as f:
            f.write(overlay_buffer.getvalue())
        return

    overlay_reader = PdfReader(overlay_buffer)
    writer = PdfWriter()
    for overlay_page in overlay_reader.pages:
        # A fresh PdfReader per page, not one shared reader reused across
        # add_page() calls: pypdf caches clones by source object identity,
        # so cloning the same template page object twice into one writer
        # returns the *same* clone both times -- merging each page's text
        # onto it in turn, and both pages end up showing all pages' content.
        template_page = PdfReader(TEMPLATE_PDF_PATH).pages[0]
        template_page.merge_page(overlay_page)
        writer.add_page(template_page)
    writer.write(out_path)


def _draw_order_rows(c, page_rows):
    date_col_width = L.COL_DATE_TIME_DIV - L.COL_LEFT - 2 * L.CELL_TEXT_PAD_X
    time_col_width = L.COL_TIME_NOTED_DIV - L.COL_DATE_TIME_DIV - 2 * L.CELL_TEXT_PAD_X
    full_width, _cont_width = _orders_col_widths()

    for i, row in enumerate(page_rows):
        row_bottom = L.row_bottom(i)
        baseline = row_bottom + L.CELL_TEXT_PAD_Y

        if row.date_str:
            fsize, dtext = _fit_single_line(row.date_str, date_col_width, L.FONT_NAME, L.DATE_TIME_FONT_SIZE)
            c.setFont(L.FONT_NAME, fsize)
            c.drawString(L.apply_x(L.COL_LEFT + L.CELL_TEXT_PAD_X), baseline, dtext)
        if row.time_str:
            fsize, ttext = _fit_single_line(row.time_str, time_col_width, L.FONT_NAME, L.DATE_TIME_FONT_SIZE)
            c.setFont(L.FONT_NAME, fsize)
            c.drawString(L.apply_x(L.COL_DATE_TIME_DIV + L.CELL_TEXT_PAD_X), baseline, ttext)

        font = L.FONT_NAME_BOLD if row.bold else L.FONT_NAME
        indent_extra = L.ORDER_CONTINUATION_INDENT if row.indent else 0.0
        ox = L.apply_x(L.COL_NOTED_ORDERS_DIV + L.CELL_TEXT_PAD_X + indent_extra)

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
