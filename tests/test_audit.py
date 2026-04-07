"""Tests for the append-only audit log.

Verifies:
  * log_action inserts a row with the expected fields
  * JSON metadata round-trips
  * The schema's BEFORE UPDATE / BEFORE DELETE triggers reject mutations
  * log_action never raises even if the caller's metadata is weird
"""

from __future__ import annotations

import json
import os
import tempfile

import pytest

os.environ.setdefault("WELLSIGN_PII_KEY_HEX", "00" * 32)


@pytest.fixture(autouse=True)
def _fresh_db(monkeypatch):
    """Point every test at its own empty data directory.

    The audit_log table is append-only (triggers block UPDATE/DELETE), so we
    can't wipe it between tests — we give each test a fresh DB file instead.
    """
    tmp_dir = tempfile.mkdtemp(prefix="wellsign_audit_test_")
    monkeypatch.setenv("WELLSIGN_DATA_DIR", tmp_dir)

    # Re-import migrate with the new env var so connect() picks it up.
    from wellsign.db.migrate import run_migrations
    run_migrations()
    yield


from wellsign.db.migrate import connect  # noqa: E402
from wellsign.util.audit import list_recent, log_action  # noqa: E402


def test_log_action_writes_row():
    log_action(
        "project_created",
        project_id="p1",
        target_type="project",
        target_id="p1",
        metadata={"name": "Highlander", "wi_count": 5},
    )
    rows = list_recent(limit=10)
    assert len(rows) == 1
    row = rows[0]
    assert row["action"] == "project_created"
    assert row["project_id"] == "p1"
    assert row["target_type"] == "project"
    assert row["target_id"] == "p1"
    meta = json.loads(row["metadata"])
    assert meta == {"name": "Highlander", "wi_count": 5}


def test_log_action_scoped_by_project():
    log_action("project_created", project_id="p1")
    log_action("investor_added", project_id="p1", investor_id="i1")
    log_action("project_created", project_id="p2")
    rows_all = list_recent(limit=10)
    rows_p1 = list_recent(limit=10, project_id="p1")
    assert len(rows_all) == 3
    assert len(rows_p1) == 2
    assert all(r["project_id"] == "p1" for r in rows_p1)


def test_log_action_none_metadata():
    log_action("phase_advanced", project_id="p1")
    rows = list_recent(limit=1)
    assert rows[0]["metadata"] is None


def test_audit_log_rejects_updates():
    log_action("project_created", project_id="p1")
    with connect() as conn:
        with pytest.raises(Exception):
            conn.execute("UPDATE audit_log SET action = 'tampered' WHERE project_id = 'p1'")
            conn.commit()


def test_audit_log_rejects_deletes():
    log_action("project_created", project_id="p1")
    with connect() as conn:
        with pytest.raises(Exception):
            conn.execute("DELETE FROM audit_log WHERE project_id = 'p1'")
            conn.commit()


def test_log_action_swallows_broken_metadata(monkeypatch):
    # Simulate a sqlite error — log_action must NOT raise.
    from wellsign.util import audit as audit_mod

    class _BoomConn:
        def execute(self, *a, **k):
            import sqlite3
            raise sqlite3.OperationalError("simulated")

        def commit(self):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(audit_mod, "connect", lambda: _BoomConn())
    # Should not raise
    log_action("test_action", project_id="x")
