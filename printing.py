import atexit
import glob
import os
import platform
import subprocess
import tempfile
import threading
import traceback

TEMP_PREFIX = "ed_order_sheet_"
CLEANUP_DELAY_SECONDS = 300  # 5 minutes -- enough time to view/print it
PRINT_DEBUG_LOG = os.path.join(tempfile.gettempdir(), "ed_order_sheet_print_debug.log")

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


def _log_print_failure():
    """Best-effort: record why the native Windows print path failed, so a
    silent fallback to open_in_viewer can actually be diagnosed later
    instead of just looking like "it opened in a browser for no reason".
    Must be called from inside the except block. Never raises -- logging
    failure must not affect printing itself."""
    try:
        with open(PRINT_DEBUG_LOG, "a", encoding="utf-8") as f:
            f.write("--- native print failed ---\n")
            f.write(traceback.format_exc())
            f.write("\n")
    except OSError:
        pass


def print_order_sheet(path):
    """Print `path`. Returns one of:
      "printed"   -- sent to a printer via the real Windows print dialog
      "cancelled" -- user cancelled that dialog; nothing was printed
      "opened"    -- fallback: opened in the default viewer instead (every
                     platform but Windows, or if the native path errored);
                     the user prints themselves with Ctrl+P/Cmd+P

    If the native Windows path throws, the exception is logged to
    PRINT_DEBUG_LOG before falling back -- check that file to see why.
    """
    if platform.system() == "Windows":
        try:
            import windows_print
            sent = windows_print.print_pdf_with_dialog(path, doc_name="ED Order Sheet")
        except Exception:
            _log_print_failure()  # native path unavailable/failed -- fall through to opening it
        else:
            discard(path)  # already fully spooled (or cancelled); nothing external needs it now
            return "printed" if sent else "cancelled"

    open_in_viewer(path)
    return "opened"
