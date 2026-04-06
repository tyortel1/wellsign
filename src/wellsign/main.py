"""Application entry point."""

from __future__ import annotations

import sys
from importlib import resources

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from wellsign.db.migrate import run_migrations
from wellsign.db.seed import seed_if_empty
from wellsign.ui.main_window import MainWindow


def _load_stylesheet() -> str:
    return resources.files("wellsign.resources").joinpath("style.qss").read_text(encoding="utf-8")


def main() -> int:
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName("WellSign")
    app.setOrganizationName("WellSign")
    app.setStyle("Fusion")
    app.setStyleSheet(_load_stylesheet())

    # Apply schema on every startup; idempotent.
    run_migrations()
    seed_if_empty()

    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
