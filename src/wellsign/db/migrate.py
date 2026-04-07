"""Tiny schema-version migration runner.

For the POC we keep this dumb on purpose: a single ``schema.sql`` file is the
source of truth, applied idempotently on every startup. When we need real
migrations later we can swap this for a versioned migrations folder.
"""

from __future__ import annotations

import sqlite3
from importlib import resources
from pathlib import Path

from wellsign.app_paths import database_path

CURRENT_VERSION = 1


def _load_schema_sql() -> str:
    return resources.files("wellsign.db").joinpath("schema.sql").read_text(encoding="utf-8")


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def run_migrations(db_path: Path | None = None) -> int:
    """Apply schema.sql, then stamp the schema_version table.

    Returns the version that is now live.
    """
    conn = connect(db_path)
    try:
        conn.executescript(_load_schema_sql())
        _ensure_columns(conn)
        cur = conn.execute("SELECT COALESCE(MAX(version), 0) FROM schema_version")
        existing = cur.fetchone()[0]
        if existing < CURRENT_VERSION:
            conn.execute(
                "INSERT INTO schema_version (version) VALUES (?)",
                (CURRENT_VERSION,),
            )
        conn.commit()
    finally:
        conn.close()
    return CURRENT_VERSION


def _ensure_columns(conn: sqlite3.Connection) -> None:
    """Idempotent ALTER TABLE for columns added after the initial schema.

    SQLite has no ``ADD COLUMN IF NOT EXISTS`` — we wrap each ALTER in a
    try/except on the duplicate-column error so this method is safe to run
    on every startup. Append new entries here when the schema gains columns.
    """
    additions: list[tuple[str, str, str]] = [
        # (table, column, type + default clause)
        ("projects", "wire_fee", "REAL NOT NULL DEFAULT 15.00"),
    ]
    for table, column, definition in additions:
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        except sqlite3.OperationalError as e:
            if "duplicate column" not in str(e).lower():
                raise
