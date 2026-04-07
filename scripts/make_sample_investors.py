"""Generate a sample investors.xlsx for testing the Excel import flow.

Run:

    python scripts/make_sample_investors.py

Writes ``sample_investors.xlsx`` to the repo root AND into ``dist/`` if that
directory exists, so the user can drag it onto the running exe.
"""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook


_HEADERS = [
    "First Name",
    "Last Name",
    "Entity Name",
    "Title",
    "Email",
    "Phone",
    "Address",
    "City",
    "State",
    "Zip",
    "WI %",
    "Payment Method",
    "Notes",
]

# WI% here is in "percentage number" form (5.0 = 5%). The import dialog
# auto-detects this and also lets the user override.
_ROWS = [
    ["Frank",    "Abernathy", None,                            "Owner",        "frank@abernathyoil.com",  "+1-210-555-0134", "812 Oak Dr",        "San Antonio", "TX", "78205", 8.0,  "wire",  "Long-time partner"],
    ["Helen",    "Borowski",  "Borowski Holdings LLC",          "Manager",      "hello@borowski.co",       "+1-713-555-0109", "2200 Post Oak Blvd","Houston",     "TX", "77056", 12.5, "wire",  None],
    [None,       None,        "Crestview Minerals Trust",       "Trustee",      "trust@crestviewmin.com",  "+1-432-555-0188", "1 Main St",         "Midland",     "TX", "79701", 18.0, "wire",  "Via Wells Fargo trust"],
    ["Diane",    "Escobar",   None,                             None,           "diane.escobar@gmail.com", "+1-512-555-0145", "910 Spruce St",     "Austin",      "TX", "78704", 6.25, "check", None],
    ["Garrett",  "Flannery",  None,                             "Operator",     "gflannery@example.com",   "+1-214-555-0177", "77 Cedar Ln",       "Dallas",      "TX", "75201", 3.75, "wire",  "Prefers email over phone"],
    [None,       None,        "Grand Harbor Partners LP",       "GP",           "ops@grandharbor.fund",    "+1-832-555-0122", "500 Louisiana",     "Houston",     "TX", "77002", 22.5, "wire",  "Per David — split the check 4 ways"],
    ["Ivan",     "Haverford", None,                             None,           "ivan@haverford.me",       "+1-830-555-0166", "45 Ranch Rd",       "New Braunfels","TX", "78130", 4.0,  "check", None],
    [None,       None,        "Jacobsen IRA Holdings",          "Custodian",    "custody@jacobsen-ira.com","+1-210-555-0190", "200 Plaza",         "San Antonio", "TX", "78216", 9.0,  "wire",  "Self-directed IRA"],
    ["Kira",     "Locksley",  None,                             None,           "klocksley@example.com",   "+1-361-555-0113", "18 Bay Vista",      "Corpus Christi","TX","78401", 5.5,  "wire",  None],
    [None,       None,        "Marlborough Family Trust",       "Trustee",      "tara@marlboroughtrust.us","+1-817-555-0170", "9 Hilltop Pl",      "Fort Worth",  "TX", "76102", 10.5, "wire",  "Send all docs to Tara"],
]


def main() -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Investors"
    ws.append(_HEADERS)
    for row in _ROWS:
        ws.append(row)

    # Column widths
    for col, width in enumerate(
        [12, 14, 32, 12, 32, 18, 22, 16, 8, 10, 10, 16, 40], start=1
    ):
        ws.column_dimensions[ws.cell(row=1, column=col).column_letter].width = width

    repo_root = Path(__file__).resolve().parent.parent
    out_paths = [repo_root / "sample_investors.xlsx"]
    dist = repo_root / "dist"
    if dist.exists():
        out_paths.append(dist / "sample_investors.xlsx")

    for p in out_paths:
        wb.save(p)
        print(f"Wrote {p}")

    total_wi = sum(row[10] for row in _ROWS)
    print(f"Total WI% in sample: {total_wi:.2f}%  ({len(_ROWS)} investors)")


if __name__ == "__main__":
    main()
