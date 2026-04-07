"""Read/write access for the ``send_events`` table.

A row exists for every Outlook send (or 'mark as sent' event) so the
SendTab queue can suppress already-sent emails and the audit trail has a
record of what went out, when, and to whom. Send events are immutable
once written.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from wellsign.db.migrate import connect


@dataclass
class SendEventRow:
    id: str
    project_id: str
    investor_id: str
    email_template_id: str | None
    subject: str | None
    sent_at: str
    attached_doc_ids: list[str]
    success: bool
    error_message: str | None


def _row_to_event(row: sqlite3.Row) -> SendEventRow:
    raw = row["attached_doc_ids"]
    parsed: list[str] = []
    if raw:
        try:
            parsed = json.loads(raw)
            if not isinstance(parsed, list):
                parsed = []
        except (json.JSONDecodeError, TypeError):
            parsed = []
    return SendEventRow(
        id=row["id"],
        project_id=row["project_id"],
        investor_id=row["investor_id"],
        email_template_id=row["email_template_id"],
        subject=row["subject"],
        sent_at=row["sent_at"],
        attached_doc_ids=parsed,
        success=bool(row["success"]),
        error_message=row["error_message"],
    )


def insert_send_event(
    *,
    project_id: str,
    investor_id: str,
    email_template_id: str | None,
    subject: str | None,
    attached_doc_ids: Iterable[str] | None = None,
    success: bool = True,
    error_message: str | None = None,
    sent_at: datetime | None = None,
) -> SendEventRow:
    new_id = str(uuid.uuid4())
    when = (sent_at or datetime.utcnow()).isoformat(timespec="seconds")
    attached_json = json.dumps(list(attached_doc_ids)) if attached_doc_ids else None
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO send_events (
                id, project_id, investor_id, email_template_id,
                subject, sent_at, attached_doc_ids, success, error_message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                new_id, project_id, investor_id, email_template_id,
                subject, when, attached_json,
                1 if success else 0, error_message,
            ),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM send_events WHERE id = ?", (new_id,)
        ).fetchone()
    return _row_to_event(row)


def list_for_investor(investor_id: str) -> list[SendEventRow]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM send_events WHERE investor_id = ? "
            " ORDER BY datetime(sent_at) DESC",
            (investor_id,),
        ).fetchall()
        return [_row_to_event(r) for r in rows]


def list_for_project(project_id: str) -> list[SendEventRow]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM send_events WHERE project_id = ? "
            " ORDER BY datetime(sent_at) DESC",
            (project_id,),
        ).fetchall()
        return [_row_to_event(r) for r in rows]


def already_sent_pairs(project_id: str, after_iso: str | None = None) -> set[tuple[str, str]]:
    """Return ``{(investor_id, email_template_id)}`` pairs that already have a
    successful send event.

    If ``after_iso`` is provided, only events with ``sent_at >= after_iso``
    count — used to scope to "since the investor entered their current stage."
    """
    with connect() as conn:
        if after_iso:
            rows = conn.execute(
                "SELECT investor_id, email_template_id FROM send_events "
                " WHERE project_id = ? AND success = 1 "
                "   AND email_template_id IS NOT NULL "
                "   AND datetime(sent_at) >= datetime(?)",
                (project_id, after_iso),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT investor_id, email_template_id FROM send_events "
                " WHERE project_id = ? AND success = 1 "
                "   AND email_template_id IS NOT NULL",
                (project_id,),
            ).fetchall()
    return {(r["investor_id"], r["email_template_id"]) for r in rows}


__all__ = [
    "SendEventRow",
    "insert_send_event",
    "list_for_investor",
    "list_for_project",
    "already_sent_pairs",
]
