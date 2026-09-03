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
  order, ready for a wet signature (or, for an AOP order — see below — an
  Ordering Nurse line plus a blank Physician line).

The Physician Name field requires credentials after the name (MD, DO, PA-C,
or NP — e.g. "Jane Smith, MD"); generating a non-AOP order sheet is blocked
with an error until they're added.

If more orders are checked than fit on one form (21 rows), it automatically
continues onto additional pages, repeating the patient header **and its own
Signature line** on each page. If a weight-based medication's order lands on
a given page, that page also gets its own "please document height/weight"
reminder line. A single order whose text is too long for one line wraps
onto an indented continuation row instead of shrinking to fit.

**Medications never get split across a page boundary** — if the whole
checked medication list doesn't fit in the space left on the current page,
the entire list moves together to start a fresh page, rather than some meds
ending up on one page and the rest on the next. (Labs/imaging/other orders
can still split across pages if they land on a boundary — only medications
are kept together, since that's the group where a split would matter most
for actually administering them.) Drips (see below) count as part of this
same group, so a checked drip and a checked medication never get split
apart from each other either.

### PRN and Drips

Only medications marked as PRN-appropriate in `data.json` show an enabled
PRN checkbox/reason field — for the rest (antibiotics, boluses, RSI/
paralytic drugs, etc.) that row's PRN checkbox stays permanently grayed out,
since PRN dosing doesn't make clinical sense for them. Add
`"allow_prn": true` to a medication entry to turn its PRN checkbox on.

The separate **Drips** tab is for continuous IV infusions that need
titration instructions rather than a simple dose/route/frequency: Initial
Dose, Titrate By (amount), Titrate Frequency, Max Dose (not-to-exceed rate),
and a free-text Goal (e.g. "MAP >= 65", "RASS -2 to 0"). A checked drip
prints as e.g. "Norepinephrine (Levophed) - Start 0.05 mcg/kg/min - Titrate
by 0.05 mcg/kg/min Q5min - Max 3 mcg/kg/min - Goal: MAP >= 65". Weight-based
drips (`requires_weight: true`, same as medications) trigger the same
height/weight reminder line.

Some drips don't fit that start/titrate/max/goal shape at all -- Amiodarone,
for example, is a fixed load-then-maintenance regimen, not something you
titrate. Those are flagged `is_protocol: true` in `data.json`: instead of
the five titration fields, the Drips tab shows one wide free-text **Protocol**
field for them (pre-filled from `default_protocol_text`, still fully
editable), and the printed order is just "{name} - {protocol text}".
Amiodarone ships this way by default; flag any other drip the same way via
the Data Editor if it's better described as a fixed protocol than a titration.

### AOP (nurse protocol) order sets

The **Order Sets** tab has three kinds of buttons:
- **Physician Order Sets** — additive. Click any number of them (and/or
  check things manually) to combine.
- **AOP / Nurse Protocol Order Sets** — an AOP ("Approved Order Protocol")
  is a bundle a nurse orders under a standing protocol rather than a
  physician composing an order individually. The 20 built in (Chest Pain,
  Stroke, Abdominal Pain, Sepsis triage, etc.) were imported from a real
  protocol spreadsheet. Clicking one:
  1. Clears any current selections and checks off exactly that protocol's
     orders (its own items stay editable/uncheckable afterward).
  2. **Locks every other order control in the app** — every other lab,
     medication, imaging, other-order, and custom-order field, plus every
     regular/AOP order-set button — so nothing outside the protocol can be
     added. A red banner ("AOP MODE ACTIVE: ...") stays visible at the
     bottom of the window on every tab as a reminder. Click **Clear All
     Selections** to exit AOP mode and unlock everything again.
  3. Adds "AOP: {protocol name} - Indication: {indication}" as the very
     first line of the printed order sheet.
  4. Replaces the usual single physician signature line with two lines on
     every page: **Ordering Nurse** (pre-filled from the "Ordering Nurse
     Name" field in the patient bar, with a blank line to sign) and a
     completely blank **Physician** line, for a physician to fill in and
     sign later when they co-sign the protocol order.
- **AOP Modifiers** — small add-ons (currently just "Female < 50 (Pregnancy
  Screen)") for criteria that cut across many protocols rather than
  defining one on their own. Unlike a regular AOP, clicking a modifier
  does **not** clear the current selection or lock anything by itself —
  it stays clickable even while an AOP is locking everything else, and
  stacks its items into the currently-allowed set instead of replacing it.
  Applied standalone (no AOP active), it just behaves like a regular
  additive order set. Its name is appended to the AOP banner/print line
  (e.g. "Chest Pain ... + Female < 50 (Pregnancy Screen)").

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

### Building the Data Editor .exe (separately)

`data_editor.py` (see below) is built the same way, but on its own —
deliberately never bundled into "ED Order Sheet.exe":

```
pyinstaller --onefile --windowed --name "ED Order Data Editor" data_editor.py
```

No `--add-data` and no `requirements.txt` install needed for this one — the
editor only imports `data.py`, which has zero third-party dependencies, so
it doesn't pull in `reportlab`/`pywin32`/`PyMuPDF` at all. (The GitHub
Actions workflow already builds and uploads both `.exe`s as separate
artifacts on every push.)

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
the app. The easiest way to edit it is the separate **Data Editor** tool
(see below); this section documents the raw file format, useful if you
ever want to hand-edit it or write your own tooling against it:

- `labs` — list of lab names.
- `medications` — list of objects with `name`, `default_dose`,
  `default_route`, `default_frequency`, and optionally `allow_prn: true`
  (turns on that row's PRN checkbox; omitted/false keeps it grayed out),
  `default_prn_reason` (only meaningful with `allow_prn: true`), and
  `requires_weight: true` for weight-based meds (checking one of these adds
  a "document height/weight" reminder line to whichever page that order
  lands on).
- `common_routes` — the options offered in the Route dropdown.
- `common_frequencies` — the options offered in the Frequency dropdown.
- `prn_reasons` — the options offered in the PRN Reason dropdown.
- `titrate_frequencies` — the options offered in the Drips tab's Frequency dropdown.
- `drips` — the rows on the **Drips** tab. Each is `{"name",
  "default_initial_dose", "default_titrate_by", "default_titrate_frequency",
  "default_max_dose", "default_goal", optional "requires_weight": true}` —
  all five dose/titration/goal fields are free text in the UI regardless of
  the defaults. For a fixed-regimen drip (not titrated), use
  `{"name", "is_protocol": true, "default_protocol_text", optional
  "requires_weight": true}` instead -- see "PRN and Drips" above.
- `imaging_modalities` — object of modality name -> list of study names.
- `contrast_modalities` — which modalities get a "With Contrast" checkbox
  (currently `["CT", "MRI"]`).
- `other_orders` — misc nursing/general orders.
- `order_sets` — the buttons on the **Order Sets** tab. Each is
  `{"name", "labs": [...], "medications": [{"name", optional "dose"/
  "route"/"frequency"/"prn": true/"prn_reason" overrides}], "drips":
  [{"name", optional "protocol"/"initial_dose"/"titrate_by"/
  "titrate_frequency"/"max_dose"/"goal" overrides}], "imaging": [{"modality", "study",
  "indication", optional "contrast": true}], "other": [...]}`. `"study"` in an imaging entry
  doesn't need to already be in that modality's dropdown list — it's added
  as free text either way. A medication's `"prn": true` override is ignored
  if that medication's own `allow_prn` isn't set.
  Add `"is_aop": true` and `"indication": "..."` to make it an AOP/nurse
  protocol set instead of a regular (additive) one, or `"is_aop_modifier":
  true` (no `"indication"` needed) to make it a stacking modifier instead —
  see "AOP (nurse protocol) order sets" above for what those change.

Edit it, save, and relaunch the app (or the .exe) — no recompiling. If
`data.json` doesn't exist yet, the app creates one next to itself on first
run, pre-filled with the built-in defaults, ready to hand-edit. If you break
the JSON syntax, the app shows a warning on startup and falls back to the
built-in defaults until it's fixed (your `data.json` is left untouched, so
nothing is lost — just correct the syntax and relaunch).

## Data Editor (a separate program)

Hand-editing JSON is clunky, so `data_editor.py` is a second, completely
independent Tkinter program for editing `data.json` -- add, edit, delete,
reorder, and duplicate everything the main app reads, without touching a
text editor. It is **not** part of "ED Order Sheet.exe" and doesn't get
bundled into it (it imports nothing from `app.py`/`pdf_gen.py`/
`printing.py`/`windows_print.py` -- only `data.py`, for the schema/
defaults), so it has to be built and shipped as its own `.exe` -- see
"Building the Data Editor .exe" above. Run it with `python3 data_editor.py`.

On launch it looks for `data.json` next to itself (same convention as the
main app), or starts from the built-in defaults if there isn't one yet.
**File > Open...** loads any other `data.json` (e.g. the one actually
sitting next to a deployed "ED Order Sheet.exe" elsewhere), and
**File > Save** / **Save As...** write changes back out. It warns before
discarding unsaved changes, and **File > Check for Issues...** scans for
duplicate names and order sets that reference something that no longer
exists (non-blocking -- the main app already skips missing references
silently, this just helps you catch typos).

Tabs mirror the main app's: **Labs**, **Other Orders**, and **Reference
Lists** (Routes/Frequencies/PRN Reasons/Titrate Frequencies) are simple
add/rename/delete/reorder lists. **Medications** and **Drips** are tables
-- Add/Edit open a form for all of that item's fields (dose, PRN
eligibility, weight-based flag, etc.). **Imaging** is a modality list
(add/rename/delete, plus a "With Contrast" checkbox per modality) next to
that modality's list of studies. **Order Sets** is the most involved: pick
a set from the list on the left (or **+ New**) and its name, type (regular
/ AOP / AOP Modifier), indication, and Labs/Other checklists update live as
you edit; Medications/Drips/Imaging use their own Add/Remove list with a
small form for each entry's overrides. Deleting something referenced
elsewhere shows you what uses it first (labs/meds/drips/other-orders/
imaging modalities), but doesn't block the deletion -- the main app handles
orphaned references gracefully either way.

## Project layout

- `app.py` — Tkinter GUI (patient info, Order Sets/Labs/Medications/Drips/
  Imaging/Other tabs, Print/Preview/calibration buttons).
- `data_editor.py` — the separate Data Editor program described above.
  Standalone: imports only `data.py`, nothing else from this app.
- `data.py` — loads `data.json` (creating it from built-in defaults on
  first run) and exposes it as the order lists the UI reads from; also the
  shared schema/defaults module `data_editor.py` imports.
- `data.json` — the editable order lists described above (git-ignored;
  generated on first run, then yours to customize per install).
- `layout.py` — page geometry (measured form coordinates) and print
  calibration load/save.
- `pdf_gen.py` — builds the PDF with `reportlab`: per-page pagination (each
  page gets its own signature/height-weight lines) and indented-continuation
  wrapping for order text that doesn't fit on one line.
- `printing.py` — private-temp-file + delayed-cleanup logic, and the
  print_order_sheet() dispatcher (native Windows dialog, else open-in-viewer
  fallback) described above; no PDF is ever written anywhere else.
- `windows_print.py` — the native Windows print dialog + GDI printing
  implementation; raises ImportError on any non-Windows platform.
- `assets/template_preview.png` — a scan of the blank form, used only in
  Preview mode; never drawn in the print output.
- `template.HEIC` — the original source photo of the blank form.
