"""
Native Windows printing.

Shows a printer-picker dialog (a plain Tkinter Toplevel, consistent with
the rest of this app's UI -- NOT the Win32 common "Print" dialog) and then
prints each page of the PDF (rasterized via PyMuPDF) to the chosen printer
via win32ui.CreateDC()/CreatePrinterDC(), the standard GDI printing path.
Nothing is spooled to a printer unless the user clicks "Print" in that
dialog; clicking Cancel sends nothing.

This used to go through win32ui.CreatePrintDialog(), pywin32's wrapper
around MFC's CPrintDialog -- the same picker any Windows desktop app's
File > Print shows. That turned out to be a dead end: PyCPrintDialog's
Python method table is empty (no GetPrinterDC, nothing) even though the
underlying MFC class has one, so there was no supported way to get a
usable printer DC back out of it. Rebuilding the "let the user pick a
printer" step in Tkinter instead sidesteps that undocumented/nonfunctional
corner of pywin32 entirely, using only the well-documented, widely-used
CreateDC/CreatePrinterDC printing path.

Windows-only. Importing this module on any other platform, or without
pywin32 + PyMuPDF installed, raises ImportError -- callers (see
printing.print_order_sheet) should catch that and fall back to opening the
PDF in the default viewer instead.

NOTE: this talks directly to Win32 GDI printing APIs and has not been
exercised on a real Windows machine as part of building this app (developed
on macOS, which doesn't have these APIs at all). If it errors, check
printing.PRINT_DEBUG_LOG for the traceback. Before relying on it for real
use, test it once -- printing to the built-in "Microsoft Print to PDF"
virtual printer is a safe, paper-free way to confirm the dialog appears and
the output looks right before trying a physical printer.
"""

import sys

if sys.platform != "win32":
    raise ImportError("windows_print is only usable on Windows")

import tkinter as tk
from tkinter import ttk

import fitz  # PyMuPDF
import win32con
import win32print
import win32ui
from PIL import Image, ImageWin


def _rasterize_pages(pdf_path, dpi):
    doc = fitz.open(pdf_path)
    try:
        zoom = dpi / 72.0
        matrix = fitz.Matrix(zoom, zoom)
        images = []
        for page in doc:
            pix = page.get_pixmap(matrix=matrix)
            mode = "RGB" if pix.n < 4 else "RGBA"
            img = Image.frombytes(mode, (pix.width, pix.height), pix.samples)
            if mode == "RGBA":
                img = img.convert("RGB")
            images.append(img)
        return images
    finally:
        doc.close()


def _list_printers():
    flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
    return sorted(p[2] for p in win32print.EnumPrinters(flags))


class _PrinterPickerDialog(tk.Toplevel):
    """Minimal printer/copies picker, standing in for the OS print dialog
    (see module docstring for why)."""

    def __init__(self, doc_name):
        super().__init__()
        self.title("Print")
        self.resizable(False, False)
        self.result = None

        printers = _list_printers()
        try:
            default_printer = win32print.GetDefaultPrinter()
        except Exception:
            default_printer = None

        frame = ttk.Frame(self, padding=16)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text='Print "{}"'.format(doc_name)).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 12)
        )

        ttk.Label(frame, text="Printer:").grid(row=1, column=0, sticky="e", padx=(0, 8), pady=4)
        initial = default_printer if default_printer in printers else (printers[0] if printers else "")
        self.printer_var = tk.StringVar(value=initial)
        printer_combo = ttk.Combobox(
            frame, textvariable=self.printer_var, values=printers, width=32, state="readonly"
        )
        printer_combo.grid(row=1, column=1, sticky="w", pady=4)

        ttk.Label(frame, text="Copies:").grid(row=2, column=0, sticky="e", padx=(0, 8), pady=4)
        self.copies_var = tk.StringVar(value="1")
        ttk.Spinbox(frame, from_=1, to=20, textvariable=self.copies_var, width=5).grid(
            row=2, column=1, sticky="w", pady=4
        )

        btns = ttk.Frame(frame)
        btns.grid(row=3, column=0, columnspan=2, pady=(16, 0), sticky="e")
        ttk.Button(btns, text="Cancel", command=self._on_cancel).pack(side="right", padx=(8, 0))
        ttk.Button(btns, text="Print", command=self._on_print).pack(side="right")
        ttk.Button(btns, text="Open as PDF Instead", command=self._on_pdf_fallback).pack(
            side="right", padx=(0, 8)
        )

        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        printer_combo.focus_set()

    def _on_print(self):
        printer = self.printer_var.get()
        if not printer:
            return
        try:
            copies = max(1, int(self.copies_var.get()))
        except ValueError:
            copies = 1
        self.result = (printer, copies)
        self.destroy()

    def _on_pdf_fallback(self):
        self.result = "pdf"
        self.destroy()

    def _on_cancel(self):
        self.result = None
        self.destroy()


def print_pdf_with_dialog(pdf_path, doc_name="Order Sheet"):
    """Shows a printer-picker dialog. Returns one of:
      True   -- user picked a printer and clicked Print (job fully spooled)
      False  -- user clicked Cancel; nothing happened
      "pdf"  -- user clicked "Open as PDF Instead"; caller should fall back
                to opening the PDF in the default viewer
    """
    picker = _PrinterPickerDialog(doc_name)
    picker.wait_window()
    if picker.result is None:
        return False
    if picker.result == "pdf":
        return "pdf"
    printer_name, copies = picker.result

    dc = win32ui.CreateDC()
    dc.CreatePrinterDC(printer_name)
    try:
        page_w = dc.GetDeviceCaps(win32con.HORZRES)
        page_h = dc.GetDeviceCaps(win32con.VERTRES)
        dpi = dc.GetDeviceCaps(win32con.LOGPIXELSX) or 300

        images = _rasterize_pages(pdf_path, dpi)

        for _ in range(copies):
            dc.StartDoc(doc_name)
            for img in images:
                dc.StartPage()
                w, h = img.size
                scale = min(page_w / w, page_h / h)
                draw_w, draw_h = int(w * scale), int(h * scale)
                dib = ImageWin.Dib(img)
                dib.draw(dc.GetHandleOutput(), (0, 0, draw_w, draw_h))
                dc.EndPage()
            dc.EndDoc()
    finally:
        dc.DeleteDC()
    return True
