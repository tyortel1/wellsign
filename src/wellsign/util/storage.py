"""Per-project file storage manager.

Every file the app writes for an investor goes through this module so the
on-disk layout is consistent and the DB only ever sees relative paths.

Layout (under ``app_paths.project_dir(project_uuid)``)::

    investors/<investor_uuid>/sent/<doc_type>_<timestamp>.pdf
    investors/<investor_uuid>/received/signed_<doc_type>_<timestamp>.pdf
    investors/<investor_uuid>/attachments/<original_filename>
    templates/<template_id>.pdf
    exports/<filename>
"""

from __future__ import annotations

import hashlib
import re
import shutil
from datetime import datetime
from pathlib import Path

from wellsign.app_paths import (
    investor_dir,
    project_dir,
    project_exports_dir,
    project_templates_dir,
)


def _safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._") or "file"


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def relpath_to_project(project_uuid: str, abs_path: Path) -> str:
    return str(abs_path.relative_to(project_dir(project_uuid))).replace("\\", "/")


def store_sent_document(
    project_uuid: str,
    investor_uuid: str,
    doc_type: str,
    src_path: Path,
) -> Path:
    """Copy a generated PDF into the investor's ``sent/`` folder."""
    dst = investor_dir(project_uuid, investor_uuid) / "sent" / f"{_safe(doc_type)}_{_timestamp()}.pdf"
    shutil.copy2(src_path, dst)
    return dst


def store_received_document(
    project_uuid: str,
    investor_uuid: str,
    doc_type: str,
    src_path: Path,
) -> Path:
    """Copy a returned signed PDF into the investor's ``received/`` folder."""
    dst = (
        investor_dir(project_uuid, investor_uuid)
        / "received"
        / f"signed_{_safe(doc_type)}_{_timestamp()}{src_path.suffix or '.pdf'}"
    )
    shutil.copy2(src_path, dst)
    return dst


def store_attachment(
    project_uuid: str,
    investor_uuid: str,
    src_path: Path,
) -> Path:
    """Copy an arbitrary attachment (W-9, ID, anything) for an investor."""
    dst = investor_dir(project_uuid, investor_uuid) / "attachments" / _safe(src_path.name)
    if dst.exists():
        dst = dst.with_name(f"{dst.stem}_{_timestamp()}{dst.suffix}")
    shutil.copy2(src_path, dst)
    return dst


def store_project_template(project_uuid: str, template_id: str, src_path: Path) -> Path:
    dst = project_templates_dir(project_uuid) / f"{_safe(template_id)}.pdf"
    shutil.copy2(src_path, dst)
    return dst


def store_export(project_uuid: str, filename: str, src_path: Path) -> Path:
    dst = project_exports_dir(project_uuid) / _safe(filename)
    shutil.copy2(src_path, dst)
    return dst
