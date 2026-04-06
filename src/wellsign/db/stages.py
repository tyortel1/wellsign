"""Compute a 'stage' for a project based on its current data.

Stages roll up investor count, documents sent, signatures, payments, and the
close deadline into a single label that's useful for color-coding the
navigator tree and the dashboard.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum

from PySide6.QtGui import QColor

from wellsign.db.migrate import connect


class ProjectStage(str, Enum):
    SETUP    = "setup"      # no investors yet
    READY    = "ready"      # investors added, nothing sent
    SENDING  = "sending"    # at least one doc sent, not all signed
    CLOSING  = "closing"    # all signed, payments pending
    CLOSED   = "closed"     # all signed AND all paid
    OVERDUE  = "overdue"    # past close deadline with outstanding work


_STAGE_LABELS = {
    ProjectStage.SETUP:    "Setup",
    ProjectStage.READY:    "Ready to send",
    ProjectStage.SENDING:  "In progress",
    ProjectStage.CLOSING:  "Awaiting payments",
    ProjectStage.CLOSED:   "Closed",
    ProjectStage.OVERDUE:  "Overdue",
}

_STAGE_COLORS = {
    ProjectStage.SETUP:    QColor("#8a93a3"),  # cool grey
    ProjectStage.READY:    QColor("#1f6feb"),  # primary blue
    ProjectStage.SENDING:  QColor("#0a958e"),  # teal
    ProjectStage.CLOSING:  QColor("#d97706"),  # amber
    ProjectStage.CLOSED:   QColor("#1a7f37"),  # green
    ProjectStage.OVERDUE:  QColor("#d1242f"),  # red
}


@dataclass(frozen=True)
class StageInfo:
    stage: ProjectStage
    label: str
    color: QColor
    investors: int
    sent: int
    signed: int
    expected_payments: int
    received_payments: int


def compute_stage(project_id: str) -> StageInfo:
    with connect() as conn:
        investors = conn.execute(
            "SELECT COUNT(*) FROM investors WHERE project_id = ?",
            (project_id,),
        ).fetchone()[0]

        sent = conn.execute(
            "SELECT COUNT(*) FROM investor_documents "
            " WHERE project_id = ? AND direction = 'sent'",
            (project_id,),
        ).fetchone()[0]

        signed = conn.execute(
            "SELECT COUNT(*) FROM investor_documents "
            " WHERE project_id = ? AND status = 'signed'",
            (project_id,),
        ).fetchone()[0]

        expected_payments = conn.execute(
            "SELECT COUNT(*) FROM payments WHERE project_id = ?",
            (project_id,),
        ).fetchone()[0]

        received_payments = conn.execute(
            "SELECT COUNT(*) FROM payments "
            " WHERE project_id = ? AND status IN ('received','partial')",
            (project_id,),
        ).fetchone()[0]

        deadline_row = conn.execute(
            "SELECT close_deadline, status FROM projects WHERE id = ?",
            (project_id,),
        ).fetchone()

    close_deadline = deadline_row["close_deadline"] if deadline_row else None
    explicit_status = deadline_row["status"] if deadline_row else None

    # Hard rules first
    if explicit_status == "closed":
        stage = ProjectStage.CLOSED
    elif investors == 0:
        stage = ProjectStage.SETUP
    elif sent == 0:
        stage = ProjectStage.READY
    elif signed < investors:
        stage = ProjectStage.SENDING
    elif expected_payments > 0 and received_payments < expected_payments:
        stage = ProjectStage.CLOSING
    else:
        stage = ProjectStage.CLOSED

    # Overdue overrides everything except CLOSED
    if stage != ProjectStage.CLOSED and close_deadline:
        try:
            deadline = date.fromisoformat(close_deadline[:10])
            if deadline < date.today():
                stage = ProjectStage.OVERDUE
        except ValueError:
            pass

    return StageInfo(
        stage=stage,
        label=_STAGE_LABELS[stage],
        color=_STAGE_COLORS[stage],
        investors=investors,
        sent=sent,
        signed=signed,
        expected_payments=expected_payments,
        received_payments=received_payments,
    )
