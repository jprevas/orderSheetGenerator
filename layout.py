"""
Coordinate geometry for the Anne Arundel Medical Center "Physician Orders"
paper form.

All base coordinates below were measured directly from a high-resolution
photo of the blank form (pixel-located table borders, converted to points
on a standard 8.5x11in / 612x792pt page) and verified by overlaying a
generated grid back onto the form image. DEFAULT_CALIBRATION is a small
fine-tuning adjustment on top of that, measured once against this app's
baked-in form template (assets/physician_orders.pdf) -- since that template
is now always what's printed on (see pdf_gen.py), rather than a physical
pre-printed form whose feed margin varies by printer, this offset doesn't
need to vary either.

There is no patient name/CSN block -- a patient ID sticker is applied to
the printed sheet afterward, in the same "PATIENT ID LABEL" box the paper
form already has for that purpose.
"""

PAGE_WIDTH = 612.0   # 8.5in
PAGE_HEIGHT = 792.0  # 11in

# Table column boundaries, in points from the left edge of the page.
COL_LEFT = 44.45          # left edge of "DATE ORDERED" column
COL_DATE_TIME_DIV = 94.19  # divider between DATE ORDERED / TIME ORDERED
COL_TIME_NOTED_DIV = 143.90  # divider between TIME ORDERED / TIME NOTED & INITIALS
COL_NOTED_ORDERS_DIV = 200.56  # divider between TIME NOTED & INITIALS / ORDERS
COL_RIGHT = 557.5          # right edge of ORDERS column

# Row geometry, in points measured from the BOTTOM of the page (reportlab's
# coordinate origin), matching the row grid printed on the form.
DATA_TOP = 629.65    # top edge of the first order row
ROW_HEIGHT = 23.45    # height of each order row
NUM_ROWS = 21         # number of order rows printed on the form

# Text inset from column edges/row bottom, so characters don't sit on the
# printed grid lines.
CELL_TEXT_PAD_X = 4.0
CELL_TEXT_PAD_Y = 7.0

# Extra left indent applied to an order's wrapped continuation line(s), so
# a second physical row visually reads as "more of the order above it"
# rather than a new dated order.
ORDER_CONTINUATION_INDENT = 14.0

FONT_NAME = "Helvetica"
FONT_NAME_BOLD = "Helvetica-Bold"
ORDER_FONT_SIZE = 9
DATE_TIME_FONT_SIZE = 9

DEFAULT_CALIBRATION = {
    "offset_x": 10.0,   # points; positive shifts everything RIGHT
    "offset_y": 0.0,    # points; positive shifts everything UP
    "row_scale": 1.03,  # multiplier on ROW_HEIGHT, for fine vertical stretch
}


def row_top(index):
    """Top y-coordinate (points from bottom) of order row `index` (0-based)."""
    row_h = ROW_HEIGHT * DEFAULT_CALIBRATION["row_scale"]
    return DATA_TOP - index * row_h + DEFAULT_CALIBRATION["offset_y"]


def row_bottom(index):
    row_h = ROW_HEIGHT * DEFAULT_CALIBRATION["row_scale"]
    return row_top(index) - row_h


def apply_x(pt):
    return pt + DEFAULT_CALIBRATION["offset_x"]