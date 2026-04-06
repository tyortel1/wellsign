"""Filesystem locations the app reads and writes.

All on-disk state lives under a single per-user directory provided by
``platformdirs`` so we honour OS conventions (e.g. ``%APPDATA%/WellSign`` on
Windows). Tests can override the root by setting ``WELLSIGN_DATA_DIR``.
"""

from __future__ import annotations

import os
from pathlib import Path

from platformdirs import user_data_dir

_APP_NAME = "WellSign"
_APP_AUTHOR = "WellSign"


def app_data_root() -> Path:
    override = os.environ.get("WELLSIGN_DATA_DIR")
    root = Path(override) if override else Path(user_data_dir(_APP_NAME, _APP_AUTHOR))
    root.mkdir(parents=True, exist_ok=True)
    return root


def database_path() -> Path:
    return app_data_root() / "wellsign.db"


def projects_root() -> Path:
    p = app_data_root() / "projects"
    p.mkdir(parents=True, exist_ok=True)
    return p


def project_dir(project_uuid: str) -> Path:
    p = projects_root() / project_uuid
    p.mkdir(parents=True, exist_ok=True)
    return p


def investor_dir(project_uuid: str, investor_uuid: str) -> Path:
    p = project_dir(project_uuid) / "investors" / investor_uuid
    (p / "sent").mkdir(parents=True, exist_ok=True)
    (p / "received").mkdir(parents=True, exist_ok=True)
    (p / "attachments").mkdir(parents=True, exist_ok=True)
    return p


def project_templates_dir(project_uuid: str) -> Path:
    p = project_dir(project_uuid) / "templates"
    p.mkdir(parents=True, exist_ok=True)
    return p


def project_exports_dir(project_uuid: str) -> Path:
    p = project_dir(project_uuid) / "exports"
    p.mkdir(parents=True, exist_ok=True)
    return p


def global_templates_dir() -> Path:
    """Where user-uploaded global PDF templates live."""
    p = app_data_root() / "templates" / "documents"
    p.mkdir(parents=True, exist_ok=True)
    return p
