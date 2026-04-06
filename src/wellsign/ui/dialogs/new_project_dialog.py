"""New Project dialog — gated on a valid license token."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from wellsign.db.projects import ProjectRow, insert_project
from wellsign.db.workflows import list_workflows
from wellsign.license_.verify import LicenseError, LicensePayload, verify_license_file


class NewProjectDialog(QDialog):
    """Collect name / region / well / license file, verify, create."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Project")
        self.setModal(True)
        self.setMinimumWidth(520)

        self._verified_license: LicensePayload | None = None
        self._created: ProjectRow | None = None

        self._build()
        self._wire_signals()
        self._update_create_enabled()

    # ---- layout ---------------------------------------------------------
    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 22, 24, 18)
        outer.setSpacing(14)

        title = QLabel("Create a new project")
        title_font = title.font()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)

        subtitle = QLabel(
            "Each project requires a license token issued by WellSign. "
            "Browse to your .wslicense file below."
        )
        subtitle.setStyleSheet("color: #5b6473;")
        subtitle.setWordWrap(True)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        form.setVerticalSpacing(10)
        form.setHorizontalSpacing(12)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g. Highlander Prospect")
        self.region_edit = QLineEdit()
        self.region_edit.setPlaceholderText("e.g. Karnes County, TX")
        self.well_edit = QLineEdit()
        self.well_edit.setPlaceholderText("e.g. Pargmann-Gisler #1")

        form.addRow("Project name:", self.name_edit)
        form.addRow("Region:", self.region_edit)
        form.addRow("Well name:", self.well_edit)

        # License file row
        license_row = QHBoxLayout()
        license_row.setSpacing(8)
        self.license_path_edit = QLineEdit()
        self.license_path_edit.setReadOnly(True)
        self.license_path_edit.setPlaceholderText("No license file selected")
        self.browse_btn = QPushButton("Browse…")
        self.browse_btn.setProperty("secondary", True)
        license_row.addWidget(self.license_path_edit, 1)
        license_row.addWidget(self.browse_btn)
        form.addRow("License token:", license_row)

        # Status line — shows verification result
        self.status_label = QLabel("Pick a license file to continue.")
        self.status_label.setStyleSheet("color: #5b6473;")
        self.status_label.setWordWrap(True)

        outer.addWidget(title)
        outer.addWidget(subtitle)
        outer.addSpacing(4)
        outer.addLayout(form)
        outer.addWidget(self.status_label)
        outer.addStretch(1)

        # Buttons
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok
        )
        self.create_btn = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.create_btn.setText("Create Project")
        self.cancel_btn = self.buttons.button(QDialogButtonBox.StandardButton.Cancel)
        self.cancel_btn.setProperty("secondary", True)
        outer.addWidget(self.buttons)

    # ---- signals --------------------------------------------------------
    def _wire_signals(self) -> None:
        self.browse_btn.clicked.connect(self._on_browse)
        self.buttons.accepted.connect(self._on_create)
        self.buttons.rejected.connect(self.reject)
        for w in (self.name_edit, self.region_edit, self.well_edit):
            w.textChanged.connect(self._update_create_enabled)

    # ---- handlers -------------------------------------------------------
    def _on_browse(self) -> None:
        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Select WellSign License File",
            str(Path.cwd()),
            "WellSign License (*.wslicense *.json);;All files (*)",
        )
        if not path_str:
            return
        self._verify_license(Path(path_str))

    def _verify_license(self, path: Path) -> None:
        self.license_path_edit.setText(str(path))
        try:
            payload = verify_license_file(path)
        except LicenseError as e:
            self._verified_license = None
            self.status_label.setText(f"✗  {e}")
            self.status_label.setStyleSheet("color: #d1242f; font-weight: 600;")
        else:
            self._verified_license = payload
            self.status_label.setText(
                f"✓  {payload.customer}  ·  expires "
                f"{payload.expires_at.date().isoformat()}"
            )
            self.status_label.setStyleSheet("color: #1a7f37; font-weight: 600;")
            if not self.name_edit.text().strip() and payload.project_name:
                self.name_edit.setText(payload.project_name)
        self._update_create_enabled()

    def _update_create_enabled(self) -> None:
        ok = (
            bool(self.name_edit.text().strip())
            and bool(self.region_edit.text().strip())
            and bool(self.well_edit.text().strip())
            and self._verified_license is not None
        )
        self.create_btn.setEnabled(ok)

    def _on_create(self) -> None:
        if self._verified_license is None:
            return
        payload = self._verified_license
        self._created = insert_project(
            name=self.name_edit.text().strip(),
            region=self.region_edit.text().strip(),
            well_name=self.well_edit.text().strip(),
            license_key_hash=payload.key_hash,
            license_customer=payload.customer,
            license_issued_at=payload.issued_at.isoformat(),
            license_expires_at=payload.expires_at.isoformat(),
            license_key_id=payload.key_id,
            is_test=False,
        )
        self.accept()

    @property
    def created_project(self) -> ProjectRow | None:
        return self._created
