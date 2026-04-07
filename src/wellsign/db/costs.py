"""Cost line items + receipt attachments — AFE budget vs actuals."""

from __future__ import annotations

import shutil
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from wellsign.app_paths import cost_attachments_dir
from wellsign.db.migrate import connect


# ---------------------------------------------------------------------------
# Status / phase / tax enums
# ---------------------------------------------------------------------------
COST_STATUSES = [
    ("planned",   "Planned"),
    ("committed", "Committed"),
    ("invoiced",  "Invoiced"),
    ("paid",      "Paid"),
]

PHASE_GROUPS = [
    ("pre_drilling", "Pre-drilling"),
    ("drilling",     "Drilling"),
    ("completion",   "Completion"),
    ("facilities",   "Facilities"),
    ("soft",         "Soft Costs"),
]

TAX_CLASSES = [
    ("intangible", "Intangible (IDC) — deductible"),
    ("tangible",   "Tangible (TDC) — depreciable"),
    ("mixed",      "Mixed"),
]

PHASE_LABEL = {code: label for code, label in PHASE_GROUPS}
TAX_LABEL = {code: label for code, label in TAX_CLASSES}


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------
@dataclass
class CostAttachmentRow:
    id: str
    cost_line_item_id: str
    file_name: str
    storage_path: str
    file_sha256: str | None
    byte_size: int | None
    mime_type: str | None
    uploaded_at: str


@dataclass
class CostLineRow:
    id: str
    project_id: str
    phase_group: str
    tax_class: str
    category: str
    description: str
    expected_amount: float
    actual_amount: float | None
    vendor: str | None
    invoice_number: str | None
    paid_at: str | None
    notes: str | None
    status: str
    item_order: int
    created_at: str
    attachments: list[CostAttachmentRow] = field(default_factory=list)

    @property
    def variance(self) -> float | None:
        if self.actual_amount is None:
            return None
        return self.actual_amount - self.expected_amount


@dataclass
class CostsTotals:
    expected: float
    actual: float
    variance: float
    receipts: int
    intangible_expected: float
    tangible_expected: float
    intangible_actual: float
    tangible_actual: float


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------
def list_cost_lines(project_id: str) -> list[CostLineRow]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM cost_line_items WHERE project_id = ? "
            " ORDER BY item_order, datetime(created_at)",
            (project_id,),
        ).fetchall()
        result: list[CostLineRow] = []
        for r in rows:
            line = _row_to_line(r)
            att_rows = conn.execute(
                "SELECT * FROM cost_attachments WHERE cost_line_item_id = ? "
                " ORDER BY datetime(uploaded_at)",
                (line.id,),
            ).fetchall()
            line.attachments = [_row_to_attachment(a) for a in att_rows]
            result.append(line)
    return result


def get_cost_line(line_id: str) -> CostLineRow | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM cost_line_items WHERE id = ?", (line_id,)).fetchone()
        if not row:
            return None
        line = _row_to_line(row)
        att_rows = conn.execute(
            "SELECT * FROM cost_attachments WHERE cost_line_item_id = ? "
            " ORDER BY datetime(uploaded_at)",
            (line.id,),
        ).fetchall()
        line.attachments = [_row_to_attachment(a) for a in att_rows]
        return line


def insert_cost_line(
    *,
    project_id: str,
    category: str,
    description: str,
    expected_amount: float,
    actual_amount: float | None = None,
    vendor: str | None = None,
    invoice_number: str | None = None,
    notes: str | None = None,
    status: str = "planned",
    phase_group: str = "drilling",
    tax_class: str = "intangible",
) -> CostLineRow:
    new_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat(timespec="seconds")
    with connect() as conn:
        next_order = conn.execute(
            "SELECT COALESCE(MAX(item_order), -1) + 1 FROM cost_line_items WHERE project_id = ?",
            (project_id,),
        ).fetchone()[0]
        conn.execute(
            """
            INSERT INTO cost_line_items (
                id, project_id, phase_group, tax_class, category, description,
                expected_amount, actual_amount, vendor, invoice_number,
                paid_at, notes, status, item_order, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, ?)
            """,
            (
                new_id, project_id, phase_group, tax_class, category, description,
                expected_amount, actual_amount, vendor, invoice_number,
                notes, status, next_order, now, now,
            ),
        )
        conn.commit()
    result = get_cost_line(new_id)
    assert result is not None
    return result


def update_cost_line(
    line_id: str,
    *,
    category: str,
    description: str,
    expected_amount: float,
    actual_amount: float | None,
    vendor: str | None,
    invoice_number: str | None,
    notes: str | None,
    status: str,
    phase_group: str = "drilling",
    tax_class: str = "intangible",
) -> CostLineRow:
    now = datetime.utcnow().isoformat(timespec="seconds")
    paid_at = now if status == "paid" else None
    with connect() as conn:
        conn.execute(
            """
            UPDATE cost_line_items
               SET phase_group = ?, tax_class = ?,
                   category = ?, description = ?, expected_amount = ?,
                   actual_amount = ?, vendor = ?, invoice_number = ?,
                   notes = ?, status = ?, paid_at = COALESCE(paid_at, ?),
                   updated_at = ?
             WHERE id = ?
            """,
            (
                phase_group, tax_class,
                category, description, expected_amount,
                actual_amount, vendor, invoice_number,
                notes, status, paid_at, now, line_id,
            ),
        )
        conn.commit()
    result = get_cost_line(line_id)
    assert result is not None
    return result


def delete_cost_line(line_id: str) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM cost_line_items WHERE id = ?", (line_id,))
        conn.commit()


def totals_for(project_id: str) -> CostsTotals:
    with connect() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(expected_amount), 0) AS exp, "
            "       COALESCE(SUM(actual_amount), 0)   AS act "
            "  FROM cost_line_items WHERE project_id = ?",
            (project_id,),
        ).fetchone()
        idc_row = conn.execute(
            "SELECT COALESCE(SUM(expected_amount), 0) AS exp, "
            "       COALESCE(SUM(actual_amount), 0)   AS act "
            "  FROM cost_line_items WHERE project_id = ? AND tax_class = 'intangible'",
            (project_id,),
        ).fetchone()
        tdc_row = conn.execute(
            "SELECT COALESCE(SUM(expected_amount), 0) AS exp, "
            "       COALESCE(SUM(actual_amount), 0)   AS act "
            "  FROM cost_line_items WHERE project_id = ? AND tax_class = 'tangible'",
            (project_id,),
        ).fetchone()
        receipts = conn.execute(
            "SELECT COUNT(*) FROM cost_attachments ca "
            "  JOIN cost_line_items cl ON cl.id = ca.cost_line_item_id "
            " WHERE cl.project_id = ?",
            (project_id,),
        ).fetchone()[0]
    return CostsTotals(
        expected=float(row["exp"]),
        actual=float(row["act"]),
        variance=float(row["act"]) - float(row["exp"]),
        receipts=int(receipts),
        intangible_expected=float(idc_row["exp"]),
        tangible_expected=float(tdc_row["exp"]),
        intangible_actual=float(idc_row["act"]),
        tangible_actual=float(tdc_row["act"]),
    )


def totals_by_phase(project_id: str) -> dict[str, dict[str, float]]:
    """Return per-phase {expected, actual, variance} dicts keyed by phase_group code."""
    out: dict[str, dict[str, float]] = {}
    with connect() as conn:
        rows = conn.execute(
            "SELECT phase_group, "
            "       COALESCE(SUM(expected_amount), 0) AS exp, "
            "       COALESCE(SUM(actual_amount), 0)   AS act "
            "  FROM cost_line_items WHERE project_id = ? "
            " GROUP BY phase_group",
            (project_id,),
        ).fetchall()
    for r in rows:
        out[r["phase_group"]] = {
            "expected": float(r["exp"]),
            "actual": float(r["act"]),
            "variance": float(r["act"]) - float(r["exp"]),
        }
    return out


# ---------------------------------------------------------------------------
# Attachments
# ---------------------------------------------------------------------------
def attach_receipt(line_id: str, project_id: str, src_path: Path) -> CostAttachmentRow:
    """Copy a receipt file into the cost line's storage folder and record it."""
    dest_dir = cost_attachments_dir(project_id, line_id)
    dest = dest_dir / src_path.name
    if dest.exists():
        stem = dest.stem
        suffix = dest.suffix
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        dest = dest_dir / f"{stem}_{ts}{suffix}"
    shutil.copy2(src_path, dest)

    new_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat(timespec="seconds")
    sha = _sha256(dest)
    size = dest.stat().st_size
    mime = _guess_mime(dest)

    with connect() as conn:
        conn.execute(
            """
            INSERT INTO cost_attachments (
                id, cost_line_item_id, file_name, storage_path,
                file_sha256, byte_size, mime_type, uploaded_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (new_id, line_id, dest.name, str(dest), sha, size, mime, now),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM cost_attachments WHERE id = ?", (new_id,)
        ).fetchone()
    return _row_to_attachment(row)


def delete_receipt(attachment_id: str) -> None:
    with connect() as conn:
        row = conn.execute(
            "SELECT storage_path FROM cost_attachments WHERE id = ?",
            (attachment_id,),
        ).fetchone()
        if row:
            try:
                Path(row["storage_path"]).unlink(missing_ok=True)
            except OSError:
                pass
        conn.execute("DELETE FROM cost_attachments WHERE id = ?", (attachment_id,))
        conn.commit()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _row_to_line(row: sqlite3.Row) -> CostLineRow:
    def _safe(key: str, default=None):
        try:
            return row[key]
        except (KeyError, IndexError):
            return default

    return CostLineRow(
        id=row["id"],
        project_id=row["project_id"],
        phase_group=_safe("phase_group", "drilling") or "drilling",
        tax_class=_safe("tax_class", "intangible") or "intangible",
        category=row["category"],
        description=row["description"],
        expected_amount=float(row["expected_amount"] or 0),
        actual_amount=row["actual_amount"],
        vendor=row["vendor"],
        invoice_number=row["invoice_number"],
        paid_at=row["paid_at"],
        notes=row["notes"],
        status=row["status"],
        item_order=row["item_order"],
        created_at=row["created_at"],
    )


def _row_to_attachment(row: sqlite3.Row) -> CostAttachmentRow:
    return CostAttachmentRow(
        id=row["id"],
        cost_line_item_id=row["cost_line_item_id"],
        file_name=row["file_name"],
        storage_path=row["storage_path"],
        file_sha256=row["file_sha256"],
        byte_size=row["byte_size"],
        mime_type=row["mime_type"],
        uploaded_at=row["uploaded_at"],
    )


def _sha256(path: Path) -> str:
    import hashlib

    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _guess_mime(path: Path) -> str:
    import mimetypes

    return mimetypes.guess_type(str(path))[0] or "application/octet-stream"
