"""
Printing without persistence.

Order sheets contain patient name/CSN, so nothing is ever written to a
user-chosen, permanent location (no "Save As" dialog). Instead each PDF is
written to a private temp file, opened in the OS's default PDF viewer, and
then deleted:
  - immediately, if something fails before handoff
  - a few minutes later otherwise, giving the viewer time to actually read
    the file (and the user time to print it)
  - on app exit, as a backstop for anything still pending
  - on the next app startup, cleaning up anything orphaned by a crash

IMPORTANT: we deliberately do NOT use OS "quick print" mechanisms (e.g. the
Windows shell "print" verb, or sending a `print` AppleEvent to Preview on
macOS) to jump straight to a print dialog. Both were tested and found to
silently send the job straight to the default printer with no dialog and no
chance to review -- exactly what this app must not do with a patient order
sheet.

On Windows, print_order_sheet() instead drives the real Win32 print dialog
directly (see windows_print.py) -- a genuine printer/copies/properties
picker where nothing is spooled unless the user clicks Print. Everywhere
else (macOS/Linux, or if that path is unavailable for any reason), it falls
back to opening the file in the default viewer and the user prints from
there with Ctrl+P/Cmd+P -- still guaranteed to be the real OS dialog, since
it's the exact same action a person would normally take.
"""

import atexit
import glob
import os
import platform
import subprocess
import tempfile
import threading

TEMP_PREFIX = "ed_order_sheet_"
CLEANUP_DELAY_SECONDS = 300  # 5 minutes -- enough time to view/print it

_tracked_files = set()
_lock = threading.Lock()


def new_temp_pdf_path():
    fd, path = tempfile.mkstemp(prefix=TEMP_PREFIX, suffix=".pdf")
    os.close(fd)
    with _lock:
        _tracked_files.add(path)
    return path


def discard(path):
    """Delete `path` right away (e.g. after a failed PDF generation)."""
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except OSError:
        pass
    with _lock:
        _tracked_files.discard(path)


def _schedule_cleanup(path, delay=CLEANUP_DELAY_SECONDS):
    timer = threading.Timer(delay, discard, args=(path,))
    timer.daemon = True
    timer.start()


def cleanup_orphans():
    """Remove leftover temp PDFs from a previous run that crashed/was killed
    before it could clean up after itself. Call once at app startup."""
    pattern = os.path.join(tempfile.gettempdir(), TEMP_PREFIX + "*.pdf")
    for path in glob.glob(pattern):
        try:
            os.remove(path)
        except OSError:
            pass


def _cleanup_all_tracked():
    with _lock:
        paths = list(_tracked_files)
    for path in paths:
        discard(path)


atexit.register(_cleanup_all_tracked)


def open_in_viewer(path):
    """Open `path` in the default PDF viewer, then schedule the temp file
    for deletion. Used for on-screen preview, and as the cross-platform
    fallback for printing -- see print_order_sheet()."""
    system = platform.system()
    try:
        if system == "Windows":
            os.startfile(path)  # noqa: F821 (Windows only)
        elif system == "Darwin":
            subprocess.run(["open", path], check=False)
        else:
            subprocess.run(["xdg-open", path], check=False)
    finally:
        _schedule_cleanup(path)


def print_order_sheet(path):
    """Print `path`. Returns one of:
      "printed"   -- sent to a printer via the real Windows print dialog
      "cancelled" -- user cancelled that dialog; nothing was printed
      "opened"    -- fallback: opened in the default viewer instead (every
                     platform but Windows, or if the native path errored);
                     the user prints themselves with Ctrl+P/Cmd+P
    """
    if platform.system() == "Windows":
        try:
            import windows_print
            sent = windows_print.print_pdf_with_dialog(path, doc_name="ED Order Sheet")
        except Exception:
            pass  # native path unavailable/failed -- fall through to opening it
        else:
            discard(path)  # already fully spooled (or cancelled); nothing external needs it now
            return "printed" if sent else "cancelled"

    open_in_viewer(path)
    return "opened"
