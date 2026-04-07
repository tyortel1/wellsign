"""Send tab — pending email queue for the active project.

Shows every email that's due (or about to be due) to go out for every
investor in the project based on the active stage's email templates and
each investor's ``entered_at + wait_days``. Subject + body are rendered
through the merge-variable system before display, so the operator sees
real values, not ``{{template}}`` placeholders.

Buttons:
  * **Mark as Sent** — log the email as sent without going through Outlook
    (for emails the operator already sent manually outside the app)
  * **Send via Outlook** — open the operator's local Outlook via COM,
    build a MailItem with the rendered subject/body and the investor's
    generated PDFs attached, save to Drafts (or send if configured), and
    write a send_events row.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from wellsign.db.investor_documents import list_for_investor
from wellsign.db.projects import ProjectRow
from wellsign.db.send_events import insert_send_event
from wellsign.db.workflows import PendingSend, compute_pending_sends
from wellsign.email_.sender import build_mail_item, outlook_available
from wellsign.ui.dialogs.help_dialog import HelpButton

_HEADERS = ["", "Investor", "Stage", "Email Template", "Due", "Status"]

_STATUS_COLOR = {
    "overdue":  QColor("#d1242f"),
    "due":      QColor("#d97706"),
    "upcoming": QColor("#5b6473"),
}

_STATUS_LABEL = {
    "overdue":  "Overdue",
    "due":      "Due",
    "upcoming": "Upcoming",
}


class SendTab(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._project: ProjectRow | None = None
        self._pending: list[PendingSend] = []
        self._build()

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 24, 28, 24)
        outer.setSpacing(14)

        # Header
        header = QHBoxLayout()
        title = QLabel("Send")
        f = title.font()
        f.setPointSize(18)
        f.setBold(True)
        title.setFont(f)
        header.addWidget(title)
        header.addStretch(1)

        self.mark_sent_btn = QPushButton("Mark as Sent")
        self.mark_sent_btn.setProperty("secondary", True)
        self.mark_sent_btn.setEnabled(False)
        self.mark_sent_btn.clicked.connect(self._on_mark_sent)
        header.addWidget(self.mark_sent_btn)

        self.send_outlook_btn = QPushButton("Send via Outlook")
        self.send_outlook_btn.setEnabled(False)
        if outlook_available():
            self.send_outlook_btn.setToolTip(
                "Open Outlook with this email + the investor's generated PDFs "
                "attached. Saves to Drafts so you can review before sending."
            )
        else:
            self.send_outlook_btn.setToolTip(
                "Outlook COM is unavailable on this machine (pywin32 not installed "
                "or Outlook not present). Use 'Mark as Sent' to log manually."
            )
        self.send_outlook_btn.clicked.connect(self._on_send_outlook)
        header.addWidget(self.send_outlook_btn)
        header.addWidget(HelpButton("send"))

        subtitle = QLabel(
            "Every email that's due to go out to this project's investors based on the "
            "active workflow stage and how long each investor has been in that stage. "
            "Select a row to preview the rendered email body on the right."
        )
        subtitle.setStyleSheet("color: #5b6473;")
        subtitle.setWordWrap(True)

        # Splitter — left: queue table, right: preview
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)

        # Queue table
        self.table = QTableWidget(0, len(_HEADERS))
        self.table.setHorizontalHeaderLabels(_HEADERS)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.itemSelectionChanged.connect(self._on_row_changed)
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        splitter.addWidget(self.table)

        # Preview pane
        preview_container = QWidget()
        preview_layout = QVBoxLayout(preview_container)
        preview_layout.setContentsMargins(12, 0, 0, 0)
        preview_layout.setSpacing(6)
        preview_title = QLabel("Preview")
        preview_title.setStyleSheet("color: #5b6473; font-weight: 600;")
        preview_layout.addWidget(preview_title)
        self.subject_label = QLabel("(Select an email to preview)")
        self.subject_label.setStyleSheet("color: #1f2430; font-weight: 600;")
        self.subject_label.setWordWrap(True)
        preview_layout.addWidget(self.subject_label)
        self.preview = QTextBrowser()
        self.preview.setOpenExternalLinks(False)
        preview_layout.addWidget(self.preview, 1)
        splitter.addWidget(preview_container)

        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([800, 400])

        self.summary_label = QLabel("")
        self.summary_label.setStyleSheet("color: #5b6473;")

        outer.addLayout(header)
        outer.addWidget(subtitle)
        outer.addWidget(self.summary_label)
        outer.addWidget(splitter, 1)

    # ---- public api ------------------------------------------------------
    def set_project(self, project: ProjectRow | None) -> None:
        self._project = project
        self.refresh()

    def refresh(self) -> None:
        self.table.setRowCount(0)
        if self._project is None:
            self.summary_label.setText("No project selected.")
            self._pending = []
            return

        self._pending = compute_pending_sends(self._project.id)
        self.table.setRowCount(len(self._pending))

        counts = {"overdue": 0, "due": 0, "upcoming": 0}
        for r, ps in enumerate(self._pending):
            counts[ps.status] += 1

            # Dot
            dot = QTableWidgetItem("●")
            dot.setForeground(QBrush(_STATUS_COLOR[ps.status]))
            dot.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            f = dot.font()
            f.setPointSize(14)
            f.setBold(True)
            dot.setFont(f)
            self.table.setItem(r, 0, dot)

            self.table.setItem(r, 1, QTableWidgetItem(ps.investor_name))
            self.table.setItem(r, 2, QTableWidgetItem(ps.stage_name))
            self.table.setItem(r, 3, QTableWidgetItem(ps.email_template_name))
            self.table.setItem(r, 4, QTableWidgetItem(ps.due_at[:10]))

            status_txt = _STATUS_LABEL[ps.status]
            if ps.status == "overdue" and ps.days_overdue > 0:
                status_txt = f"Overdue {ps.days_overdue}d"
            elif ps.status == "upcoming" and ps.days_overdue < 0:
                status_txt = f"Upcoming ({-ps.days_overdue}d)"
            status_item = QTableWidgetItem(status_txt)
            status_item.setForeground(QBrush(_STATUS_COLOR[ps.status]))
            self.table.setItem(r, 5, status_item)

        self.summary_label.setText(
            f"<span style='color:#d1242f;'><b>{counts['overdue']}</b> overdue</span>"
            f"  ·  "
            f"<span style='color:#d97706;'><b>{counts['due']}</b> due now</span>"
            f"  ·  "
            f"<span style='color:#5b6473;'><b>{counts['upcoming']}</b> upcoming</span>"
            f"  ·  <b>{len(self._pending)}</b> total"
        )

        self._on_row_changed()

    # ---- handlers --------------------------------------------------------
    def _selected_index(self) -> int | None:
        rows = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        if not rows:
            return None
        idx = rows[0].row()
        if 0 <= idx < len(self._pending):
            return idx
        return None

    def _on_row_changed(self) -> None:
        idx = self._selected_index()
        has = idx is not None
        self.mark_sent_btn.setEnabled(has)
        # Outlook button: enabled when a row is selected AND Outlook COM is reachable
        self.send_outlook_btn.setEnabled(has and outlook_available())
        if idx is None:
            self.subject_label.setText("(Select an email to preview)")
            self.preview.clear()
            return
        ps = self._pending[idx]
        self.subject_label.setText(ps.subject)
        self.preview.setHtml(ps.body_html)

    def _on_mark_sent(self) -> None:
        """Log the email as sent without touching Outlook.

        Use case: the operator already sent it manually (cold call follow-up
        from their phone, or before they had WellSign installed) and just wants
        to suppress it from the queue.
        """
        idx = self._selected_index()
        if idx is None or self._project is None:
            return
        ps = self._pending[idx]
        try:
            insert_send_event(
                project_id=self._project.id,
                investor_id=ps.investor_id,
                email_template_id=ps.email_template_id,
                subject=ps.subject,
                attached_doc_ids=None,
                success=True,
                error_message="manual mark — not sent through WellSign",
            )
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(
                self, "Could not log send",
                f"Failed to write send_events row:\n\n{e}",
            )
            return
        self.refresh()

    def _on_send_outlook(self) -> None:
        """Build an Outlook MailItem with the investor's PDFs attached and save it.

        Saves to Drafts (not Send) so the operator can review every email
        before it goes out — that's the whole point of using their own
        Outlook profile instead of an SMTP relay.
        """
        idx = self._selected_index()
        if idx is None or self._project is None:
            return
        ps = self._pending[idx]

        if not ps.investor_email:
            QMessageBox.warning(
                self, "No email address",
                f"{ps.investor_name} has no email address on file. "
                "Add one on the Investors tab and try again.",
            )
            return

        # Collect every generated PDF for this investor as attachments
        docs = list_for_investor(ps.investor_id)
        attachment_paths: list[Path] = []
        attached_doc_ids: list[str] = []
        for d in docs:
            if d.direction == "sent" and d.storage_path:
                p = Path(d.storage_path)
                if p.exists():
                    attachment_paths.append(p)
                    attached_doc_ids.append(d.id)

        result = build_mail_item(
            to=ps.investor_email,
            subject=ps.subject,
            body_html=ps.body_html,
            attachments=attachment_paths,
            send_immediately=False,
        )

        # Always log the attempt — success OR failure goes in send_events
        try:
            insert_send_event(
                project_id=self._project.id,
                investor_id=ps.investor_id,
                email_template_id=ps.email_template_id,
                subject=ps.subject,
                attached_doc_ids=attached_doc_ids,
                success=result.success,
                error_message=None if result.success else result.message,
            )
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(
                self, "Could not log send",
                f"Outlook reported: {result.message}\n\n"
                f"But the send_events row failed to write:\n{e}",
            )
            return

        if result.success:
            QMessageBox.information(
                self,
                "Outlook draft created",
                f"<b>{ps.investor_name}</b><br>{result.message}<br><br>"
                "Check the Outlook Drafts folder to review and send when ready.",
            )
            self.refresh()
        else:
            QMessageBox.warning(
                self,
                "Outlook send failed",
                f"<b>{ps.investor_name}</b><br>{result.message}<br><br>"
                "Logged as a failed attempt in the audit trail. The email was "
                "NOT removed from the pending queue.",
            )

    def refresh_summary_only(self) -> None:
        counts = {"overdue": 0, "due": 0, "upcoming": 0}
        for ps in self._pending:
            counts[ps.status] += 1
        self.summary_label.setText(
            f"<span style='color:#d1242f;'><b>{counts['overdue']}</b> overdue</span>"
            f"  ·  "
            f"<span style='color:#d97706;'><b>{counts['due']}</b> due now</span>"
            f"  ·  "
            f"<span style='color:#5b6473;'><b>{counts['upcoming']}</b> upcoming</span>"
            f"  ·  <b>{len(self._pending)}</b> total"
        )
