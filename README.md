# ED Physician Order Sheet Generator

A desktop app for checking off common Emergency Department orders (labs,
medications, imaging, and other nursing orders) and generating a PDF that
prints **directly into the boxes** of the pre-printed Anne Arundel Medical
Center "Physician Orders" paper form.

It fills in:
- Patient name and CSN, top left of the page.
- One row per checked order, with today's date/time in the DATE ORDERED
  and TIME ORDERED columns (the TIME NOTED & INITIALS column is left
  blank, as intended for staff to complete by hand).
- A "Signature: ____________  Dr. {name}" line immediately after the last
  order, ready for a wet signature.

If more orders are checked than fit on one form (21 rows), it automatically
continues onto additional pages, repeating the patient header on each.

## Running on macOS (for testing / day-to-day use)

1. Install Python 3.9+ (macOS ships with Python, but Tkinter support needs
   the Tcl/Tk bindings — if `python3 -m tkinter` fails, run
   `brew install python-tk@3.13`, matching your Python's minor version).
2. From the project folder:
   ```
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   python3 app.py
   ```

Since the pre-printed paper form usually isn't loaded in a home/office
printer, use the **Preview mode** checkbox at the bottom of the window
before clicking Generate PDF — it overlays your entries on a scan of the
actual form so you can eyeball alignment on screen. Uncheck it when you're
ready to print for real onto the hospital's pre-printed stock (Preview mode
draws the scanned form as a background image, which you do NOT want on the
real printout).

## Building a Windows .exe

Do this step on a Windows machine (PyInstaller builds for the OS it runs
on — you can't cross-build a .exe from macOS):

```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
pip install pyinstaller
pyinstaller --onefile --windowed --name "ED Order Sheet" --add-data "assets;assets" app.py
```

The .exe will be in `dist\ED Order Sheet.exe`. The `--add-data` flag is
required so the bundled `assets/template_preview.png` (used only for
Preview mode) ships inside the .exe.

If you ever need to build on macOS instead, the equivalent command is:
```
pyinstaller --onefile --windowed --name "ED Order Sheet" --add-data "assets:template_preview.png:assets" app.py
```
(note the `:` separator instead of `;` on macOS/Linux) — but this produces
a macOS app bundle, not a .exe.

## Print calibration

The coordinates in `layout.py` were measured directly from a high-resolution
photo of the blank form and verified by overlaying a generated grid back
onto it, so alignment should be close out of the box. Every printer feeds
paper with a slightly different margin, though, so if text is a little off
once printed on an actual form:

1. Open the app, click **Print Calibration...**.
2. Click **Print Test Page** — it prints small row/column markers at every
   position the app will write to.
3. Hold that test page up to a blank form (or print it directly onto a
   spare form) and note how far off it is, in points (72pt = 1 inch).
4. Enter the horizontal/vertical offsets (and row spacing scale, if the
   rows are drifting more the further down the page you go) and **Save**.
   The offsets are stored in `~/.ed_order_sheet_calibration.json` and
   applied to every PDF generated afterward.

## Customizing the order sets

Edit `data.py` — it's just plain lists/dicts:
- `LABS` — list of lab names.
- `MEDICATIONS` — list of `{"name", "default_dose", "default_route"}`.
- `IMAGING_MODALITIES` — dict of modality -> list of study names.
- `OTHER_ORDERS` — misc nursing/general orders.

No other file needs to change to add, remove, or rename items.

## Project layout

- `app.py` — Tkinter GUI (patient info, Labs/Medications/Imaging/Other
  tabs, Generate PDF / calibration buttons).
- `data.py` — the editable order lists described above.
- `layout.py` — page geometry (measured form coordinates) and print
  calibration load/save.
- `pdf_gen.py` — builds the PDF with `reportlab`, including pagination and
  automatic text shrink/wrap for long order lines.
- `assets/template_preview.png` — a scan of the blank form, used only in
  Preview mode; never printed in the final/print output.
- `template.HEIC` — the original source photo of the blank form.
