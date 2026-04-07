"""Documents tab — generate filled PDF packets for every investor."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from wellsign.app_paths import investor_dir
from wellsign.db.investor_documents import (
    delete_for_project,
    list_for_project,
    record_generated_document,
)
from wellsign.db.investors import list_investors
from wellsign.db.projects import ProjectRow
from wellsign.db.templates import list_doc_templates
from wellsign.pdf_.fill import (
    build_merge_context,
    fill_template,
    output_filename,
    resolve_field_values,
)
from wellsign.ui.dialogs.help_dialog import HelpButton

_HEADERS = ["Investor", "Doc type", "Template", "File", "Created"]
_PATH_ROLE = Qt.ItemDataRole.UserRole + 1


class DocumentsTab(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._project: ProjectRow | None = None
        self._build()

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 24, 28, 24)
        outer.setSpacing(14)

        header = QHBoxLayout()
        title = QLabel("Documents")
        f = title.font()
        f.setPointSize(18)
        f.setBold(True)
        title.setFont(f)
        header.addWidget(title)
        header.addStretch(1)

        self.regenerate_btn = QPushButton("Regenerate All")
        self.regenerate_btn.setProperty("secondary", True)
        self.regenerate_btn.setToolTip("Wipe and rebuild every packet for this project")
        self.regenerate_btn.clicked.connect(self._on_regenerate_all)
        self.generate_btn = QPushButton("+ Generate Packets")
        self.generate_btn.clicked.connect(self._on_generate)
        header.addWidget(self.regenerate_btn)
        header.addWidget(self.generate_btn)
        header.addWidget(HelpButton("documents"))

        self.summary_label = QLabel("No project selected.")
        self.summary_label.setStyleSheet("color: #5b6473;")

        self.table = QTableWidget(0, len(_HEADERS))
        self.table.setHorizontalHeaderLabels(_HEADERS)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.doubleClicked.connect(self._on_open_file)
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)

        outer.addLayout(header)
        outer.addWidget(self.summary_label)
        outer.addWidget(self.table, 1)

    # ----------------------------------------------------------------- API
    def set_project(self, project: ProjectRow | None) -> None:
        self._project = project
        self.refresh()

    def refresh(self) -> None:
        if self._project is None:
            self.table.setRowCount(0)
            self.summary_label.setText("No project selected.")
            return
        rows = list_for_project(self._project.id)
        self.table.setRowCount(len(rows))
        if not rows:
            self.summary_label.setText(
                "No packets generated yet. Click <b>+ Generate Packets</b> to build "
                "filled PDFs for every investor on this project."
            )
        else:
            self.summary_label.setText(
                f"<b>{len(rows)}</b> generated documents on disk for this project."
            )

        # Need investor display names
        investor_names = {i.id: i.display_name for i in list_investors(self._project.id)}
        # And template names
        template_names = {t.id: t.name for t in list_doc_templates()}

        for r, doc in enumerate(rows):
            template_id = doc.metadata.get("template_id", "")
            cells = [
                investor_names.get(doc.investor_id, "(unknown)"),
                doc.doc_type.replace("_", " ").upper(),
                template_names.get(template_id, doc.metadata.get("template_name", "—")),
                Path(doc.storage_path or "").name,
                (doc.created_at or "")[:19].replace("T", " "),
            ]
            for col, text in enumerate(cells):
                item = QTableWidgetItem(text)
                if col == 0 and doc.storage_path:
                    item.setData(_PATH_ROLE, doc.storage_path)
                self.table.setItem(r, col, item)

    # ----------------------------------------------------------- handlers
    def _on_generate(self) -> None:
        if self._project is None:
            return
        investors = list_investors(self._project.id)
        if not investors:
            QMessageBox.information(
                self, "No investors",
                "Add at least one investor on the Investors tab first.",
            )
            return
        templates = [t for t in list_doc_templates() if t.field_mapping]
        unmapped = [t for t in list_doc_templates() if not t.field_mapping]
        if not templates:
            QMessageBox.information(
                self, "No mapped templates",
                "No document templates have a field mapping yet. Open <b>Document "
                "Templates</b> in the navigator and click <b>Map Fields…</b> on a "
                "template to bind its PDF fields to merge variables.",
            )
            return

        warnings: list[str] = []
        if unmapped:
            warnings.append(
                f"{len(unmapped)} template(s) skipped — no field mapping: "
                + ", ".join(t.name for t in unmapped)
            )

        generated = 0
        errors = 0
        for inv in investors:
            ctx = build_merge_context(self._project, inv)
            for tpl in templates:
                template_path = Path(tpl.storage_path or "")
                if not template_path.exists():
                    warnings.append(f"{tpl.name}: template PDF not found on disk")
                    continue
                try:
                    field_values = resolve_field_values(tpl.field_mapping, ctx)
                    out_dir = investor_dir(self._project.id, inv.id) / "sent"
                    out_path = out_dir / output_filename(tpl)
                    fill_template(template_path, field_values, out_path)
                    record_generated_document(
                        project_id=self._project.id,
                        investor_id=inv.id,
                        doc_type=tpl.doc_type,
                        storage_path=str(out_path),
                        byte_size=out_path.stat().st_size,
                        metadata={
                            "template_id": tpl.id,
                            "template_name": tpl.name,
                        },
                    )
                    generated += 1
                except Exception as e:  # noqa: BLE001
                    errors += 1
                    warnings.append(f"{inv.display_name} / {tpl.name}: {e}")

        self.refresh()

        body_lines = [
            f"<b>{generated}</b> document(s) generated for "
            f"<b>{len(investors)}</b> investor(s) × "
            f"<b>{len(templates)}</b> template(s)."
        ]
        if errors:
            body_lines.append(f"<br><b>{errors}</b> error(s) — see details.")
        if warnings:
            body_lines.append("<br><br>" + "<br>".join(warnings[:20]))
            if len(warnings) > 20:
                body_lines.append(f"<br>... and {len(warnings) - 20} more.")

        QMessageBox.information(self, "Generation complete", "<br>".join(body_lines))

    def _on_regenerate_all(self) -> None:
        if self._project is None:
            return
        ans = QMessageBox.question(
            self,
            "Regenerate all?",
            "This will delete every generated document row for this project and "
            "rebuild them from scratch. Files on disk are NOT deleted, but new "
            "ones will be added alongside.\n\nProceed?",
        )
        if ans != QMessageBox.StandardButton.Yes:
            return
        delete_for_project(self._project.id)
        self.refresh()
        self._on_generate()

    def _on_open_file(self, index) -> None:
        item = self.table.item(index.row(), 0)
        if item is None:
            return
        path = item.data(_PATH_ROLE)
        if not path:
            return
        try:
            if sys.platform == "win32":
                os.startfile(path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.run(["open", path], check=False)
            else:
                subprocess.run(["xdg-open", path], check=False)
        except Exception:
            QMessageBox.warning(self, "Could not open file", f"{path}")
