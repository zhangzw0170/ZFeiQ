"""Bridge: expose the original full MainWindow as the module's `MainWindow`.

This file intentionally does not reimplement the UI — it simply re-exports
the `MainWindow` from `main_window_full.py` (which is the verbatim original
GUI). Any interface adaptation should be done via adapters/bindings; do not
modify the original window implementation here.
"""

from .main_window_full import MainWindow  # re-export original implementation

