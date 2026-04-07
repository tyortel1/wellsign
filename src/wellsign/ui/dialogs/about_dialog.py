"""About + Licenses dialog.

Required by the LGPL v3 obligations for PySide6: WellSign is a commercial
closed-source product, and we depend on PySide6 under the LGPL. The
compliance plan documented in ``docs/licenses.md`` says we must ship:

  * A list of every third-party dependency and its license
  * A statement that PySide6 is LGPL v3 and can be relinked by the user
  * A link to the upstream Qt source

This dialog renders all of that in-app.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from wellsign import __version__
from wellsign.app_paths import database_path


_DEPENDENCY_ROWS: list[tuple[str, str, str]] = [
    # (name, license, short note)
    ("PySide6",       "LGPL v3 / Qt Commercial", "Dynamically linked. See LGPL compliance below."),
    ("cryptography",  "Apache 2.0 / BSD",        "AES-256-GCM PII encryption."),
    ("keyring",       "MIT",                     "Windows Credential Manager bridge."),
    ("openpyxl",      "MIT",                     "Excel investor import."),
    ("pypdf",         "BSD-3-Clause",            "PDF AcroForm read + fill."),
    ("pdfrw",         "MIT",                     "PDF fallback reader."),
    ("reportlab",     "BSD-3-Clause",            "Synthesized PDFs (open source edition)."),
    ("pywin32",       "PSF-style",               "Outlook COM automation."),
    ("platformdirs",  "MIT",                     "%APPDATA% path resolution."),
    ("PyInstaller",   "GPL v2 + bootloader exception",
     "Bootloader exception makes packaged .exe commercial-safe."),
]


_LGPL_NOTICE = """\
WellSign uses the Qt for Python (PySide6) library under the GNU Lesser
General Public License v3.0.

You have the right to modify or replace the PySide6 libraries bundled
with this application. The Qt libraries live in the same directory as
WellSign.exe (one-folder PyInstaller layout) and can be swapped for a
compatible LGPL v3 version at your option.

Upstream PySide6 / Qt source is available from:
  https://www.qt.io/download-qt-source
  https://pypi.org/project/PySide6/

A copy of the LGPL v3 license text is shipped in the LICENSES/ folder
alongside this executable.
"""


_CREDITS = """\
WellSign — investor document workflow for oil & gas operators

Built by Jeremy Keeler with the help of Parker.
© 2026 WellSign. All rights reserved.

This product is commercial software licensed per-project. Each project
requires a license key issued by WellSign. Keys are RSA-signed offline
and never phone home — the entire application runs on your local machine
with no cloud dependency.
"""


class AboutDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("About WellSign")
        self.setModal(True)
        self.setMinimumSize(640, 520)
        self._build()

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 18, 20, 16)
        outer.setSpacing(12)

        # Header
        title = QLabel(f"<b style='font-size:18pt;'>WellSign</b>  "
                       f"<span style='color:#5b6473;'>v{__version__}</span>")
        outer.addWidget(title)

        sub = QLabel("Local desktop app for oil &amp; gas investor packet workflows.")
        sub.setStyleSheet("color: #5b6473;")
        outer.addWidget(sub)

        tabs = QTabWidget()
        tabs.setDocumentMode(True)
        tabs.addTab(self._build_about_tab(),     "About")
        tabs.addTab(self._build_licenses_tab(),  "Licenses")
        tabs.addTab(self._build_system_tab(),    "System")
        outer.addWidget(tabs, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        # The Close button maps to rejected; wire it to accept too for Enter key
        close_btn = buttons.button(QDialogButtonBox.StandardButton.Close)
        if close_btn:
            close_btn.setDefault(True)
            close_btn.clicked.connect(self.accept)
        outer.addWidget(buttons)

    def _build_about_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(4, 10, 4, 4)
        layout.setSpacing(8)

        credits = QPlainTextEdit()
        credits.setReadOnly(True)
        credits.setPlainText(_CREDITS)
        credits.setFrameShape(QPlainTextEdit.Shape.NoFrame)
        credits.setStyleSheet("background: transparent;")
        layout.addWidget(credits, 1)
        return w

    def _build_licenses_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(4, 10, 4, 4)
        layout.setSpacing(8)

        intro = QLabel(
            "WellSign is a commercial closed-source product. Every dependency "
            "below permits commercial redistribution. No GPL (without an "
            "exception clause), no AGPL, no SSPL, no non-commercial-only."
        )
        intro.setStyleSheet("color: #5b6473;")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        # Dependency table as HTML so it renders cleanly in QTextBrowser
        html_rows = [
            "<table cellspacing='0' cellpadding='6' "
            "style='border-collapse: collapse; width: 100%;'>",
            "<tr style='background: #eef0f4;'>"
            "<th align='left'>Package</th>"
            "<th align='left'>License</th>"
            "<th align='left'>Notes</th></tr>",
        ]
        for name, lic, note in _DEPENDENCY_ROWS:
            html_rows.append(
                f"<tr>"
                f"<td style='border-top: 1px solid #d8dce3;'><b>{name}</b></td>"
                f"<td style='border-top: 1px solid #d8dce3;'>{lic}</td>"
                f"<td style='border-top: 1px solid #d8dce3; color: #5b6473;'>{note}</td>"
                f"</tr>"
            )
        html_rows.append("</table>")

        html_rows.append("<h4 style='margin-top: 20px; color: #1f2430;'>"
                         "LGPL v3 compliance notice</h4>")
        html_rows.append(
            f"<pre style='background: #f0f3fa; border: 1px solid #d8dce3; "
            f"border-radius: 6px; padding: 10px; font-family: Consolas, "
            f"monospace; font-size: 9pt; color: #1f2430;'>{_LGPL_NOTICE}</pre>"
        )

        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setHtml("".join(html_rows))
        layout.addWidget(browser, 1)
        return w

    def _build_system_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(4, 10, 4, 4)
        layout.setSpacing(8)

        import platform
        import sys

        lines = [
            f"WellSign version:  {__version__}",
            f"Python version:    {sys.version.split()[0]}",
            f"Platform:          {platform.platform()}",
            f"Architecture:      {platform.machine()}",
            "",
            f"Database path:     {database_path()}",
            f"Data directory:    {database_path().parent}",
        ]

        info = QPlainTextEdit()
        info.setReadOnly(True)
        info.setPlainText("\n".join(lines))
        info.setStyleSheet(
            "QPlainTextEdit { font-family: Consolas, monospace; font-size: 9pt; "
            "background: #f0f3fa; border: 1px solid #d8dce3; border-radius: 6px; }"
        )
        layout.addWidget(info, 1)

        # Copy-to-clipboard helper
        row = QHBoxLayout()
        row.addStretch(1)
        copy_btn = QPushButton("Copy to clipboard")
        copy_btn.setProperty("secondary", True)
        copy_btn.clicked.connect(lambda: self._copy_system_info("\n".join(lines)))
        row.addWidget(copy_btn)
        layout.addLayout(row)
        return w

    def _copy_system_info(self, text: str) -> None:
        from PySide6.QtWidgets import QApplication

        cb = QApplication.clipboard()
        if cb is not None:
            cb.setText(text)


__all__ = ["AboutDialog"]
