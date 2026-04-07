"""Workflows page — view and edit a single workflow's ordered stages.

Stage cards live in a QListWidget with InternalMove drag-drop so reordering
is just a matter of dragging the cards. Each card is a custom QFrame widget
showing the stage name, SLA, exit condition, and assigned doc/email templates.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from wellsign.ui.pages.workflow_visual import WorkflowVisualWidget


# ===========================================================================
# _TemplateChip — click-body-to-edit, click-✕-to-remove
# ===========================================================================
class _TemplateChip(QFrame):
    """A rounded chip with a text label + a small ✕ button.

    ``on_edit`` fires when the operator clicks the text (or double-clicks).
    ``on_remove`` fires when the operator clicks the ✕. The two actions are
    physically separated so a stray click can't drop a binding.
    """

    def __init__(
        self,
        text: str,
        on_edit,
        on_remove,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._on_edit = on_edit
        self._on_remove = on_remove

        self.setObjectName("TemplateChip")
        self.setStyleSheet(
            "QFrame#TemplateChip { background: #f0f3fa; border: 1px solid #d8dce3; "
            "border-radius: 12px; }"
            "QFrame#TemplateChip:hover { background: #e2ecff; border-color: #b6c7ea; }"
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 2, 4, 2)
        layout.setSpacing(4)

        self._label = QLabel(text)
        self._label.setStyleSheet("background: transparent; border: none; color: #1f2430;")
        self._label.setCursor(Qt.CursorShape.PointingHandCursor)
        self._label.setToolTip("Click to edit this template")
        # Clicking the text opens the editor
        self._label.mousePressEvent = lambda _evt: self._fire_edit()  # type: ignore[assignment]
        layout.addWidget(self._label)

        self._remove_btn = QPushButton("✕")
        self._remove_btn.setFlat(True)
        self._remove_btn.setFixedSize(20, 20)
        self._remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._remove_btn.setStyleSheet(
            "QPushButton { background: transparent; border: none; color: #8a93a3; "
            "font-weight: bold; }"
            "QPushButton:hover { color: #d1242f; }"
        )
        self._remove_btn.setToolTip("Remove this binding")
        self._remove_btn.clicked.connect(self._fire_remove)
        layout.addWidget(self._remove_btn)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802 - Qt override
        self._fire_edit()

    def _fire_edit(self) -> None:
        try:
            self._on_edit()
        except Exception:
            pass

    def _fire_remove(self) -> None:
        try:
            self._on_remove()
        except Exception:
            pass

from wellsign.db.templates import get_doc_template, get_email_template
from wellsign.db.workflows import (
    EXIT_LABELS,
    ExitCondition,
    StageRow,
    WorkflowRow,
    attach_doc_to_stage,
    attach_email_to_stage,
    delete_stage,
    delete_workflow,
    detach_doc_from_stage,
    detach_email_from_stage,
    get_workflow,
    insert_stage,
    insert_workflow,
    list_stages,
    list_workflows,
    reorder_stages,
    update_stage,
)
from wellsign.ui.dialogs import (
    NewDocTemplateDialog,
    NewEmailTemplateDialog,
    PickerMode,
    TemplatePickerDialog,
)
from wellsign.ui.dialogs.help_dialog import HelpButton


# ===========================================================================
# StageCard — one row inside the QListWidget
# ===========================================================================
class StageCard(QFrame):
    changed = Signal()  # emitted on any persisted edit so the page can refresh

    def __init__(self, stage: StageRow, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._stage = stage
        self.setObjectName("StageCard")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(
            "QFrame#StageCard { background: #ffffff; border: 1px solid #d8dce3; "
            "border-radius: 8px; }"
        )
        self._build()

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 14, 16, 14)
        outer.setSpacing(10)

        # Header row: drag handle + title + SLA + exit + delete
        header = QHBoxLayout()
        header.setSpacing(10)

        handle = QLabel("⋮⋮")
        handle.setStyleSheet("color: #aab1bd; font-size: 16pt; font-weight: 700;")
        handle.setToolTip("Drag to reorder")
        handle.setFixedWidth(18)
        header.addWidget(handle)

        title = QLabel(f"<b style='font-size:12pt;'>Stage {self._stage.stage_order + 1}: "
                       f"{self._stage.name}</b>")
        header.addWidget(title)
        header.addStretch(1)

        sla_lbl = QLabel("SLA:")
        sla_lbl.setStyleSheet("color: #5b6473;")
        header.addWidget(sla_lbl)

        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(0, 365)
        self.duration_spin.setValue(self._stage.duration_days or 0)
        self.duration_spin.setSuffix(" days")
        self.duration_spin.setFixedWidth(110)
        self.duration_spin.valueChanged.connect(self._on_field_changed)
        header.addWidget(self.duration_spin)

        exit_lbl = QLabel("Exit:")
        exit_lbl.setStyleSheet("color: #5b6473;")
        header.addWidget(exit_lbl)

        self.exit_combo = QComboBox()
        for code in [c.value for c in ExitCondition]:
            self.exit_combo.addItem(EXIT_LABELS[code], userData=code)
        idx = self.exit_combo.findData(self._stage.exit_condition)
        if idx >= 0:
            self.exit_combo.setCurrentIndex(idx)
        self.exit_combo.currentIndexChanged.connect(self._on_field_changed)
        self.exit_combo.setFixedWidth(240)
        header.addWidget(self.exit_combo)

        self.delete_btn = QPushButton("✕")
        self.delete_btn.setProperty("secondary", True)
        self.delete_btn.setFixedWidth(32)
        self.delete_btn.setToolTip("Delete this stage")
        self.delete_btn.clicked.connect(self._on_delete)
        header.addWidget(self.delete_btn)

        outer.addLayout(header)

        # Docs row
        docs_row = QHBoxLayout()
        docs_row.setSpacing(8)
        docs_label = QLabel("📄 Docs:")
        docs_label.setStyleSheet("color: #5b6473; font-weight: 600;")
        docs_label.setFixedWidth(70)
        docs_row.addWidget(docs_label)

        if self._stage.docs:
            for d in self._stage.docs:
                chip = _TemplateChip(
                    d.doc_template_name,
                    on_edit=lambda _tid=d.doc_template_id: self._on_edit_doc(_tid),
                    on_remove=lambda _id=d.id: self._on_remove_doc(_id),
                )
                docs_row.addWidget(chip)
        else:
            empty = QLabel("(none)")
            empty.setStyleSheet("color: #aab1bd; font-style: italic;")
            docs_row.addWidget(empty)

        docs_row.addStretch(1)
        add_doc_btn = QPushButton("+ Add doc")
        add_doc_btn.setProperty("secondary", True)
        add_doc_btn.clicked.connect(self._on_add_doc)
        docs_row.addWidget(add_doc_btn)
        outer.addLayout(docs_row)

        # Emails row
        emails_row = QHBoxLayout()
        emails_row.setSpacing(8)
        emails_label = QLabel("✉️ Emails:")
        emails_label.setStyleSheet("color: #5b6473; font-weight: 600;")
        emails_label.setFixedWidth(70)
        emails_row.addWidget(emails_label)

        if self._stage.emails:
            for e in self._stage.emails:
                wait_text = f"  (wait {e.wait_days}d)" if e.wait_days else "  (immediate)"
                chip = _TemplateChip(
                    e.email_template_name + wait_text,
                    on_edit=lambda _tid=e.email_template_id: self._on_edit_email(_tid),
                    on_remove=lambda _id=e.id: self._on_remove_email(_id),
                )
                emails_row.addWidget(chip)
        else:
            empty = QLabel("(none)")
            empty.setStyleSheet("color: #aab1bd; font-style: italic;")
            emails_row.addWidget(empty)

        emails_row.addStretch(1)
        add_email_btn = QPushButton("+ Add email")
        add_email_btn.setProperty("secondary", True)
        add_email_btn.clicked.connect(self._on_add_email)
        emails_row.addWidget(add_email_btn)
        outer.addLayout(emails_row)

    @property
    def stage(self) -> StageRow:
        return self._stage

    def _on_edit_doc(self, template_id: str) -> None:
        """Open the doc template editor for the template bound to this chip."""
        tpl = get_doc_template(template_id)
        if tpl is None:
            QMessageBox.warning(
                self, "Template missing",
                "This document template no longer exists. Remove the binding.",
            )
            return
        dlg = NewDocTemplateDialog(self, existing=tpl)
        if dlg.exec():
            self.changed.emit()

    def _on_edit_email(self, template_id: str) -> None:
        """Open the email template editor for the template bound to this chip."""
        tpl = get_email_template(template_id)
        if tpl is None:
            QMessageBox.warning(
                self, "Template missing",
                "This email template no longer exists. Remove the binding.",
            )
            return
        dlg = NewEmailTemplateDialog(self, existing=tpl)
        if dlg.exec():
            self.changed.emit()

    def _on_field_changed(self) -> None:
        update_stage(
            self._stage.id,
            name=self._stage.name,
            duration_days=self.duration_spin.value() or None,
            exit_condition=self.exit_combo.currentData(),
            description=self._stage.description or "",
        )
        self.changed.emit()

    def _on_delete(self) -> None:
        ans = QMessageBox.question(
            self,
            "Delete stage",
            f"Delete stage '{self._stage.name}'? This cannot be undone.",
        )
        if ans != QMessageBox.StandardButton.Yes:
            return
        delete_stage(self._stage.id)
        self.changed.emit()

    def _on_add_doc(self) -> None:
        dlg = TemplatePickerDialog(self, mode=PickerMode.DOCS)
        if dlg.exec() and dlg.result is not None:
            for tid in dlg.result.template_ids:
                attach_doc_to_stage(self._stage.id, tid)
            self.changed.emit()

    def _on_remove_doc(self, item_id: str) -> None:
        ans = QMessageBox.question(
            self, "Remove doc binding",
            "Remove this document from the stage? The template itself is not deleted.",
        )
        if ans != QMessageBox.StandardButton.Yes:
            return
        detach_doc_from_stage(item_id)
        self.changed.emit()

    def _on_add_email(self) -> None:
        dlg = TemplatePickerDialog(self, mode=PickerMode.EMAILS)
        if dlg.exec() and dlg.result is not None:
            for tid in dlg.result.template_ids:
                attach_email_to_stage(
                    self._stage.id, tid, wait_days=dlg.result.wait_days
                )
            self.changed.emit()

    def _on_remove_email(self, item_id: str) -> None:
        ans = QMessageBox.question(
            self, "Remove email binding",
            "Remove this email from the stage? The template itself is not deleted.",
        )
        if ans != QMessageBox.StandardButton.Yes:
            return
        detach_email_from_stage(item_id)
        self.changed.emit()


# ===========================================================================
# WorkflowsPage — main page widget
# ===========================================================================
class WorkflowsPage(QWidget):
    workflowCreated = Signal(str)  # workflow_id
    workflowDeleted = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._workflow: WorkflowRow | None = None
        self._build()
        self._load_first_workflow()

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 24, 28, 24)
        outer.setSpacing(14)

        # Header
        header = QHBoxLayout()
        self.title_label = QLabel("Workflows")
        f = self.title_label.font()
        f.setPointSize(18)
        f.setBold(True)
        self.title_label.setFont(f)
        header.addWidget(self.title_label)
        header.addStretch(1)

        self.new_workflow_btn = QPushButton("+ New Workflow")
        self.new_workflow_btn.clicked.connect(self._on_new_workflow)
        header.addWidget(self.new_workflow_btn)

        self.new_stage_btn = QPushButton("+ Add Stage")
        self.new_stage_btn.clicked.connect(self._on_add_stage)
        header.addWidget(self.new_stage_btn)

        self.delete_workflow_btn = QPushButton("Delete Workflow")
        self.delete_workflow_btn.setProperty("danger", True)
        self.delete_workflow_btn.clicked.connect(self._on_delete_workflow)
        header.addWidget(self.delete_workflow_btn)
        header.addWidget(HelpButton("workflows"))

        self.description_label = QLabel("")
        self.description_label.setStyleSheet("color: #5b6473;")
        self.description_label.setWordWrap(True)

        outer.addLayout(header)
        outer.addWidget(self.description_label)

        # Tab toggle: Edit / Visual
        self.view_tabs = QTabWidget()
        self.view_tabs.setDocumentMode(True)

        # --- Edit tab: current stages list (drag-drop, edit in place) -----
        edit_container = QWidget()
        edit_layout = QVBoxLayout(edit_container)
        edit_layout.setContentsMargins(0, 8, 0, 0)
        edit_layout.setSpacing(0)

        self.stages_list = QListWidget()
        self.stages_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.stages_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.stages_list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.stages_list.setSpacing(10)
        self.stages_list.setFrameShape(QFrame.Shape.NoFrame)
        self.stages_list.setStyleSheet(
            "QListWidget { background: #ffffff; border: none; padding: 8px 0 8px 0; }"
            "QListWidget::item { background: transparent; border: none; padding: 0; }"
            "QListWidget::item:selected { background: transparent; }"
        )
        self.stages_list.model().rowsMoved.connect(self._on_rows_moved)
        edit_layout.addWidget(self.stages_list, 1)

        # --- Visual tab: horizontal flowchart -----------------------------
        self.visual_widget = WorkflowVisualWidget()

        self.view_tabs.addTab(edit_container, "Edit")
        self.view_tabs.addTab(self.visual_widget, "Visual")

        outer.addWidget(self.view_tabs, 1)

    # -- public api -----------------------------------------------------
    def show_workflow(self, workflow_id: str) -> None:
        self._workflow = get_workflow(workflow_id)
        self._refresh()

    def _load_first_workflow(self) -> None:
        wfs = list_workflows()
        if wfs:
            self.show_workflow(wfs[0].id)

    # -- internals ------------------------------------------------------
    def _refresh(self) -> None:
        if self._workflow is None:
            self.title_label.setText("Workflows")
            self.description_label.setText(
                "No workflow selected. Click + New Workflow to create one."
            )
            self.stages_list.clear()
            self.visual_widget.show_workflow(None)
            self.new_stage_btn.setEnabled(False)
            self.delete_workflow_btn.setEnabled(False)
            return

        self.title_label.setText(self._workflow.name)
        self.description_label.setText(self._workflow.description or "")
        self.new_stage_btn.setEnabled(True)
        self.delete_workflow_btn.setEnabled(True)

        self.stages_list.clear()
        for stage in list_stages(self._workflow.id):
            self._append_stage(stage)

        self.visual_widget.show_workflow(self._workflow.id)

    def _on_new_workflow(self) -> None:
        name, ok = QInputDialog.getText(
            self, "New workflow", "Workflow name:", text="My new workflow"
        )
        if not ok or not name.strip():
            return
        description, ok2 = QInputDialog.getText(
            self,
            "Description",
            "Optional one-line description:",
            text="",
        )
        if not ok2:
            description = ""
        new_wf = insert_workflow(name=name.strip(), description=description.strip())
        self.show_workflow(new_wf.id)
        self.workflowCreated.emit(new_wf.id)

    def _on_delete_workflow(self) -> None:
        if self._workflow is None:
            return
        ans = QMessageBox.question(
            self,
            "Delete workflow",
            f"Delete workflow '{self._workflow.name}' and all of its stages? "
            f"This cannot be undone.",
        )
        if ans != QMessageBox.StandardButton.Yes:
            return
        delete_workflow(self._workflow.id)
        self._workflow = None
        self._load_first_workflow()
        if self._workflow is None:
            self._refresh()
        self.workflowDeleted.emit()

    def _append_stage(self, stage: StageRow) -> None:
        item = QListWidgetItem()
        item.setData(Qt.ItemDataRole.UserRole, stage.id)
        card = StageCard(stage)
        card.changed.connect(self._refresh)
        item.setSizeHint(QSize(0, card.sizeHint().height() + 8))
        self.stages_list.addItem(item)
        self.stages_list.setItemWidget(item, card)

    def _on_add_stage(self) -> None:
        if self._workflow is None:
            return
        name, ok = QInputDialog.getText(
            self, "New stage", "Stage name:", text="New stage"
        )
        if not ok or not name.strip():
            return
        insert_stage(workflow_id=self._workflow.id, name=name.strip(), duration_days=14)
        self._refresh()

    def _on_rows_moved(self, *_args) -> None:
        if self._workflow is None:
            return
        ordered_ids: list[str] = []
        for row in range(self.stages_list.count()):
            item = self.stages_list.item(row)
            sid = item.data(Qt.ItemDataRole.UserRole)
            if sid:
                ordered_ids.append(sid)
        reorder_stages(self._workflow.id, ordered_ids)
        # Re-render so the "Stage N:" prefixes update
        self._refresh()
