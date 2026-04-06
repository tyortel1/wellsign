"""New Document Template dialog — pick a PDF, name it, save to global library."""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from wellsign.app_paths import global_templates_dir
from wellsign.db.templates import DocTemplateRow, insert_doc_template, update_doc_template
from wellsign.pdf_.fields import page_count, read_form_fields

DOC_TYPES = [
    ("joa",          "Joint Operating Agreement"),
    ("pa",           "Participation Agreement"),
    ("cash_call_c1", "Cash Call C-1 (LLG → Decker)"),
    ("cash_call_c2", "Cash Call C-2 (DHC → Paloma)"),
    ("info_sheet",   "Investor Info Sheet"),
    ("w9",           "W-9"),
    ("wiring",       "Wiring Instructions"),
    ("other",        "Other"),
]

PAGE_SIZES = ["letter", "legal"]


class NewDocTemplateDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None = None,
        existing: DocTemplateRow | None = None,
    ) -> None:
        super().__init__(parent)
        self._editing = existing
        title = "Edit Document Template" if existing else "New Document Template"
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(600)

        self._picked_pdf: Path | None = None
        self._created: DocTemplateRow | None = None

        self._build()
        self._wire()
        if existing is not None:
            self._prefill_from(existing)
        self._update_save_enabled()

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 22, 24, 18)
        outer.setSpacing(14)

        title = QLabel("Edit document template" if self._editing else "New document template")
        f = title.font()
        f.setPointSize(14)
        f.setBold(True)
        title.setFont(f)

        subtitle = QLabel(
            "Pick a blank PDF that already has form fields. WellSign will read "
            "the field names so you can map them to merge variables later."
        )
        subtitle.setStyleSheet("color: #5b6473;")
        subtitle.setWordWrap(True)

        form = QFormLayout()
        form.setVerticalSpacing(10)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g. Paloma Cash Call C-1")

        self.type_combo = QComboBox()
        for code, label in DOC_TYPES:
            self.type_combo.addItem(label, userData=code)

        self.size_combo = QComboBox()
        self.size_combo.addItems(PAGE_SIZES)

        self.notary_check = QCheckBox("Requires notarisation")

        # File row
        file_row = QHBoxLayout()
        self.file_edit = QLineEdit()
        self.file_edit.setReadOnly(True)
        self.file_edit.setPlaceholderText("No PDF selected")
        self.browse_btn = QPushButton("Browse…")
        self.browse_btn.setProperty("secondary", True)
        file_row.addWidget(self.file_edit, 1)
        file_row.addWidget(self.browse_btn)

        form.addRow("Template name:", self.name_edit)
        form.addRow("Document type:", self.type_combo)
        form.addRow("Page size:", self.size_combo)
        form.addRow("", self.notary_check)
        form.addRow("PDF file:", file_row)

        # Detected fields preview
        fields_label = QLabel("Detected form fields:")
        fields_label.setStyleSheet("color: #5b6473; font-weight: 600;")
        self.fields_list = QListWidget()
        self.fields_list.setMaximumHeight(140)

        outer.addWidget(title)
        outer.addWidget(subtitle)
        outer.addSpacing(4)
        outer.addLayout(form)
        outer.addWidget(fields_label)
        outer.addWidget(self.fields_list)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save
        )
        self.save_btn = self.buttons.button(QDialogButtonBox.StandardButton.Save)
        self.save_btn.setText("Save Changes" if self._editing else "Save Template")
        self.cancel_btn = self.buttons.button(QDialogButtonBox.StandardButton.Cancel)
        self.cancel_btn.setProperty("secondary", True)
        outer.addWidget(self.buttons)

    def _wire(self) -> None:
        self.browse_btn.clicked.connect(self._on_browse)
        self.name_edit.textChanged.connect(self._update_save_enabled)
        self.buttons.accepted.connect(self._on_save)
        self.buttons.rejected.connect(self.reject)

    def _on_browse(self) -> None:
        path_str, _ = QFileDialog.getOpenFileName(
            self, "Select Template PDF", str(Path.cwd()), "PDF (*.pdf)"
        )
        if not path_str:
            return
        path = Path(path_str)
        self._picked_pdf = path
        self.file_edit.setText(str(path))
        self.fields_list.clear()
        try:
            fields = read_form_fields(path)
            pages = page_count(path)
            if not fields:
                self.fields_list.addItem(
                    f"(No form fields detected — {pages} page{'s' if pages != 1 else ''}.)"
                )
            else:
                for f in fields:
                    self.fields_list.addItem(f"{f.name}    [{f.field_type}]")
        except Exception as e:
            self.fields_list.addItem(f"(Could not read PDF: {e})")
        if not self.name_edit.text().strip():
            self.name_edit.setText(path.stem.replace("_", " ").replace("-", " ").title())
        self._update_save_enabled()

    def _prefill_from(self, t: DocTemplateRow) -> None:
        self.name_edit.setText(t.name)
        for i in range(self.type_combo.count()):
            if self.type_combo.itemData(i) == t.doc_type:
                self.type_combo.setCurrentIndex(i)
                break
        if t.page_size and t.page_size in PAGE_SIZES:
            self.size_combo.setCurrentText(t.page_size)
        self.notary_check.setChecked(t.notary_required)
        self.file_edit.setText(t.storage_path or "(none — pick a PDF to attach)")
        self.fields_list.clear()
        self.fields_list.addItem("(Existing PDF unchanged — pick a new file to replace.)")

    def _update_save_enabled(self) -> None:
        # In edit mode the existing PDF is acceptable; only require name.
        if self._editing is not None:
            ok = bool(self.name_edit.text().strip())
        else:
            ok = bool(self.name_edit.text().strip()) and self._picked_pdf is not None
        self.save_btn.setEnabled(ok)

    def _on_save(self) -> None:
        # Decide whether to keep the existing PDF or copy a new one in.
        if self._picked_pdf is not None:
            new_id = str(uuid.uuid4())
            dest = global_templates_dir() / f"{new_id}.pdf"
            shutil.copy2(self._picked_pdf, dest)
            storage_path = str(dest)
        elif self._editing is not None:
            storage_path = self._editing.storage_path
        else:
            return  # shouldn't happen — guarded by save-enabled

        if self._editing is not None:
            self._created = update_doc_template(
                self._editing.id,
                name=self.name_edit.text().strip(),
                doc_type=self.type_combo.currentData(),
                storage_path=storage_path,
                page_size=self.size_combo.currentText(),
                notary_required=self.notary_check.isChecked(),
            )
        else:
            self._created = insert_doc_template(
                name=self.name_edit.text().strip(),
                doc_type=self.type_combo.currentData(),
                storage_path=storage_path,
                page_size=self.size_combo.currentText(),
                notary_required=self.notary_check.isChecked(),
                is_global=True,
            )
        self.accept()

    @property
    def created_template(self) -> DocTemplateRow | None:
        return self._created
