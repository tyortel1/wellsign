"""New Email Template dialog — name, purpose, subject, body."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from wellsign.db.templates import EmailTemplateRow, insert_email_template, update_email_template

PURPOSES = [
    ("invitation", "Initial invitation"),
    ("reminder",   "Reminder"),
    ("thank_you",  "Thank you / completion"),
    ("custom",     "Custom"),
]


class NewEmailTemplateDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None = None,
        existing: EmailTemplateRow | None = None,
    ) -> None:
        super().__init__(parent)
        self._editing = existing
        self.setWindowTitle("Edit Email Template" if existing else "New Email Template")
        self.setModal(True)
        self.setMinimumWidth(620)
        self.setMinimumHeight(460)

        self._created: EmailTemplateRow | None = None

        self._build()
        self._wire()
        if existing is not None:
            self._prefill_from(existing)
        self._update_save_enabled()

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 22, 24, 18)
        outer.setSpacing(14)

        title = QLabel("Edit email template" if self._editing else "New email template")
        f = title.font()
        f.setPointSize(14)
        f.setBold(True)
        title.setFont(f)

        subtitle = QLabel(
            "Subject and body support merge variables like {{investor_name}}, "
            "{{prospect_name}}, {{llg_amount}}, {{dhc_amount}}, {{close_deadline}}."
        )
        subtitle.setStyleSheet("color: #5b6473;")
        subtitle.setWordWrap(True)

        form = QFormLayout()
        form.setVerticalSpacing(10)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g. Initial Investor Invitation")

        self.purpose_combo = QComboBox()
        for code, label in PURPOSES:
            self.purpose_combo.addItem(label, userData=code)

        self.subject_edit = QLineEdit()
        self.subject_edit.setPlaceholderText("{{prospect_name}} — Investor Documents for {{investor_name}}")

        self.body_edit = QPlainTextEdit()
        self.body_edit.setPlaceholderText(
            "Hi {{investor_first_name}},\n\nAttached are your documents for the {{prospect_name}} project..."
        )
        self.body_edit.setMinimumHeight(200)

        form.addRow("Template name:", self.name_edit)
        form.addRow("Purpose:", self.purpose_combo)
        form.addRow("Subject:", self.subject_edit)
        form.addRow("Body:", self.body_edit)

        outer.addWidget(title)
        outer.addWidget(subtitle)
        outer.addSpacing(4)
        outer.addLayout(form)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save
        )
        self.save_btn = self.buttons.button(QDialogButtonBox.StandardButton.Save)
        self.save_btn.setText("Save Changes" if self._editing else "Save Template")
        self.cancel_btn = self.buttons.button(QDialogButtonBox.StandardButton.Cancel)
        self.cancel_btn.setProperty("secondary", True)
        outer.addWidget(self.buttons)

    def _wire(self) -> None:
        self.name_edit.textChanged.connect(self._update_save_enabled)
        self.subject_edit.textChanged.connect(self._update_save_enabled)
        self.body_edit.textChanged.connect(self._update_save_enabled)
        self.buttons.accepted.connect(self._on_save)
        self.buttons.rejected.connect(self.reject)

    def _update_save_enabled(self) -> None:
        ok = (
            bool(self.name_edit.text().strip())
            and bool(self.subject_edit.text().strip())
            and bool(self.body_edit.toPlainText().strip())
        )
        self.save_btn.setEnabled(ok)

    def _prefill_from(self, t: EmailTemplateRow) -> None:
        self.name_edit.setText(t.name)
        for i in range(self.purpose_combo.count()):
            if self.purpose_combo.itemData(i) == t.purpose:
                self.purpose_combo.setCurrentIndex(i)
                break
        self.subject_edit.setText(t.subject)
        self.body_edit.setPlainText(t.body_html)

    def _on_save(self) -> None:
        if self._editing is not None:
            self._created = update_email_template(
                self._editing.id,
                name=self.name_edit.text().strip(),
                purpose=self.purpose_combo.currentData(),
                subject=self.subject_edit.text().strip(),
                body_html=self.body_edit.toPlainText(),
            )
        else:
            self._created = insert_email_template(
                name=self.name_edit.text().strip(),
                purpose=self.purpose_combo.currentData(),
                subject=self.subject_edit.text().strip(),
                body_html=self.body_edit.toPlainText(),
                is_global=True,
            )
        self.accept()

    @property
    def created_template(self) -> EmailTemplateRow | None:
        return self._created
