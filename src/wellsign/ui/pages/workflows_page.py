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
    QVBoxLayout,
    QWidget,
)

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
from wellsign.ui.dialogs import PickerMode, TemplatePickerDialog


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
                chip = self._make_chip(
                    d.doc_template_name,
                    on_remove=lambda _evt=None, _id=d.id: self._on_remove_doc(_id),
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
                chip = self._make_chip(
                    e.email_template_name + wait_text,
                    on_remove=lambda _evt=None, _id=e.id: self._on_remove_email(_id),
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

    def _make_chip(self, text: str, on_remove) -> QLabel:
        chip = QLabel(f"  {text}  ✕  ")
        chip.setStyleSheet(
            "QLabel { background: #f0f3fa; color: #1f2430; border: 1px solid #d8dce3; "
            "border-radius: 12px; padding: 4px 4px; }"
            "QLabel:hover { background: #e2ecff; }"
        )
        chip.setCursor(Qt.CursorShape.PointingHandCursor)
        chip.mousePressEvent = lambda evt, cb=on_remove: cb(evt)  # type: ignore[assignment]
        return chip

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

        self.description_label = QLabel("")
        self.description_label.setStyleSheet("color: #5b6473;")
        self.description_label.setWordWrap(True)

        outer.addLayout(header)
        outer.addWidget(self.description_label)

        # Stages list
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

        outer.addWidget(self.stages_list, 1)

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
