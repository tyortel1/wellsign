"""Mark Payment Received dialog.

Compact modal for the Payments tab. Operator opens a single payment row
and records: amount received, date, method (wire/check), reference number,
notes. Saving calls ``db/payments.mark_received`` which auto-derives the
new status (received / partial) from the amount delta.
"""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from wellsign.db.payments import PAYMENT_METHODS, PaymentRow, clear_payment, mark_received


class PaymentDialog(QDialog):
    """Mark a single payment as received (or clear it back to expected)."""

    def __init__(
        self,
        payment: PaymentRow,
        investor_name: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._payment = payment
        self._saved: PaymentRow | None = None
        self._cleared = False

        ptype = payment.payment_type.upper()
        payee = "Decker Exploration" if payment.payee == "decker" else "Paloma Operating"
        self.setWindowTitle(f"Mark {ptype} payment received — {investor_name}")
        self.setModal(True)
        self.setMinimumWidth(480)

        self._build(investor_name, ptype, payee)
        self._wire()

    # ---- layout ---------------------------------------------------------
    def _build(self, investor_name: str, ptype_label: str, payee_label: str) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 22, 24, 18)
        outer.setSpacing(14)

        title = QLabel(
            f"<b style='font-size:14pt;'>{ptype_label} payment</b><br>"
            f"<span style='color:#5b6473;'>"
            f"{investor_name}  →  {payee_label}"
            f"</span>"
        )
        outer.addWidget(title)

        # Expected reminder strip
        exp = QLabel(
            f"<b>Expected:</b> ${self._payment.expected_amount:,.2f}"
        )
        exp.setStyleSheet(
            "background: #f0f3fa; border: 1px solid #d8dce3; "
            "border-radius: 6px; padding: 8px 14px;"
        )
        outer.addWidget(exp)

        form = QFormLayout()
        form.setVerticalSpacing(10)
        form.setHorizontalSpacing(12)

        self.amount_spin = QDoubleSpinBox()
        self.amount_spin.setRange(0, 100_000_000)
        self.amount_spin.setDecimals(2)
        self.amount_spin.setPrefix("$ ")
        self.amount_spin.setGroupSeparatorShown(True)
        self.amount_spin.setSingleStep(100)
        # Default to expected so the operator just clicks Save in the common
        # case of "they paid the full amount"
        if self._payment.received_amount is not None:
            self.amount_spin.setValue(self._payment.received_amount)
        else:
            self.amount_spin.setValue(self._payment.expected_amount)

        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        self.date_edit.setMinimumDate(QDate(2000, 1, 1))
        if self._payment.received_at:
            try:
                d = date.fromisoformat(self._payment.received_at[:10])
                self.date_edit.setDate(QDate(d.year, d.month, d.day))
            except ValueError:
                self.date_edit.setDate(QDate.currentDate())
        else:
            self.date_edit.setDate(QDate.currentDate())

        self.method_combo = QComboBox()
        for code, label in PAYMENT_METHODS:
            self.method_combo.addItem(label, userData=code)
        if self._payment.method:
            idx = self.method_combo.findData(self._payment.method)
            if idx >= 0:
                self.method_combo.setCurrentIndex(idx)

        self.reference_edit = QLineEdit(self._payment.reference_number or "")
        self.reference_edit.setPlaceholderText("Wire confirmation # / check #")

        self.notes_edit = QPlainTextEdit(self._payment.notes or "")
        self.notes_edit.setPlaceholderText("Optional notes")
        self.notes_edit.setFixedHeight(60)

        form.addRow("Amount received:", self.amount_spin)
        form.addRow("Date received:", self.date_edit)
        form.addRow("Method:", self.method_combo)
        form.addRow("Reference #:", self.reference_edit)
        form.addRow("Notes:", self.notes_edit)
        outer.addLayout(form)

        # Buttons — Clear button on the left, Save/Cancel on the right
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Reset
            | QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.Save
        )
        self.save_btn = self.buttons.button(QDialogButtonBox.StandardButton.Save)
        self.save_btn.setText("Save")
        self.cancel_btn = self.buttons.button(QDialogButtonBox.StandardButton.Cancel)
        self.cancel_btn.setProperty("secondary", True)
        self.clear_btn = self.buttons.button(QDialogButtonBox.StandardButton.Reset)
        self.clear_btn.setText("Clear / Reset")
        self.clear_btn.setProperty("danger", True)
        # Hide Clear when there's nothing to clear
        if self._payment.received_amount is None:
            self.clear_btn.setVisible(False)
        outer.addWidget(self.buttons)

    # ---- signals --------------------------------------------------------
    def _wire(self) -> None:
        self.buttons.accepted.connect(self._on_save)
        self.buttons.rejected.connect(self.reject)
        self.clear_btn.clicked.connect(self._on_clear)

    def _on_save(self) -> None:
        amount = float(self.amount_spin.value())
        if amount <= 0:
            QMessageBox.warning(
                self, "Zero amount",
                "Use the Clear / Reset button to clear a payment back to expected.",
            )
            return
        try:
            self._saved = mark_received(
                self._payment.id,
                received_amount=amount,
                method=self.method_combo.currentData(),
                received_at=self.date_edit.date().toString("yyyy-MM-dd"),
                reference_number=self.reference_edit.text().strip() or None,
                notes=self.notes_edit.toPlainText().strip() or None,
            )
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "Save failed", f"{e}")
            return
        self.accept()

    def _on_clear(self) -> None:
        ans = QMessageBox.question(
            self,
            "Clear payment?",
            "Reset this payment back to expected? The received amount, date, "
            "method, and reference number will be wiped. Use this only for "
            "data entry errors.",
        )
        if ans != QMessageBox.StandardButton.Yes:
            return
        try:
            self._saved = clear_payment(self._payment.id)
            self._cleared = True
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "Clear failed", f"{e}")
            return
        self.accept()

    @property
    def saved_payment(self) -> PaymentRow | None:
        return self._saved
