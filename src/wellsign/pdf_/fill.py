"""PDF auto-fill engine.

The product's beating heart: given a blank-but-form-fillable template PDF,
a per-template field mapping (PDF field name → system merge variable), and a
``MergeContext`` built from a project + investor, produce a filled PDF.

We use ``pypdf`` to copy the template into a writer, set field values via
``update_page_form_field_values`` per page, and write the result. The
``NeedAppearances`` flag is set so Acrobat / Reader regenerates appearance
streams for the values we just wrote (otherwise the form looks blank in
some viewers).

Returned filenames go into the per-investor ``sent/`` folder via
``util/storage``. Filename format::

    <doc_type>_<safe_template_name>_<timestamp>.pdf
"""

from __future__ import annotations

import re
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.generic import BooleanObject, NameObject

from wellsign.db.investors import InvestorRow
from wellsign.db.migrate import connect
from wellsign.db.projects import ProjectRow
from wellsign.db.templates import DocTemplateRow
from wellsign.pdf_.merge_vars import MergeContext, render


def _safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._") or "file"


def build_merge_context(project: ProjectRow, investor: InvestorRow) -> MergeContext:
    """Pull the loose project + investor row pair into a flat MergeContext.

    Reads supplemental project columns (totals, county, dates) directly from
    the DB so callers don't need to hand-thread them.
    """
    with connect() as conn:
        row = conn.execute(
            "SELECT prospect_name, operator_llc, county, state, agreement_date, "
            "       close_deadline, total_llg_cost, total_dhc_cost "
            "  FROM projects WHERE id = ?",
            (project.id,),
        ).fetchone()
    if row is None:
        prospect_name = ""
        operator_llc = ""
        county = ""
        state = ""
        agreement_date = ""
        close_deadline = ""
        total_llg = 0.0
        total_dhc = 0.0
    else:
        prospect_name  = row["prospect_name"] or ""
        operator_llc   = row["operator_llc"] or ""
        county         = row["county"] or ""
        state          = row["state"] or ""
        agreement_date = row["agreement_date"] or ""
        close_deadline = row["close_deadline"] or ""
        total_llg      = float(row["total_llg_cost"] or 0)
        total_dhc      = float(row["total_dhc_cost"] or 0)

    return MergeContext(
        investor_first_name=investor.first_name or "",
        investor_last_name=investor.last_name or "",
        investor_entity=investor.entity_name or "",
        investor_title=investor.title or "",
        investor_email=investor.email or "",
        investor_phone=investor.phone or "",
        investor_address1=investor.address_line1 or "",
        investor_address2=investor.address_line2 or "",
        investor_city=investor.city or "",
        investor_state=investor.state or "",
        investor_zip=investor.zip or "",
        investor_wi_fraction=float(investor.wi_percent or 0),
        investor_llg_amount=float(investor.llg_amount or 0),
        investor_dhc_amount=float(investor.dhc_amount or 0),
        investor_payment_preference=investor.payment_preference or "",
        project_name=project.name or "",
        prospect_name=prospect_name,
        well_name=project.well_name or "",
        operator_llc=operator_llc,
        county=county,
        state=state,
        agreement_date=agreement_date,
        close_deadline=close_deadline,
        total_llg_cost=total_llg,
        total_dhc_cost=total_dhc,
    )


def resolve_field_values(
    field_mapping: dict[str, str],
    ctx: MergeContext,
) -> dict[str, str]:
    """Turn ``{pdf_field: merge_var_key}`` into ``{pdf_field: rendered_text}``."""
    out: dict[str, str] = {}
    for pdf_field, merge_key in field_mapping.items():
        if not merge_key:
            continue
        out[pdf_field] = render(merge_key, ctx)
    return out


def fill_template(
    template_path: Path,
    field_values: dict[str, str],
    output_path: Path,
) -> Path:
    """Write a copy of ``template_path`` with the given field values applied.

    ``field_values`` keys are PDF AcroForm field names; values are plain
    strings (already rendered). Missing fields are silently skipped — the
    caller decides whether to warn.
    """
    if not template_path.exists():
        raise FileNotFoundError(f"Template PDF not found: {template_path}")

    reader = PdfReader(str(template_path))
    writer = PdfWriter(clone_from=reader)

    # Apply per page so multi-page templates with form fields scattered work
    for page in writer.pages:
        try:
            writer.update_page_form_field_values(page, field_values)
        except Exception:
            # Some pages have no fields — that's fine.
            continue

    # Force Acrobat / Reader to regenerate appearance streams so values render
    try:
        if "/AcroForm" in writer._root_object:  # type: ignore[attr-defined]
            writer._root_object["/AcroForm"].update(  # type: ignore[index]
                {NameObject("/NeedAppearances"): BooleanObject(True)}
            )
    except Exception:
        pass

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("wb") as f:
        writer.write(f)
    return output_path


def output_filename(template: DocTemplateRow) -> str:
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"{_safe_name(template.doc_type)}_{_safe_name(template.name)}_{ts}.pdf"


__all__ = [
    "MergeContext",
    "build_merge_context",
    "resolve_field_values",
    "fill_template",
    "output_filename",
]
