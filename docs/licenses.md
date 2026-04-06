# WellSign — Dependency License Audit

> **Hard requirement:** WellSign is a commercial product (paid per-project license keys). **Every** dependency must permit redistribution in a closed-source commercial product. **No GPL** (without an exception clause), **no AGPL**, **no SSPL**, **no "non-commercial only" licenses**.
>
> Re-run this audit before adding any new dependency.

## Runtime dependencies (`pyproject.toml`)

| Package | License | Commercial OK? | Obligations |
|---|---|---|---|
| **PySide6** | **LGPL v3** + commercial (Qt) | ✅ with conditions | See PySide6 section below |
| `cryptography` | Apache 2.0 / BSD | ✅ | Include license text |
| `keyring` | MIT | ✅ | Include license text |
| `openpyxl` | MIT | ✅ | Include license text |
| `pypdf` | BSD-3-Clause | ✅ | Include license text |
| `pdfrw` | MIT | ✅ | Include license text |
| `reportlab` | BSD-3-Clause (open source edition) | ✅ | Include license text. The "ReportLab PLUS" commercial edition is NOT needed |
| `pywin32` | PSF-style | ✅ | Include license text |
| `platformdirs` | MIT | ✅ | Include license text |

## Dev / build dependencies (not redistributed in the .exe)

| Package | License | Commercial OK? | Notes |
|---|---|---|---|
| `pytest` | MIT | ✅ | Test only, not bundled |
| `pytest-qt` | MIT | ✅ | Test only |
| `ruff` | MIT | ✅ | Lint only |
| `mypy` | MIT | ✅ | Type-check only |
| **`pyinstaller`** | **GPL v2** + bootloader exception | ✅ | See PyInstaller section below |

## PySide6 — LGPL v3 compliance

PySide6 is licensed LGPL v3. **It is permitted for commercial closed-source use**, but you must comply with the LGPL's relinking and notice requirements:

1. **Dynamic linking only.** Python's `import PySide6` satisfies this — no static linking happens.
2. **Include the LGPL v3 license text** with the WellSign distribution. Drop it at `LICENSES/LGPL-3.0.txt`.
3. **State that WellSign uses PySide6 (LGPL v3)** in an "About" / "Licenses" dialog inside the app.
4. **Allow users to replace the bundled Qt libraries** with a different version (the LGPL "relinking" requirement). For PyInstaller, this means:
   - Use **one-folder mode** (`pyinstaller --onedir`), NOT `--onefile`. The PySide6 `.pyd` files must be distinguishable on disk so a user can swap them.
   - The current `wellsign.spec` should be set to `--onedir`. Verify before shipping.
   - Document in the About dialog: "PySide6 binaries can be replaced with a compatible LGPL version. See [link to LGPL compliance notes]."
5. **Provide LGPL source on request OR a written offer.** Easiest: link to the upstream PySide6 source on the Qt project site from the About dialog.
6. **Do NOT modify Qt source.** If you ever modify Qt, the modified version must be distributed under LGPL.

If LGPL obligations become a problem (e.g., a customer requires a sealed single-file `.exe` with no LGPL strings), the alternative is the **commercial Qt license** from The Qt Company. It's a paid per-developer or per-distribution license. Defer until/unless a customer demands it.

### Things NOT to use as a Qt alternative

- ❌ **PyQt6** — GPL v3 OR commercial-only. The free version is GPL, which would force WellSign to be GPL too. **Do not import PyQt6 anywhere.**

## PyInstaller — GPL + bootloader exception

PyInstaller is GPL v2, which would normally taint the bundled application. However, PyInstaller has an **explicit bootloader exception**:

> *"As a special exception, the PyInstaller team gives you unlimited permission to link or embed compiled bootloader and related files into combinations with other programs, and to distribute those combinations without being obliged to provide the source code for the bootloader and related files."*

This means a PyInstaller-packaged WellSign `.exe` is **NOT** subject to GPL. Standard practice. Include the PyInstaller license text in `LICENSES/` for completeness.

## Future dependencies — pre-add checklist

Before `pip install`-ing anything new, verify on PyPI / the project's GitHub:

1. **License field is permissive** (MIT, BSD, Apache 2.0, ISC, MPL 2.0, PSF, Unlicense, LGPL with relinking compliance).
2. **Reject:** GPL (any version, without an exception clause), AGPL, SSPL, BUSL, "non-commercial use only", "free for evaluation", "commercial license required".
3. **For LGPL deps:** confirm dynamic linking only and add to the LGPL compliance section above.
4. **For dual-licensed deps** (e.g. "GPL or commercial"): confirm whether you can use the GPL leg under WellSign's distribution model. Usually you can't, and you'd need to buy the commercial license.
5. Update this file with the new dependency, license, and any obligations.

## Proposed future dependencies (see [roadmap.md](roadmap.md))

These are NOT in `pyproject.toml` yet — listed here so the licensing decision is on the table when the time comes:

| Proposed | License | OK? | Why we'd want it |
|---|---|---|---|
| `docxtpl` | LGPL v2.1+ | ✅ with same compliance pattern as PySide6 | Word `.docx` template merging — Paloma maintains templates in Word, not PDF |
| `python-docx` | MIT | ✅ | Lower-level Word doc reading/writing |
| `docx2pdf` | MIT | ✅ | Convert filled `.docx` to PDF on Windows via Word COM (works with the existing `pywin32` dep) |
| `pandadoc-python-client` | MIT | ✅ | E-signature API integration |
| `requests` (transitive of above) | Apache 2.0 | ✅ | HTTP client |

## Distribution `LICENSES/` folder

When PyInstaller packaging happens, ship a `LICENSES/` folder alongside `wellsign.exe` containing:

- `LGPL-3.0.txt` (for PySide6)
- `MIT.txt`, `BSD-3-Clause.txt`, `Apache-2.0.txt`, `PSF.txt` (for the rest)
- `PyInstaller.txt` (the GPL + bootloader exception text, so the exception is visible)
- `THIRD_PARTY_NOTICES.txt` listing each dependency, its version, and which license file applies

The in-app "About → Licenses" dialog should display the same content.

## Open license questions

- Does the Qt commercial license make sense if we ever want to ship one-file `.exe`? Decision deferred until first commercial customer asks.
- Are we comfortable with the user-replaceable Qt requirement, or is that going to confuse non-technical operators? (Probably fine — the requirement is to *allow* it, not promote it.)
