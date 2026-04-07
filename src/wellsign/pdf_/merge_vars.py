"""Canonical registry of system merge variables for PDF / email templates.

Every entry in ``MERGE_VARIABLES`` defines:
  * ``key``         — the variable name as it appears in templates and mappings
  * ``label``       — friendly label for the field-mapping editor UI
  * ``group``       — section heading in the editor (Investor / Project / Constants)
  * ``getter``      — callable(ctx) -> str that returns the formatted value

The getter takes a flat ``MergeContext`` (a typed dict-like) built by
``pdf_/fill.build_merge_context()`` from a project + investor pair.

The variable names are the contract — they're the same names used in PDF
field mappings, in email templates' ``{{double_curly}}`` substitutions, and
in the docs at ``docs/paloma-packet.md``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class MergeContext:
    # Investor side
    investor_first_name: str
    investor_last_name: str
    investor_entity: str
    investor_title: str
    investor_email: str
    investor_phone: str
    investor_address1: str
    investor_address2: str
    investor_city: str
    investor_state: str
    investor_zip: str
    investor_wi_fraction: float       # e.g. 0.01000000 for 1%
    investor_llg_amount: float
    investor_dhc_amount: float
    investor_payment_preference: str

    # Project side
    project_name: str
    prospect_name: str
    well_name: str
    operator_llc: str
    county: str
    state: str
    agreement_date: str
    close_deadline: str
    total_llg_cost: float
    total_dhc_cost: float


@dataclass(frozen=True)
class MergeVar:
    key: str
    label: str
    group: str
    getter: Callable[[MergeContext], str]


def _money(v: float) -> str:
    return f"${v:,.2f}"


def _name(ctx: MergeContext) -> str:
    if ctx.investor_entity:
        return ctx.investor_entity
    parts = [p for p in (ctx.investor_first_name, ctx.investor_last_name) if p]
    return " ".join(parts)


def _address_oneline(ctx: MergeContext) -> str:
    bits: list[str] = []
    if ctx.investor_address1:
        bits.append(ctx.investor_address1)
    if ctx.investor_address2:
        bits.append(ctx.investor_address2)
    city_state_zip = ", ".join([x for x in (ctx.investor_city, ctx.investor_state) if x])
    if ctx.investor_zip:
        city_state_zip = (city_state_zip + " " + ctx.investor_zip).strip()
    if city_state_zip:
        bits.append(city_state_zip)
    return ", ".join(bits)


def _county_state(ctx: MergeContext) -> str:
    if ctx.county and ctx.state:
        return f"{ctx.county} County, {ctx.state}"
    return ctx.county or ctx.state or ""


# ---------------------------------------------------------------------------
# The registry
# ---------------------------------------------------------------------------
MERGE_VARIABLES: list[MergeVar] = [
    # ---- Investor ----
    MergeVar("investor_name",          "Full name (entity if set, else first+last)", "Investor",
             _name),
    MergeVar("investor_first_name",    "First name", "Investor",
             lambda c: c.investor_first_name),
    MergeVar("investor_last_name",     "Last name", "Investor",
             lambda c: c.investor_last_name),
    MergeVar("investor_entity",        "Entity / LLC / trust name", "Investor",
             lambda c: c.investor_entity),
    MergeVar("investor_title",         "Signing title", "Investor",
             lambda c: c.investor_title),
    MergeVar("investor_email",         "Email", "Investor",
             lambda c: c.investor_email),
    MergeVar("investor_phone",         "Phone", "Investor",
             lambda c: c.investor_phone),
    MergeVar("investor_address",       "Address (one line)", "Investor",
             _address_oneline),
    MergeVar("investor_address1",      "Address line 1", "Investor",
             lambda c: c.investor_address1),
    MergeVar("investor_address2",      "Address line 2", "Investor",
             lambda c: c.investor_address2),
    MergeVar("investor_city",          "City", "Investor",
             lambda c: c.investor_city),
    MergeVar("investor_state",         "State", "Investor",
             lambda c: c.investor_state),
    MergeVar("investor_zip",           "Zip", "Investor",
             lambda c: c.investor_zip),
    MergeVar("investor_wi_percent",    "Working interest (8 dp, e.g. 0.01000000)", "Investor",
             lambda c: f"{c.investor_wi_fraction:.8f}"),
    MergeVar("investor_wi_percent_display", "Working interest (display, e.g. 1.000000%)", "Investor",
             lambda c: f"{c.investor_wi_fraction * 100:.6f}%"),
    MergeVar("llg_amount",             "LLG cash call ($, → Decker)", "Investor",
             lambda c: _money(c.investor_llg_amount)),
    MergeVar("dhc_amount",             "DHC cash call ($, → Paloma)", "Investor",
             lambda c: _money(c.investor_dhc_amount)),
    MergeVar("investor_payment_preference", "Payment preference (wire/check)", "Investor",
             lambda c: c.investor_payment_preference),

    # ---- Project ----
    MergeVar("project_name",           "Project name", "Project",
             lambda c: c.project_name),
    MergeVar("prospect_name",          "Prospect name", "Project",
             lambda c: c.prospect_name),
    MergeVar("well_name",              "Well name", "Project",
             lambda c: c.well_name),
    MergeVar("operator_name",          "Operator LLC", "Project",
             lambda c: c.operator_llc),
    MergeVar("county_state",           "County, State", "Project",
             _county_state),
    MergeVar("agreement_date",         "Agreement date", "Project",
             lambda c: c.agreement_date),
    MergeVar("close_deadline",         "Close deadline", "Project",
             lambda c: c.close_deadline),
    MergeVar("total_llg_cost",         "Project LLG total ($)", "Project",
             lambda c: _money(c.total_llg_cost)),
    MergeVar("total_dhc_cost",         "Project DHC total ($)", "Project",
             lambda c: _money(c.total_dhc_cost)),

    # ---- Constants ----
    MergeVar("payee_c1",               "C-1 payee (always Decker)", "Constants",
             lambda _c: "Decker Exploration, Inc."),
    MergeVar("payee_c2",               "C-2 payee (always operator / Paloma)", "Constants",
             lambda c: c.operator_llc),
]


MERGE_VARS_BY_KEY: dict[str, MergeVar] = {v.key: v for v in MERGE_VARIABLES}


def render(key: str, ctx: MergeContext) -> str:
    """Resolve a single merge variable. Unknown keys return an empty string."""
    var = MERGE_VARS_BY_KEY.get(key)
    if var is None:
        return ""
    try:
        return var.getter(ctx) or ""
    except Exception:
        return ""


def render_template(text: str, ctx: MergeContext) -> str:
    """Substitute every ``{{key}}`` placeholder in ``text`` with its rendered value.

    Used by email subject + body rendering. PDF templates use a different
    mechanism (AcroForm field mapping → see ``pdf_/fill.py``).

    Unknown keys are replaced with an empty string. Whitespace inside the
    braces is tolerated: ``{{ key }}`` and ``{{key}}`` both work.
    """
    if not text:
        return text
    import re

    def _sub(match: "re.Match[str]") -> str:
        key = match.group(1).strip()
        return render(key, ctx)

    return re.sub(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}", _sub, text)


def all_keys() -> list[str]:
    return [v.key for v in MERGE_VARIABLES]


def grouped() -> dict[str, list[MergeVar]]:
    """Return variables grouped by section, preserving registry order."""
    out: dict[str, list[MergeVar]] = {}
    for v in MERGE_VARIABLES:
        out.setdefault(v.group, []).append(v)
    return out


# ---------------------------------------------------------------------------
# Smart-map: heuristic PDF-field-name → merge-variable-key matching
# ---------------------------------------------------------------------------
# For each merge variable key, we list a handful of common aliases that real
# PDF templates use for that concept. The matcher normalises both sides
# (lowercase, strip non-alphanumerics) and then tries:
#   1. Exact normalised match against an alias
#   2. Exact normalised match against the merge variable key itself
#   3. Longest substring overlap with any alias
#
# Hand-curated and conservative — when in doubt, return None.
_AUTO_MATCH_ALIASES: dict[str, list[str]] = {
    "investor_name":          ["name", "investor", "investorname", "fullname", "client", "clientname", "subscriber"],
    "investor_first_name":    ["first", "firstname", "fname", "given", "givenname"],
    "investor_last_name":     ["last", "lastname", "lname", "surname", "family", "familyname"],
    "investor_entity":        ["entity", "entityname", "company", "companyname", "llc", "trust", "ira", "fund", "partnership"],
    "investor_title":         ["title", "position", "role", "signingtitle", "signertitle"],
    "investor_email":         ["email", "emailaddress", "mail", "contactemail"],
    "investor_phone":         ["phone", "phonenumber", "telephone", "cell", "mobile", "tel", "contactphone"],
    "investor_address":       ["address", "fulladdress", "mailingaddress"],
    "investor_address1":      ["address1", "addressline1", "street", "streetaddress", "addr1", "line1"],
    "investor_address2":      ["address2", "addressline2", "addr2", "line2", "apt", "suite", "unit", "ste"],
    "investor_city":          ["city", "town"],
    "investor_state":         ["state", "province", "investorstate"],
    "investor_zip":           ["zip", "zipcode", "postal", "postalcode", "postcode"],
    "investor_wi_percent":    ["wi", "wipct", "wipercent", "workinginterest", "wifraction", "interest", "interestpct"],
    "investor_wi_percent_display": ["widisplay", "interestdisplay", "wipctdisplay"],
    "llg_amount":             ["llg", "llgamount", "leaseholdcost", "deckeramount", "c1", "c1amount", "cashcall1"],
    "dhc_amount":             ["dhc", "dhcamount", "dryholecost", "palomaamount", "c2", "c2amount", "cashcall2"],
    "investor_payment_preference": ["payment", "paymentmethod", "paymentpref", "wireorcheck", "method"],
    "project_name":           ["project", "projectname"],
    "prospect_name":          ["prospect", "prospectname", "play", "playname"],
    "well_name":              ["well", "wellname", "wellbore"],
    "operator_name":          ["operator", "operatorname", "operatorllc", "operatingcompany"],
    "county_state":           ["countystate", "location", "countyandstate"],
    "agreement_date":         ["agreement", "agreementdate", "execdate", "executiondate", "effective", "effectivedate"],
    "close_deadline":         ["close", "closedeadline", "closingdate", "closing", "deadline", "duedate", "dueby"],
    "total_llg_cost":         ["totalllg", "totalleasehold", "llgtotal", "leaseholdtotal"],
    "total_dhc_cost":         ["totaldhc", "totaldryhole", "dhctotal", "dryholetotal"],
    "payee_c1":               ["c1payee", "deckerpayee", "leaseholdpayee"],
    "payee_c2":               ["c2payee", "operatorpayee", "dryholepayee"],
}


def _normalize_name(s: str) -> str:
    return "".join(c for c in (s or "").lower() if c.isalnum())


def auto_match_field(pdf_field_name: str) -> str | None:
    """Guess the best merge variable key for a PDF form field name.

    Returns the matched key, or ``None`` if no confident match could be made.
    Used by the field-mapping dialog's Smart Map button.

    Strategy:
      1. Exact match against any alias (any length)
      2. Exact match against a merge variable key itself
      3. Substring overlap — but only if the input has more than 3
         characters, to avoid 2-char field names like ``St`` matching
         the substring of every long alias.
    """
    norm = _normalize_name(pdf_field_name)
    if not norm:
        return None

    # 1. Exact match against any alias
    for var_key, aliases in _AUTO_MATCH_ALIASES.items():
        for alias in aliases:
            if _normalize_name(alias) == norm:
                return var_key

    # 2. Exact match against the merge variable key itself
    for k in MERGE_VARS_BY_KEY:
        if _normalize_name(k) == norm:
            return k

    # 3. Substring overlap — only for inputs of meaningful length
    if len(norm) <= 3:
        return None

    best_key: str | None = None
    best_len = 0
    for var_key, aliases in _AUTO_MATCH_ALIASES.items():
        for alias in aliases:
            na = _normalize_name(alias)
            if len(na) < 4:
                continue  # avoid noisy 1-3 char alias matches in substring mode
            if na in norm or norm in na:
                # Score by the length of the alias — prefer longer, more specific aliases
                if len(na) > best_len:
                    best_len = len(na)
                    best_key = var_key
    return best_key


def auto_match_all(pdf_field_names: list[str]) -> dict[str, str]:
    """Run auto_match_field over a batch — returns ``{pdf_field: merge_key}`` only for matches."""
    out: dict[str, str] = {}
    for name in pdf_field_names:
        match = auto_match_field(name)
        if match:
            out[name] = match
    return out
