"""Append-only audit log writer.

Every state-changing action in WellSign logs a row here. The schema enforces
append-only via triggers (``audit_log_no_update`` and ``audit_log_no_delete``
in ``schema.sql``), so there is no update or delete code path — by design.

Usage::

    from wellsign.util.audit import log_action

    log_action(
        "project_created",
        project_id=proj.id,
        target_type="project",
        target_id=proj.id,
        metadata={"name": proj.name, "license_customer": payload.customer},
    )

**PII rule:** ``metadata`` is stored as plaintext JSON. Never put decrypted
SSN / EIN / bank routing / account / full emails into it. Store IDs, booleans,
counts, and type labels — nothing that would leak real investor data if the
audit log were ever exported for discovery or forensics.
"""

from __future__ import annotations

import getpass
import json
import sqlite3
from typing import Any

from wellsign.db.migrate import connect


def _actor() -> str:
    try:
        return getpass.getuser()
    except Exception:
        return "unknown"


def log_action(
    action: str,
    *,
    project_id: str | None = None,
    investor_id: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Append one row to the audit log.

    Silent on failure — an audit write must never abort a business action.
    If the audit insert raises, we swallow the exception to protect the
    caller's transaction. The loss of a single audit row is preferable to
    rolling back a real user action because the log file was locked.
    """
    try:
        payload = json.dumps(metadata, sort_keys=True) if metadata else None
        with connect() as conn:
            conn.execute(
                """
                INSERT INTO audit_log
                    (actor, project_id, investor_id, action,
                     target_type, target_id, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    _actor(),
                    project_id,
                    investor_id,
                    action,
                    target_type,
                    target_id,
                    payload,
                ),
            )
            conn.commit()
    except sqlite3.Error:
        # Never let audit failures break the caller's flow.
        return


def list_recent(limit: int = 100, project_id: str | None = None) -> list[sqlite3.Row]:
    """Return the most recent audit rows, optionally scoped to one project."""
    with connect() as conn:
        if project_id:
            rows = conn.execute(
                "SELECT * FROM audit_log WHERE project_id = ? "
                " ORDER BY id DESC LIMIT ?",
                (project_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
    return list(rows)


__all__ = ["log_action", "list_recent"]
