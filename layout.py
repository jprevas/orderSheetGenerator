"""
Coordinate geometry for the Anne Arundel Medical Center "Physician Orders"
paper form, plus user-adjustable print calibration.

All base coordinates below were measured directly from a high-resolution
photo of the blank form (pixel-located table borders, converted to points
on a standard 8.5x11in / 612x792pt page) and verified by overlaying a
generated grid back onto the form image. They should line up closely out
of the box, but every printer/copier feeds paper with a slightly different
edge margin, so a small CALIBRATION offset is applied on top and is
adjustable from the app (Settings -> Print Calibration) without touching
this file.
"""

import json
import os

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

# Patient name / CSN block, printed in the blank box on the upper right
# of the form -- the same box labeled "PATIENT ID LABEL" (where a printed
# patient sticker would normally be affixed), just right of the vertical
# divider line and above that caption text.
PATIENT_BLOCK_X = 314.0
PATIENT_NAME_Y = 730.0
PATIENT_CSN_Y = 712.0

# Text inset from column edges/row bottom, so characters don't sit on the
# printed grid lines.
CELL_TEXT_PAD_X = 4.0
CELL_TEXT_PAD_Y = 7.0

FONT_NAME = "Helvetica"
FONT_NAME_BOLD = "Helvetica-Bold"
ORDER_FONT_SIZE = 9
DATE_TIME_FONT_SIZE = 9
PATIENT_FONT_SIZE = 11

CALIBRATION_PATH = os.path.join(os.path.expanduser("~"), ".ed_order_sheet_calibration.json")

DEFAULT_CALIBRATION = {
    "offset_x": 0.0,   # points; positive shifts everything RIGHT
    "offset_y": 0.0,   # points; positive shifts everything UP
    "row_scale": 1.0,  # multiplier on ROW_HEIGHT, for fine vertical stretch
}


def load_calibration():
    if os.path.exists(CALIBRATION_PATH):
        try:
            with open(CALIBRATION_PATH, "r") as f:
                data = json.load(f)
            cal = dict(DEFAULT_CALIBRATION)
            cal.update({k: v for k, v in data.items() if k in DEFAULT_CALIBRATION})
            return cal
        except (json.JSONDecodeError, OSError):
            pass
    return dict(DEFAULT_CALIBRATION)


def save_calibration(cal):
    clean = dict(DEFAULT_CALIBRATION)
    clean.update({k: v for k, v in cal.items() if k in DEFAULT_CALIBRATION})
    with open(CALIBRATION_PATH, "w") as f:
        json.dump(clean, f, indent=2)


def row_top(index, cal):
    """Top y-coordinate (points from bottom) of order row `index` (0-based)."""
    row_h = ROW_HEIGHT * cal.get("row_scale", 1.0)
    return DATA_TOP - index * row_h + cal.get("offset_y", 0.0)


def row_bottom(index, cal):
    row_h = ROW_HEIGHT * cal.get("row_scale", 1.0)
    return row_top(index, cal) - row_h


def apply_x(pt, cal):
    return pt + cal.get("offset_x", 0.0)