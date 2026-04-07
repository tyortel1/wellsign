"""Edit Project dialog — modify a project's editable fields after creation.

Mirrors the layout of NewProjectDialog but skips the license file (binding
is immutable post-creation) and pre-populates from the existing row. Saves
via ``db/projects.update_project`` and emits the refreshed ProjectRow.
"""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from wellsign.db.migrate import connect
from wellsign.db.projects import ProjectRow, update_project


class EditProjectDialog(QDialog):
    """Edit prospect / well / county / dates / totals on an existing project."""

    def __init__(self, project: ProjectRow, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._project = project
        self._saved: ProjectRow | None = None

        self.setWindowTitle(f"Edit Project — {project.name}")
        self.setModal(True)
        self.setMinimumWidth(560)

        self._build()
        self._load_extra_fields()
        self._wire()

    # ---- layout ---------------------------------------------------------
    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 22, 24, 18)
        outer.setSpacing(14)

        title = QLabel("Edit project")
        f = title.font()
        f.setPointSize(14)
        f.setBold(True)
        title.setFont(f)
        outer.addWidget(title)

        subtitle = QLabel(
            "License binding, workflow, and phase aren't editable here. Use "
            "the phase banner to advance phase; the license is fixed at "
            "project creation."
        )
        subtitle.setStyleSheet("color: #5b6473;")
        subtitle.setWordWrap(True)
        outer.addWidget(subtitle)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        form.setVerticalSpacing(10)
        form.setHorizontalSpacing(12)

        self.name_edit = QLineEdit(self._project.name or "")
        self.prospect_edit = QLineEdit(self._project.prospect_name or "")
        self.well_edit = QLineEdit(self._project.well_name or "")
        self.operator_edit = QLineEdit(self._project.operator_llc or "")
        self.county_edit = QLineEdit("")  # populated by _load_extra_fields
        self.state_edit = QLineEdit(self._project.region or "")

        self.agreement_edit = QDateEdit()
        self.agreement_edit.setCalendarPopup(True)
        self.agreement_edit.setDisplayFormat("yyyy-MM-dd")
        self.agreement_edit.setSpecialValueText(" ")
        self.agreement_edit.setMinimumDate(QDate(2000, 1, 1))

        self.close_edit = QDateEdit()
        self.close_edit.setCalendarPopup(True)
        self.close_edit.setDisplayFormat("yyyy-MM-dd")
        self.close_edit.setSpecialValueText(" ")
        self.close_edit.setMinimumDate(QDate(2000, 1, 1))

        self.llg_spin = QDoubleSpinBox()
        self.llg_spin.setRange(0, 1_000_000_000)
        self.llg_spin.setDecimals(2)
        self.llg_spin.setPrefix("$ ")
        self.llg_spin.setGroupSeparatorShown(True)
        self.llg_spin.setSingleStep(10_000)

        self.dhc_spin = QDoubleSpinBox()
        self.dhc_spin.setRange(0, 1_000_000_000)
        self.dhc_spin.setDecimals(2)
        self.dhc_spin.setPrefix("$ ")
        self.dhc_spin.setGroupSeparatorShown(True)
        self.dhc_spin.setSingleStep(10_000)

        form.addRow("Project name:", self.name_edit)
        form.addRow("Prospect name:", self.prospect_edit)
        form.addRow("Well name:", self.well_edit)
        form.addRow("Operator LLC:", self.operator_edit)
        form.addRow("County:", self.county_edit)
        form.addRow("State:", self.state_edit)
        form.addRow("Agreement date:", self.agreement_edit)
        form.addRow("Close deadline:", self.close_edit)
        form.addRow("Total LLG cost (→ Decker):", self.llg_spin)
        form.addRow("Total DHC cost (→ Paloma):", self.dhc_spin)

        outer.addLayout(form)
        outer.addStretch(1)

        # Buttons
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save
        )
        self.save_btn = self.buttons.button(QDialogButtonBox.StandardButton.Save)
        self.save_btn.setText("Save Changes")
        self.cancel_btn = self.buttons.button(QDialogButtonBox.StandardButton.Cancel)
        self.cancel_btn.setProperty("secondary", True)
        outer.addWidget(self.buttons)

    def _load_extra_fields(self) -> None:
        """Pull county / dates / totals straight from the DB.

        ProjectRow doesn't carry these, so we hit the table directly.
        """
        with connect() as conn:
            row = conn.execute(
                "SELECT county, agreement_date, close_deadline, "
                "       total_llg_cost, total_dhc_cost "
                "  FROM projects WHERE id = ?",
                (self._project.id,),
            ).fetchone()
        if row is None:
            return
        self.county_edit.setText(row["county"] or "")

        ad = self._parse_iso(row["agreement_date"])
        if ad is not None:
            self.agreement_edit.setDate(ad)
        cd = self._parse_iso(row["close_deadline"])
        if cd is not None:
            self.close_edit.setDate(cd)

        self.llg_spin.setValue(float(row["total_llg_cost"] or 0))
        self.dhc_spin.setValue(float(row["total_dhc_cost"] or 0))

    @staticmethod
    def _parse_iso(value: str | None) -> QDate | None:
        if not value:
            return None
        try:
            d = date.fromisoformat(value[:10])
            return QDate(d.year, d.month, d.day)
        except (ValueError, TypeError):
            return None

    # ---- signals --------------------------------------------------------
    def _wire(self) -> None:
        self.buttons.accepted.connect(self._on_save)
        self.buttons.rejected.connect(self.reject)

    def _on_save(self) -> None:
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Missing name", "Project name is required.")
            return

        # Dates: convert from QDate to ISO string. SpecialValueText (' ')
        # means cleared — treat as None.
        ad_qdate = self.agreement_edit.date()
        cd_qdate = self.close_edit.date()
        agreement_iso = (
            ad_qdate.toString("yyyy-MM-dd") if ad_qdate.isValid() else None
        )
        close_iso = cd_qdate.toString("yyyy-MM-dd") if cd_qdate.isValid() else None

        # Sanity: close deadline shouldn't be before agreement
        if agreement_iso and close_iso and close_iso < agreement_iso:
            QMessageBox.warning(
                self,
                "Invalid dates",
                "Close deadline must be on or after the agreement date.",
            )
            return

        try:
            self._saved = update_project(
                self._project.id,
                name=name,
                prospect_name=self.prospect_edit.text().strip() or None,
                well_name=self.well_edit.text().strip() or None,
                operator_llc=self.operator_edit.text().strip() or None,
                county=self.county_edit.text().strip() or None,
                state=self.state_edit.text().strip() or None,
                agreement_date=agreement_iso,
                close_deadline=close_iso,
                total_llg_cost=self.llg_spin.value(),
                total_dhc_cost=self.dhc_spin.value(),
            )
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "Save failed", f"{e}")
            return
        self.accept()

    @property
    def saved_project(self) -> ProjectRow | None:
        return self._saved
