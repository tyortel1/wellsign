"""Multi-select template picker for the workflows builder.

Pops a dialog showing every doc OR every email template in the global
library with a checkbox next to each, lets the operator select multiple
at once, and (for emails) collects a single ``wait_days`` value that
applies to the whole batch.

Usage::

    dlg = TemplatePickerDialog(self, mode=PickerMode.DOCS)
    if dlg.exec() and dlg.result is not None:
        for tid in dlg.result.template_ids:
            attach_doc_to_stage(stage_id, tid)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from wellsign.db.templates import (
    DocTemplateRow,
    EmailTemplateRow,
    list_doc_templates,
    list_email_templates,
)


class PickerMode(str, Enum):
    DOCS = "docs"
    EMAILS = "emails"


@dataclass
class TemplatePickerResult:
    template_ids: list[str]
    wait_days: int  # only meaningful for emails; 0 for docs


class TemplatePickerDialog(QDialog):
    """Multi-select picker for doc OR email templates."""

    def __init__(
        self,
        parent: QWidget | None = None,
        mode: PickerMode = PickerMode.DOCS,
    ) -> None:
        super().__init__(parent)
        self._mode = mode
        self.result: TemplatePickerResult | None = None
        self._checkboxes: dict[str, QCheckBox] = {}

        is_docs = mode == PickerMode.DOCS
        self.setWindowTitle("Add documents to stage" if is_docs else "Add emails to stage")
        self.setModal(True)
        self.setMinimumWidth(540)
        self.setMinimumHeight(440)

        self._build()
        self._wire()
        self._update_ok_enabled()

    # ---- layout ---------------------------------------------------------
    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 22, 24, 18)
        outer.setSpacing(14)

        is_docs = self._mode == PickerMode.DOCS

        title = QLabel("Add documents to stage" if is_docs else "Add emails to stage")
        f = title.font()
        f.setPointSize(14)
        f.setBold(True)
        title.setFont(f)
        outer.addWidget(title)

        subtitle = QLabel(
            "Tick one or more templates to attach. They'll be added in the "
            "order shown — you can detach and re-add to reorder."
        )
        subtitle.setStyleSheet("color: #5b6473;")
        subtitle.setWordWrap(True)
        outer.addWidget(subtitle)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.StyledPanel)
        scroll.setStyleSheet(
            "QScrollArea { background: #ffffff; border: 1px solid #d8dce3; "
            "border-radius: 6px; }"
        )

        list_widget = QWidget()
        list_layout = QVBoxLayout(list_widget)
        list_layout.setContentsMargins(14, 12, 14, 12)
        list_layout.setSpacing(6)

        if is_docs:
            doc_templates = list_doc_templates()
            if not doc_templates:
                self._add_empty_message(
                    list_layout,
                    "No document templates yet. Create one in Templates → Document templates.",
                )
            else:
                for t in doc_templates:
                    cb = QCheckBox(self._format_doc_label(t))
                    cb.toggled.connect(self._update_ok_enabled)
                    self._checkboxes[t.id] = cb
                    list_layout.addWidget(cb)
        else:
            email_templates = list_email_templates()
            if not email_templates:
                self._add_empty_message(
                    list_layout,
                    "No email templates yet. Create one in Templates → Email templates.",
                )
            else:
                for t in email_templates:
                    cb = QCheckBox(self._format_email_label(t))
                    cb.toggled.connect(self._update_ok_enabled)
                    self._checkboxes[t.id] = cb
                    list_layout.addWidget(cb)

        list_layout.addStretch(1)
        scroll.setWidget(list_widget)
        outer.addWidget(scroll, 1)

        # Wait-days field for emails only
        self.wait_spin: QSpinBox | None = None
        if not is_docs:
            wait_row = QHBoxLayout()
            wait_row.setSpacing(8)
            wait_label = QLabel("Wait days after stage entry:")
            wait_label.setStyleSheet("color: #5b6473;")
            self.wait_spin = QSpinBox()
            self.wait_spin.setRange(0, 365)
            self.wait_spin.setValue(0)
            self.wait_spin.setSuffix(" days")
            self.wait_spin.setFixedWidth(140)
            wait_row.addWidget(wait_label)
            wait_row.addWidget(self.wait_spin)
            wait_row.addStretch(1)
            wait_hint = QLabel("(applies to all selected emails in this batch)")
            wait_hint.setStyleSheet("color: #aab1bd; font-style: italic;")
            wait_row.addWidget(wait_hint)
            outer.addLayout(wait_row)

        # Buttons
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok
        )
        self.ok_btn = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.ok_btn.setText("Add")
        self.cancel_btn = self.buttons.button(QDialogButtonBox.StandardButton.Cancel)
        self.cancel_btn.setProperty("secondary", True)
        outer.addWidget(self.buttons)

    def _add_empty_message(self, layout: QVBoxLayout, text: str) -> None:
        empty = QLabel(text)
        empty.setStyleSheet("color: #aab1bd; font-style: italic;")
        empty.setWordWrap(True)
        layout.addWidget(empty)

    def _format_doc_label(self, t: DocTemplateRow) -> str:
        meta_bits: list[str] = []
        if t.page_size:
            meta_bits.append(t.page_size)
        if t.notary_required:
            meta_bits.append("notary")
        if t.doc_type:
            meta_bits.append(t.doc_type)
        meta = f"   [{' · '.join(meta_bits)}]" if meta_bits else ""
        return f"{t.name}{meta}"

    def _format_email_label(self, t: EmailTemplateRow) -> str:
        return f"{t.name}   [{t.purpose}]"

    # ---- signals --------------------------------------------------------
    def _wire(self) -> None:
        self.buttons.accepted.connect(self._on_accept)
        self.buttons.rejected.connect(self.reject)

    def _update_ok_enabled(self) -> None:
        n = sum(1 for cb in self._checkboxes.values() if cb.isChecked())
        self.ok_btn.setEnabled(n > 0)
        is_docs = self._mode == PickerMode.DOCS
        noun = "doc" if is_docs else "email"
        plural = "" if n == 1 else "s"
        self.ok_btn.setText(f"Add {n} {noun}{plural}" if n else "Add")

    def _on_accept(self) -> None:
        selected_ids = [tid for tid, cb in self._checkboxes.items() if cb.isChecked()]
        wait_days = self.wait_spin.value() if self.wait_spin is not None else 0
        self.result = TemplatePickerResult(
            template_ids=selected_ids,
            wait_days=wait_days,
        )
        self.accept()
