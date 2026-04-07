"""Add / edit a single AFE cost line item."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from wellsign.db.costs import (
    COST_STATUSES,
    CostLineRow,
    PHASE_GROUPS,
    TAX_CLASSES,
    insert_cost_line,
    update_cost_line,
)

CATEGORY_SUGGESTIONS = [
    # Pre-drilling
    "Lease Bonus", "Title Work", "Landman Fees", "Right of Way",
    "Permits / Regulatory", "Surveying", "Site Prep", "Roads / Location",
    # Drilling
    "Drilling", "Drill Bits / BHA", "Directional Drilling", "Mud / Fluids",
    "Logging", "Cement", "Mob / Demob", "Trucking",
    # Casing (tangible)
    "Surface Casing", "Intermediate Casing", "Production Casing", "Tubing",
    # Completion
    "Frac Services", "Proppant / Sand", "Frac Fluids",
    "Perforating", "Wireline", "Coiled Tubing", "Stimulation",
    # Facilities (tangible)
    "Wellhead", "Tank Battery", "Separator", "Flowlines",
    "Pipeline / Gathering", "Meter / SCADA", "Compressor",
    # Soft costs
    "Operator Overhead", "Contingency", "Insurance", "Legal", "Roustabout / Labor",
    "Other",
]


class CostLineDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None = None,
        project_id: str | None = None,
        existing: CostLineRow | None = None,
    ) -> None:
        super().__init__(parent)
        if project_id is None and existing is not None:
            project_id = existing.project_id
        self._project_id = project_id
        self._editing = existing
        self._created: CostLineRow | None = None

        self.setWindowTitle("Edit Cost Line" if existing else "New Cost Line")
        self.setModal(True)
        self.setMinimumWidth(540)

        self._build()
        self._wire()
        if existing is not None:
            self._prefill(existing)
        self._update_save_enabled()

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 22, 24, 18)
        outer.setSpacing(12)

        title = QLabel("Edit cost line" if self._editing else "New cost line")
        f = title.font()
        f.setPointSize(14)
        f.setBold(True)
        title.setFont(f)
        outer.addWidget(title)

        form = QFormLayout()
        form.setVerticalSpacing(10)

        self.phase_combo = QComboBox()
        for code, label in PHASE_GROUPS:
            self.phase_combo.addItem(label, userData=code)

        self.tax_combo = QComboBox()
        for code, label in TAX_CLASSES:
            self.tax_combo.addItem(label, userData=code)

        self.category_combo = QComboBox()
        self.category_combo.setEditable(True)
        self.category_combo.addItems(CATEGORY_SUGGESTIONS)

        self.description_edit = QLineEdit()
        self.description_edit.setPlaceholderText("e.g. Surface casing — 13-3/8 in")

        self.expected_spin = QDoubleSpinBox()
        self.expected_spin.setRange(0, 100_000_000)
        self.expected_spin.setDecimals(2)
        self.expected_spin.setPrefix("$ ")
        self.expected_spin.setGroupSeparatorShown(True)
        self.expected_spin.setSingleStep(1000)

        self.actual_spin = QDoubleSpinBox()
        self.actual_spin.setRange(0, 100_000_000)
        self.actual_spin.setDecimals(2)
        self.actual_spin.setPrefix("$ ")
        self.actual_spin.setGroupSeparatorShown(True)
        self.actual_spin.setSpecialValueText("(no actual yet)")
        self.actual_spin.setSingleStep(1000)

        self.vendor_edit = QLineEdit()
        self.vendor_edit.setPlaceholderText("Vendor / payee")

        self.invoice_edit = QLineEdit()
        self.invoice_edit.setPlaceholderText("Invoice / PO number")

        self.status_combo = QComboBox()
        for code, label in COST_STATUSES:
            self.status_combo.addItem(label, userData=code)

        self.notes_edit = QPlainTextEdit()
        self.notes_edit.setMaximumHeight(80)

        form.addRow("Phase:", self.phase_combo)
        form.addRow("Tax class:", self.tax_combo)
        form.addRow("Category:", self.category_combo)
        form.addRow("Description:", self.description_edit)
        form.addRow("Expected (AFE):", self.expected_spin)
        form.addRow("Actual:", self.actual_spin)
        form.addRow("Vendor:", self.vendor_edit)
        form.addRow("Invoice #:", self.invoice_edit)
        form.addRow("Status:", self.status_combo)
        form.addRow("Notes:", self.notes_edit)

        outer.addLayout(form)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save
        )
        self.save_btn = self.buttons.button(QDialogButtonBox.StandardButton.Save)
        self.save_btn.setText("Save Changes" if self._editing else "Save Line Item")
        self.cancel_btn = self.buttons.button(QDialogButtonBox.StandardButton.Cancel)
        self.cancel_btn.setProperty("secondary", True)
        outer.addWidget(self.buttons)

    def _wire(self) -> None:
        self.description_edit.textChanged.connect(self._update_save_enabled)
        self.category_combo.currentTextChanged.connect(self._update_save_enabled)
        self.buttons.accepted.connect(self._on_save)
        self.buttons.rejected.connect(self.reject)

    def _prefill(self, line: CostLineRow) -> None:
        idx_p = self.phase_combo.findData(line.phase_group)
        if idx_p >= 0:
            self.phase_combo.setCurrentIndex(idx_p)
        idx_t = self.tax_combo.findData(line.tax_class)
        if idx_t >= 0:
            self.tax_combo.setCurrentIndex(idx_t)
        idx = self.category_combo.findText(line.category)
        if idx >= 0:
            self.category_combo.setCurrentIndex(idx)
        else:
            self.category_combo.setCurrentText(line.category)
        self.description_edit.setText(line.description)
        self.expected_spin.setValue(line.expected_amount)
        if line.actual_amount is not None:
            self.actual_spin.setValue(line.actual_amount)
        else:
            self.actual_spin.setValue(0)
        self.vendor_edit.setText(line.vendor or "")
        self.invoice_edit.setText(line.invoice_number or "")
        idx2 = self.status_combo.findData(line.status)
        if idx2 >= 0:
            self.status_combo.setCurrentIndex(idx2)
        self.notes_edit.setPlainText(line.notes or "")

    def _update_save_enabled(self) -> None:
        ok = (
            bool(self.category_combo.currentText().strip())
            and bool(self.description_edit.text().strip())
        )
        self.save_btn.setEnabled(ok)

    def _on_save(self) -> None:
        actual: float | None = self.actual_spin.value() or None
        if actual == 0.0:
            actual = None
        phase = self.phase_combo.currentData()
        tax = self.tax_combo.currentData()
        if self._editing is not None:
            self._created = update_cost_line(
                self._editing.id,
                category=self.category_combo.currentText().strip(),
                description=self.description_edit.text().strip(),
                expected_amount=self.expected_spin.value(),
                actual_amount=actual,
                vendor=self.vendor_edit.text().strip() or None,
                invoice_number=self.invoice_edit.text().strip() or None,
                notes=self.notes_edit.toPlainText().strip() or None,
                status=self.status_combo.currentData(),
                phase_group=phase,
                tax_class=tax,
            )
        else:
            assert self._project_id is not None
            self._created = insert_cost_line(
                project_id=self._project_id,
                category=self.category_combo.currentText().strip(),
                description=self.description_edit.text().strip(),
                expected_amount=self.expected_spin.value(),
                actual_amount=actual,
                vendor=self.vendor_edit.text().strip() or None,
                invoice_number=self.invoice_edit.text().strip() or None,
                notes=self.notes_edit.toPlainText().strip() or None,
                status=self.status_combo.currentData(),
                phase_group=phase,
                tax_class=tax,
            )
        self.accept()

    @property
    def created_line(self) -> CostLineRow | None:
        return self._created
