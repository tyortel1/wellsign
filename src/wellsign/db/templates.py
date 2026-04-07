"""Read/write access for ``document_templates`` and ``email_templates``."""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime

from wellsign.db.migrate import connect
from wellsign.util.audit import log_action


# ---------------------------------------------------------------------------
# Document templates
# ---------------------------------------------------------------------------
@dataclass
class DocTemplateRow:
    id: str
    name: str
    doc_type: str
    storage_path: str
    page_size: str | None
    notary_required: bool
    is_global: bool
    created_at: str
    field_mapping: dict[str, str] = field(default_factory=dict)


def _row_to_doc_template(row: sqlite3.Row) -> DocTemplateRow:
    raw_mapping = None
    try:
        raw_mapping = row["field_mapping"]
    except (KeyError, IndexError):
        raw_mapping = None
    parsed_mapping: dict[str, str] = {}
    if raw_mapping:
        try:
            parsed_mapping = json.loads(raw_mapping)
            if not isinstance(parsed_mapping, dict):
                parsed_mapping = {}
        except (json.JSONDecodeError, TypeError):
            parsed_mapping = {}
    return DocTemplateRow(
        id=row["id"],
        name=row["name"],
        doc_type=row["doc_type"],
        storage_path=row["storage_path"],
        page_size=row["page_size"],
        notary_required=bool(row["notary_required"]),
        is_global=bool(row["is_global"]),
        created_at=row["created_at"],
        field_mapping=parsed_mapping,
    )


def update_doc_template_mapping(template_id: str, mapping: dict[str, str]) -> None:
    """Persist a PDF-field-name → system-merge-variable map to the template row."""
    now = datetime.utcnow().isoformat(timespec="seconds")
    payload = json.dumps(mapping, sort_keys=True)
    with connect() as conn:
        conn.execute(
            "UPDATE document_templates SET field_mapping = ?, updated_at = ? WHERE id = ?",
            (payload, now, template_id),
        )
        conn.commit()
    log_action(
        "template_mapping_updated",
        target_type="document_template",
        target_id=template_id,
        metadata={"field_count": len(mapping)},
    )


def list_doc_templates() -> list[DocTemplateRow]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM document_templates ORDER BY name"
        ).fetchall()
        return [_row_to_doc_template(r) for r in rows]


def get_doc_template(template_id: str) -> DocTemplateRow | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM document_templates WHERE id = ?", (template_id,)
        ).fetchone()
        return _row_to_doc_template(row) if row else None


def update_doc_template(
    template_id: str,
    *,
    name: str,
    doc_type: str,
    storage_path: str,
    page_size: str | None = None,
    notary_required: bool = False,
) -> DocTemplateRow:
    now = datetime.utcnow().isoformat(timespec="seconds")
    with connect() as conn:
        conn.execute(
            """
            UPDATE document_templates
               SET name = ?, doc_type = ?, storage_path = ?, page_size = ?,
                   notary_required = ?, updated_at = ?
             WHERE id = ?
            """,
            (name, doc_type, storage_path, page_size,
             1 if notary_required else 0, now, template_id),
        )
        conn.commit()
    result = get_doc_template(template_id)
    assert result is not None
    return result


def insert_doc_template(
    *,
    name: str,
    doc_type: str,
    storage_path: str,
    page_size: str | None = None,
    notary_required: bool = False,
    is_global: bool = True,
) -> DocTemplateRow:
    new_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat(timespec="seconds")
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO document_templates (
                id, name, doc_type, storage_path, page_size,
                notary_required, is_global, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (new_id, name, doc_type, storage_path, page_size,
             1 if notary_required else 0, 1 if is_global else 0, now, now),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM document_templates WHERE id = ?", (new_id,)
        ).fetchone()
    log_action(
        "template_uploaded",
        target_type="document_template",
        target_id=new_id,
        metadata={"name": name, "doc_type": doc_type, "page_size": page_size},
    )
    return _row_to_doc_template(row)


# ---------------------------------------------------------------------------
# Email templates
# ---------------------------------------------------------------------------
@dataclass
class EmailTemplateRow:
    id: str
    name: str
    purpose: str
    subject: str
    body_html: str
    is_global: bool
    created_at: str


def _row_to_email_template(row: sqlite3.Row) -> EmailTemplateRow:
    return EmailTemplateRow(
        id=row["id"],
        name=row["name"],
        purpose=row["purpose"],
        subject=row["subject"],
        body_html=row["body_html"],
        is_global=bool(row["is_global"]),
        created_at=row["created_at"],
    )


def list_email_templates() -> list[EmailTemplateRow]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM email_templates ORDER BY purpose, name"
        ).fetchall()
        return [_row_to_email_template(r) for r in rows]


def get_email_template(template_id: str) -> EmailTemplateRow | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM email_templates WHERE id = ?", (template_id,)
        ).fetchone()
        return _row_to_email_template(row) if row else None


def update_email_template(
    template_id: str,
    *,
    name: str,
    purpose: str,
    subject: str,
    body_html: str,
) -> EmailTemplateRow:
    now = datetime.utcnow().isoformat(timespec="seconds")
    with connect() as conn:
        conn.execute(
            """
            UPDATE email_templates
               SET name = ?, purpose = ?, subject = ?, body_html = ?, updated_at = ?
             WHERE id = ?
            """,
            (name, purpose, subject, body_html, now, template_id),
        )
        conn.commit()
    result = get_email_template(template_id)
    assert result is not None
    return result


def insert_email_template(
    *,
    name: str,
    purpose: str,
    subject: str,
    body_html: str,
    is_global: bool = True,
) -> EmailTemplateRow:
    new_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat(timespec="seconds")
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO email_templates (
                id, name, purpose, subject, body_html, is_global,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (new_id, name, purpose, subject, body_html, 1 if is_global else 0, now, now),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM email_templates WHERE id = ?", (new_id,)
        ).fetchone()
    return _row_to_email_template(row)
