"""End-to-end smoke test: boot the app, render the main window, quit."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

# Use a throwaway data dir + key so the test doesn't touch the real keyring/DB.
_tmp = tempfile.mkdtemp(prefix="wellsign_test_")
os.environ["WELLSIGN_DATA_DIR"] = _tmp
os.environ["WELLSIGN_PII_KEY_HEX"] = "00" * 32

from PySide6.QtCore import QTimer  # noqa: E402

from wellsign.db.migrate import run_migrations  # noqa: E402
from wellsign.ui.main_window import MainWindow  # noqa: E402


def test_main_window_boots(qtbot):
    run_migrations()
    win = MainWindow()
    qtbot.addWidget(win)
    win.show()
    # New structure: navigator on the left, stacked pages on the right.
    assert win.navigator is not None
    assert win.stack.count() == 4
    assert win.windowTitle().startswith("WellSign")
    QTimer.singleShot(50, win.close)
    qtbot.waitUntil(lambda: not win.isVisible(), timeout=2000)


def test_database_path_exists_after_migration():
    run_migrations()
    assert (Path(_tmp) / "wellsign.db").exists()
