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

Nothing is ever saved to disk. **Print Order Sheet** and **Preview on
Screen** both write the PDF to a private OS temp file and delete it again
shortly after (also cleaned up on app exit, and on the next launch in case
of a crash). There's no "Save As" dialog anywhere in the app.

**On Windows**, Print Order Sheet drives the real Windows print dialog
directly (`windows_print.py`, via `pywin32` + `PyMuPDF`) — a genuine
printer/copies/properties picker. Nothing is spooled to a printer unless you
click **Print** in that dialog; clicking Cancel prints nothing. This talks
directly to the Win32 GDI printing APIs and was developed on macOS (which
doesn't have them at all), so **test it once before relying on it** — print
to the built-in "Microsoft Print to PDF" virtual printer first, a safe,
paper-free way to confirm the dialog appears and the output looks right.

**Everywhere else** (macOS/Linux, or if the native Windows path errors for
any reason), it falls back to opening the PDF in the default viewer; you
print from there with Cmd+P/Ctrl+P. That fallback is a deliberate choice,
not a shortcut we didn't get to: OS-level "quick print" shortcuts (the
Windows shell "print" verb, an AppleEvent "print" to Preview) were tested
and both turned out to silently send the job straight to the default
printer with no dialog and no chance to review — exactly wrong for a
patient order sheet, so this app never uses them.

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
printer, use **Preview on Screen** — it overlays your entries on a scan of
the actual form so you can eyeball alignment. Use **Print Order Sheet** when
you're ready to print for real onto the hospital's pre-printed stock (this
mode never draws the scanned form background — only your entries, positioned
to land in the form's boxes).

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
Preview mode) ships inside the .exe. `pywin32` and `PyMuPDF` (installed via
`requirements.txt` on Windows) are what power the native print dialog in
`windows_print.py` — PyInstaller bundles them automatically; no extra flags
needed for those two.

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

## Customizing the order sets (no recompiling needed)

The order lists live in **`data.json`**, a plain text file kept next to
`app.py` (or next to `ED Order Sheet.exe` once compiled) — not baked into
the app. Open it in any text editor:

- `labs` — list of lab names.
- `medications` — list of objects with `name`, `default_dose`,
  `default_route`, and optionally `requires_weight: true` for weight-based
  meds (checking one of these adds a "document height/weight" reminder line
  to the printed sheet).
- `common_routes` — the options offered in the Route dropdown.
- `imaging_modalities` — object of modality name -> list of study names.
- `contrast_modalities` — which modalities get a "With Contrast" checkbox
  (currently `["CT", "MRI"]`).
- `other_orders` — misc nursing/general orders.

Edit it, save, and relaunch the app (or the .exe) — no recompiling. If
`data.json` doesn't exist yet, the app creates one next to itself on first
run, pre-filled with the built-in defaults, ready to hand-edit. If you break
the JSON syntax, the app shows a warning on startup and falls back to the
built-in defaults until it's fixed (your `data.json` is left untouched, so
nothing is lost — just correct the syntax and relaunch).

## Project layout

- `app.py` — Tkinter GUI (patient info, Labs/Medications/Imaging/Other
  tabs, Print/Preview/calibration buttons).
- `data.py` — loads `data.json` (creating it from built-in defaults on
  first run) and exposes it as the order lists the UI reads from.
- `data.json` — the editable order lists described above (git-ignored;
  generated on first run, then yours to customize per install).
- `layout.py` — page geometry (measured form coordinates) and print
  calibration load/save.
- `pdf_gen.py` — builds the PDF with `reportlab`, including pagination and
  automatic text shrink/wrap for long order lines.
- `printing.py` — private-temp-file + delayed-cleanup logic, and the
  print_order_sheet() dispatcher (native Windows dialog, else open-in-viewer
  fallback) described above; no PDF is ever written anywhere else.
- `windows_print.py` — the native Windows print dialog + GDI printing
  implementation; raises ImportError on any non-Windows platform.
- `assets/template_preview.png` — a scan of the blank form, used only in
  Preview mode; never drawn in the print output.
- `template.HEIC` — the original source photo of the blank form.
