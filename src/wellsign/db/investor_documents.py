"""Read/write access for the ``investor_documents`` table.

A row exists for every PDF that has been generated, sent, or received for
an investor on a project. The packet generator writes ``direction='sent'``
rows; the received-folder watcher (future) will write ``direction='received'``
rows.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime

from wellsign.db.migrate import connect
from wellsign.util.audit import log_action


@dataclass
class InvestorDocumentRow:
    id: str
    project_id: str
    investor_id: str
    doc_type: str
    direction: str       # sent | received | attachment
    source: str          # app | manual_upload | email_import | docusign | pandadoc
    storage_path: str | None
    external_url: str | None
    file_sha256: str | None
    byte_size: int | None
    mime_type: str | None
    status: str
    sent_at: str | None
    received_at: str | None
    signed_at: str | None
    metadata: dict
    created_at: str


def _row_to_doc(row: sqlite3.Row) -> InvestorDocumentRow:
    raw_meta = row["metadata"]
    parsed_meta: dict = {}
    if raw_meta:
        try:
            parsed_meta = json.loads(raw_meta)
        except (json.JSONDecodeError, TypeError):
            parsed_meta = {}
    return InvestorDocumentRow(
        id=row["id"],
        project_id=row["project_id"],
        investor_id=row["investor_id"],
        doc_type=row["doc_type"],
        direction=row["direction"],
        source=row["source"],
        storage_path=row["storage_path"],
        external_url=row["external_url"],
        file_sha256=row["file_sha256"],
        byte_size=row["byte_size"],
        mime_type=row["mime_type"],
        status=row["status"],
        sent_at=row["sent_at"],
        received_at=row["received_at"],
        signed_at=row["signed_at"],
        metadata=parsed_meta,
        created_at=row["created_at"],
    )


def list_for_project(project_id: str) -> list[InvestorDocumentRow]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM investor_documents "
            " WHERE project_id = ? "
            " ORDER BY datetime(created_at) DESC",
            (project_id,),
        ).fetchall()
        return [_row_to_doc(r) for r in rows]


def list_for_investor(investor_id: str) -> list[InvestorDocumentRow]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM investor_documents "
            " WHERE investor_id = ? "
            " ORDER BY datetime(created_at) DESC",
            (investor_id,),
        ).fetchall()
        return [_row_to_doc(r) for r in rows]


def record_generated_document(
    *,
    project_id: str,
    investor_id: str,
    doc_type: str,
    storage_path: str,
    byte_size: int | None = None,
    metadata: dict | None = None,
) -> InvestorDocumentRow:
    """Record a freshly-generated PDF for an investor.

    ``status`` starts as ``generated``. The Send tab will later flip it to
    ``sent`` (and stamp ``sent_at``) when an Outlook draft is fired.
    """
    new_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat(timespec="seconds")
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO investor_documents (
                id, project_id, investor_id,
                doc_type, direction, source,
                storage_path, byte_size, mime_type,
                status, metadata, created_at, updated_at
            ) VALUES (
                :id, :project_id, :investor_id,
                :doc_type, 'sent', 'app',
                :storage_path, :byte_size, 'application/pdf',
                'generated', :metadata, :now, :now
            )
            """,
            {
                "id": new_id,
                "project_id": project_id,
                "investor_id": investor_id,
                "doc_type": doc_type,
                "storage_path": storage_path,
                "byte_size": byte_size,
                "metadata": json.dumps(metadata) if metadata else None,
                "now": now,
            },
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM investor_documents WHERE id = ?", (new_id,)
        ).fetchone()
    log_action(
        "packet_generated",
        project_id=project_id,
        investor_id=investor_id,
        target_type="investor_document",
        target_id=new_id,
        metadata={
            "doc_type": doc_type,
            "template_id": (metadata or {}).get("template_id"),
            "byte_size": byte_size,
        },
    )
    return _row_to_doc(row)


def delete_for_project(project_id: str) -> int:
    """Wipe every document row for a project — used by 'Regenerate all'."""
    with connect() as conn:
        cur = conn.execute(
            "DELETE FROM investor_documents WHERE project_id = ?",
            (project_id,),
        )
        conn.commit()
        return cur.rowcount or 0
