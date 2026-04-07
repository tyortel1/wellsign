"""Add / Edit Investor dialog.

Sectioned modal:
  * Identity:   first / last / entity / title / email / phone
  * Address:    line1 / line2 / city / state / zip
  * Investment: WI% (8 dp), payment preference, live LLG / DHC dollar preview
  * Banking & PII: SSN/EIN, bank name / routing / account.
                    PII fields are AES-256-GCM encrypted on save and shown
                    masked when editing — operator clicks "Show" to reveal.

Used by ``InvestorsTab`` for both add and edit.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QDoubleValidator
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from wellsign.db.investors import (
    InvestorRow,
    insert_investor,
    update_investor,
)
from wellsign.db.payments import ensure_payments_for_investor
from wellsign.db.projects import ProjectRow, get_project_totals
from wellsign.db.workflows import start_workflow_for_investor
from wellsign.util.calc import compute_amounts
from wellsign.util.crypto import decrypt_pii, mask_pii


class _PiiField(QWidget):
    """Line-edit + Show/Hide toggle for a PII value.

    States:
      * empty (new investor):     editable, no toggle
      * stored (edit existing):   shows mask + 'Show' button. Clicking 'Show'
                                  decrypts the stored value once and lets the
                                  operator edit it. We track ``modified`` so
                                  the dialog only sends a new value back if
                                  the operator actually changed something.
    """

    def __init__(
        self,
        encrypted: str | None,
        placeholder: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._encrypted = encrypted
        self._modified = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.edit = QLineEdit()
        self.edit.setPlaceholderText(placeholder)
        self.edit.textEdited.connect(self._on_edited)
        layout.addWidget(self.edit, 1)

        self.toggle_btn = QPushButton("Show")
        self.toggle_btn.setProperty("secondary", True)
        self.toggle_btn.setFixedWidth(64)
        self.toggle_btn.clicked.connect(self._on_toggle)
        layout.addWidget(self.toggle_btn)

        if encrypted:
            # Display masked placeholder, hide the actual value until Show
            self.edit.setReadOnly(True)
            try:
                plain = decrypt_pii(encrypted)
            except Exception:
                plain = None
            self._cached_plain = plain
            self.edit.setText(mask_pii(plain) if plain else "(stored)")
        else:
            self._cached_plain = None
            self.toggle_btn.setEnabled(False)

    def _on_edited(self, _text: str) -> None:
        self._modified = True

    def _on_toggle(self) -> None:
        if self.edit.isReadOnly():
            # Reveal: show plaintext and let user edit
            self.edit.setReadOnly(False)
            self.edit.setText(self._cached_plain or "")
            self.edit.setFocus()
            self.toggle_btn.setText("Hide")
        else:
            # Hide: re-mask, but don't drop a freshly-typed edit
            current = self.edit.text()
            self.edit.setReadOnly(True)
            self.edit.setText(mask_pii(current) if current else "")
            self.toggle_btn.setText("Show")

    def value_for_save(self) -> str | None:
        """Return what to pass to insert/update.

        ``None`` means 'no change'. Empty string means 'clear'. A real string
        means 'encrypt this value'.
        """
        if self._encrypted is None:
            # New investor: anything in the box is the value
            text = self.edit.text().strip()
            return text if text else None
        if not self._modified:
            return None  # leave existing encrypted value alone
        # Editing existing — operator changed something. Use whatever's in the
        # field right now (which is plaintext after Show).
        return self.edit.text().strip()


class InvestorDialog(QDialog):
    """Modal for adding or editing a single investor."""

    def __init__(
        self,
        project: ProjectRow,
        parent: QWidget | None = None,
        existing: InvestorRow | None = None,
    ) -> None:
        super().__init__(parent)
        self._project = project
        self._editing = existing
        self._saved: InvestorRow | None = None

        self.setWindowTitle("Edit Investor" if existing else "Add Investor")
        self.setModal(True)
        self.setMinimumWidth(640)
        self.setMinimumHeight(560)

        self._total_llg, self._total_dhc = get_project_totals(project.id)

        self._build()
        self._wire()
        if existing is not None:
            self._prefill(existing)
        self._recompute_amounts()

    # ------------------------------------------------------------------ build
    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 22, 24, 18)
        outer.setSpacing(14)

        title = QLabel("Edit investor" if self._editing else "Add a new investor")
        f = title.font()
        f.setPointSize(15)
        f.setBold(True)
        title.setFont(f)
        outer.addWidget(title)

        sub = QLabel(
            f"Project: <b>{self._project.name}</b>"
            f"  ·  LLG total ${self._total_llg:,.2f}"
            f"  ·  DHC total ${self._total_dhc:,.2f}"
        )
        sub.setStyleSheet("color: #5b6473;")
        outer.addWidget(sub)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.addTab(self._build_identity_tab(),   "Identity")
        self.tabs.addTab(self._build_address_tab(),    "Address")
        self.tabs.addTab(self._build_investment_tab(), "Investment")
        self.tabs.addTab(self._build_pii_tab(),        "Banking & PII")
        outer.addWidget(self.tabs, 1)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save
        )
        self.save_btn = self.buttons.button(QDialogButtonBox.StandardButton.Save)
        self.save_btn.setText("Save Investor")
        self.cancel_btn = self.buttons.button(QDialogButtonBox.StandardButton.Cancel)
        self.cancel_btn.setProperty("secondary", True)
        outer.addWidget(self.buttons)

    def _build_identity_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setVerticalSpacing(10)
        form.setHorizontalSpacing(12)

        self.first_edit = QLineEdit()
        self.first_edit.setPlaceholderText("Given name")
        self.last_edit = QLineEdit()
        self.last_edit.setPlaceholderText("Family name")
        self.entity_edit = QLineEdit()
        self.entity_edit.setPlaceholderText("LLC / trust / IRA name (optional)")
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Signing title (optional)")
        self.email_edit = QLineEdit()
        self.email_edit.setPlaceholderText("name@example.com")
        self.phone_edit = QLineEdit()
        self.phone_edit.setPlaceholderText("(555) 555-1212")

        form.addRow("First name:", self.first_edit)
        form.addRow("Last name:", self.last_edit)
        form.addRow("Entity:", self.entity_edit)
        form.addRow("Title:", self.title_edit)
        form.addRow("Email:", self.email_edit)
        form.addRow("Phone:", self.phone_edit)
        return w

    def _build_address_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setVerticalSpacing(10)
        form.setHorizontalSpacing(12)

        self.addr1_edit = QLineEdit()
        self.addr1_edit.setPlaceholderText("Street")
        self.addr2_edit = QLineEdit()
        self.addr2_edit.setPlaceholderText("Apt / unit / suite (optional)")
        self.city_edit = QLineEdit()
        self.state_edit = QLineEdit()
        self.state_edit.setPlaceholderText("e.g. TX")
        self.state_edit.setMaxLength(3)
        self.zip_edit = QLineEdit()
        self.zip_edit.setPlaceholderText("e.g. 78201")
        self.zip_edit.setMaxLength(10)

        form.addRow("Address line 1:", self.addr1_edit)
        form.addRow("Address line 2:", self.addr2_edit)
        form.addRow("City:", self.city_edit)
        form.addRow("State:", self.state_edit)
        form.addRow("Zip:", self.zip_edit)
        return w

    def _build_investment_tab(self) -> QWidget:
        w = QWidget()
        outer = QVBoxLayout(w)
        outer.setContentsMargins(0, 8, 0, 8)
        outer.setSpacing(12)

        form = QFormLayout()
        form.setVerticalSpacing(10)
        form.setHorizontalSpacing(12)

        self.wi_edit = QLineEdit()
        self.wi_edit.setPlaceholderText("e.g. 5.0 (percent)")
        # Allow up to 6 decimals on input — we keep 8 internally
        validator = QDoubleValidator(0.0, 100.0, 6, self)
        validator.setNotation(QDoubleValidator.Notation.StandardNotation)
        self.wi_edit.setValidator(validator)

        self.payment_combo = QComboBox()
        self.payment_combo.addItem("Wire", userData="wire")
        self.payment_combo.addItem("Check", userData="check")

        form.addRow("Working interest %:", self.wi_edit)
        form.addRow("Payment preference:", self.payment_combo)
        outer.addLayout(form)

        # Live amounts preview
        preview = QFrame()
        preview.setObjectName("AmountsPreview")
        preview.setStyleSheet(
            "QFrame#AmountsPreview { background: #f0f3fa; border: 1px solid #d8dce3; "
            "border-radius: 8px; }"
        )
        preview.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        prev_layout = QVBoxLayout(preview)
        prev_layout.setContentsMargins(16, 12, 16, 12)
        prev_layout.setSpacing(4)

        prev_title = QLabel("Cash call preview")
        pf = prev_title.font()
        pf.setBold(True)
        prev_title.setFont(pf)
        prev_layout.addWidget(prev_title)

        self.llg_preview = QLabel("LLG (→ Decker): $0.00")
        self.dhc_preview = QLabel("DHC (→ Paloma): $0.00")
        prev_layout.addWidget(self.llg_preview)
        prev_layout.addWidget(self.dhc_preview)

        outer.addWidget(preview)

        # Notes
        notes_label = QLabel("Notes:")
        notes_label.setStyleSheet("color: #5b6473;")
        outer.addWidget(notes_label)
        self.notes_edit = QPlainTextEdit()
        self.notes_edit.setPlaceholderText("Free-form notes about this investor (optional)")
        self.notes_edit.setFixedHeight(100)
        outer.addWidget(self.notes_edit)
        outer.addStretch(1)

        return w

    def _build_pii_tab(self) -> QWidget:
        w = QWidget()
        outer = QVBoxLayout(w)
        outer.setContentsMargins(0, 8, 0, 8)
        outer.setSpacing(10)

        warn = QLabel(
            "<b>These fields are encrypted at rest with AES-256-GCM.</b><br>"
            "The master key lives in the Windows Credential Manager via keyring "
            "and never touches disk. PII values are masked on display — click "
            "<i>Show</i> to reveal."
        )
        warn.setStyleSheet(
            "background: #fff8e1; border: 1px solid #f0c000; border-radius: 6px; "
            "padding: 10px; color: #5b4400;"
        )
        warn.setWordWrap(True)
        outer.addWidget(warn)

        form = QFormLayout()
        form.setVerticalSpacing(10)
        form.setHorizontalSpacing(12)

        existing = self._editing
        self.ssn_field = _PiiField(
            existing.ssn_enc if existing else None,
            placeholder="123-45-6789",
        )
        self.ein_field = _PiiField(
            existing.ein_enc if existing else None,
            placeholder="12-3456789",
        )
        self.bank_name_field = _PiiField(
            existing.bank_name_enc if existing else None,
            placeholder="e.g. Bank of America",
        )
        self.bank_routing_field = _PiiField(
            existing.bank_routing_enc if existing else None,
            placeholder="9-digit routing number",
        )
        self.bank_account_field = _PiiField(
            existing.bank_account_enc if existing else None,
            placeholder="Account number",
        )

        form.addRow("SSN:", self.ssn_field)
        form.addRow("EIN:", self.ein_field)
        form.addRow("Bank name:", self.bank_name_field)
        form.addRow("Bank routing:", self.bank_routing_field)
        form.addRow("Bank account:", self.bank_account_field)

        outer.addLayout(form)
        outer.addStretch(1)
        return w

    # ----------------------------------------------------------------- wiring
    def _wire(self) -> None:
        self.wi_edit.textChanged.connect(self._recompute_amounts)
        self.buttons.accepted.connect(self._on_save)
        self.buttons.rejected.connect(self.reject)

    def _prefill(self, inv: InvestorRow) -> None:
        self.first_edit.setText(inv.first_name or "")
        self.last_edit.setText(inv.last_name or "")
        self.entity_edit.setText(inv.entity_name or "")
        self.title_edit.setText(inv.title or "")
        self.email_edit.setText(inv.email or "")
        self.phone_edit.setText(inv.phone or "")
        self.addr1_edit.setText(inv.address_line1 or "")
        self.addr2_edit.setText(inv.address_line2 or "")
        self.city_edit.setText(inv.city or "")
        self.state_edit.setText(inv.state or "")
        self.zip_edit.setText(inv.zip or "")
        # WI is stored as a fraction; display as percent
        self.wi_edit.setText(f"{inv.wi_percent * 100:.6f}".rstrip("0").rstrip("."))
        idx = self.payment_combo.findData(inv.payment_preference or "wire")
        if idx >= 0:
            self.payment_combo.setCurrentIndex(idx)
        self.notes_edit.setPlainText(inv.notes or "")

    def _recompute_amounts(self) -> None:
        try:
            wi_pct_input = float(self.wi_edit.text() or "0")
        except ValueError:
            wi_pct_input = 0.0
        wi_fraction = wi_pct_input / 100.0
        llg, dhc = compute_amounts(wi_fraction, self._total_llg, self._total_dhc)
        self.llg_preview.setText(f"LLG (→ Decker): ${llg:,.2f}")
        self.dhc_preview.setText(f"DHC (→ Paloma): ${dhc:,.2f}")

    def _on_save(self) -> None:
        try:
            wi_pct_input = float(self.wi_edit.text() or "0")
        except ValueError:
            QMessageBox.warning(self, "Invalid WI%", "Working interest must be a number.")
            return
        if wi_pct_input < 0 or wi_pct_input > 100:
            QMessageBox.warning(
                self,
                "Invalid WI%",
                "Working interest must be between 0 and 100 percent.",
            )
            return

        wi_fraction = wi_pct_input / 100.0
        llg, dhc = compute_amounts(wi_fraction, self._total_llg, self._total_dhc)

        # Display name validation: at least one of first/last/entity
        if not (self.first_edit.text().strip() or
                self.last_edit.text().strip() or
                self.entity_edit.text().strip()):
            QMessageBox.warning(
                self,
                "Missing name",
                "Provide at least a first/last name or an entity name.",
            )
            return

        common = {
            "first_name":         self.first_edit.text().strip() or None,
            "last_name":          self.last_edit.text().strip() or None,
            "entity_name":        self.entity_edit.text().strip() or None,
            "title":              self.title_edit.text().strip() or None,
            "email":              self.email_edit.text().strip() or None,
            "phone":              self.phone_edit.text().strip() or None,
            "address_line1":      self.addr1_edit.text().strip() or None,
            "address_line2":      self.addr2_edit.text().strip() or None,
            "city":               self.city_edit.text().strip() or None,
            "state":              self.state_edit.text().strip() or None,
            "zip_code":           self.zip_edit.text().strip() or None,
            "wi_percent":         wi_fraction,
            "llg_amount":         llg,
            "dhc_amount":         dhc,
            "payment_preference": self.payment_combo.currentData(),
            "notes":              self.notes_edit.toPlainText().strip() or None,
        }

        if self._editing is None:
            # Create — read PII from each field
            self._saved = insert_investor(
                project_id=self._project.id,
                ssn=self.ssn_field.value_for_save(),
                ein=self.ein_field.value_for_save(),
                bank_name=self.bank_name_field.value_for_save(),
                bank_routing=self.bank_routing_field.value_for_save(),
                bank_account=self.bank_account_field.value_for_save(),
                **common,
            )
            # Kick off the project's workflow at stage 1 so traffic lights
            # come alive immediately. No-op if the project has no workflow.
            start_workflow_for_investor(self._saved.id, self._project.id)
        else:
            # Update — PII fields return None (= leave alone) unless modified
            self._saved = update_investor(
                self._editing.id,
                ssn=self.ssn_field.value_for_save(),
                ein=self.ein_field.value_for_save(),
                bank_name=self.bank_name_field.value_for_save(),
                bank_routing=self.bank_routing_field.value_for_save(),
                bank_account=self.bank_account_field.value_for_save(),
                **common,
            )

        # Create or refresh LLG + DHC payment rows so the Payments tab tracks
        # this investor automatically. Already-received rows are preserved;
        # only ``expected`` status rows get their amount refreshed.
        if self._saved is not None:
            ensure_payments_for_investor(self._saved)

        self.accept()

    @property
    def saved_investor(self) -> InvestorRow | None:
        return self._saved
