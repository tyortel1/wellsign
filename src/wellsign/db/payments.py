"""Read/write access for the ``payments`` table.

Tracks money the operator EXPECTS to receive from investors:
  * LLG payments wire/check to **Decker Exploration**
  * DHC payments wire/check to **Paloma Operating** (the operator)

This is the OTHER side of the AFE costs picture — Costs is what the operator
SPENDS, payments is what the operator COLLECTS. Variance between the two is
what eventually drives the surplus / supplemental cash call calculation.

Each investor on a project gets exactly two rows: one ``llg`` and one ``dhc``.
``ensure_payments_for_investor()`` is the idempotent entry point — call it
from InvestorDialog after insert/update so the rows always reflect the
investor's current ``llg_amount`` / ``dhc_amount``. Already-received rows
are never overwritten.
"""

from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass
from datetime import date, datetime

from wellsign.db.investors import InvestorRow, get_investor, list_investors
from wellsign.db.migrate import connect


PAYMENT_TYPES = [
    ("llg", "LLG"),
    ("dhc", "DHC"),
]

PAYEE_BY_TYPE = {
    "llg": "decker",
    "dhc": "paloma",
}

PAYMENT_METHODS = [
    ("wire", "Wire"),
    ("check", "Check"),
]

PAYMENT_STATUSES = [
    ("expected", "Expected"),
    ("partial",  "Partial"),
    ("received", "Received"),
    ("overdue",  "Overdue"),
]


@dataclass
class PaymentRow:
    id: str
    project_id: str
    investor_id: str
    payment_type: str               # 'llg' | 'dhc'
    payee: str                      # 'decker' | 'paloma'
    expected_amount: float
    received_amount: float | None
    method: str | None              # 'wire' | 'check'
    received_at: str | None         # ISO date when received
    reference_number: str | None
    notes: str | None
    status: str                     # 'expected' | 'partial' | 'received' | 'overdue'
    created_at: str

    @property
    def variance(self) -> float | None:
        if self.received_amount is None:
            return None
        return self.received_amount - self.expected_amount


@dataclass
class PaymentTotals:
    llg_expected: float
    llg_received: float
    llg_outstanding: float
    dhc_expected: float
    dhc_received: float
    dhc_outstanding: float

    @property
    def total_expected(self) -> float:
        return self.llg_expected + self.dhc_expected

    @property
    def total_received(self) -> float:
        return self.llg_received + self.dhc_received

    @property
    def total_outstanding(self) -> float:
        return self.total_expected - self.total_received


# ---------------------------------------------------------------------------
# Row mapping
# ---------------------------------------------------------------------------
def _row_to_payment(row: sqlite3.Row) -> PaymentRow:
    return PaymentRow(
        id=row["id"],
        project_id=row["project_id"],
        investor_id=row["investor_id"],
        payment_type=row["payment_type"],
        payee=row["payee"],
        expected_amount=float(row["expected_amount"] or 0),
        received_amount=row["received_amount"],
        method=row["method"],
        received_at=row["received_at"],
        reference_number=row["reference_number"],
        notes=row["notes"],
        status=row["status"],
        created_at=row["created_at"],
    )


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------
def list_for_project(project_id: str) -> list[PaymentRow]:
    """Return every payment row for a project, ordered by investor + type."""
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT p.* FROM payments p
              JOIN investors i ON i.id = p.investor_id
             WHERE p.project_id = ?
             ORDER BY i.last_name, i.first_name, i.entity_name,
                      CASE p.payment_type WHEN 'llg' THEN 0 ELSE 1 END
            """,
            (project_id,),
        ).fetchall()
        return [_row_to_payment(r) for r in rows]


def list_for_investor(investor_id: str) -> list[PaymentRow]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM payments WHERE investor_id = ? "
            " ORDER BY CASE payment_type WHEN 'llg' THEN 0 ELSE 1 END",
            (investor_id,),
        ).fetchall()
        return [_row_to_payment(r) for r in rows]


def get_payment(payment_id: str) -> PaymentRow | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM payments WHERE id = ?", (payment_id,)
        ).fetchone()
        return _row_to_payment(row) if row else None


def _insert_row(
    *,
    project_id: str,
    investor_id: str,
    payment_type: str,
    expected_amount: float,
) -> str:
    new_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat(timespec="seconds")
    payee = PAYEE_BY_TYPE.get(payment_type, "decker")
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO payments (
                id, project_id, investor_id, payment_type, payee,
                expected_amount, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'expected', ?, ?)
            """,
            (new_id, project_id, investor_id, payment_type, payee,
             expected_amount, now, now),
        )
        conn.commit()
    return new_id


def ensure_payments_for_investor(investor: InvestorRow) -> tuple[PaymentRow, PaymentRow]:
    """Idempotent — create or refresh the LLG + DHC rows for an investor.

    * If no rows exist yet → INSERT both at the investor's current amounts.
    * If rows exist and are still ``expected`` → UPDATE expected_amount to
      match the investor's latest llg_amount / dhc_amount (handles WI changes).
    * If rows exist and are already ``received`` (or ``partial``) → leave them
      alone. Historical facts shouldn't get rewritten by a WI tweak.

    Called by InvestorDialog after insert/update so payment rows track the
    investor automatically. Also called by update_project's amount-cascade
    (see ``recalc_for_project``).
    """
    existing = list_for_investor(investor.id)
    by_type = {p.payment_type: p for p in existing}

    expected_llg = float(investor.llg_amount or 0)
    expected_dhc = float(investor.dhc_amount or 0)

    if "llg" not in by_type:
        llg_id = _insert_row(
            project_id=investor.project_id,
            investor_id=investor.id,
            payment_type="llg",
            expected_amount=expected_llg,
        )
    else:
        llg = by_type["llg"]
        if llg.status == "expected" and abs(llg.expected_amount - expected_llg) > 0.005:
            _update_expected(llg.id, expected_llg)
        llg_id = llg.id

    if "dhc" not in by_type:
        dhc_id = _insert_row(
            project_id=investor.project_id,
            investor_id=investor.id,
            payment_type="dhc",
            expected_amount=expected_dhc,
        )
    else:
        dhc = by_type["dhc"]
        if dhc.status == "expected" and abs(dhc.expected_amount - expected_dhc) > 0.005:
            _update_expected(dhc.id, expected_dhc)
        dhc_id = dhc.id

    llg_row = get_payment(llg_id)
    dhc_row = get_payment(dhc_id)
    assert llg_row is not None and dhc_row is not None
    return llg_row, dhc_row


def _update_expected(payment_id: str, expected_amount: float) -> None:
    now = datetime.utcnow().isoformat(timespec="seconds")
    with connect() as conn:
        conn.execute(
            "UPDATE payments SET expected_amount = ?, updated_at = ? WHERE id = ?",
            (expected_amount, now, payment_id),
        )
        conn.commit()


def recalc_for_project(project_id: str) -> int:
    """Walk every investor on the project and ensure their payment rows
    track current llg_amount / dhc_amount.

    Used after EditProjectDialog changes total_llg_cost or total_dhc_cost,
    or after a bulk Excel investor import.

    Returns the number of investors processed.
    """
    n = 0
    for inv in list_investors(project_id):
        ensure_payments_for_investor(inv)
        n += 1
    return n


def mark_received(
    payment_id: str,
    *,
    received_amount: float,
    method: str | None,
    received_at: str | None = None,
    reference_number: str | None = None,
    notes: str | None = None,
) -> PaymentRow:
    """Record receipt of a payment.

    Status is computed from received_amount vs expected_amount:
      * received_amount >= expected_amount   → 'received'
      * 0 < received_amount < expected_amount → 'partial'
      * received_amount == 0                  → 'expected' (cleared)
    """
    existing = get_payment(payment_id)
    if existing is None:
        raise ValueError(f"Payment {payment_id} not found")

    if received_amount <= 0:
        new_status = "expected"
    elif received_amount + 0.005 < existing.expected_amount:
        new_status = "partial"
    else:
        new_status = "received"

    when = received_at or date.today().isoformat()
    now = datetime.utcnow().isoformat(timespec="seconds")
    with connect() as conn:
        conn.execute(
            """
            UPDATE payments
               SET received_amount   = ?,
                   method            = ?,
                   received_at       = ?,
                   reference_number  = ?,
                   notes             = ?,
                   status            = ?,
                   updated_at        = ?
             WHERE id = ?
            """,
            (received_amount, method, when, reference_number, notes,
             new_status, now, payment_id),
        )
        conn.commit()
    result = get_payment(payment_id)
    assert result is not None
    return result


def clear_payment(payment_id: str) -> PaymentRow:
    """Reset a payment back to expected. For undo / data correction."""
    now = datetime.utcnow().isoformat(timespec="seconds")
    with connect() as conn:
        conn.execute(
            """
            UPDATE payments
               SET received_amount  = NULL,
                   method           = NULL,
                   received_at      = NULL,
                   reference_number = NULL,
                   status           = 'expected',
                   updated_at       = ?
             WHERE id = ?
            """,
            (now, payment_id),
        )
        conn.commit()
    result = get_payment(payment_id)
    assert result is not None
    return result


def mark_overdue_if_past(project_id: str, deadline_iso: str) -> int:
    """Flip any unreceived payments past the deadline to 'overdue'.

    Should be called whenever the close deadline is reached, or on tab open.
    Returns the number of rows updated.
    """
    if not deadline_iso:
        return 0
    today = date.today().isoformat()
    if today <= deadline_iso[:10]:
        return 0
    now = datetime.utcnow().isoformat(timespec="seconds")
    with connect() as conn:
        cur = conn.execute(
            """
            UPDATE payments
               SET status = 'overdue', updated_at = ?
             WHERE project_id = ?
               AND status = 'expected'
            """,
            (now, project_id),
        )
        conn.commit()
        return cur.rowcount or 0


def totals_for_project(project_id: str) -> PaymentTotals:
    """Aggregate LLG / DHC expected / received / outstanding for a project."""
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT payment_type,
                   COALESCE(SUM(expected_amount), 0) AS exp,
                   COALESCE(SUM(received_amount), 0) AS rec
              FROM payments
             WHERE project_id = ?
             GROUP BY payment_type
            """,
            (project_id,),
        ).fetchall()
    expected: dict[str, float] = {"llg": 0.0, "dhc": 0.0}
    received: dict[str, float] = {"llg": 0.0, "dhc": 0.0}
    for r in rows:
        t = r["payment_type"]
        expected[t] = float(r["exp"] or 0)
        received[t] = float(r["rec"] or 0)
    return PaymentTotals(
        llg_expected=expected["llg"],
        llg_received=received["llg"],
        llg_outstanding=expected["llg"] - received["llg"],
        dhc_expected=expected["dhc"],
        dhc_received=received["dhc"],
        dhc_outstanding=expected["dhc"] - received["dhc"],
    )


__all__ = [
    "PAYMENT_TYPES",
    "PAYEE_BY_TYPE",
    "PAYMENT_METHODS",
    "PAYMENT_STATUSES",
    "PaymentRow",
    "PaymentTotals",
    "list_for_project",
    "list_for_investor",
    "get_payment",
    "ensure_payments_for_investor",
    "recalc_for_project",
    "mark_received",
    "clear_payment",
    "mark_overdue_if_past",
    "totals_for_project",
]
