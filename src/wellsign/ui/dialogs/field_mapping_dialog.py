"""Field-mapping editor.

Two columns:
  * left:  every AcroForm text field discovered in the template's PDF
  * right: every system merge variable from ``pdf_/merge_vars``

The operator picks a row on the left, then double-clicks (or hits 'Bind →')
on the right to assign that merge variable to the field. The current binding
is shown inline next to each PDF field. Clear-binding is one keystroke.

On Save the resulting ``{pdf_field: merge_key}`` map is persisted to
``document_templates.field_mapping`` (JSON).
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from wellsign.db.templates import DocTemplateRow, update_doc_template_mapping
from wellsign.pdf_.fields import read_form_fields
from wellsign.pdf_.merge_vars import grouped as grouped_vars

_BINDING_ROLE = Qt.ItemDataRole.UserRole + 1
_FIELD_NAME_ROLE = Qt.ItemDataRole.UserRole + 2
_VAR_KEY_ROLE = Qt.ItemDataRole.UserRole + 3


class FieldMappingDialog(QDialog):
    """Edit a single document template's PDF-field-to-variable mapping."""

    def __init__(
        self,
        template: DocTemplateRow,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._template = template
        self._mapping: dict[str, str] = dict(template.field_mapping or {})
        self._saved: bool = False

        self.setWindowTitle(f"Map fields — {template.name}")
        self.setModal(True)
        self.setMinimumSize(880, 560)

        self._build()
        self._load_pdf_fields()
        self._load_merge_vars()

    # -------------------------------------------------------------- layout
    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 18, 20, 16)
        outer.setSpacing(12)

        title = QLabel(f"<b style='font-size:14pt;'>{self._template.name}</b>")
        outer.addWidget(title)

        sub = QLabel(
            "Bind each PDF form field to a system merge variable. "
            "When you generate a packet for an investor, WellSign substitutes "
            "the right value into each field."
        )
        sub.setStyleSheet("color: #5b6473;")
        sub.setWordWrap(True)
        outer.addWidget(sub)

        body = QHBoxLayout()
        body.setSpacing(14)

        # Left: PDF fields
        left = QVBoxLayout()
        left.setSpacing(6)
        left_title = QLabel("PDF form fields")
        lf = left_title.font()
        lf.setBold(True)
        left_title.setFont(lf)
        left.addWidget(left_title)

        self.fields_tree = QTreeWidget()
        self.fields_tree.setColumnCount(2)
        self.fields_tree.setHeaderLabels(["PDF field", "Bound variable"])
        self.fields_tree.setRootIsDecorated(False)
        self.fields_tree.setUniformRowHeights(True)
        self.fields_tree.setAlternatingRowColors(True)
        h = self.fields_tree.header()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        left.addWidget(self.fields_tree, 1)

        clear_row = QHBoxLayout()
        self.clear_btn = QPushButton("Clear binding")
        self.clear_btn.setProperty("secondary", True)
        self.clear_btn.clicked.connect(self._on_clear)
        clear_row.addWidget(self.clear_btn)
        clear_row.addStretch(1)
        left.addLayout(clear_row)

        # Right: merge variables
        right = QVBoxLayout()
        right.setSpacing(6)
        right_title = QLabel("System merge variables")
        rf = right_title.font()
        rf.setBold(True)
        right_title.setFont(rf)
        right.addWidget(right_title)

        self.vars_tree = QTreeWidget()
        self.vars_tree.setColumnCount(2)
        self.vars_tree.setHeaderLabels(["Variable", "Description"])
        h2 = self.vars_tree.header()
        h2.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        h2.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.vars_tree.itemDoubleClicked.connect(self._on_var_double_click)
        right.addWidget(self.vars_tree, 1)

        bind_row = QHBoxLayout()
        self.bind_btn = QPushButton("Bind →")
        self.bind_btn.clicked.connect(self._on_bind)
        bind_row.addWidget(self.bind_btn)
        bind_row.addStretch(1)
        right.addLayout(bind_row)

        body.addLayout(left, 1)
        body.addLayout(right, 1)
        outer.addLayout(body, 1)

        # Buttons
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save
        )
        save = self.buttons.button(QDialogButtonBox.StandardButton.Save)
        save.setText("Save Mapping")
        cancel = self.buttons.button(QDialogButtonBox.StandardButton.Cancel)
        cancel.setProperty("secondary", True)
        self.buttons.accepted.connect(self._on_save)
        self.buttons.rejected.connect(self.reject)
        outer.addWidget(self.buttons)

    # -------------------------------------------------------------- loading
    def _load_pdf_fields(self) -> None:
        path = Path(self._template.storage_path or "")
        self.fields_tree.clear()
        if not path.exists():
            placeholder = QTreeWidgetItem(["(template PDF not on disk)", ""])
            placeholder.setDisabled(True)
            self.fields_tree.addTopLevelItem(placeholder)
            return
        try:
            fields = read_form_fields(path)
        except Exception as e:
            placeholder = QTreeWidgetItem([f"(failed to read PDF: {e})", ""])
            placeholder.setDisabled(True)
            self.fields_tree.addTopLevelItem(placeholder)
            return

        if not fields:
            placeholder = QTreeWidgetItem(["(no AcroForm fields found)", ""])
            placeholder.setDisabled(True)
            self.fields_tree.addTopLevelItem(placeholder)
            return

        for f in fields:
            bound = self._mapping.get(f.name, "")
            item = QTreeWidgetItem([f.name, bound or "—"])
            item.setData(0, _FIELD_NAME_ROLE, f.name)
            item.setData(0, _BINDING_ROLE, bound)
            if bound:
                item.setForeground(1, Qt.GlobalColor.darkGreen)
            self.fields_tree.addTopLevelItem(item)
        self.fields_tree.setCurrentItem(self.fields_tree.topLevelItem(0))

    def _load_merge_vars(self) -> None:
        self.vars_tree.clear()
        for group_name, vars_in_group in grouped_vars().items():
            group_item = QTreeWidgetItem([group_name, ""])
            font = group_item.font(0)
            font.setBold(True)
            group_item.setFont(0, font)
            self.vars_tree.addTopLevelItem(group_item)
            for var in vars_in_group:
                child = QTreeWidgetItem([var.key, var.label])
                child.setData(0, _VAR_KEY_ROLE, var.key)
                group_item.addChild(child)
            group_item.setExpanded(True)

    # -------------------------------------------------------------- actions
    def _selected_field_item(self) -> QTreeWidgetItem | None:
        item = self.fields_tree.currentItem()
        if item is None or item.isDisabled():
            return None
        return item

    def _selected_var_key(self) -> str | None:
        item = self.vars_tree.currentItem()
        if item is None:
            return None
        return item.data(0, _VAR_KEY_ROLE)

    def _on_bind(self) -> None:
        field_item = self._selected_field_item()
        var_key = self._selected_var_key()
        if field_item is None:
            QMessageBox.information(self, "No field", "Select a PDF field on the left first.")
            return
        if not var_key:
            QMessageBox.information(self, "No variable", "Pick a variable (not a section header) on the right.")
            return
        self._apply_binding(field_item, var_key)

    def _on_var_double_click(self, item: QTreeWidgetItem, _column: int) -> None:
        var_key = item.data(0, _VAR_KEY_ROLE)
        if not var_key:
            return
        field_item = self._selected_field_item()
        if field_item is None:
            return
        self._apply_binding(field_item, var_key)

    def _apply_binding(self, field_item: QTreeWidgetItem, var_key: str) -> None:
        field_name = field_item.data(0, _FIELD_NAME_ROLE)
        if not field_name:
            return
        self._mapping[field_name] = var_key
        field_item.setText(1, var_key)
        field_item.setData(0, _BINDING_ROLE, var_key)
        field_item.setForeground(1, Qt.GlobalColor.darkGreen)
        # Advance selection so the operator can keep clicking
        idx = self.fields_tree.indexOfTopLevelItem(field_item)
        if idx + 1 < self.fields_tree.topLevelItemCount():
            self.fields_tree.setCurrentItem(self.fields_tree.topLevelItem(idx + 1))

    def _on_clear(self) -> None:
        field_item = self._selected_field_item()
        if field_item is None:
            return
        field_name = field_item.data(0, _FIELD_NAME_ROLE)
        if not field_name:
            return
        self._mapping.pop(field_name, None)
        field_item.setText(1, "—")
        field_item.setData(0, _BINDING_ROLE, "")
        field_item.setForeground(1, Qt.GlobalColor.gray)

    def _on_save(self) -> None:
        update_doc_template_mapping(self._template.id, self._mapping)
        self._saved = True
        self.accept()

    @property
    def saved(self) -> bool:
        return self._saved
