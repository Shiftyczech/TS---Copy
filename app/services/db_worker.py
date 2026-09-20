"""
Generic QThread worker for running DB-heavy operations off the main thread.
"""
from PySide6.QtCore import QThread, Signal


class DbWorker(QThread):
    """Run a callable in a background thread with progress reporting.

    Usage:
        def do_work(progress_cb):
            for i in range(n):
                # ... heavy work ...
                progress_cb(i + 1, f"Processing {i+1}/{n}")
            return moved_count

        worker = DbWorker(do_work)
        worker.progress.connect(on_progress)       # (int, str)
        worker.finished.connect(on_finished)        # (bool, str, object)
        worker.start()
    """
    progress = Signal(int, str)           # (step, label)
    finished = Signal(bool, str, object)  # (success, message, result)

    def __init__(self, fn, parent=None):
        super().__init__(parent)
        self._fn = fn

    def run(self):
        try:
            result = self._fn(self._emit_progress)
            self.finished.emit(True, "", result)
        except Exception as e:
            self.finished.emit(False, str(e), None)

    def _emit_progress(self, step: int, label: str = ""):
        self.progress.emit(step, label)
