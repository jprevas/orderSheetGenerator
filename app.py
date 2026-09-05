"""
ED Physician Order Sheet Generator

A small desktop app for checking off common Emergency Department orders
and generating a PDF of the "Physician Orders" form (see
assets/physician_orders.pdf), with the checked orders printed directly
into its boxes -- the form itself is baked into every generated PDF, so
it prints on plain paper, no pre-printed stock needed.
"""

import platform
import tkinter as tk
from datetime import datetime
from tkinter import ttk, messagebox

import data
import layout as L
import pdf_gen
import printing

# Credential suffixes required after a physician's name on a (non-AOP)
# order sheet, e.g. "Jane Smith, MD". Matched case-insensitively against
# the end of the entered name.
CREDENTIAL_SUFFIXES = ("MD", "DO", "PA-C", "NP")


def _has_credentials(name):
    stripped = name.strip().rstrip(".")
    upper = stripped.upper()
    return any(upper.endswith(suffix) for suffix in CREDENTIAL_SUFFIXES)


# Presentation-only grouping for the Labs/Medications/Other Orders tabs --
# purely a UI convenience to make a long flat checklist/table easier to
# scan, not part of the data.json schema. A name not listed in any group
# here (e.g. something added later via the Data Editor) falls into a
# trailing "Other" section instead of disappearing.
LAB_CATEGORIES = [
    ("Hematology / Coagulation", ["CBC", "PT/INR", "PTT", "D-Dimer", "Type & Screen", "Type & Crossmatch"]),
    ("Chemistry", ["BMP", "CMP", "LFTs", "Lipase", "Magnesium", "Phosphorus", "Ammonia", "Lactic Acid", "TSH", "POC Glucose"]),
    ("Cardiac Markers", ["Troponin", "BNP"]),
    ("Blood Gas", ["Venous Blood Gas (VBG)", "Arterial Blood Gas (ABG)"]),
    ("Urine / Pregnancy", ["Urinalysis (UA)", "Urine Culture", "Urine hCG", "Serum hCG (Qualitative)", "Serum hCG (Quantitative)"]),
    ("Microbiology", ["Blood Cultures x2", "Rapid Strep", "Influenza/COVID/RSV PCR"]),
    ("Toxicology", ["Serum Tox", "Urine Toxicology Screen", "Ethanol Level", "Acetaminophen Level", "Salicylate Level"]),
]

MED_CATEGORIES = [
    ("Analgesics / Antipyretics", ["Acetaminophen (Tylenol)", "Ibuprofen (Motrin)", "Ketorolac (Toradol)", "Aspirin", "Morphine", "Fentanyl", "Nitroglycerin SL"]),
    ("Antiemetics / GI", ["Ondansetron (Zofran) ODT", "Ondansetron (Zofran)", "Metoclopramide (Reglan)", "Famotidine (Pepcid)"]),
    ("Allergy / Anaphylaxis", ["Diphenhydramine (Benadryl)", "Epinephrine 1:1,000"]),
    ("Sedation / Anxiolysis", ["Lorazepam (Ativan)"]),
    ("Reversal Agents", ["Naloxone (Narcan)"]),
    ("Respiratory", ["Albuterol Nebulizer", "Ipratropium Nebulizer"]),
    ("Steroids", ["Methylprednisolone (Solu-Medrol)", "Dexamethasone", "Prednisone"]),
    ("Antibiotics", ["Ceftriaxone (Rocephin)", "Cefazolin (Ancef)", "Cefepime", "Vancomycin", "Ampicillin-Sulbactam (Unasyn)", "Piperacillin-Tazobactam (Zosyn)", "Azithromycin", "Metronidazole (Flagyl)"]),
    ("IV Fluids / Electrolytes", ["Normal Saline Bolus", "Lactated Ringers Bolus", "Dextrose 50%", "Insulin Regular for Hyperkalemia", "Insulin Aspart (Novolog)", "Magnesium Sulfate", "Calcium Gluconate", "Sodium Bicarbonate"]),
    ("Toxicology / Prophylaxis", ["Activated Charcoal", "Tetanus/Tdap Booster"]),
    ("Sedation / RSI / Paralytics", ["Propofol", "Ketamine", "Etomidate", "Rocuronium", "Succinylcholine"]),
]

OTHER_CATEGORIES = [
    ("Cardiac / Monitoring", ["EKG", "Continuous Cardiac Monitoring", "Continuous Pulse Oximetry", "Vital Signs per ED Protocol"]),
    ("Access / Respiratory", ["IV Access", "Nasal Cannula Oxygen @ 2 L/min", "Foley Catheter", "Straight Catheterization"]),
    ("Diet / Precautions", ["NPO", "Fall Precautions", "Aspiration Precautions", "Strict Intake & Output", "Close Observation (Suicide Precautions)", "C-Collar Placement"]),
    ("Wound / Orthopedic Care", ["Wound Care / Dressing Change", "Splint Application", "Ice Pack to Affected Area", "Elevate Extremity", "Weight-Bearing as Tolerated", "Non-Weight-Bearing"]),
    ("Neuro / Stroke", ["NIH Stroke Scale", "Neuro Checks", "Dysphagia Screen"]),
    ("Consults / Therapy", ["Social Work Consult", "Case Management Consult", "Incentive Spirometry"]),
]


def _grouped(items, categories, name_of=lambda item: item):
    """Groups `items` into (label, [item, ...]) sections per `categories`,
    in the order given there; anything left over goes into a trailing
    "Other" section, preserving its original relative order."""
    assigned = set()
    groups = []
    for label, wanted in categories:
        by_name = {name_of(item): item for item in items}
        present = [by_name[n] for n in wanted if n in by_name]
        if present:
            groups.append((label, present))
            assigned.update(name_of(item) for item in present)
    leftover = [item for item in items if name_of(item) not in assigned]
    if leftover:
        groups.append(("Other", leftover))
    return groups


class ScrollableFrame(ttk.Frame):
    """A vertically scrollable frame. Put widgets in `self.body`."""

    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        self.body = ttk.Frame(canvas)

        self.body.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        window_id = canvas.create_window((0, 0), window=self.body, anchor="nw")
        canvas.bind(
            "<Configure>",
            lambda e: canvas.itemconfigure(window_id, width=e.width),
        )
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def _on_mousewheel(event):
            delta = event.delta
            if platform.system() == "Darwin":
                canvas.yview_scroll(int(-1 * delta), "units")
            else:
                canvas.yview_scroll(int(-1 * delta / 120), "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel, add="+")


class MedRow:
    """Widget state for one row in the Medications tab."""

    def __init__(
        self, med, var, dose_var, route_var, freq_var,
        prn_var, prn_reason_var, prn_check, prn_reason_combo, widgets,
    ):
        self.med = med
        self.var = var
        self.dose_var = dose_var
        self.route_var = route_var
        self.freq_var = freq_var
        self.prn_var = prn_var
        self.prn_reason_var = prn_reason_var
        self.prn_check = prn_check
        self.prn_reason_combo = prn_reason_combo
        self.widgets = widgets  # every widget in this row, for bulk enable/disable


class DripRow:
    """Widget state for one row in the Drips tab."""

    def __init__(
        self, drip, var, initial_dose_var, titrate_by_var, titrate_freq_var,
        max_dose_var, goal_var, protocol_var, widgets,
    ):
        self.drip = drip
        self.var = var
        self.initial_dose_var = initial_dose_var
        self.titrate_by_var = titrate_by_var
        self.titrate_freq_var = titrate_freq_var
        self.max_dose_var = max_dose_var
        self.goal_var = goal_var
        self.protocol_var = protocol_var
        self.widgets = widgets  # every widget in this row, for bulk enable/disable


class EDOrderApp(tk.Tk):
    def __init__(self):
        super().__init__()
        printing.cleanup_orphans()

        self.title("Order Sheet Generator")
        self.geometry("1150x800")

        if data.LOAD_ERROR:
            self.after(200, lambda: messagebox.showwarning(
                "Order list file problem",
                "{}\n\nUsing the built-in default order lists instead. Fix or delete "
                "data.json next to the app and restart to pick up your custom lists.".format(
                    data.LOAD_ERROR
                ),
            ))

        top_row = ttk.Frame(self)
        top_row.pack(fill="x")
        self._build_order_info_bar(top_row)
        ttk.Button(top_row, text="Clear All Selections", command=self._clear_all_orders).pack(
            side="right", anchor="n", padx=8, pady=8
        )

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=8, pady=(4, 0))

        self.order_sets_tab = ScrollableFrame(self.notebook)
        self.labs_tab = ScrollableFrame(self.notebook)
        self.meds_tab = ScrollableFrame(self.notebook)
        self.drips_tab = ScrollableFrame(self.notebook)
        self.imaging_tab = ttk.Frame(self.notebook)
        self.other_tab = ScrollableFrame(self.notebook)

        self.notebook.add(self.order_sets_tab, text="Order Sets")
        self.notebook.add(self.labs_tab, text="Labs")
        self.notebook.add(self.meds_tab, text="Medications")
        self.notebook.add(self.drips_tab, text="Drips")
        self.notebook.add(self.imaging_tab, text="Imaging")
        self.notebook.add(self.other_tab, text="Other Orders")

        self.lab_vars = []
        self.med_rows = []
        self.drip_rows = []
        self.other_vars = []
        self.imaging_studies = []
        self.custom_orders = []
        self.active_aop = None  # set to an order_set dict while an AOP is locking the app
        self.active_aop_modifiers = []  # order_set dicts stacked on top of active_aop
        self.aop_banner_var = tk.StringVar(value="")

        self._build_labs_tab()
        self._build_meds_tab()
        self._build_drips_tab()
        self._build_imaging_tab()
        self._build_other_tab()
        self._build_order_sets_tab()  # after the others -- it looks up their vars by name

        self._build_bottom_bar()

    # -- Order info ---------------------------------------------------------
    def _build_order_info_bar(self, parent):
        frame = ttk.LabelFrame(parent, text="Order Info")
        frame.pack(side="left", fill="x", expand=True, padx=8, pady=8)

        now = datetime.now()

        ttk.Label(frame, text="Physician Name (with credentials, e.g. \"MD\"):").grid(
            row=0, column=0, sticky="e", padx=(10, 2), pady=6
        )
        self.physician_var = tk.StringVar(value="")
        ttk.Combobox(
            frame, textvariable=self.physician_var, values=data.PROVIDERS, width=26,
        ).grid(row=0, column=1, sticky="w", pady=6)

        row2 = ttk.Frame(frame)
        row2.grid(row=1, column=0, columnspan=6, sticky="w")
        ttk.Label(row2, text="Ordering Nurse Name (for AOP orders):").pack(side="left", padx=(10, 2), pady=(0, 6))
        self.nurse_name_var = tk.StringVar(value="")
        ttk.Entry(row2, textvariable=self.nurse_name_var, width=22).pack(side="left")

        row3 = ttk.Frame(frame)
        row3.grid(row=2, column=0, columnspan=6, sticky="w")
        ttk.Label(row3, text="Order Date (MM/DD/YY):").pack(side="left", padx=(10, 2), pady=(0, 6))
        self.order_date_var = tk.StringVar(value=now.strftime("%m/%d/%y"))
        ttk.Entry(row3, textvariable=self.order_date_var, width=10).pack(side="left")

        ttk.Label(row3, text="Order Time (HH:MM):").pack(side="left", padx=(16, 2))
        self.order_time_var = tk.StringVar(value=now.strftime("%H:%M"))
        ttk.Entry(row3, textvariable=self.order_time_var, width=8).pack(side="left")

        ttk.Button(row3, text="Set to Now", command=self._set_now).pack(side="left", padx=12)

    def _set_now(self):
        now = datetime.now()
        self.order_date_var.set(now.strftime("%m/%d/%y"))
        self.order_time_var.set(now.strftime("%H:%M"))

    # -- Labs tab -----------------------------------------------------------
    def _build_labs_tab(self):
        body = self.labs_tab.body
        cols = 3
        self.lab_cell_by_name = {}
        row = 0
        for label, labs in _grouped(data.LABS, LAB_CATEGORIES):
            ttk.Label(body, text=label, font=("TkDefaultFont", 9, "bold")).grid(
                row=row, column=0, columnspan=cols, sticky="w", padx=10, pady=(10, 2)
            )
            start_row = row + 1
            for i, lab in enumerate(labs):
                r, c = divmod(i, cols)
                cell = ttk.Frame(body)
                cell.grid(row=start_row + r, column=c, sticky="w", padx=10, pady=4)
                var = tk.BooleanVar(value=False)
                ttk.Checkbutton(cell, text=lab, variable=var, width=28).pack(side="left")
                self.lab_vars.append((lab, var))
                self.lab_cell_by_name[lab] = cell
            row = start_row + divmod(len(labs) - 1, cols)[0] + 1

        self.lab_var_by_name = {name: var for name, var in self.lab_vars}

    # -- Medications tab ------------------------------------------------------
    def _build_meds_tab(self):
        body = self.meds_tab.body

        # Every widget below grids directly into `body` with a shared set of
        # column indices (header included) -- that's what guarantees the
        # header labels and the entry/combobox columns actually line up.
        # Packing each row in its own sub-frame (the previous approach)
        # doesn't: pack sizes each row independently from its widgets'
        # *rendered* width, and a bold header Label measures differently
        # per character than a regular-weight Entry/Combobox, so the
        # column boundaries silently drift apart from row to row.
        columns = [
            ("", 0), ("Medication", 1), ("Dose", 2), ("Route", 3),
            ("Frequency", 4), ("PRN", 5), ("PRN Reason", 6),
        ]
        for text, col in columns:
            ttk.Label(body, text=text, font=("TkDefaultFont", 9, "bold")).grid(
                row=0, column=col, sticky="w", padx=(10 if col == 0 else 2, 2), pady=(6, 4)
            )

        r = 1
        for label, meds in _grouped(data.MEDICATIONS, MED_CATEGORIES, name_of=lambda m: m["name"]):
            ttk.Label(body, text=label, font=("TkDefaultFont", 9, "bold", "italic")).grid(
                row=r, column=0, columnspan=len(columns), sticky="w", padx=10, pady=(10, 2)
            )
            r += 1
            for med in meds:
                widgets = []

                var = tk.BooleanVar(value=False)
                cb = ttk.Checkbutton(body, variable=var)
                cb.grid(row=r, column=0, sticky="w", padx=(10, 2), pady=1)
                widgets.append(cb)

                name_text = med["name"] + (" (wt-based)" if med.get("requires_weight") else "")
                name_label = ttk.Label(body, text=name_text)
                name_label.grid(row=r, column=1, sticky="w", padx=2, pady=1)
                widgets.append(name_label)

                dose_var = tk.StringVar(value=med.get("default_dose", ""))
                dose_entry = ttk.Entry(body, textvariable=dose_var, width=10)
                dose_entry.grid(row=r, column=2, sticky="w", padx=2, pady=1)
                widgets.append(dose_entry)

                route_var = tk.StringVar(value=med.get("default_route", ""))
                route_combo = ttk.Combobox(body, textvariable=route_var, values=data.COMMON_ROUTES, width=7)
                route_combo.grid(row=r, column=3, sticky="w", padx=2, pady=1)
                widgets.append(route_combo)

                freq_var = tk.StringVar(value=med.get("default_frequency", ""))
                freq_combo = ttk.Combobox(body, textvariable=freq_var, values=data.COMMON_FREQUENCIES, width=9)
                freq_combo.grid(row=r, column=4, sticky="w", padx=2, pady=1)
                widgets.append(freq_combo)

                prn_var = tk.BooleanVar(value=False)
                prn_reason_var = tk.StringVar(value=med.get("default_prn_reason", ""))
                prn_reason_combo = ttk.Combobox(
                    body, textvariable=prn_reason_var, values=data.PRN_REASONS, width=18, state="disabled",
                )

                def on_prn_toggle(prn_var=prn_var, combo=prn_reason_combo):
                    combo.configure(state="normal" if prn_var.get() else "disabled")

                prn_check = ttk.Checkbutton(body, variable=prn_var, command=on_prn_toggle)
                prn_check.grid(row=r, column=5, sticky="w", padx=2, pady=1)
                if not med.get("allow_prn"):
                    prn_check.configure(state="disabled")
                widgets.append(prn_check)

                prn_reason_combo.grid(row=r, column=6, sticky="w", padx=2, pady=1)
                widgets.append(prn_reason_combo)

                self.med_rows.append(MedRow(
                    med, var, dose_var, route_var, freq_var, prn_var, prn_reason_var, prn_check, prn_reason_combo, widgets,
                ))
                r += 1

        self.med_row_by_name = {row.med["name"]: row for row in self.med_rows}

    # -- Drips tab --------------------------------------------------------------
    def _build_drips_tab(self):
        body = self.drips_tab.body

        # See the comment in _build_meds_tab -- everything grids directly
        # into `body` on shared column indices so the header actually lines
        # up with the columns below it.
        ttk.Label(
            body,
            text="Continuous IV infusions with titration instructions.",
        ).grid(row=0, column=0, columnspan=7, sticky="w", padx=10, pady=(6, 6))

        columns = [
            ("", 0), ("Drip", 1), ("Initial Dose", 2), ("Titrate By", 3),
            ("Frequency", 4), ("Max Dose", 5), ("Goal", 6),
        ]
        for text, col in columns:
            ttk.Label(body, text=text, font=("TkDefaultFont", 9, "bold")).grid(
                row=1, column=col, sticky="w", padx=(10 if col == 0 else 2, 2), pady=(0, 4)
            )

        for i, drip in enumerate(data.DRIPS):
            r = i + 2
            widgets = []
            is_protocol = bool(drip.get("is_protocol"))

            var = tk.BooleanVar(value=False)
            cb = ttk.Checkbutton(body, variable=var)
            cb.grid(row=r, column=0, sticky="w", padx=(10, 2), pady=1)
            widgets.append(cb)

            name_text = drip["name"] + (" (wt-based)" if drip.get("requires_weight") else "")
            name_label = ttk.Label(body, text=name_text)
            name_label.grid(row=r, column=1, sticky="w", padx=2, pady=1)
            widgets.append(name_label)

            protocol_var = tk.StringVar(value=drip.get("default_protocol_text", ""))

            if is_protocol:
                # Fixed, non-titrated regimen (e.g. Amiodarone's load-then-
                # maintenance dosing) -- one free-text field spanning where
                # the titration columns would be, instead of them.
                protocol_entry = ttk.Entry(body, textvariable=protocol_var, width=70)
                protocol_entry.grid(row=r, column=2, columnspan=5, sticky="w", padx=2, pady=1)
                widgets.append(protocol_entry)
                initial_dose_var = tk.StringVar(value="")
                titrate_by_var = tk.StringVar(value="")
                titrate_freq_var = tk.StringVar(value="")
                max_dose_var = tk.StringVar(value="")
                goal_var = tk.StringVar(value="")
            else:
                initial_dose_var = tk.StringVar(value=drip.get("default_initial_dose", ""))
                initial_dose_entry = ttk.Entry(body, textvariable=initial_dose_var, width=14)
                initial_dose_entry.grid(row=r, column=2, sticky="w", padx=2, pady=1)
                widgets.append(initial_dose_entry)

                titrate_by_var = tk.StringVar(value=drip.get("default_titrate_by", ""))
                titrate_by_entry = ttk.Entry(body, textvariable=titrate_by_var, width=14)
                titrate_by_entry.grid(row=r, column=3, sticky="w", padx=2, pady=1)
                widgets.append(titrate_by_entry)

                titrate_freq_var = tk.StringVar(value=drip.get("default_titrate_frequency", ""))
                titrate_freq_combo = ttk.Combobox(
                    body, textvariable=titrate_freq_var, values=data.TITRATE_FREQUENCIES, width=9
                )
                titrate_freq_combo.grid(row=r, column=4, sticky="w", padx=2, pady=1)
                widgets.append(titrate_freq_combo)

                max_dose_var = tk.StringVar(value=drip.get("default_max_dose", ""))
                max_dose_entry = ttk.Entry(body, textvariable=max_dose_var, width=13)
                max_dose_entry.grid(row=r, column=5, sticky="w", padx=2, pady=1)
                widgets.append(max_dose_entry)

                goal_var = tk.StringVar(value=drip.get("default_goal", ""))
                goal_entry = ttk.Entry(body, textvariable=goal_var, width=22)
                goal_entry.grid(row=r, column=6, sticky="w", padx=2, pady=1)
                widgets.append(goal_entry)

            self.drip_rows.append(DripRow(
                drip, var, initial_dose_var, titrate_by_var, titrate_freq_var,
                max_dose_var, goal_var, protocol_var, widgets,
            ))

        self.drip_row_by_name = {row.drip["name"]: row for row in self.drip_rows}

    # -- Imaging tab ------------------------------------------------------------
    def _build_imaging_tab(self):
        top = ttk.LabelFrame(self.imaging_tab, text="Add Imaging Study")
        top.pack(fill="x", padx=10, pady=10)
        self.imaging_add_frame = top

        ttk.Label(top, text="Modality:").grid(row=0, column=0, sticky="e", padx=6, pady=6)
        self.modality_var = tk.StringVar(value="XR")
        self.modality_combo = ttk.Combobox(
            top, textvariable=self.modality_var,
            values=list(data.IMAGING_MODALITIES.keys()), width=8, state="readonly",
        )
        self.modality_combo.grid(row=0, column=1, sticky="w", pady=6)

        ttk.Label(top, text="Study:").grid(row=0, column=2, sticky="e", padx=6)
        self.study_var = tk.StringVar()
        # Editable (not "readonly") so a study not in the list can be typed in directly.
        self.study_combo = ttk.Combobox(top, textvariable=self.study_var, width=32, state="normal")
        self.study_combo.grid(row=0, column=3, sticky="w", pady=6)

        self.contrast_var = tk.BooleanVar(value=False)
        self.contrast_check = ttk.Checkbutton(top, text="With Contrast", variable=self.contrast_var)
        self.contrast_check.grid(row=0, column=4, sticky="w", padx=6)

        self.side_label = ttk.Label(top, text="Side:")
        self.side_label.grid(row=0, column=5, sticky="e", padx=(6, 2))
        self.laterality_var = tk.StringVar(value="")
        self.laterality_combo = ttk.Combobox(
            top, textvariable=self.laterality_var, values=["", "Left", "Right", "Bilateral"],
            width=9, state="readonly",
        )
        self.laterality_combo.grid(row=0, column=6, sticky="w")

        sided_lower = {s.lower() for s in data.SIDED_STUDIES}

        def update_laterality_visibility(*_):
            study = self.study_var.get().strip().lower()
            if study in sided_lower:
                self.side_label.grid()
                self.laterality_combo.grid()
            else:
                self.laterality_var.set("")
                self.side_label.grid_remove()
                self.laterality_combo.grid_remove()

        self.study_var.trace_add("write", update_laterality_visibility)

        def on_modality_change(*_):
            modality = self.modality_var.get()
            studies = data.IMAGING_MODALITIES.get(modality, [])
            self.study_combo["values"] = studies
            if studies:
                self.study_var.set(studies[0])
            if modality in data.CONTRAST_MODALITIES:
                self.contrast_check.grid()
            else:
                self.contrast_var.set(False)
                self.contrast_check.grid_remove()

        self.modality_combo.bind("<<ComboboxSelected>>", on_modality_change)
        on_modality_change()

        ttk.Label(top, text="Indication:").grid(row=1, column=0, sticky="e", padx=6, pady=6)
        self.indication_var = tk.StringVar()
        ttk.Entry(top, textvariable=self.indication_var, width=45).grid(
            row=1, column=1, columnspan=3, sticky="w", pady=6
        )

        ttk.Button(top, text="+ Add Study", command=self._add_imaging_study).grid(
            row=0, column=7, rowspan=2, padx=10
        )

        list_frame = ttk.LabelFrame(self.imaging_tab, text="Studies to Order")
        list_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        columns = ("modality", "study", "indication")
        self.imaging_tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=10)
        for col, w in zip(columns, (70, 260, 400)):
            self.imaging_tree.heading(col, text=col.capitalize())
            self.imaging_tree.column(col, width=w)
        self.imaging_tree.pack(fill="both", expand=True, side="left", padx=(6, 0), pady=6)

        scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.imaging_tree.yview)
        self.imaging_tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="left", fill="y", pady=6)

        btns = ttk.Frame(list_frame)
        btns.pack(side="left", fill="y", padx=10)
        ttk.Button(btns, text="Remove Selected", command=self._remove_imaging_study).pack(pady=4)
        ttk.Button(btns, text="Clear All", command=self._clear_imaging_studies).pack(pady=4)
        self.imaging_manage_frame = btns

    @staticmethod
    def _compose_study_text(modality, study, contrast, laterality=""):
        text = study.strip()
        if laterality:
            text = "{} {}".format(laterality, text)
        if modality in data.CONTRAST_MODALITIES and contrast and "contrast" not in text.lower():
            text = "{} w/ Contrast".format(text)
        return text

    def _add_imaging_study(self):
        modality = self.modality_var.get()
        study = self.study_var.get().strip()
        indication = self.indication_var.get().strip()
        if not study:
            messagebox.showwarning("Missing study", "Choose or type a study before adding.")
            return
        self._add_imaging_study_from(
            modality, study, indication, self.contrast_var.get(), self.laterality_var.get()
        )
        self.indication_var.set("")
        self.laterality_var.set("")

    def _add_imaging_study_from(self, modality, study, indication, contrast=False, laterality=""):
        """Adds one imaging study to the list/tree. Used both by the "+ Add
        Study" button (reading the current input fields) and by order sets
        (passing explicit values, without touching those input fields)."""
        study_text = self._compose_study_text(modality, study, contrast, laterality)
        record = {"modality": modality, "study": study_text, "indication": indication}
        self.imaging_studies.append(record)
        self.imaging_tree.insert("", "end", values=(modality, study_text, indication))

    def _remove_imaging_study(self):
        selected = self.imaging_tree.selection()
        for item in selected:
            idx = self.imaging_tree.index(item)
            self.imaging_tree.delete(item)
            del self.imaging_studies[idx]

    def _clear_imaging_studies(self):
        for item in self.imaging_tree.get_children():
            self.imaging_tree.delete(item)
        self.imaging_studies.clear()

    # -- Other Orders tab ---------------------------------------------------
    def _build_other_tab(self):
        body = self.other_tab.body

        preset_frame = ttk.LabelFrame(body, text="Common Orders")
        preset_frame.grid(row=0, column=0, sticky="w", padx=10, pady=10)
        cols = 2
        self.other_cell_by_name = {}
        self.ekg_indication_var = tk.StringVar(value="")
        self.ekg_indication_combo = None
        row = 0
        for label, items in _grouped(data.OTHER_ORDERS, OTHER_CATEGORIES):
            ttk.Label(preset_frame, text=label, font=("TkDefaultFont", 9, "bold", "italic")).grid(
                row=row, column=0, columnspan=cols, sticky="w", padx=10, pady=(10, 2)
            )
            start_row = row + 1
            for i, item in enumerate(items):
                r, c = divmod(i, cols)
                cell = ttk.Frame(preset_frame)
                cell.grid(row=start_row + r, column=c, sticky="w", padx=10, pady=4)
                var = tk.BooleanVar(value=False)
                cb_width = 12 if item == "EKG" else 32
                checkbutton = ttk.Checkbutton(cell, text=item, variable=var, width=cb_width)
                checkbutton.pack(side="left")
                if item == "EKG":
                    ttk.Label(cell, text="Indication").pack(side="left", padx=(8, 2))
                    combo = ttk.Combobox(
                        cell, textvariable=self.ekg_indication_var,
                        values=data.EKG_INDICATIONS, width=22, state="disabled",
                    )
                    combo.pack(side="left")
                    self.ekg_indication_combo = combo

                    def on_ekg_toggle(var=var, combo=combo):
                        combo.configure(state="normal" if var.get() else "disabled")

                    checkbutton.configure(command=on_ekg_toggle)
                self.other_vars.append((item, var))
                self.other_cell_by_name[item] = cell
            row = start_row + divmod(len(items) - 1, cols)[0] + 1

        self.other_var_by_name = {name: var for name, var in self.other_vars}

        custom_frame = ttk.LabelFrame(body, text="Custom Order (free text)")
        custom_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=10)
        self.custom_add_frame = custom_frame

        self.custom_entry_var = tk.StringVar()
        ttk.Entry(custom_frame, textvariable=self.custom_entry_var, width=60).pack(
            side="left", padx=6, pady=6
        )
        ttk.Button(custom_frame, text="+ Add", command=self._add_custom_order).pack(side="left", padx=6)

        self.custom_listbox = tk.Listbox(body, height=6, width=90)
        self.custom_listbox.grid(row=2, column=0, sticky="w", padx=10, pady=(0, 6))
        self.custom_remove_btn = ttk.Button(
            body, text="Remove Selected Custom Order", command=self._remove_custom_order,
        )
        self.custom_remove_btn.grid(row=3, column=0, sticky="w", padx=10, pady=(0, 10))

    def _add_custom_order(self):
        text = self.custom_entry_var.get().strip()
        if not text:
            return
        self.custom_orders.append(text)
        self.custom_listbox.insert("end", text)
        self.custom_entry_var.set("")

    def _remove_custom_order(self):
        sel = list(self.custom_listbox.curselection())
        sel.reverse()
        for idx in sel:
            self.custom_listbox.delete(idx)
            del self.custom_orders[idx]

    # -- Order Sets tab ---------------------------------------------------------
    def _build_order_sets_tab(self):
        frame = self.order_sets_tab.body
        self.order_set_buttons = []
        self.aop_modifier_buttons = []

        regular_sets = [s for s in data.ORDER_SETS if not s.get("is_aop") and not s.get("is_aop_modifier")]
        aop_sets = [s for s in data.ORDER_SETS if s.get("is_aop")]
        modifier_sets = [s for s in data.ORDER_SETS if s.get("is_aop_modifier")]
        cols = 3

        ttk.Label(
            frame,
            text="Physician Order Sets -- additive; combine as many as you like with each other or with "
                 "manual selections.",
        ).pack(anchor="w", padx=10, pady=(10, 4))
        reg_grid = ttk.Frame(frame)
        reg_grid.pack(fill="x", padx=10, pady=(0, 10))
        for i, order_set in enumerate(regular_sets):
            r, c = divmod(i, cols)
            btn = ttk.Button(
                reg_grid, text=order_set["name"], width=26,
                command=lambda os=order_set: self._apply_order_set(os),
            )
            btn.grid(row=r, column=c, padx=6, pady=6, sticky="ew")
            self.order_set_buttons.append(btn)

        ttk.Separator(frame, orient="horizontal").pack(fill="x", padx=10, pady=6)

        ttk.Label(
            frame,
            text="AOP / Nurse Protocol Order Sets -- clicking one clears any current selections, checks off "
                 "exactly that protocol's orders, and locks everything else in the app until you click "
                 "\"Clear All Selections\".",
        ).pack(anchor="w", padx=10, pady=(4, 4))
        aop_grid = ttk.Frame(frame)
        aop_grid.pack(fill="x", padx=10, pady=(0, 10))
        for i, order_set in enumerate(aop_sets):
            r, c = divmod(i, cols)
            btn = ttk.Button(
                aop_grid, text=order_set["name"], width=26,
                command=lambda os=order_set: self._apply_aop(os),
            )
            btn.grid(row=r, column=c, padx=6, pady=6, sticky="ew")
            self.order_set_buttons.append(btn)

        if modifier_sets:
            ttk.Separator(frame, orient="horizontal").pack(fill="x", padx=10, pady=6)

            ttk.Label(
                frame,
                text="AOP Modifiers -- stack on top of an active AOP (or apply standalone) without clearing "
                     "or locking anything themselves; stay clickable even while an AOP is active.",
            ).pack(anchor="w", padx=10, pady=(4, 4))
            mod_grid = ttk.Frame(frame)
            mod_grid.pack(fill="x", padx=10, pady=(0, 10))
            for i, order_set in enumerate(modifier_sets):
                r, c = divmod(i, cols)
                btn = ttk.Button(
                    mod_grid, text=order_set["name"], width=26,
                    command=lambda os=order_set: self._apply_aop_modifier(os),
                )
                btn.grid(row=r, column=c, padx=6, pady=6, sticky="ew")
                self.aop_modifier_buttons.append(btn)

        ttk.Button(frame, text="Clear All Selections", command=self._clear_all_orders).pack(
            anchor="w", padx=10, pady=(10, 4)
        )

        self.order_set_status_var = tk.StringVar(value="")
        ttk.Label(frame, textvariable=self.order_set_status_var, foreground="#2a6b2a", wraplength=1050).pack(
            anchor="w", padx=10, pady=(4, 10)
        )

    def _apply_items(self, order_set):
        """Checks off / adds everything in order_set; returns the list of
        item names applied. Shared by regular order sets and AOPs."""
        applied = []

        for lab_name in order_set.get("labs", []):
            var = self.lab_var_by_name.get(lab_name)
            if var is not None:
                var.set(True)
                applied.append(lab_name)

        for spec in order_set.get("medications", []):
            row = self.med_row_by_name.get(spec["name"])
            if row is None:
                continue
            row.var.set(True)
            if "dose" in spec:
                row.dose_var.set(spec["dose"])
            if "route" in spec:
                row.route_var.set(spec["route"])
            if "frequency" in spec:
                row.freq_var.set(spec["frequency"])
            if spec.get("prn") and row.med.get("allow_prn"):
                row.prn_var.set(True)
                row.prn_reason_combo.configure(state="normal")
                if "prn_reason" in spec:
                    row.prn_reason_var.set(spec["prn_reason"])
            applied.append(spec["name"])

        for spec in order_set.get("drips", []):
            row = self.drip_row_by_name.get(spec["name"])
            if row is None:
                continue
            row.var.set(True)
            if "initial_dose" in spec:
                row.initial_dose_var.set(spec["initial_dose"])
            if "titrate_by" in spec:
                row.titrate_by_var.set(spec["titrate_by"])
            if "titrate_frequency" in spec:
                row.titrate_freq_var.set(spec["titrate_frequency"])
            if "max_dose" in spec:
                row.max_dose_var.set(spec["max_dose"])
            if "goal" in spec:
                row.goal_var.set(spec["goal"])
            if "protocol" in spec:
                row.protocol_var.set(spec["protocol"])
            applied.append(spec["name"])

        for spec in order_set.get("imaging", []):
            self._add_imaging_study_from(
                spec["modality"], spec["study"], spec.get("indication", ""),
                spec.get("contrast", False), spec.get("side", ""),
            )
            applied.append("{} {}".format(spec["modality"], spec["study"]))

        for name in order_set.get("other", []):
            var = self.other_var_by_name.get(name)
            if var is not None:
                var.set(True)
                applied.append(name)
                if name == "EKG" and self.ekg_indication_combo is not None:
                    self.ekg_indication_combo.configure(state="normal")

        ekg_indication = order_set.get("ekg_indication")
        if ekg_indication:
            self.ekg_indication_var.set(ekg_indication)

        return applied

    def _apply_order_set(self, order_set):
        if self.active_aop:
            return  # defensive -- these buttons are disabled during AOP lockdown anyway
        applied = self._apply_items(order_set)
        self.order_set_status_var.set(
            'Applied "{}" -- {} item(s) checked/added.'.format(order_set["name"], len(applied))
        )

    def _apply_aop(self, order_set):
        self._set_lockdown(False)  # in case anything was left disabled; defensive
        self._clear_selection_state()
        self.active_aop_modifiers = []
        applied = self._apply_items(order_set)
        self.active_aop = order_set
        self._set_lockdown(True)

        self.order_set_status_var.set(
            'AOP ACTIVE: "{}" (Indication: {}) -- {} item(s) checked. All other ordering is locked. '
            'Click "Clear All Selections" below to exit AOP mode. AOP Modifiers above stay available '
            'to stack on top of this.'.format(order_set["name"], order_set.get("indication", ""), len(applied))
        )
        self._update_aop_banner()

    def _apply_aop_modifier(self, order_set):
        applied = self._apply_items(order_set)
        if self.active_aop:
            self.active_aop_modifiers.append(order_set)
            self._set_lockdown(True)  # recompute the allowed set to include this modifier's items
        self.order_set_status_var.set(
            'Applied modifier "{}" -- {} item(s) checked/added.'.format(order_set["name"], len(applied))
        )
        self._update_aop_banner()

    def _update_aop_banner(self):
        if not self.active_aop:
            self.aop_banner_var.set("")
            return
        names = [self.active_aop["name"]] + [m["name"] for m in self.active_aop_modifiers]
        self.aop_banner_var.set(
            'AOP MODE ACTIVE: "{}" (Indication: {})'.format(
                " + ".join(names), self.active_aop.get("indication", "")
            )
        )

    @staticmethod
    def _set_widget_tree_state(widget, state):
        try:
            widget.configure(state=state)
        except tk.TclError:
            pass
        for child in widget.winfo_children():
            EDOrderApp._set_widget_tree_state(child, state)

    def _set_lockdown(self, locked):
        """When locked, disables every order-selection control that isn't
        part of the active AOP or one of its stacked modifiers (those items
        stay editable), plus every regular/AOP order-set button (modifier
        buttons stay enabled -- they're meant to stack on top). "Clear All
        Selections" is the only other escape hatch and is never disabled."""
        aop_sets = ([self.active_aop] + self.active_aop_modifiers) if locked and self.active_aop else []
        allowed_labs = {n for s in aop_sets for n in s.get("labs", [])}
        allowed_meds = {m["name"] for s in aop_sets for m in s.get("medications", [])}
        allowed_drips = {d["name"] for s in aop_sets for d in s.get("drips", [])}
        allowed_other = {n for s in aop_sets for n in s.get("other", [])}

        for name, cell in self.lab_cell_by_name.items():
            state = "normal" if (not locked or name in allowed_labs) else "disabled"
            self._set_widget_tree_state(cell, state)

        for row in self.med_rows:
            state = "normal" if (not locked or row.med["name"] in allowed_meds) else "disabled"
            for widget in row.widgets:
                widget.configure(state=state)

        for row in self.drip_rows:
            state = "normal" if (not locked or row.drip["name"] in allowed_drips) else "disabled"
            for widget in row.widgets:
                widget.configure(state=state)

        for name, cell in self.other_cell_by_name.items():
            state = "normal" if (not locked or name in allowed_other) else "disabled"
            self._set_widget_tree_state(cell, state)

        imaging_state = "disabled" if locked else "normal"
        self._set_widget_tree_state(self.imaging_add_frame, imaging_state)
        self._set_widget_tree_state(self.imaging_manage_frame, imaging_state)

        custom_state = "disabled" if locked else "normal"
        self._set_widget_tree_state(self.custom_add_frame, custom_state)
        self.custom_remove_btn.configure(state=custom_state)

        for btn in self.order_set_buttons:
            btn.configure(state="disabled" if locked else "normal")

        # The blanket "normal" pass above would otherwise re-enable a PRN
        # checkbox for a medication that doesn't allow PRN at all, and
        # doesn't know to re-disable a PRN Reason combo whose box is
        # currently unchecked -- fix both up regardless of `locked`.
        for row in self.med_rows:
            if not row.med.get("allow_prn"):
                row.prn_check.configure(state="disabled")
                row.prn_reason_combo.configure(state="disabled")
            else:
                row.prn_reason_combo.configure(state="normal" if row.prn_var.get() else "disabled")

        if self.ekg_indication_combo is not None:
            ekg_var = self.other_var_by_name.get("EKG")
            ekg_allowed = ekg_var is not None and (not locked or "EKG" in allowed_other)
            self.ekg_indication_combo.configure(
                state="normal" if (ekg_allowed and ekg_var.get()) else "disabled"
            )

    def _clear_selection_state(self):
        """Unchecks/clears everything without touching lock state -- the
        data-only half of _clear_all_orders, reused by _apply_aop so it can
        start from a clean slate before applying the protocol."""
        for _, var in self.lab_vars:
            var.set(False)
        for row in self.med_rows:
            row.var.set(False)
            row.prn_var.set(False)
            row.prn_reason_combo.configure(state="disabled")
        for row in self.drip_rows:
            row.var.set(False)
        for _, var in self.other_vars:
            var.set(False)
        self.ekg_indication_var.set("")
        if self.ekg_indication_combo is not None:
            self.ekg_indication_combo.configure(state="disabled")
        self._clear_imaging_studies()
        self.custom_orders.clear()
        self.custom_listbox.delete(0, "end")

    def _clear_all_orders(self):
        self.active_aop = None
        self.active_aop_modifiers = []
        self._set_lockdown(False)
        self._clear_selection_state()
        self.aop_banner_var.set("")
        self.order_set_status_var.set("All selections cleared.")

    # -- Bottom bar / generate ------------------------------------------------
    def _build_bottom_bar(self):
        ttk.Label(
            self, textvariable=self.aop_banner_var,
            foreground="#a02020", font=("TkDefaultFont", 10, "bold"),
        ).pack(fill="x", padx=8, pady=(0, 4), anchor="w")

        bar = ttk.Frame(self)
        bar.pack(fill="x", padx=8, pady=10)

        ttk.Label(
            bar,
            text="Nothing is saved — orders go straight to the print dialog and the "
                 "temporary file is deleted right after.",
            foreground="#555555",
        ).pack(side="left", padx=(0, 20))

        ttk.Button(bar, text="Print Order Sheet", command=self._print_order_sheet).pack(side="right", padx=4)
        ttk.Button(bar, text="Preview on Screen...", command=self._preview_order_sheet).pack(side="right", padx=4)

    def _collect_orders(self):
        """Returns a list of {"text": str, "requires_weight": bool, "group":
        str} dicts, one per checked/added order, in Labs -> Medications ->
        Imaging -> Other -> Custom order. The "group" tag lets pdf_gen keep
        a whole contiguous run (e.g. all medications) together on one page
        instead of splitting it across a page boundary."""
        orders = []

        for lab_name, var in self.lab_vars:
            if var.get():
                orders.append({"text": lab_name, "requires_weight": False, "group": "labs"})

        for row in self.med_rows:
            if not row.var.get():
                continue
            parts = [row.med["name"]]
            dose = row.dose_var.get().strip()
            route = row.route_var.get().strip()
            freq = row.freq_var.get().strip()
            if dose:
                parts.append(dose)
            if route:
                parts.append(route)
            if freq:
                parts.append(freq)
            text = " ".join(parts)
            if row.prn_var.get():
                reason = row.prn_reason_var.get().strip()
                text += " PRN" + (" for {}".format(reason) if reason else "")
            orders.append({
                "text": text,
                "requires_weight": bool(row.med.get("requires_weight")),
                "group": "medications",
            })

        for row in self.drip_rows:
            if not row.var.get():
                continue
            parts = [row.drip["name"]]
            if row.drip.get("is_protocol"):
                protocol = row.protocol_var.get().strip()
                if protocol:
                    parts.append(protocol)
            else:
                initial_dose = row.initial_dose_var.get().strip()
                titrate_by = row.titrate_by_var.get().strip()
                titrate_freq = row.titrate_freq_var.get().strip()
                max_dose = row.max_dose_var.get().strip()
                goal = row.goal_var.get().strip()
                if initial_dose:
                    parts.append("Start {}".format(initial_dose))
                if titrate_by:
                    titration = "Titrate by {}".format(titrate_by)
                    if titrate_freq:
                        titration += " {}".format(titrate_freq)
                    parts.append(titration)
                if max_dose:
                    parts.append("Max {}".format(max_dose))
                if goal:
                    parts.append("Goal: {}".format(goal))
            orders.append({
                "text": " - ".join(parts),
                "requires_weight": bool(row.drip.get("requires_weight")),
                "group": "medications",
            })

        for study in self.imaging_studies:
            txt = "{} {}".format(study["modality"], study["study"])
            if study["indication"]:
                txt += " - Indication: {}".format(study["indication"])
            orders.append({"text": txt, "requires_weight": False, "group": "imaging"})

        for name, var in self.other_vars:
            if var.get():
                text = name
                if name == "EKG":
                    indication = self.ekg_indication_var.get().strip()
                    if indication:
                        text += " - Indication: {}".format(indication)
                orders.append({"text": text, "requires_weight": False, "group": "other"})

        for text in self.custom_orders:
            orders.append({"text": text, "requires_weight": False, "group": "custom"})

        if self.active_aop:
            names = [self.active_aop["name"]] + [m["name"] for m in self.active_aop_modifiers]
            banner = "AOP: {} - Indication: {}".format(
                " + ".join(names), self.active_aop.get("indication", "")
            )
            orders.insert(0, {"text": banner, "requires_weight": False, "group": None, "bold": True})

        return orders

    def _gather_and_validate(self):
        """Returns a dict of order info, or None if the user should
        not proceed (validation failed or they cancelled a confirmation)."""
        physician = self.physician_var.get().strip()
        nurse_name = self.nurse_name_var.get().strip()

        if self.active_aop:
            if not nurse_name:
                if not messagebox.askyesno(
                    "Missing nurse name",
                    "Ordering Nurse Name is blank for this AOP order set. Continue anyway?",
                ):
                    return None
        elif physician and not _has_credentials(physician):
            messagebox.showerror(
                "Missing credentials",
                "Please add credentials after the physician's name (e.g. \"Jane Smith, MD\").\n"
                "Accepted: {}.".format(", ".join(CREDENTIAL_SUFFIXES)),
            )
            return None

        orders = self._collect_orders()
        if not orders:
            messagebox.showwarning("No orders selected", "Check off at least one order first.")
            return None

        max_lines = L.NUM_ROWS * 20  # sanity ceiling, not a real limit (pagination handles overflow)
        if len(orders) > max_lines:
            messagebox.showerror("Too many orders", "That's a lot of orders. Trim the list and try again.")
            return None

        return {
            "physician": physician,
            "nurse_name": nurse_name if self.active_aop else None,
            "orders": orders,
        }

    def _build_temp_pdf(self):
        """Generates a PDF to a private temp file and returns its path, or
        None if validation failed or generation errored (temp file, if any,
        is discarded immediately in that case)."""
        info = self._gather_and_validate()
        if info is None:
            return None

        path = printing.new_temp_pdf_path()
        try:
            pdf_gen.generate_pdf(
                path,
                physician_name=info["physician"],
                orders=info["orders"],
                order_date_str=self.order_date_var.get().strip(),
                order_time_str=self.order_time_var.get().strip(),
                nurse_name=info["nurse_name"],
            )
        except Exception as exc:  # noqa: BLE001
            printing.discard(path)
            messagebox.showerror("Error generating PDF", str(exc))
            return None
        return path

    def _print_order_sheet(self):
        path = self._build_temp_pdf()
        if not path:
            return

        status = printing.print_order_sheet(path)

        if status == "printed":
            messagebox.showinfo("Sent to printer", "The order sheet was sent to the printer. Nothing was saved.")
        elif status == "cancelled":
            pass  # user cancelled the print dialog -- nothing printed, nothing to say
        else:  # "opened": fallback viewer (non-Windows, or native print path unavailable)
            shortcut = "Cmd+P" if platform.system() == "Darwin" else "Ctrl+P"
            messagebox.showinfo(
                "Ready to print",
                "The order sheet opened in your PDF viewer.\n\n"
                "Press {} there to print it. Nothing is saved -- the temporary "
                "file is deleted automatically in a few minutes.".format(shortcut),
            )

    def _preview_order_sheet(self):
        path = self._build_temp_pdf()
        if not path:
            return
        printing.open_in_viewer(path)


def main():
    app = EDOrderApp()
    app.mainloop()


if __name__ == "__main__":
    main()