"""
Native Windows print-dialog printing.

Rasterizes each page of a PDF (via PyMuPDF) and sends it through the real
Windows common Print dialog (via pywin32) -- the same picker you'd get from
any desktop app's File > Print, with a printer/copies/properties chooser.
Nothing is spooled to a printer unless the user clicks "Print" in that
dialog; clicking Cancel sends nothing.

Windows-only. Importing this module on any other platform, or without
pywin32 + PyMuPDF installed, raises ImportError -- callers (see
printing.print_order_sheet) should catch that and fall back to opening the
PDF in the default viewer instead.

NOTE: this talks directly to Win32 GDI printing APIs and has not been
exercised on a real Windows machine as part of building this app (developed
on macOS, which doesn't have these APIs at all). Before relying on it for
real use, test it once -- printing to the built-in "Microsoft Print to PDF"
virtual printer is a safe, paper-free way to confirm the dialog appears and
the output looks right before trying a physical printer.
"""

import sys

if sys.platform != "win32":
    raise ImportError("windows_print is only usable on Windows")

import fitz  # PyMuPDF
import win32con
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


def print_pdf_with_dialog(pdf_path, doc_name="Order Sheet"):
    """Shows the native Print dialog. Returns True if a job was spooled
    (user picked a printer and clicked Print), False if they cancelled."""
    flags = (
        win32con.PD_RETURNDC
        | win32con.PD_USEDEVMODECOPIES
        | win32con.PD_NOPAGENUMS
        | win32con.PD_NOSELECTION
    )
    pd = win32ui.CreatePrintDialog(flags, None)
    if pd.DoModal() != win32con.IDOK:
        return False

    dc = win32ui.CreateDCFromHandle(pd.GetPrinterDC())
    page_w = dc.GetDeviceCaps(win32con.HORZRES)
    page_h = dc.GetDeviceCaps(win32con.VERTRES)
    dpi = dc.GetDeviceCaps(win32con.LOGPIXELSX) or 300

    images = _rasterize_pages(pdf_path, dpi)

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
    return True
