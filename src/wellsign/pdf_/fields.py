"""Read form-field metadata from a PDF using pypdf.

Used by the New Document Template flow so the operator can map a PDF's
existing form fields to system merge variables (investor_name, wi_percent,
llg_amount, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader


@dataclass
class PdfFormField:
    name: str
    field_type: str  # /Tx (text), /Btn (button/checkbox), /Ch (choice), etc.
    page_number: int | None
    value: str | None


def read_form_fields(pdf_path: Path) -> list[PdfFormField]:
    """Return every form field present in a PDF, ordered by name."""
    reader = PdfReader(str(pdf_path))
    raw = reader.get_form_text_fields() or {}
    fields: list[PdfFormField] = []
    seen: set[str] = set()

    for name, value in raw.items():
        if name in seen:
            continue
        seen.add(name)
        fields.append(PdfFormField(name=name, field_type="/Tx", page_number=None, value=value))

    # pypdf's higher-level helper above only returns text fields. Walk the
    # AcroForm /Fields array directly to pick up checkboxes / choices too.
    try:
        acroform = reader.trailer["/Root"].get("/AcroForm")
        if acroform is not None:
            for field in acroform.get("/Fields", []):
                obj = field.get_object()
                name = obj.get("/T")
                ft = obj.get("/FT")
                if name and name not in seen:
                    seen.add(name)
                    fields.append(
                        PdfFormField(
                            name=str(name),
                            field_type=str(ft) if ft else "?",
                            page_number=None,
                            value=None,
                        )
                    )
    except Exception:
        # Some PDFs lack a clean AcroForm tree; the text-field pass is enough.
        pass

    fields.sort(key=lambda f: f.name)
    return fields


def page_count(pdf_path: Path) -> int:
    return len(PdfReader(str(pdf_path)).pages)
