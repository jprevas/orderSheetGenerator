"""
ED Order Data Editor

A separate, standalone tool for editing data.json -- the sidecar file the
main ED Order Sheet app reads its labs/medications/drips/imaging/order-sets
from. This is deliberately its own program: it is NOT imported by app.py
and pulls in no PDF/printing dependencies, so it must be packaged as its
own .exe, separate from "ED Order Sheet.exe" -- see README.md.

Run with:   python3 data_editor.py

On startup it looks for data.json next to this script (or next to this
tool's own .exe, once compiled) -- the same convention the main app uses --
and loads it if present, or starts from the main app's built-in defaults
otherwise. Use File > Open... to edit a data.json somewhere else (e.g. the
one actually sitting next to a deployed "ED Order Sheet.exe"), and
File > Save / Save As... to write changes back out.
"""

import copy
import json
import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog

import data  # only for the DEFAULT_* constants / schema -- no other coupling

SCHEMA_KEYS = [
    "labs", "medications", "common_routes", "common_frequencies", "prn_reasons",
    "titrate_frequencies", "drips", "imaging_modalities", "contrast_modalities",
    "sided_studies", "other_orders", "order_sets",
]


def default_data():
    return {
        "labs": copy.deepcopy(data.DEFAULT_LABS),
        "medications": copy.deepcopy(data.DEFAULT_MEDICATIONS),
        "common_routes": copy.deepcopy(data.DEFAULT_COMMON_ROUTES),
        "common_frequencies": copy.deepcopy(data.DEFAULT_COMMON_FREQUENCIES),
        "prn_reasons": copy.deepcopy(data.DEFAULT_PRN_REASONS),
        "titrate_frequencies": copy.deepcopy(data.DEFAULT_TITRATE_FREQUENCIES),
        "drips": copy.deepcopy(data.DEFAULT_DRIPS),
        "imaging_modalities": copy.deepcopy(data.DEFAULT_IMAGING_MODALITIES),
        "contrast_modalities": copy.deepcopy(data.DEFAULT_CONTRAST_MODALITIES),
        "sided_studies": copy.deepcopy(data.DEFAULT_SIDED_STUDIES),
        "other_orders": copy.deepcopy(data.DEFAULT_OTHER_ORDERS),
        "order_sets": copy.deepcopy(data.DEFAULT_ORDER_SETS),
    }


def default_data_path():
    return data.DATA_FILE_PATH  # "next to this script/exe" -- same convention as the main app


class ScrollableFrame(ttk.Frame):
    """A vertically scrollable frame. Put widgets in `self.body`."""

    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        self.body = ttk.Frame(canvas)

        self.body.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        window_id = canvas.create_window((0, 0), window=self.body, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(window_id, width=e.width))
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def _on_mousewheel(event):
            delta = event.delta
            if sys.platform == "darwin":
                canvas.yview_scroll(int(-1 * delta), "units")
            else:
                canvas.yview_scroll(int(-1 * delta / 120), "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel, add="+")


class FormDialog(tk.Toplevel):
    """A small modal form. `fields` is a list of dicts:
        {"key", "label", "kind": "entry"|"combobox"|"checkbutton",
         "values": [...] (combobox only), "state": "readonly" (optional),
         "default": initial value}
    self.result is a {key: value} dict on OK, or None on Cancel."""

    def __init__(self, parent, title, fields):
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.result = None
        self.vars = {}

        for i, f in enumerate(fields):
            ttk.Label(self, text=f["label"] + ":").grid(row=i, column=0, sticky="e", padx=8, pady=5)
            kind = f.get("kind", "entry")
            default = f.get("default", "")
            if kind == "checkbutton":
                var = tk.BooleanVar(value=bool(default))
                ttk.Checkbutton(self, variable=var).grid(row=i, column=1, sticky="w", padx=8, pady=5)
            elif kind == "combobox":
                var = tk.StringVar(value=default)
                ttk.Combobox(
                    self, textvariable=var, values=f.get("values", []), width=30,
                    state=f.get("state", "normal"),
                ).grid(row=i, column=1, sticky="w", padx=8, pady=5)
            else:
                var = tk.StringVar(value=default)
                ttk.Entry(self, textvariable=var, width=33).grid(row=i, column=1, sticky="w", padx=8, pady=5)
            self.vars[f["key"]] = var

        btns = ttk.Frame(self)
        btns.grid(row=len(fields), column=0, columnspan=2, pady=10)
        ttk.Button(btns, text="OK", command=self._on_ok).pack(side="left", padx=4)
        ttk.Button(btns, text="Cancel", command=self.destroy).pack(side="left", padx=4)

        self.bind("<Return>", lambda e: self._on_ok())
        self.bind("<Escape>", lambda e: self.destroy())
        self.transient(parent)
        self.grab_set()

    def _on_ok(self):
        self.result = {k: v.get() for k, v in self.vars.items()}
        self.destroy()

    @classmethod
    def ask(cls, parent, title, fields):
        dlg = cls(parent, title, fields)
        parent.wait_window(dlg)
        return dlg.result


class StringListEditor(ttk.Frame):
    """Add/Remove/Rename/Reorder editor for a plain list of strings, backed
    directly by the list object passed in (mutated in place)."""

    def __init__(self, parent, items, label, on_change=None, describe_usage=None):
        super().__init__(parent)
        self.items = items
        self.on_change = on_change
        self.describe_usage = describe_usage  # optional callable(item) -> str, shown before delete

        ttk.Label(self, text=label, font=("TkDefaultFont", 10, "bold")).pack(anchor="w", pady=(0, 4))

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True)

        self.listbox = tk.Listbox(body, height=14, width=34, exportselection=False)
        self.listbox.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(body, orient="vertical", command=self.listbox.yview)
        scroll.pack(side="left", fill="y")
        self.listbox.configure(yscrollcommand=scroll.set)

        btns = ttk.Frame(body)
        btns.pack(side="left", fill="y", padx=(8, 0))
        ttk.Button(btns, text="+ Add", command=self._add).pack(fill="x", pady=2)
        ttk.Button(btns, text="Rename", command=self._rename).pack(fill="x", pady=2)
        ttk.Button(btns, text="Delete", command=self._delete).pack(fill="x", pady=2)
        ttk.Button(btns, text="Move Up", command=lambda: self._move(-1)).pack(fill="x", pady=(12, 2))
        ttk.Button(btns, text="Move Down", command=lambda: self._move(1)).pack(fill="x", pady=2)

        self._refresh()

    def _refresh(self):
        self.listbox.delete(0, "end")
        for item in self.items:
            self.listbox.insert("end", item)

    def _changed(self):
        if self.on_change:
            self.on_change()

    def _add(self):
        name = simpledialog.askstring("Add", "New entry:", parent=self)
        if not name:
            return
        name = name.strip()
        if not name:
            return
        if name in self.items:
            messagebox.showwarning("Duplicate", '"{}" is already in the list.'.format(name))
            return
        self.items.append(name)
        self._refresh()
        self._changed()

    def _selected_index(self):
        sel = self.listbox.curselection()
        return sel[0] if sel else None

    def _rename(self):
        i = self._selected_index()
        if i is None:
            return
        new_name = simpledialog.askstring("Rename", "New name:", initialvalue=self.items[i], parent=self)
        if not new_name:
            return
        new_name = new_name.strip()
        if not new_name:
            return
        if new_name != self.items[i] and new_name in self.items:
            messagebox.showwarning("Duplicate", '"{}" is already in the list.'.format(new_name))
            return
        self.items[i] = new_name
        self._refresh()
        self.listbox.selection_set(i)
        self._changed()

    def _delete(self):
        i = self._selected_index()
        if i is None:
            return
        msg = 'Delete "{}"?'.format(self.items[i])
        if self.describe_usage:
            msg += "\n\n" + self.describe_usage(self.items[i])
        if not messagebox.askyesno("Delete", msg):
            return
        del self.items[i]
        self._refresh()
        self._changed()

    def _move(self, delta):
        i = self._selected_index()
        if i is None:
            return
        j = i + delta
        if not (0 <= j < len(self.items)):
            return
        self.items[i], self.items[j] = self.items[j], self.items[i]
        self._refresh()
        self.listbox.selection_set(j)
        self._changed()


MED_COLUMNS = ("name", "default_dose", "default_route", "default_frequency", "allow_prn", "default_prn_reason", "requires_weight")
MED_HEADERS = ("Name", "Dose", "Route", "Frequency", "PRN?", "PRN Reason", "Wt-Based?")

DRIP_COLUMNS = ("name", "is_protocol", "default_initial_dose", "default_titrate_by", "default_titrate_frequency", "default_max_dose", "default_goal", "default_protocol_text", "requires_weight")
DRIP_HEADERS = ("Name", "Protocol?", "Initial Dose", "Titrate By", "Frequency", "Max Dose", "Goal", "Protocol Text", "Wt-Based?")


class DataEditorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("ED Order Data Editor")
        self.geometry("1300x850")

        self.data = None
        self.file_path = None
        self.dirty = False

        self._build_menu()

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=8, pady=(8, 0))

        self.status_var = tk.StringVar(value="")
        ttk.Label(self, textvariable=self.status_var, foreground="#555555").pack(
            anchor="w", padx=10, pady=(4, 8)
        )

        self._load_initial()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # -- Menu / file handling -------------------------------------------------
    def _build_menu(self):
        menubar = tk.Menu(self)
        file_menu = tk.Menu(menubar, tearoff=False)
        file_menu.add_command(label="Open...", command=self._open, accelerator="Cmd+O")
        file_menu.add_command(label="Save", command=self._save, accelerator="Cmd+S")
        file_menu.add_command(label="Save As...", command=self._save_as)
        file_menu.add_separator()
        file_menu.add_command(label="Reset Everything to Built-in Defaults", command=self._reset_defaults)
        file_menu.add_command(label="Check for Issues...", command=self._check_issues)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._on_close)
        menubar.add_cascade(label="File", menu=file_menu)
        self.config(menu=menubar)
        self.bind_all("<Command-o>", lambda e: self._open())
        self.bind_all("<Command-s>", lambda e: self._save())

    def _load_initial(self):
        path = default_data_path()
        if os.path.exists(path):
            try:
                self._load_from_path(path)
                return
            except (OSError, json.JSONDecodeError, KeyError) as exc:
                messagebox.showwarning(
                    "Couldn't load data.json",
                    "{}\n\nStarting from the built-in defaults instead.".format(exc),
                )
        self.data = default_data()
        self.file_path = path
        self._mark_clean()
        self._rebuild_tabs()

    def _load_from_path(self, path):
        with open(path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        merged = default_data()
        for k in SCHEMA_KEYS:
            if k in loaded:
                merged[k] = loaded[k]
        self.data = merged
        self.file_path = path
        self._mark_clean()
        self._rebuild_tabs()

    def _open(self):
        if not self._confirm_discard_changes():
            return
        start_dir = os.path.dirname(self.file_path) if self.file_path else os.getcwd()
        path = filedialog.askopenfilename(
            title="Open data.json", initialdir=start_dir, filetypes=[("JSON", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            self._load_from_path(path)
        except (OSError, json.JSONDecodeError) as exc:
            messagebox.showerror("Error", "Couldn't load {}:\n{}".format(path, exc))

    def _save(self):
        if not self.file_path:
            self._save_as()
            return
        self._write_to(self.file_path)

    def _save_as(self):
        start_dir = os.path.dirname(self.file_path) if self.file_path else os.getcwd()
        path = filedialog.asksaveasfilename(
            title="Save data.json", initialdir=start_dir, initialfile="data.json",
            defaultextension=".json", filetypes=[("JSON", "*.json")],
        )
        if not path:
            return
        self._write_to(path)

    def _write_to(self, path):
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2)
        except OSError as exc:
            messagebox.showerror("Error saving", str(exc))
            return
        self.file_path = path
        self._mark_clean()
        messagebox.showinfo("Saved", "Saved to:\n{}".format(path))

    def _reset_defaults(self):
        if not messagebox.askyesno(
            "Reset to defaults",
            "Discard everything currently loaded and reset all lists to the app's built-in defaults?\n\n"
            "This doesn't touch any file until you Save.",
        ):
            return
        self.data = default_data()
        self._mark_dirty()
        self._rebuild_tabs()

    def _check_issues(self):
        problems = []
        lab_names = set(self.data["labs"])
        med_names = set(m["name"] for m in self.data["medications"])
        drip_names = set(d["name"] for d in self.data["drips"])
        other_names = set(self.data["other_orders"])

        seen = {}
        for key, names in [
            ("labs", self.data["labs"]), ("other_orders", self.data["other_orders"]),
            ("medications", [m["name"] for m in self.data["medications"]]),
            ("drips", [d["name"] for d in self.data["drips"]]),
            ("order_sets", [s["name"] for s in self.data["order_sets"]]),
        ]:
            dupes = {n for n in names if names.count(n) > 1}
            if dupes:
                problems.append("Duplicate name(s) in {}: {}".format(key, ", ".join(sorted(dupes))))

        for s in self.data["order_sets"]:
            for n in s.get("labs", []):
                if n not in lab_names:
                    problems.append('Order set "{}" references missing lab "{}"'.format(s["name"], n))
            for m in s.get("medications", []):
                if m["name"] not in med_names:
                    problems.append('Order set "{}" references missing medication "{}"'.format(s["name"], m["name"]))
            for d in s.get("drips", []):
                if d["name"] not in drip_names:
                    problems.append('Order set "{}" references missing drip "{}"'.format(s["name"], d["name"]))
            for n in s.get("other", []):
                if n not in other_names:
                    problems.append('Order set "{}" references missing other-order "{}"'.format(s["name"], n))
            if s.get("is_aop") and not s.get("indication", "").strip():
                problems.append('AOP order set "{}" has no indication text'.format(s["name"]))

        if not problems:
            messagebox.showinfo("Check for Issues", "No issues found.")
        else:
            messagebox.showwarning("Check for Issues", "\n".join(problems))

    def _mark_dirty(self):
        self.dirty = True
        self._update_status()

    def _mark_clean(self):
        self.dirty = False
        self._update_status()

    def _update_status(self):
        self.status_var.set(
            "{}{}".format(self.file_path or "(no file loaded)", "  --  unsaved changes" if self.dirty else "")
        )

    def _confirm_discard_changes(self):
        if not self.dirty:
            return True
        resp = messagebox.askyesnocancel("Unsaved changes", "Save changes first?")
        if resp is None:
            return False
        if resp:
            self._save()
            return not self.dirty
        return True

    def _on_close(self):
        if self._confirm_discard_changes():
            self.destroy()

    def _reference_warning(self, category, name):
        users = []
        for s in self.data["order_sets"]:
            if category == "labs" and name in s.get("labs", []):
                users.append(s["name"])
            elif category == "medications" and any(m["name"] == name for m in s.get("medications", [])):
                users.append(s["name"])
            elif category == "drips" and any(d["name"] == name for d in s.get("drips", [])):
                users.append(s["name"])
            elif category == "other" and name in s.get("other", []):
                users.append(s["name"])
        if not users:
            return "Not currently used by any order set."
        return "Used by {} order set(s): {}\n(they'll just silently skip it once it's gone)".format(
            len(users), ", ".join(users)
        )

    # -- Tabs -------------------------------------------------------------------
    def _rebuild_tabs(self):
        for tab in self.notebook.tabs():
            self.notebook.forget(tab)
        self._build_labs_tab()
        self._build_other_tab()
        self._build_reference_lists_tab()
        self._build_medications_tab()
        self._build_drips_tab()
        self._build_imaging_tab()
        self._build_order_sets_tab()

    def _build_labs_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Labs")
        editor = StringListEditor(
            tab, self.data["labs"], "Labs", on_change=self._mark_dirty,
            describe_usage=lambda n: self._reference_warning("labs", n),
        )
        editor.pack(fill="both", expand=True, padx=10, pady=10)

    def _build_other_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Other Orders")
        editor = StringListEditor(
            tab, self.data["other_orders"], "Other Orders", on_change=self._mark_dirty,
            describe_usage=lambda n: self._reference_warning("other", n),
        )
        editor.pack(fill="both", expand=True, padx=10, pady=10)

    def _build_reference_lists_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Reference Lists")
        ttk.Label(
            tab,
            text="Options offered in various dropdowns throughout the main app.",
        ).grid(row=0, column=0, columnspan=4, sticky="w", padx=10, pady=(10, 4))
        specs = [
            ("common_routes", "Routes (Medications tab)"),
            ("common_frequencies", "Frequencies (Medications tab)"),
            ("prn_reasons", "PRN Reasons (Medications tab)"),
            ("titrate_frequencies", "Titrate Frequencies (Drips tab)"),
            ("sided_studies", "Sided Studies (Imaging tab -- offers Left/Right/Bilateral;\nmatched by name across all modalities)"),
        ]
        for col, (key, label) in enumerate(specs):
            editor = StringListEditor(tab, self.data[key], label, on_change=self._mark_dirty)
            editor.grid(row=1, column=col, sticky="nsew", padx=10, pady=(0, 10))
            tab.columnconfigure(col, weight=1)

    # -- Medications tab ----------------------------------------------------
    def _build_medications_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Medications")

        ttk.Label(tab, text="Medications", font=("TkDefaultFont", 10, "bold")).pack(
            anchor="w", padx=10, pady=(10, 4)
        )

        body = ttk.Frame(tab)
        body.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        tree = ttk.Treeview(body, columns=MED_COLUMNS, show="headings", height=18)
        for col, header in zip(MED_COLUMNS, MED_HEADERS):
            tree.heading(col, text=header)
            tree.column(col, width=210 if col == "name" else 100)
        tree.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(body, orient="vertical", command=tree.yview)
        scroll.pack(side="left", fill="y")
        tree.configure(yscrollcommand=scroll.set)
        tree.bind("<Double-1>", lambda e: self._edit_medication())
        self.med_tree = tree

        btns = ttk.Frame(body)
        btns.pack(side="left", fill="y", padx=(8, 0))
        ttk.Button(btns, text="+ Add", command=self._add_medication).pack(fill="x", pady=2)
        ttk.Button(btns, text="Edit", command=self._edit_medication).pack(fill="x", pady=2)
        ttk.Button(btns, text="Delete", command=self._delete_medication).pack(fill="x", pady=2)
        ttk.Button(btns, text="Move Up", command=lambda: self._move_medication(-1)).pack(fill="x", pady=(12, 2))
        ttk.Button(btns, text="Move Down", command=lambda: self._move_medication(1)).pack(fill="x", pady=2)

        self._refresh_medications_tree()

    def _refresh_medications_tree(self):
        self.med_tree.delete(*self.med_tree.get_children())
        for m in self.data["medications"]:
            self.med_tree.insert("", "end", values=(
                m.get("name", ""), m.get("default_dose", ""), m.get("default_route", ""),
                m.get("default_frequency", ""), "Yes" if m.get("allow_prn") else "",
                m.get("default_prn_reason", ""), "Yes" if m.get("requires_weight") else "",
            ))

    def _medication_fields(self, med=None):
        med = med or {}
        return [
            {"key": "name", "label": "Name", "default": med.get("name", "")},
            {"key": "default_dose", "label": "Default Dose", "default": med.get("default_dose", "")},
            {"key": "default_route", "label": "Default Route", "kind": "combobox",
             "values": self.data["common_routes"], "default": med.get("default_route", "")},
            {"key": "default_frequency", "label": "Default Frequency", "kind": "combobox",
             "values": self.data["common_frequencies"], "default": med.get("default_frequency", "")},
            {"key": "allow_prn", "label": "Allow PRN", "kind": "checkbutton", "default": med.get("allow_prn", False)},
            {"key": "default_prn_reason", "label": "Default PRN Reason", "kind": "combobox",
             "values": self.data["prn_reasons"], "default": med.get("default_prn_reason", "")},
            {"key": "requires_weight", "label": "Weight-Based", "kind": "checkbutton",
             "default": med.get("requires_weight", False)},
        ]

    @staticmethod
    def _medication_from_form(result):
        med = {"name": result["name"].strip()}
        if result["default_dose"].strip():
            med["default_dose"] = result["default_dose"].strip()
        if result["default_route"].strip():
            med["default_route"] = result["default_route"].strip()
        if result["default_frequency"].strip():
            med["default_frequency"] = result["default_frequency"].strip()
        if result["allow_prn"]:
            med["allow_prn"] = True
        if result["default_prn_reason"].strip():
            med["default_prn_reason"] = result["default_prn_reason"].strip()
        if result["requires_weight"]:
            med["requires_weight"] = True
        return med

    def _selected_med_index(self):
        sel = self.med_tree.selection()
        return self.med_tree.index(sel[0]) if sel else None

    def _add_medication(self):
        result = FormDialog.ask(self, "Add Medication", self._medication_fields())
        if not result:
            return
        name = result["name"].strip()
        if not name:
            return
        if any(m["name"] == name for m in self.data["medications"]):
            messagebox.showwarning("Duplicate", '"{}" already exists.'.format(name))
            return
        self.data["medications"].append(self._medication_from_form(result))
        self._refresh_medications_tree()
        self._mark_dirty()

    def _edit_medication(self):
        i = self._selected_med_index()
        if i is None:
            return
        result = FormDialog.ask(self, "Edit Medication", self._medication_fields(self.data["medications"][i]))
        if not result:
            return
        name = result["name"].strip()
        if not name:
            return
        if any(j != i and m["name"] == name for j, m in enumerate(self.data["medications"])):
            messagebox.showwarning("Duplicate", '"{}" already exists.'.format(name))
            return
        self.data["medications"][i] = self._medication_from_form(result)
        self._refresh_medications_tree()
        self.med_tree.selection_set(self.med_tree.get_children()[i])
        self._mark_dirty()

    def _delete_medication(self):
        i = self._selected_med_index()
        if i is None:
            return
        name = self.data["medications"][i]["name"]
        msg = 'Delete "{}"?\n\n{}'.format(name, self._reference_warning("medications", name))
        if not messagebox.askyesno("Delete", msg):
            return
        del self.data["medications"][i]
        self._refresh_medications_tree()
        self._mark_dirty()

    def _move_medication(self, delta):
        i = self._selected_med_index()
        if i is None:
            return
        j = i + delta
        meds = self.data["medications"]
        if not (0 <= j < len(meds)):
            return
        meds[i], meds[j] = meds[j], meds[i]
        self._refresh_medications_tree()
        self.med_tree.selection_set(self.med_tree.get_children()[j])
        self._mark_dirty()

    # -- Drips tab ------------------------------------------------------------
    def _build_drips_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Drips")

        ttk.Label(tab, text="Drips", font=("TkDefaultFont", 10, "bold")).pack(anchor="w", padx=10, pady=(10, 4))

        body = ttk.Frame(tab)
        body.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        tree = ttk.Treeview(body, columns=DRIP_COLUMNS, show="headings", height=18)
        col_widths = {"name": 180, "is_protocol": 70, "default_protocol_text": 260}
        for col, header in zip(DRIP_COLUMNS, DRIP_HEADERS):
            tree.heading(col, text=header)
            tree.column(col, width=col_widths.get(col, 90))
        tree.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(body, orient="vertical", command=tree.yview)
        scroll.pack(side="left", fill="y")
        tree.configure(yscrollcommand=scroll.set)
        tree.bind("<Double-1>", lambda e: self._edit_drip())
        self.drip_tree = tree

        btns = ttk.Frame(body)
        btns.pack(side="left", fill="y", padx=(8, 0))
        ttk.Button(btns, text="+ Add", command=self._add_drip).pack(fill="x", pady=2)
        ttk.Button(btns, text="Edit", command=self._edit_drip).pack(fill="x", pady=2)
        ttk.Button(btns, text="Delete", command=self._delete_drip).pack(fill="x", pady=2)
        ttk.Button(btns, text="Move Up", command=lambda: self._move_drip(-1)).pack(fill="x", pady=(12, 2))
        ttk.Button(btns, text="Move Down", command=lambda: self._move_drip(1)).pack(fill="x", pady=2)

        self._refresh_drips_tree()

    def _refresh_drips_tree(self):
        self.drip_tree.delete(*self.drip_tree.get_children())
        for d in self.data["drips"]:
            self.drip_tree.insert("", "end", values=(
                d.get("name", ""), "Yes" if d.get("is_protocol") else "",
                d.get("default_initial_dose", ""), d.get("default_titrate_by", ""),
                d.get("default_titrate_frequency", ""), d.get("default_max_dose", ""),
                d.get("default_goal", ""), d.get("default_protocol_text", ""),
                "Yes" if d.get("requires_weight") else "",
            ))

    def _drip_fields(self, drip=None):
        drip = drip or {}
        return [
            {"key": "name", "label": "Name", "default": drip.get("name", "")},
            {"key": "is_protocol", "label": "Fixed protocol (not titrated)", "kind": "checkbutton",
             "default": drip.get("is_protocol", False)},
            {"key": "default_protocol_text", "label": "Protocol text (e.g. Amiodarone load/maintenance)",
             "default": drip.get("default_protocol_text", "")},
            {"key": "default_initial_dose", "label": "Initial Dose (if not a fixed protocol)",
             "default": drip.get("default_initial_dose", "")},
            {"key": "default_titrate_by", "label": "Titrate By (if not a fixed protocol)",
             "default": drip.get("default_titrate_by", "")},
            {"key": "default_titrate_frequency", "label": "Titrate Frequency (if not a fixed protocol)",
             "kind": "combobox", "values": self.data["titrate_frequencies"],
             "default": drip.get("default_titrate_frequency", "")},
            {"key": "default_max_dose", "label": "Max Dose (if not a fixed protocol)",
             "default": drip.get("default_max_dose", "")},
            {"key": "default_goal", "label": "Goal (if not a fixed protocol)", "default": drip.get("default_goal", "")},
            {"key": "requires_weight", "label": "Weight-Based", "kind": "checkbutton",
             "default": drip.get("requires_weight", False)},
        ]

    @staticmethod
    def _drip_from_form(result):
        drip = {"name": result["name"].strip()}
        if result["is_protocol"]:
            drip["is_protocol"] = True
        if result["default_protocol_text"].strip():
            drip["default_protocol_text"] = result["default_protocol_text"].strip()
        for key in ("default_initial_dose", "default_titrate_by", "default_titrate_frequency", "default_max_dose", "default_goal"):
            if result[key].strip():
                drip[key] = result[key].strip()
        if result["requires_weight"]:
            drip["requires_weight"] = True
        return drip

    def _selected_drip_index(self):
        sel = self.drip_tree.selection()
        return self.drip_tree.index(sel[0]) if sel else None

    def _add_drip(self):
        result = FormDialog.ask(self, "Add Drip", self._drip_fields())
        if not result:
            return
        name = result["name"].strip()
        if not name:
            return
        if any(d["name"] == name for d in self.data["drips"]):
            messagebox.showwarning("Duplicate", '"{}" already exists.'.format(name))
            return
        self.data["drips"].append(self._drip_from_form(result))
        self._refresh_drips_tree()
        self._mark_dirty()

    def _edit_drip(self):
        i = self._selected_drip_index()
        if i is None:
            return
        result = FormDialog.ask(self, "Edit Drip", self._drip_fields(self.data["drips"][i]))
        if not result:
            return
        name = result["name"].strip()
        if not name:
            return
        if any(j != i and d["name"] == name for j, d in enumerate(self.data["drips"])):
            messagebox.showwarning("Duplicate", '"{}" already exists.'.format(name))
            return
        self.data["drips"][i] = self._drip_from_form(result)
        self._refresh_drips_tree()
        self.drip_tree.selection_set(self.drip_tree.get_children()[i])
        self._mark_dirty()

    def _delete_drip(self):
        i = self._selected_drip_index()
        if i is None:
            return
        name = self.data["drips"][i]["name"]
        msg = 'Delete "{}"?\n\n{}'.format(name, self._reference_warning("drips", name))
        if not messagebox.askyesno("Delete", msg):
            return
        del self.data["drips"][i]
        self._refresh_drips_tree()
        self._mark_dirty()

    def _move_drip(self, delta):
        i = self._selected_drip_index()
        if i is None:
            return
        j = i + delta
        drips = self.data["drips"]
        if not (0 <= j < len(drips)):
            return
        drips[i], drips[j] = drips[j], drips[i]
        self._refresh_drips_tree()
        self.drip_tree.selection_set(self.drip_tree.get_children()[j])
        self._mark_dirty()

    # -- Imaging tab ------------------------------------------------------------
    def _build_imaging_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Imaging")

        left = ttk.Frame(tab)
        left.pack(side="left", fill="y", padx=10, pady=10)
        ttk.Label(left, text="Modalities", font=("TkDefaultFont", 10, "bold")).pack(anchor="w", pady=(0, 4))

        mbody = ttk.Frame(left)
        mbody.pack(fill="both", expand=True)
        self.modality_listbox = tk.Listbox(mbody, height=14, width=16, exportselection=False)
        self.modality_listbox.pack(side="left", fill="both", expand=True)
        mscroll = ttk.Scrollbar(mbody, orient="vertical", command=self.modality_listbox.yview)
        mscroll.pack(side="left", fill="y")
        self.modality_listbox.configure(yscrollcommand=mscroll.set)
        self.modality_listbox.bind("<<ListboxSelect>>", lambda e: self._on_modality_select())

        mbtns = ttk.Frame(left)
        mbtns.pack(fill="x", pady=(6, 0))
        ttk.Button(mbtns, text="+ Add", command=self._add_modality).pack(fill="x", pady=2)
        ttk.Button(mbtns, text="Rename", command=self._rename_modality).pack(fill="x", pady=2)
        ttk.Button(mbtns, text="Delete", command=self._delete_modality).pack(fill="x", pady=2)

        self.contrast_var = tk.BooleanVar(value=False)
        self.contrast_check = ttk.Checkbutton(
            left, text='Offer "With Contrast"\ncheckbox for this modality',
            variable=self.contrast_var, command=self._on_contrast_toggle,
        )
        self.contrast_check.pack(anchor="w", pady=(12, 0))

        self.studies_container = ttk.Frame(tab)
        self.studies_container.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        self.studies_editor = None

        self._refresh_modality_list()

    def _refresh_modality_list(self, select=None):
        self.modality_listbox.delete(0, "end")
        names = list(self.data["imaging_modalities"].keys())
        for name in names:
            self.modality_listbox.insert("end", name)
        if select is not None and select in names:
            self.modality_listbox.selection_set(names.index(select))
            self._on_modality_select()
        elif names:
            self.modality_listbox.selection_set(0)
            self._on_modality_select()
        else:
            self._clear_studies_editor()

    def _selected_modality(self):
        sel = self.modality_listbox.curselection()
        if not sel:
            return None
        return list(self.data["imaging_modalities"].keys())[sel[0]]

    def _on_modality_select(self):
        modality = self._selected_modality()
        self._clear_studies_editor()
        if modality is None:
            return
        self.contrast_var.set(modality in self.data["contrast_modalities"])
        self.studies_editor = StringListEditor(
            self.studies_container, self.data["imaging_modalities"][modality],
            "Studies for {}".format(modality), on_change=self._mark_dirty,
        )
        self.studies_editor.pack(fill="both", expand=True)

    def _clear_studies_editor(self):
        if self.studies_editor is not None:
            self.studies_editor.destroy()
            self.studies_editor = None

    def _on_contrast_toggle(self):
        modality = self._selected_modality()
        if modality is None:
            return
        cm = self.data["contrast_modalities"]
        if self.contrast_var.get():
            if modality not in cm:
                cm.append(modality)
        else:
            if modality in cm:
                cm.remove(modality)
        self._mark_dirty()

    def _add_modality(self):
        name = simpledialog.askstring("Add Modality", "Modality name (e.g. XR, CT):", parent=self)
        if not name:
            return
        name = name.strip().upper()
        if not name:
            return
        if name in self.data["imaging_modalities"]:
            messagebox.showwarning("Duplicate", '"{}" already exists.'.format(name))
            return
        self.data["imaging_modalities"][name] = []
        self._refresh_modality_list(select=name)
        self._mark_dirty()

    def _rename_modality(self):
        old = self._selected_modality()
        if old is None:
            return
        new = simpledialog.askstring("Rename Modality", "New name:", initialvalue=old, parent=self)
        if not new:
            return
        new = new.strip().upper()
        if not new or new == old:
            return
        if new in self.data["imaging_modalities"]:
            messagebox.showwarning("Duplicate", '"{}" already exists.'.format(new))
            return
        self.data["imaging_modalities"] = {
            (new if k == old else k): v for k, v in self.data["imaging_modalities"].items()
        }
        self.data["contrast_modalities"] = [
            (new if m == old else m) for m in self.data["contrast_modalities"]
        ]
        for s in self.data["order_sets"]:
            for im in s.get("imaging", []):
                if im.get("modality") == old:
                    im["modality"] = new
        self._refresh_modality_list(select=new)
        self._mark_dirty()

    def _delete_modality(self):
        modality = self._selected_modality()
        if modality is None:
            return
        users = [
            s["name"] for s in self.data["order_sets"]
            if any(im.get("modality") == modality for im in s.get("imaging", []))
        ]
        msg = 'Delete modality "{}" and all its studies?'.format(modality)
        if users:
            msg += "\n\nUsed by {} order set(s): {}\n(they'll just silently skip it once it's gone)".format(
                len(users), ", ".join(users)
            )
        if not messagebox.askyesno("Delete", msg):
            return
        del self.data["imaging_modalities"][modality]
        if modality in self.data["contrast_modalities"]:
            self.data["contrast_modalities"].remove(modality)
        self._refresh_modality_list()
        self._mark_dirty()

    # -- Order Sets tab -----------------------------------------------------
    def _build_order_sets_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Order Sets")
        self._loading = False
        self._current_os_index = None

        left = ttk.Frame(tab)
        left.pack(side="left", fill="y", padx=10, pady=10)
        ttk.Label(left, text="Order Sets", font=("TkDefaultFont", 10, "bold")).pack(anchor="w", pady=(0, 4))

        lbody = ttk.Frame(left)
        lbody.pack(fill="both", expand=True)
        self.os_listbox = tk.Listbox(lbody, height=30, width=34, exportselection=False)
        self.os_listbox.pack(side="left", fill="both", expand=True)
        lscroll = ttk.Scrollbar(lbody, orient="vertical", command=self.os_listbox.yview)
        lscroll.pack(side="left", fill="y")
        self.os_listbox.configure(yscrollcommand=lscroll.set)
        self.os_listbox.bind("<<ListboxSelect>>", lambda e: self._on_order_set_select())

        lbtns = ttk.Frame(left)
        lbtns.pack(fill="x", pady=(6, 0))
        ttk.Button(lbtns, text="+ New", command=self._add_order_set).pack(fill="x", pady=2)
        ttk.Button(lbtns, text="Duplicate", command=self._duplicate_order_set).pack(fill="x", pady=2)
        ttk.Button(lbtns, text="Delete", command=self._delete_order_set).pack(fill="x", pady=2)
        ttk.Button(lbtns, text="Move Up", command=lambda: self._move_order_set(-1)).pack(fill="x", pady=(12, 2))
        ttk.Button(lbtns, text="Move Down", command=lambda: self._move_order_set(1)).pack(fill="x", pady=2)

        right_container = ScrollableFrame(tab)
        right_container.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        self.os_detail = right_container.body
        self._build_order_set_detail_widgets()

        self._refresh_order_sets_list()

    @staticmethod
    def _order_set_label(s):
        tag = ""
        if s.get("is_aop"):
            tag = "[AOP] "
        elif s.get("is_aop_modifier"):
            tag = "[MOD] "
        return tag + s.get("name", "(unnamed)")

    def _refresh_order_sets_list(self, select_index=None):
        self.os_listbox.delete(0, "end")
        for s in self.data["order_sets"]:
            self.os_listbox.insert("end", self._order_set_label(s))
        n = len(self.data["order_sets"])
        if select_index is not None and 0 <= select_index < n:
            self.os_listbox.selection_set(select_index)
            self._on_order_set_select()
        elif n:
            self.os_listbox.selection_set(0)
            self._on_order_set_select()
        else:
            self._current_os_index = None
            self._load_order_set_into_form(None)

    def _build_order_set_detail_widgets(self):
        body = self.os_detail

        top = ttk.Frame(body)
        top.pack(fill="x", pady=(0, 10))
        ttk.Label(top, text="Name:").grid(row=0, column=0, sticky="e", padx=4, pady=4)
        self.os_name_var = tk.StringVar(value="")
        ttk.Entry(top, textvariable=self.os_name_var, width=42).grid(row=0, column=1, sticky="w", padx=4, pady=4)
        self.os_name_var.trace_add("write", lambda *a: self._on_os_name_change())

        ttk.Label(top, text="Type:").grid(row=1, column=0, sticky="e", padx=4, pady=4)
        type_frame = ttk.Frame(top)
        type_frame.grid(row=1, column=1, sticky="w", padx=4, pady=4)
        self.os_type_var = tk.StringVar(value="regular")
        for val, label in ORDER_SET_TYPES:
            ttk.Radiobutton(
                type_frame, text=label, variable=self.os_type_var, value=val, command=self._on_os_type_change,
            ).pack(side="left", padx=(0, 10))

        ttk.Label(top, text="Indication:").grid(row=2, column=0, sticky="e", padx=4, pady=4)
        self.os_indication_var = tk.StringVar(value="")
        self.os_indication_entry = ttk.Entry(top, textvariable=self.os_indication_var, width=55)
        self.os_indication_entry.grid(row=2, column=1, sticky="w", padx=4, pady=4)
        self.os_indication_var.trace_add("write", lambda *a: self._on_os_indication_change())
        ttk.Label(top, text="(AOP sets only -- printed as the top line of the order sheet)", foreground="#777777").grid(
            row=3, column=1, sticky="w", padx=4
        )

        ttk.Label(body, text="Labs", font=("TkDefaultFont", 9, "bold")).pack(anchor="w", pady=(6, 2))
        self.os_labs_frame = ttk.Frame(body)
        self.os_labs_frame.pack(fill="x", pady=(0, 10))
        self.os_lab_vars = {}

        ttk.Label(body, text="Other Orders", font=("TkDefaultFont", 9, "bold")).pack(anchor="w", pady=(6, 2))
        self.os_other_frame = ttk.Frame(body)
        self.os_other_frame.pack(fill="x", pady=(0, 10))
        self.os_other_vars = {}

        ttk.Label(body, text="Medications", font=("TkDefaultFont", 9, "bold")).pack(anchor="w", pady=(6, 2))
        med_body = ttk.Frame(body)
        med_body.pack(fill="x", pady=(0, 10))
        med_cols = ("name", "dose", "route", "frequency", "prn", "prn_reason")
        self.os_med_tree = ttk.Treeview(med_body, columns=med_cols, show="headings", height=6)
        for col, header in zip(med_cols, ("Name", "Dose", "Route", "Frequency", "PRN?", "PRN Reason")):
            self.os_med_tree.heading(col, text=header)
            self.os_med_tree.column(col, width=160 if col == "name" else 95)
        self.os_med_tree.pack(side="left", fill="x", expand=True)
        med_btns = ttk.Frame(med_body)
        med_btns.pack(side="left", padx=(8, 0))
        ttk.Button(med_btns, text="+ Add", command=self._add_os_medication).pack(fill="x", pady=2)
        ttk.Button(med_btns, text="Remove", command=self._remove_os_medication).pack(fill="x", pady=2)

        ttk.Label(body, text="Drips", font=("TkDefaultFont", 9, "bold")).pack(anchor="w", pady=(6, 2))
        drip_body = ttk.Frame(body)
        drip_body.pack(fill="x", pady=(0, 10))
        drip_cols = ("name", "protocol", "initial_dose", "titrate_by", "titrate_frequency", "max_dose", "goal")
        self.os_drip_tree = ttk.Treeview(drip_body, columns=drip_cols, show="headings", height=5)
        drip_headers = ("Name", "Protocol", "Initial Dose", "Titrate By", "Frequency", "Max Dose", "Goal")
        drip_widths = {"name": 150, "protocol": 200}
        for col, header in zip(drip_cols, drip_headers):
            self.os_drip_tree.heading(col, text=header)
            self.os_drip_tree.column(col, width=drip_widths.get(col, 90))
        self.os_drip_tree.pack(side="left", fill="x", expand=True)
        drip_btns = ttk.Frame(drip_body)
        drip_btns.pack(side="left", padx=(8, 0))
        ttk.Button(drip_btns, text="+ Add", command=self._add_os_drip).pack(fill="x", pady=2)
        ttk.Button(drip_btns, text="Remove", command=self._remove_os_drip).pack(fill="x", pady=2)

        ttk.Label(body, text="Imaging", font=("TkDefaultFont", 9, "bold")).pack(anchor="w", pady=(6, 2))
        img_body = ttk.Frame(body)
        img_body.pack(fill="x", pady=(0, 10))
        img_cols = ("modality", "study", "indication", "contrast", "side")
        self.os_img_tree = ttk.Treeview(img_body, columns=img_cols, show="headings", height=5)
        for col, header, w in zip(img_cols, ("Modality", "Study", "Indication", "Contrast?", "Side"), (70, 180, 260, 70, 60)):
            self.os_img_tree.heading(col, text=header)
            self.os_img_tree.column(col, width=w)
        self.os_img_tree.pack(side="left", fill="x", expand=True)
        img_btns = ttk.Frame(img_body)
        img_btns.pack(side="left", padx=(8, 0))
        ttk.Button(img_btns, text="+ Add", command=self._add_os_imaging).pack(fill="x", pady=2)
        ttk.Button(img_btns, text="Remove", command=self._remove_os_imaging).pack(fill="x", pady=2)

    def _on_order_set_select(self):
        sel = self.os_listbox.curselection()
        if not sel:
            return
        self._current_os_index = sel[0]
        self._load_order_set_into_form(self.data["order_sets"][self._current_os_index])

    def _update_indication_state(self):
        self.os_indication_entry.configure(state="normal" if self.os_type_var.get() == "aop" else "disabled")

    def _load_order_set_into_form(self, s):
        self._loading = True
        if s is None:
            self.os_name_var.set("")
            self.os_type_var.set("regular")
            self.os_indication_var.set("")
            self._update_indication_state()
            for frame, vars_dict_name in ((self.os_labs_frame, "os_lab_vars"), (self.os_other_frame, "os_other_vars")):
                for w in frame.winfo_children():
                    w.destroy()
                setattr(self, vars_dict_name, {})
            self.os_med_tree.delete(*self.os_med_tree.get_children())
            self.os_drip_tree.delete(*self.os_drip_tree.get_children())
            self.os_img_tree.delete(*self.os_img_tree.get_children())
            self._loading = False
            return

        self.os_name_var.set(s.get("name", ""))
        if s.get("is_aop"):
            self.os_type_var.set("aop")
        elif s.get("is_aop_modifier"):
            self.os_type_var.set("modifier")
        else:
            self.os_type_var.set("regular")
        self.os_indication_var.set(s.get("indication", ""))
        self._update_indication_state()

        cols = 3
        for w in self.os_labs_frame.winfo_children():
            w.destroy()
        self.os_lab_vars = {}
        selected_labs = set(s.get("labs", []))
        for i, lab in enumerate(self.data["labs"]):
            var = tk.BooleanVar(value=lab in selected_labs)
            var.trace_add("write", lambda *a, name=lab: self._on_os_lab_toggle(name))
            r, c = divmod(i, cols)
            ttk.Checkbutton(self.os_labs_frame, text=lab, variable=var).grid(row=r, column=c, sticky="w", padx=4, pady=1)
            self.os_lab_vars[lab] = var

        for w in self.os_other_frame.winfo_children():
            w.destroy()
        self.os_other_vars = {}
        selected_other = set(s.get("other", []))
        for i, name in enumerate(self.data["other_orders"]):
            var = tk.BooleanVar(value=name in selected_other)
            var.trace_add("write", lambda *a, n=name: self._on_os_other_toggle(n))
            r, c = divmod(i, cols)
            ttk.Checkbutton(self.os_other_frame, text=name, variable=var).grid(row=r, column=c, sticky="w", padx=4, pady=1)
            self.os_other_vars[name] = var

        self._refresh_os_med_tree(s)
        self._refresh_os_drip_tree(s)
        self._refresh_os_img_tree(s)
        self._loading = False

    def _relabel_current_order_set(self):
        s = self.data["order_sets"][self._current_os_index]
        idx = self._current_os_index
        self.os_listbox.delete(idx)
        self.os_listbox.insert(idx, self._order_set_label(s))
        self.os_listbox.selection_set(idx)

    def _on_os_name_change(self):
        if self._loading or self._current_os_index is None:
            return
        self.data["order_sets"][self._current_os_index]["name"] = self.os_name_var.get()
        self._relabel_current_order_set()
        self._mark_dirty()

    def _on_os_indication_change(self):
        if self._loading or self._current_os_index is None:
            return
        self.data["order_sets"][self._current_os_index]["indication"] = self.os_indication_var.get()
        self._mark_dirty()

    def _on_os_type_change(self):
        if self._current_os_index is None:
            return
        s = self.data["order_sets"][self._current_os_index]
        val = self.os_type_var.get()
        s.pop("is_aop", None)
        s.pop("is_aop_modifier", None)
        if val == "aop":
            s["is_aop"] = True
            s.setdefault("indication", "")
        elif val == "modifier":
            s["is_aop_modifier"] = True
            s.pop("indication", None)
        else:
            s.pop("indication", None)
        self._update_indication_state()
        self._relabel_current_order_set()
        self._mark_dirty()

    def _on_os_lab_toggle(self, name):
        if self._loading or self._current_os_index is None:
            return
        s = self.data["order_sets"][self._current_os_index]
        labs = s.setdefault("labs", [])
        checked = self.os_lab_vars[name].get()
        if checked and name not in labs:
            labs.append(name)
        elif not checked and name in labs:
            labs.remove(name)
        self._mark_dirty()

    def _on_os_other_toggle(self, name):
        if self._loading or self._current_os_index is None:
            return
        s = self.data["order_sets"][self._current_os_index]
        others = s.setdefault("other", [])
        checked = self.os_other_vars[name].get()
        if checked and name not in others:
            others.append(name)
        elif not checked and name in others:
            others.remove(name)
        self._mark_dirty()

    def _refresh_os_med_tree(self, s):
        self.os_med_tree.delete(*self.os_med_tree.get_children())
        for m in s.get("medications", []):
            self.os_med_tree.insert("", "end", values=(
                m["name"], m.get("dose", ""), m.get("route", ""), m.get("frequency", ""),
                "Yes" if m.get("prn") else "", m.get("prn_reason", ""),
            ))

    def _add_os_medication(self):
        if self._current_os_index is None:
            return
        med_names = [m["name"] for m in self.data["medications"]]
        if not med_names:
            messagebox.showinfo("No medications", "Add medications on the Medications tab first.")
            return
        fields = [
            {"key": "name", "label": "Medication", "kind": "combobox", "values": med_names,
             "state": "readonly", "default": med_names[0]},
            {"key": "dose", "label": "Dose override (optional)", "default": ""},
            {"key": "route", "label": "Route override (optional)", "kind": "combobox",
             "values": self.data["common_routes"], "default": ""},
            {"key": "frequency", "label": "Frequency override (optional)", "kind": "combobox",
             "values": self.data["common_frequencies"], "default": ""},
            {"key": "prn", "label": "PRN", "kind": "checkbutton", "default": False},
            {"key": "prn_reason", "label": "PRN Reason override (optional)", "kind": "combobox",
             "values": self.data["prn_reasons"], "default": ""},
        ]
        result = FormDialog.ask(self, "Add Medication to Order Set", fields)
        if not result:
            return
        spec = {"name": result["name"]}
        if result["dose"].strip():
            spec["dose"] = result["dose"].strip()
        if result["route"].strip():
            spec["route"] = result["route"].strip()
        if result["frequency"].strip():
            spec["frequency"] = result["frequency"].strip()
        if result["prn"]:
            spec["prn"] = True
        if result["prn_reason"].strip():
            spec["prn_reason"] = result["prn_reason"].strip()
        s = self.data["order_sets"][self._current_os_index]
        s.setdefault("medications", []).append(spec)
        self._refresh_os_med_tree(s)
        self._mark_dirty()

    def _remove_os_medication(self):
        if self._current_os_index is None:
            return
        sel = self.os_med_tree.selection()
        if not sel:
            return
        idx = self.os_med_tree.index(sel[0])
        s = self.data["order_sets"][self._current_os_index]
        del s["medications"][idx]
        self._refresh_os_med_tree(s)
        self._mark_dirty()

    def _refresh_os_drip_tree(self, s):
        self.os_drip_tree.delete(*self.os_drip_tree.get_children())
        for d in s.get("drips", []):
            self.os_drip_tree.insert("", "end", values=(
                d["name"], d.get("protocol", ""), d.get("initial_dose", ""), d.get("titrate_by", ""),
                d.get("titrate_frequency", ""), d.get("max_dose", ""), d.get("goal", ""),
            ))

    def _add_os_drip(self):
        if self._current_os_index is None:
            return
        drip_names = [d["name"] for d in self.data["drips"]]
        if not drip_names:
            messagebox.showinfo("No drips", "Add drips on the Drips tab first.")
            return
        fields = [
            {"key": "name", "label": "Drip", "kind": "combobox", "values": drip_names,
             "state": "readonly", "default": drip_names[0]},
            {"key": "protocol", "label": "Protocol text override (optional, for fixed-protocol drips)", "default": ""},
            {"key": "initial_dose", "label": "Initial Dose override (optional)", "default": ""},
            {"key": "titrate_by", "label": "Titrate By override (optional)", "default": ""},
            {"key": "titrate_frequency", "label": "Titrate Frequency override (optional)", "kind": "combobox",
             "values": self.data["titrate_frequencies"], "default": ""},
            {"key": "max_dose", "label": "Max Dose override (optional)", "default": ""},
            {"key": "goal", "label": "Goal override (optional)", "default": ""},
        ]
        result = FormDialog.ask(self, "Add Drip to Order Set", fields)
        if not result:
            return
        spec = {"name": result["name"]}
        for key in ("protocol", "initial_dose", "titrate_by", "titrate_frequency", "max_dose", "goal"):
            if result[key].strip():
                spec[key] = result[key].strip()
        s = self.data["order_sets"][self._current_os_index]
        s.setdefault("drips", []).append(spec)
        self._refresh_os_drip_tree(s)
        self._mark_dirty()

    def _remove_os_drip(self):
        if self._current_os_index is None:
            return
        sel = self.os_drip_tree.selection()
        if not sel:
            return
        idx = self.os_drip_tree.index(sel[0])
        s = self.data["order_sets"][self._current_os_index]
        del s["drips"][idx]
        self._refresh_os_drip_tree(s)
        self._mark_dirty()

    def _refresh_os_img_tree(self, s):
        self.os_img_tree.delete(*self.os_img_tree.get_children())
        for im in s.get("imaging", []):
            self.os_img_tree.insert("", "end", values=(
                im.get("modality", ""), im.get("study", ""), im.get("indication", ""),
                "Yes" if im.get("contrast") else "", im.get("side", ""),
            ))

    def _add_os_imaging(self):
        if self._current_os_index is None:
            return
        modalities = list(self.data["imaging_modalities"].keys())
        if not modalities:
            messagebox.showinfo("No modalities", "Add an imaging modality on the Imaging tab first.")
            return
        fields = [
            {"key": "modality", "label": "Modality", "kind": "combobox", "values": modalities,
             "state": "readonly", "default": modalities[0]},
            {"key": "study", "label": "Study", "default": ""},
            {"key": "indication", "label": "Indication", "default": ""},
            {"key": "contrast", "label": "With Contrast", "kind": "checkbutton", "default": False},
            {"key": "side", "label": "Side (optional)", "kind": "combobox",
             "values": ["", "Left", "Right", "Bilateral"], "state": "readonly", "default": ""},
        ]
        result = FormDialog.ask(self, "Add Imaging to Order Set", fields)
        if not result:
            return
        if not result["study"].strip():
            messagebox.showwarning("Missing study", "Enter a study name.")
            return
        spec = {
            "modality": result["modality"], "study": result["study"].strip(),
            "indication": result["indication"].strip(),
        }
        if result["contrast"]:
            spec["contrast"] = True
        if result["side"]:
            spec["side"] = result["side"]
        s = self.data["order_sets"][self._current_os_index]
        s.setdefault("imaging", []).append(spec)
        self._refresh_os_img_tree(s)
        self._mark_dirty()

    def _remove_os_imaging(self):
        if self._current_os_index is None:
            return
        sel = self.os_img_tree.selection()
        if not sel:
            return
        idx = self.os_img_tree.index(sel[0])
        s = self.data["order_sets"][self._current_os_index]
        del s["imaging"][idx]
        self._refresh_os_img_tree(s)
        self._mark_dirty()

    def _add_order_set(self):
        new_set = {"name": "New Order Set", "labs": [], "medications": [], "drips": [], "imaging": [], "other": []}
        self.data["order_sets"].append(new_set)
        self._refresh_order_sets_list(select_index=len(self.data["order_sets"]) - 1)
        self._mark_dirty()

    def _duplicate_order_set(self):
        if self._current_os_index is None:
            return
        copy_set = copy.deepcopy(self.data["order_sets"][self._current_os_index])
        copy_set["name"] = copy_set.get("name", "") + " (Copy)"
        self.data["order_sets"].insert(self._current_os_index + 1, copy_set)
        self._refresh_order_sets_list(select_index=self._current_os_index + 1)
        self._mark_dirty()

    def _delete_order_set(self):
        if self._current_os_index is None:
            return
        name = self.data["order_sets"][self._current_os_index]["name"]
        if not messagebox.askyesno("Delete Order Set", 'Delete "{}"?'.format(name)):
            return
        del self.data["order_sets"][self._current_os_index]
        self._current_os_index = None
        self._refresh_order_sets_list()
        self._mark_dirty()

    def _move_order_set(self, delta):
        if self._current_os_index is None:
            return
        i = self._current_os_index
        j = i + delta
        sets = self.data["order_sets"]
        if not (0 <= j < len(sets)):
            return
        sets[i], sets[j] = sets[j], sets[i]
        self._refresh_order_sets_list(select_index=j)
        self._mark_dirty()


ORDER_SET_TYPES = [
    ("regular", "Physician Order Set (additive)"),
    ("aop", "AOP / Nurse Protocol"),
    ("modifier", "AOP Modifier"),
]


def main():
    app = DataEditorApp()
    app.mainloop()


if __name__ == "__main__":
    main()
