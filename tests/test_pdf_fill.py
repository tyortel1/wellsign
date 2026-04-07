"""Tests for the PDF auto-fill engine.

Uses reportlab to generate a tiny AcroForm PDF on disk so the fill engine
has something real to write into. Then re-reads the output with pypdf and
asserts the field values made it through.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

# Use a throwaway data dir so the import of wellsign.db modules doesn't touch
# the real DB on disk if anything pulls in app_paths transitively.
os.environ.setdefault("WELLSIGN_DATA_DIR", tempfile.mkdtemp(prefix="wellsign_pdf_test_"))
os.environ.setdefault("WELLSIGN_PII_KEY_HEX", "00" * 32)

from pypdf import PdfReader  # noqa: E402
from reportlab.pdfgen import canvas  # noqa: E402

from wellsign.pdf_.fill import (  # noqa: E402
    fill_template,
    resolve_field_values,
)
from wellsign.pdf_.merge_vars import MergeContext, render  # noqa: E402


@pytest.fixture
def acroform_pdf(tmp_path: Path) -> Path:
    """Generate a one-page PDF with three text form fields."""
    out = tmp_path / "fixture.pdf"
    c = canvas.Canvas(str(out))
    c.setFont("Helvetica", 12)
    c.drawString(72, 760, "Investor Info Sheet — TEST")

    form = c.acroForm
    c.drawString(72, 720, "Name:")
    form.textfield(name="investor_name_field", x=140, y=712, width=300, height=20)
    c.drawString(72, 690, "WI %:")
    form.textfield(name="wi_field", x=140, y=682, width=300, height=20)
    c.drawString(72, 660, "LLG $:")
    form.textfield(name="llg_field", x=140, y=652, width=300, height=20)

    c.showPage()
    c.save()
    return out


def _make_ctx() -> MergeContext:
    return MergeContext(
        investor_first_name="Roberto",
        investor_last_name="Almanza",
        investor_entity="",
        investor_title="",
        investor_email="ralmanza@example.com",
        investor_phone="",
        investor_address1="",
        investor_address2="",
        investor_city="San Antonio",
        investor_state="TX",
        investor_zip="",
        investor_wi_fraction=0.05,
        investor_llg_amount=75000.00,
        investor_dhc_amount=137500.00,
        investor_payment_preference="wire",
        project_name="Highlander Prospect",
        prospect_name="Highlander Prospect",
        well_name="Pargmann-Gisler #1",
        operator_llc="Paloma Operating LLC",
        county="Karnes",
        state="TX",
        agreement_date="2026-04-01",
        close_deadline="2026-05-01",
        total_llg_cost=1_500_000.00,
        total_dhc_cost=2_750_000.00,
    )


def test_render_basic_variables():
    ctx = _make_ctx()
    assert render("investor_name", ctx) == "Roberto Almanza"
    assert render("investor_wi_percent", ctx) == "0.05000000"
    assert render("investor_wi_percent_display", ctx) == "5.000000%"
    assert render("llg_amount", ctx) == "$75,000.00"
    assert render("dhc_amount", ctx) == "$137,500.00"
    assert render("payee_c1", ctx) == "Decker Exploration, Inc."
    assert render("payee_c2", ctx) == "Paloma Operating LLC"
    assert render("county_state", ctx) == "Karnes County, TX"


def test_render_entity_overrides_personal_name():
    ctx = _make_ctx()
    ctx2 = MergeContext(**{**ctx.__dict__, "investor_entity": "Almanza Family Trust"})
    assert render("investor_name", ctx2) == "Almanza Family Trust"


def test_resolve_field_values_skips_empty_keys():
    ctx = _make_ctx()
    mapping = {
        "name_field": "investor_name",
        "wi_field": "investor_wi_percent",
        "skip_me": "",
    }
    out = resolve_field_values(mapping, ctx)
    assert out["name_field"] == "Roberto Almanza"
    assert out["wi_field"] == "0.05000000"
    assert "skip_me" not in out


def test_fill_template_writes_values(acroform_pdf: Path, tmp_path: Path):
    ctx = _make_ctx()
    field_values = {
        "investor_name_field": render("investor_name", ctx),
        "wi_field": render("investor_wi_percent_display", ctx),
        "llg_field": render("llg_amount", ctx),
    }
    out = tmp_path / "filled.pdf"
    written = fill_template(acroform_pdf, field_values, out)

    assert written == out
    assert out.exists()
    assert out.stat().st_size > 0

    # Re-read and verify values landed
    reader = PdfReader(str(out))
    text_fields = reader.get_form_text_fields() or {}
    assert text_fields.get("investor_name_field") == "Roberto Almanza"
    assert text_fields.get("wi_field") == "5.000000%"
    assert text_fields.get("llg_field") == "$75,000.00"


def test_fill_template_missing_template(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        fill_template(tmp_path / "nope.pdf", {"x": "y"}, tmp_path / "out.pdf")
