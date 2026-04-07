"""Application entry point."""

from __future__ import annotations

import sys
from importlib import resources

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox

from wellsign.db.migrate import run_migrations
from wellsign.db.seed import seed_if_empty
from wellsign.ui.main_window import MainWindow
from wellsign.util.crypto import MasterKeyMissingError, healthcheck_master_key


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

    # PII encryption master key health check.
    # On a fresh install this auto-generates a new key in the keyring.
    # On a returning install with no key but existing encrypted data,
    # this refuses to boot with a clear "key was wiped" error.
    try:
        healthcheck_master_key()
    except MasterKeyMissingError as e:
        QMessageBox.critical(
            None,
            "WellSign — Encryption Key Missing",
            str(e),
        )
        return 1

    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
