"""
ED Physician Order Sheet Generator

A small desktop app for checking off common Emergency Department orders
and generating a PDF that prints directly into the boxes of the
pre-printed "Physician Orders" paper form (see assets/template_preview.png
for what that form looks like).

Run with:   python3 app.py
Package to a Windows .exe with PyInstaller -- see README.md.
"""

import os
import platform
import subprocess
import sys
import tkinter as tk
from datetime import datetime
from tkinter import ttk, filedialog, messagebox

import data
import layout as L
import pdf_gen


def open_file(path):
    try:
        if platform.system() == "Darwin":
            subprocess.run(["open", path], check=False)
        elif platform.system() == "Windows":
            os.startfile(path)  # noqa: F821 (Windows only)
        else:
            subprocess.run(["xdg-open", path], check=False)
    except Exception:
        pass


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


class CalibrationDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Print Calibration")
        self.resizable(False, False)
        self.cal = L.load_calibration()

        pad = {"padx": 8, "pady": 6}

        info = (
            "If printed text doesn't line up with the boxes on the paper form,\n"
            "nudge the offsets below (in points, 72pt = 1 inch), then print the\n"
            "test page and compare it against a blank form."
        )
        ttk.Label(self, text=info, justify="left").grid(row=0, column=0, columnspan=2, **pad)

        ttk.Label(self, text="Horizontal offset (pt, + = right):").grid(row=1, column=0, sticky="e", **pad)
        self.x_var = tk.DoubleVar(value=self.cal["offset_x"])
        ttk.Entry(self, textvariable=self.x_var, width=10).grid(row=1, column=1, sticky="w", **pad)

        ttk.Label(self, text="Vertical offset (pt, + = up):").grid(row=2, column=0, sticky="e", **pad)
        self.y_var = tk.DoubleVar(value=self.cal["offset_y"])
        ttk.Entry(self, textvariable=self.y_var, width=10).grid(row=2, column=1, sticky="w", **pad)

        ttk.Label(self, text="Row spacing scale (1.0 = default):").grid(row=3, column=0, sticky="e", **pad)
        self.scale_var = tk.DoubleVar(value=self.cal["row_scale"])
        ttk.Entry(self, textvariable=self.scale_var, width=10).grid(row=3, column=1, sticky="w", **pad)

        btns = ttk.Frame(self)
        btns.grid(row=4, column=0, columnspan=2, pady=(10, 10))
        ttk.Button(btns, text="Print Test Page", command=self.print_test).pack(side="left", padx=4)
        ttk.Button(btns, text="Save", command=self.save).pack(side="left", padx=4)
        ttk.Button(btns, text="Reset to Defaults", command=self.reset).pack(side="left", padx=4)
        ttk.Button(btns, text="Close", command=self.destroy).pack(side="left", padx=4)

    def _current_cal(self):
        return {
            "offset_x": self.x_var.get(),
            "offset_y": self.y_var.get(),
            "row_scale": self.scale_var.get(),
        }

    def print_test(self):
        path = filedialog.asksaveasfilename(
            title="Save calibration test page",
            defaultextension=".pdf",
            initialfile="calibration_test.pdf",
            filetypes=[("PDF", "*.pdf")],
        )
        if not path:
            return
        pdf_gen.generate_calibration_test_page(path, self._current_cal())
        open_file(path)

    def save(self):
        L.save_calibration(self._current_cal())
        messagebox.showinfo("Saved", "Calibration saved. It will be used for all future PDFs.")

    def reset(self):
        self.x_var.set(L.DEFAULT_CALIBRATION["offset_x"])
        self.y_var.set(L.DEFAULT_CALIBRATION["offset_y"])
        self.scale_var.set(L.DEFAULT_CALIBRATION["row_scale"])


class EDOrderApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("ED Physician Order Sheet Generator")
        self.geometry("980x760")

        self._build_patient_bar()

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=8, pady=(4, 0))

        self.labs_tab = ScrollableFrame(self.notebook)
        self.meds_tab = ScrollableFrame(self.notebook)
        self.imaging_tab = ttk.Frame(self.notebook)
        self.other_tab = ScrollableFrame(self.notebook)

        self.notebook.add(self.labs_tab, text="Labs")
        self.notebook.add(self.meds_tab, text="Medications")
        self.notebook.add(self.imaging_tab, text="Imaging")
        self.notebook.add(self.other_tab, text="Other Orders")

        self.lab_vars = []
        self.med_rows = []
        self.other_vars = []
        self.imaging_studies = []
        self.custom_orders = []

        self._build_labs_tab()
        self._build_meds_tab()
        self._build_imaging_tab()
        self._build_other_tab()

        self._build_bottom_bar()

    # -- Patient info -----------------------------------------------------
    def _build_patient_bar(self):
        frame = ttk.LabelFrame(self, text="Patient / Order Info")
        frame.pack(fill="x", padx=8, pady=8)

        now = datetime.now()

        def add_field(label, col, width=18, default=""):
            ttk.Label(frame, text=label).grid(row=0, column=col * 2, sticky="e", padx=(10, 2), pady=6)
            var = tk.StringVar(value=default)
            ttk.Entry(frame, textvariable=var, width=width).grid(row=0, column=col * 2 + 1, sticky="w", pady=6)
            return var

        self.patient_name_var = add_field("Patient Name:", 0, width=22)
        self.csn_var = add_field("CSN:", 1, width=14)
        self.physician_var = add_field("Physician Name:", 2, width=20)

        row2 = ttk.Frame(frame)
        row2.grid(row=1, column=0, columnspan=6, sticky="w")
        ttk.Label(row2, text="Order Date (MM/DD/YY):").pack(side="left", padx=(10, 2), pady=(0, 6))
        self.order_date_var = tk.StringVar(value=now.strftime("%m/%d/%y"))
        ttk.Entry(row2, textvariable=self.order_date_var, width=10).pack(side="left")

        ttk.Label(row2, text="Order Time (HH:MM):").pack(side="left", padx=(16, 2))
        self.order_time_var = tk.StringVar(value=now.strftime("%H:%M"))
        ttk.Entry(row2, textvariable=self.order_time_var, width=8).pack(side="left")

        ttk.Button(row2, text="Set to Now", command=self._set_now).pack(side="left", padx=12)

    def _set_now(self):
        now = datetime.now()
        self.order_date_var.set(now.strftime("%m/%d/%y"))
        self.order_time_var.set(now.strftime("%H:%M"))

    # -- Labs tab -----------------------------------------------------------
    def _build_labs_tab(self):
        body = self.labs_tab.body
        cols = 3
        for i, lab in enumerate(data.LABS):
            r, c = divmod(i, cols)
            cell = ttk.Frame(body)
            cell.grid(row=r, column=c, sticky="w", padx=10, pady=4)
            var = tk.BooleanVar(value=False)
            ttk.Checkbutton(cell, text=lab, variable=var, width=28).pack(side="left")
            self.lab_vars.append((lab, var))

    # -- Medications tab ------------------------------------------------------
    def _build_meds_tab(self):
        body = self.meds_tab.body

        header = ttk.Frame(body)
        header.grid(row=0, column=0, sticky="w", padx=10, pady=(6, 2))
        for text, w in [("", 4), ("Medication", 32), ("Dose", 12), ("Route", 10)]:
            ttk.Label(header, text=text, width=w, font=("TkDefaultFont", 9, "bold")).pack(side="left")

        for i, med in enumerate(data.MEDICATIONS):
            row = ttk.Frame(body)
            row.grid(row=i + 1, column=0, sticky="w", padx=10, pady=2)

            var = tk.BooleanVar(value=False)
            ttk.Checkbutton(row, variable=var, width=4).pack(side="left")
            ttk.Label(row, text=med["name"], width=32).pack(side="left")

            dose_var = tk.StringVar(value=med.get("default_dose", ""))
            ttk.Entry(row, textvariable=dose_var, width=12).pack(side="left", padx=2)

            route_var = tk.StringVar(value=med.get("default_route", ""))
            ttk.Combobox(
                row, textvariable=route_var, values=data.COMMON_ROUTES, width=8
            ).pack(side="left", padx=2)

            self.med_rows.append((med["name"], var, dose_var, route_var))

    # -- Imaging tab ------------------------------------------------------------
    def _build_imaging_tab(self):
        top = ttk.LabelFrame(self.imaging_tab, text="Add Imaging Study")
        top.pack(fill="x", padx=10, pady=10)

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
            row=0, column=5, rowspan=2, padx=10
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

    @staticmethod
    def _compose_study_text(modality, study, contrast):
        text = study.strip()
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
        study_text = self._compose_study_text(modality, study, self.contrast_var.get())
        record = {"modality": modality, "study": study_text, "indication": indication}
        self.imaging_studies.append(record)
        self.imaging_tree.insert(
            "", "end",
            values=(modality, study_text, indication),
        )
        self.indication_var.set("")

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
        for i, item in enumerate(data.OTHER_ORDERS):
            r, c = divmod(i, cols)
            cell = ttk.Frame(preset_frame)
            cell.grid(row=r, column=c, sticky="w", padx=10, pady=4)
            var = tk.BooleanVar(value=False)
            ttk.Checkbutton(cell, text=item, variable=var, width=32).pack(side="left")
            self.other_vars.append((item, var))

        custom_frame = ttk.LabelFrame(body, text="Custom Order (free text)")
        custom_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=10)

        self.custom_entry_var = tk.StringVar()
        ttk.Entry(custom_frame, textvariable=self.custom_entry_var, width=60).pack(
            side="left", padx=6, pady=6
        )
        ttk.Button(custom_frame, text="+ Add", command=self._add_custom_order).pack(side="left", padx=6)

        self.custom_listbox = tk.Listbox(body, height=6, width=90)
        self.custom_listbox.grid(row=2, column=0, sticky="w", padx=10, pady=(0, 6))
        ttk.Button(body, text="Remove Selected Custom Order", command=self._remove_custom_order).grid(
            row=3, column=0, sticky="w", padx=10, pady=(0, 10)
        )

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

    # -- Bottom bar / generate ------------------------------------------------
    def _build_bottom_bar(self):
        bar = ttk.Frame(self)
        bar.pack(fill="x", padx=8, pady=10)

        self.preview_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            bar,
            text="Preview mode (overlay on scanned form image — for on-screen checking only; "
                 "uncheck before printing on the real paper form)",
            variable=self.preview_var,
        ).pack(side="left", padx=(0, 20))

        ttk.Button(bar, text="Print Calibration...", command=self._open_calibration).pack(side="right", padx=4)
        ttk.Button(bar, text="Generate PDF", command=self._generate).pack(side="right", padx=4)

    def _open_calibration(self):
        CalibrationDialog(self)

    def _collect_order_texts(self):
        texts = []

        for lab_name, var in self.lab_vars:
            if var.get():
                texts.append(lab_name)

        for name, var, dose_var, route_var in self.med_rows:
            if var.get():
                parts = [name]
                dose = dose_var.get().strip()
                route = route_var.get().strip()
                if dose:
                    parts.append(dose)
                if route:
                    parts.append(route)
                texts.append(" ".join(parts))

        for study in self.imaging_studies:
            txt = "{} {}".format(study["modality"], study["study"])
            if study["indication"]:
                txt += " - Indication: {}".format(study["indication"])
            texts.append(txt)

        for name, var in self.other_vars:
            if var.get():
                texts.append(name)

        texts.extend(self.custom_orders)

        return texts

    def _generate(self):
        patient_name = self.patient_name_var.get().strip()
        csn = self.csn_var.get().strip()
        physician = self.physician_var.get().strip()

        if not patient_name or not csn:
            if not messagebox.askyesno(
                "Missing patient info",
                "Patient Name and/or CSN is blank. Generate the PDF anyway?",
            ):
                return

        order_texts = self._collect_order_texts()
        if not order_texts:
            messagebox.showwarning("No orders selected", "Check off at least one order first.")
            return

        max_lines = L.NUM_ROWS * 20  # sanity ceiling, not a real limit (pagination handles overflow)
        if len(order_texts) > max_lines:
            messagebox.showerror("Too many orders", "That's a lot of orders. Trim the list and try again.")
            return

        default_name = "orders_{}_{}.pdf".format(
            (patient_name or "patient").replace(" ", "_"), csn or "noCSN"
        )
        path = filedialog.asksaveasfilename(
            title="Save order sheet PDF",
            defaultextension=".pdf",
            initialfile=default_name,
            filetypes=[("PDF", "*.pdf")],
        )
        if not path:
            return

        try:
            pdf_gen.generate_pdf(
                path,
                patient_name=patient_name,
                csn=csn,
                physician_name=physician,
                order_texts=order_texts,
                order_date_str=self.order_date_var.get().strip(),
                order_time_str=self.order_time_var.get().strip(),
                include_background=self.preview_var.get(),
            )
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Error generating PDF", str(exc))
            return

        n_pages = -(-len(order_texts) // L.NUM_ROWS) or 1
        if messagebox.askyesno(
            "PDF generated",
            "Saved to:\n{}\n\n({} page{}). Open it now?".format(
                path, n_pages, "s" if n_pages != 1 else ""
            ),
        ):
            open_file(path)


def main():
    app = EDOrderApp()
    app.mainloop()


if __name__ == "__main__":
    main()