"""Stage-aware document generator.

Bridges the workflow layer to the PDF auto-fill engine: given an investor
who has just entered (or is currently in) a workflow stage, walk that
stage's attached document templates and produce a filled PDF for each one,
recording the result in ``investor_documents``.

Idempotent — if the investor already has a generated doc for a given
template, that template is skipped. The caller can force regeneration by
deleting the existing row first.

Used by:
  * ``advance_investor_stage`` — auto-generate the new stage's docs the
    moment an investor moves into it
  * ``start_workflow_for_investor`` — auto-generate stage 1's docs when an
    investor is first added to a project
  * (future) Documents tab "Generate this stage only" button
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from wellsign.app_paths import investor_dir
from wellsign.db.investor_documents import list_for_investor, record_generated_document
from wellsign.db.investors import InvestorRow
from wellsign.db.projects import ProjectRow
from wellsign.db.templates import get_doc_template
from wellsign.db.workflows import StageRow
from wellsign.pdf_.fill import (
    build_merge_context,
    fill_template,
    output_filename,
    resolve_field_values,
)


@dataclass
class StageDocResult:
    template_id: str
    template_name: str
    status: str          # 'generated' | 'skipped_duplicate' | 'skipped_unmapped' | 'skipped_missing_pdf' | 'error'
    storage_path: str | None
    error: str | None = None


def generate_stage_docs(
    project: ProjectRow,
    investor: InvestorRow,
    stage: StageRow,
) -> list[StageDocResult]:
    """Generate every doc attached to ``stage`` for ``investor``.

    Returns a list of per-template result rows so the caller can show a
    summary or surface errors. Never raises — individual template failures
    are captured in the ``error`` field of their result.
    """
    if not stage.docs:
        return []

    # Build the merge context once — every template uses the same one
    ctx = build_merge_context(project, investor)

    # Pre-fetch existing generated docs so we can skip duplicates
    existing_template_ids: set[str] = set()
    for d in list_for_investor(investor.id):
        if d.direction != "sent":
            continue
        tid = (d.metadata or {}).get("template_id")
        if tid:
            existing_template_ids.add(str(tid))

    results: list[StageDocResult] = []

    for stage_doc in stage.docs:
        template = get_doc_template(stage_doc.doc_template_id)
        if template is None:
            results.append(
                StageDocResult(
                    template_id=stage_doc.doc_template_id,
                    template_name=stage_doc.doc_template_name,
                    status="error",
                    storage_path=None,
                    error="template not found",
                )
            )
            continue

        # Idempotency check — skip if already generated
        if template.id in existing_template_ids:
            results.append(
                StageDocResult(
                    template_id=template.id,
                    template_name=template.name,
                    status="skipped_duplicate",
                    storage_path=None,
                )
            )
            continue

        if not template.field_mapping:
            results.append(
                StageDocResult(
                    template_id=template.id,
                    template_name=template.name,
                    status="skipped_unmapped",
                    storage_path=None,
                )
            )
            continue

        template_path = Path(template.storage_path or "")
        if not template_path.exists():
            results.append(
                StageDocResult(
                    template_id=template.id,
                    template_name=template.name,
                    status="skipped_missing_pdf",
                    storage_path=None,
                    error=f"template PDF not found: {template_path}",
                )
            )
            continue

        try:
            field_values = resolve_field_values(template.field_mapping, ctx)
            out_dir = investor_dir(project.id, investor.id) / "sent"
            out_path = out_dir / output_filename(template)
            fill_template(template_path, field_values, out_path)
            record_generated_document(
                project_id=project.id,
                investor_id=investor.id,
                doc_type=template.doc_type,
                storage_path=str(out_path),
                byte_size=out_path.stat().st_size,
                metadata={
                    "template_id": template.id,
                    "template_name": template.name,
                    "stage_id": stage.id,
                    "stage_name": stage.name,
                },
            )
            results.append(
                StageDocResult(
                    template_id=template.id,
                    template_name=template.name,
                    status="generated",
                    storage_path=str(out_path),
                )
            )
        except Exception as e:  # noqa: BLE001
            results.append(
                StageDocResult(
                    template_id=template.id,
                    template_name=template.name,
                    status="error",
                    storage_path=None,
                    error=str(e),
                )
            )

    return results


def template_ids_for_stage(stage: StageRow) -> set[str]:
    """Convenience for the Send tab — set of doc_template_ids attached to a stage."""
    return {d.doc_template_id for d in stage.docs}
