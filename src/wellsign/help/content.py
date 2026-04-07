"""In-app help content registry.

One entry per topic key. The body is HTML — rendered into a QTextBrowser
by ``ui/dialogs/help_dialog.py``. We use HTML directly (no markdown
dependency) so the package ships clean through PyInstaller.

To add help for a new tab/page: add a new entry below and call
``HelpButton("topic_key")`` from the tab's header layout.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HelpTopic:
    key: str
    title: str
    body_html: str


# ---------------------------------------------------------------------------
# Topic content
# ---------------------------------------------------------------------------

_PROJECT_SETUP = """
<h2>Project Setup</h2>
<p>The configuration panel for the active well project. Everything every
other tab needs (totals, dates, parties) is set here.</p>

<h3>The phase banner</h3>
<p>The colored bar at the top shows where this project sits in its lifecycle:</p>
<ul>
  <li><b>Prospect Generation</b> — geological evaluation, no investors yet</li>
  <li><b>Outreach</b> — pitching the deal to existing relationships</li>
  <li><b>Subscription</b> — collecting signed legal documents</li>
  <li><b>Cash Call</b> — collecting LLG to Decker + DHC to the operator</li>
  <li><b>Drilling</b> — well is being drilled, track AFE actuals on the Costs tab</li>
  <li><b>Plugged &amp; Abandoned</b> — dry hole, refund unspent capital</li>
  <li><b>Completion</b> — producible well, supplemental cash call needed</li>
</ul>
<p>Use <b>Advance →</b> to move to the next phase. After Drilling there's a
fork — you choose Plugged &amp; Abandoned or Completion. <b>Set Phase…</b> lets
you jump to any phase manually if you need to fix a mistake.</p>

<h3>The summary card</h3>
<p>Read-only display of every editable field. Click <b>Edit Project…</b> to
open a dialog and change anything except the license binding (which is
fixed at creation) and the workflow assignment (which would orphan
existing investor stage runs).</p>

<h3>Editable fields</h3>
<ul>
  <li><b>Project name</b> — what shows up in the navigator</li>
  <li><b>Prospect name</b> — the geological play (e.g. Highlander Prospect)</li>
  <li><b>Well name</b> — the specific well (e.g. Pargmann-Gisler #1)</li>
  <li><b>Operator LLC</b> — the operating company on the JOA</li>
  <li><b>County / State</b> — the well location (drives the JOA legal description)</li>
  <li><b>Agreement date</b> — when the PA is dated</li>
  <li><b>Close deadline</b> — when all docs and money are due back. Drives the
      Burndown chart and the Payments tab "overdue" status.</li>
  <li><b>Total LLG cost (→ Decker)</b> — total leasehold/geological cost. Each
      investor's LLG cash call is <code>WI% × this</code>.</li>
  <li><b>Total DHC cost (→ Paloma)</b> — total dry-hole/drilling cost. Each
      investor's DHC cash call is <code>WI% × this</code>.</li>
</ul>

<h3>Test mode banner</h3>
<p>If a yellow <b>TEST PROJECT</b> banner appears at the top of this tab,
this project is flagged as test data. Outlook sends will be saved to
Drafts only and any costs/payments are mock. Use this for training and
to verify the workflow before running it on a real well.</p>
"""

_INVESTORS = """
<h2>Investors</h2>
<p>The list of every working interest partner on this project. Add them
one at a time with <b>+ Add Investor</b> or bulk-load from a spreadsheet
with <b>Import from Excel…</b></p>

<h3>The summary line</h3>
<p>The header strip shows three numbers you should always glance at:</p>
<ul>
  <li><b>Investor count</b> — how many partners on the deal</li>
  <li><b>WI sum</b> — must total <b>100.000000%</b> for the cash call math
      to add up. Yellow = doesn't match yet, green = exactly 100%.</li>
  <li><b>LLG total</b> / <b>DHC total</b> — running totals of each investor's
      computed cash call amount. Should match the project totals on the
      Project Setup tab within $0.10.</li>
</ul>

<h3>The traffic-light dot</h3>
<p>The first column shows where each investor sits in their workflow:</p>
<ul>
  <li>🟢 <b>Green</b> — in stage, within SLA</li>
  <li>🟡 <b>Yellow</b> — in stage, ≤ 3 days remaining on the SLA</li>
  <li>🔴 <b>Red</b> — overdue past SLA</li>
  <li>⚪ <b>Grey</b> — no active stage run yet</li>
</ul>
<p>Hover the dot to see the full status string ("Subscription — 12d left" or
"Cash Call — 4d overdue").</p>

<h3>Adding an investor</h3>
<p>Click <b>+ Add Investor</b> to open the editor. The dialog has tabs for
Identity, Address, Investment, and Banking &amp; PII. The Investment tab is
where you set <b>WI %</b> and the LLG/DHC dollar amounts auto-compute live
as you type. The Banking &amp; PII tab encrypts everything (SSN, EIN, bank
routing, account number) at the application layer with AES-256-GCM
before writing to the database.</p>

<p>When you save a new investor, WellSign automatically:</p>
<ul>
  <li>Creates the investor folder on disk for sent/received documents</li>
  <li>Inserts an LLG and a DHC payment row in the Payments tab</li>
  <li>Starts the project's workflow at stage 1 (the traffic light goes green)</li>
</ul>

<h3>Editing an investor</h3>
<p>Double-click any row to open the same editor in edit mode. Changes to
WI% will recompute the cash call amounts AND refresh the unreceived
expected amounts on the Payments tab. Already-received payments are
preserved — historical facts don't get rewritten by a WI tweak.</p>

<h3>Excel import</h3>
<p><b>Import from Excel…</b> opens a column-mapping dialog. You drop a
.xlsx file (see <code>sample_investors.xlsx</code> for the format), pick
which spreadsheet column maps to which investor field, preview the
parsed rows, fix any WI% sum issues, and bulk-insert.</p>
"""

_DOCUMENTS = """
<h2>Documents</h2>
<p>The packet generator. Takes the project's document templates (set up
in <b>Templates → Document templates</b>) and produces a filled PDF for
every (investor × template) pair, with merge variables substituted.</p>

<h3>How packet generation works</h3>
<ol>
  <li>For each investor, WellSign builds a <b>merge context</b> — name,
      address, WI%, LLG amount, DHC amount, project info, etc.</li>
  <li>For each document template with a <b>field mapping</b> set, the
      system reads the PDF's AcroForm fields, looks up each one in the
      mapping, and writes the resolved merge value into it.</li>
  <li>The filled PDF is saved under
      <code>%APPDATA%/WellSign/projects/&lt;project&gt;/investors/&lt;investor&gt;/sent/</code>
      with a <code>&lt;doc_type&gt;_&lt;template_name&gt;_&lt;timestamp&gt;.pdf</code> filename.</li>
  <li>An <code>investor_documents</code> row is inserted with status
      <b>generated</b> so the Status tab and Send tab can find it.</li>
</ol>

<h3>+ Generate Packets</h3>
<p>The big button. Loops every investor × every mapped template, fills,
saves, records. Templates without a field mapping are skipped (you'll
see a warning). Templates whose source PDF is missing on disk are also
skipped with an error.</p>

<h3>Regenerate All</h3>
<p>Wipes every <code>investor_documents</code> row for this project (in the DB
only — files on disk are NOT deleted) and rebuilds from scratch. Use
this after editing template field mappings or after a cash call amount
changes.</p>

<h3>The table</h3>
<p>Every generated PDF on disk for this project. Columns: investor name,
doc type, template name, file name, generation timestamp. Double-click
any row to open the file in your default PDF viewer.</p>

<h3>Common workflow</h3>
<ol>
  <li>Add investors on the Investors tab</li>
  <li>Set total LLG and DHC costs on the Project Setup tab</li>
  <li>Make sure document templates have field mappings (Templates →
      Document templates → Map Fields…)</li>
  <li>Click <b>+ Generate Packets</b></li>
  <li>Spot-check a few PDFs by double-clicking them</li>
  <li>Move to the Send tab to email them out</li>
</ol>
"""

_SEND = """
<h2>Send</h2>
<p>The pending email queue for this project. Shows every email that's
due (or about to be due) to go out, based on each investor's current
workflow stage and the wait_days configured on the stage's email
templates.</p>

<h3>The queue</h3>
<p>One row per (investor, email template) pair where the investor has
an active stage run AND the email hasn't already been sent. Status dot
colors:</p>
<ul>
  <li>🔴 <b>Overdue</b> — past due_at, you should send today</li>
  <li>🟠 <b>Due</b> — due now or in the next 2 days</li>
  <li>⚫ <b>Upcoming</b> — due more than 2 days from now</li>
</ul>
<p>Subject and body are pre-rendered with merge variables substituted —
the operator sees the real values (e.g. <i>"Highlander Prospect — Investor
Documents for Roberto Almanza"</i>), not <code>{{template}}</code>
placeholders.</p>

<h3>The preview pane</h3>
<p>Click any row to see the rendered email body on the right. The
subject appears in bold above the body. The body is full HTML — exactly
what Outlook will render.</p>

<h3>Send via Outlook</h3>
<p>The main button. Opens your local Outlook (via COM) and builds a new
MailItem with:</p>
<ul>
  <li>Recipient = the investor's email address</li>
  <li>Subject = the rendered subject line</li>
  <li>HTML body = the rendered body</li>
  <li>Attachments = every generated PDF for this investor (from the
      Documents tab)</li>
</ul>
<p>By default the email is <b>saved to your Outlook Drafts folder</b>
(not sent immediately) so you can review every email before it goes
out. Open Outlook to find it in Drafts, double-check the recipient, and
click Send.</p>
<p>The button is greyed out if Outlook isn't installed or pywin32 isn't
available — in that case, use Mark as Sent to log the manual send and
fall back to your normal email workflow.</p>

<h3>Mark as Sent</h3>
<p>Records the email as sent without going through Outlook. Use this
when you sent the email manually outside of WellSign (cold call from
your phone, or before you had WellSign installed) and just want it
suppressed from the queue.</p>

<h3>Why it disappears after sending</h3>
<p>Both Send via Outlook and Mark as Sent write a row to the
<code>send_events</code> table. Next time the queue refreshes, the
<code>compute_pending_sends</code> function filters out any
(investor, template) pair that already has a successful send event,
so the row is gone.</p>
"""

_STATUS = """
<h2>Status</h2>
<p>Per-investor dashboard showing where each partner sits in the
workflow right now. This is the operator's morning view: <i>"who do I
need to chase today?"</i></p>

<h3>The columns</h3>
<ul>
  <li><b>● Traffic light</b> — green / yellow / red / grey, same rules as
      the Investors tab</li>
  <li><b>Investor / Entity</b> — display name and signing entity</li>
  <li><b>Stage</b> — which workflow stage they're currently in (Outreach,
      Subscription, Cash Call, etc.)</li>
  <li><b>Days In</b> — how long they've been in the current stage</li>
  <li><b>SLA</b> — how long the stage is supposed to take</li>
  <li><b>Remaining</b> — days left before they're overdue. Negative =
      already overdue.</li>
  <li><b>Next Email</b> — the next email template that's due to go out
      to this investor (with "due today", "in 3d", or "overdue 5d")</li>
  <li><b>Status</b> — full traffic-light label</li>
</ul>

<h3>Sorting</h3>
<p>Click any column header to sort. Common moves:</p>
<ul>
  <li>Sort by <b>Remaining</b> ascending → most-overdue first</li>
  <li>Sort by <b>Stage</b> → group by where investors are in the pipeline</li>
  <li>Sort by <b>Next Email</b> → see who's due to be contacted today</li>
</ul>

<h3>Summary bar</h3>
<p>The top strip shows counts: <i>N on track · M warning · K overdue · J
not started · total</i>. Glance at this number every morning — if "K
overdue" is greater than zero, the Send tab almost certainly has work
for you.</p>

<h3>Status vs Payments vs Reconcile</h3>
<p>Three tabs answer three different questions:</p>
<ul>
  <li><b>Status</b> — workflow stage progress (where each investor is)</li>
  <li><b>Payments</b> — money in (per investor LLG/DHC tracking)</li>
  <li><b>Reconcile</b> — money math (raised vs spent, refunds vs supplementals)</li>
</ul>
"""

_COSTS = """
<h2>Costs (AFE Budget vs Actuals)</h2>
<p>The operator's well-cost ledger. <b>This is what you SPEND</b> — drilling,
casing, frac, equipment. The Payments tab tracks what you COLLECT from
investors. The Reconcile tab does the math between the two.</p>

<h3>Line items</h3>
<p>Each row is a single budget line. Categories are O&amp;G-typical
(Drilling, Casing, Mud / Fluids, Cement, Logging, Completion, Permits,
Surveying, etc.) but the field is free text so you can add anything.</p>
<p>Each line has:</p>
<ul>
  <li><b>Phase group</b> — pre-drilling / drilling / completion / facilities / soft costs</li>
  <li><b>Tax class</b> — intangible (IDC, deductible) / tangible (TDC,
      depreciable) / mixed. Drives the K-1 export later.</li>
  <li><b>Expected (AFE)</b> — what you budgeted</li>
  <li><b>Actual</b> — what you actually spent (blank until you have an invoice)</li>
  <li><b>Vendor</b> — who you paid</li>
  <li><b>Invoice number</b> — for matching invoices to the line</li>
  <li><b>Status</b> — planned → committed → invoiced → paid</li>
  <li><b>Notes</b> — free text</li>
</ul>

<h3>Variance coloring</h3>
<p>The Variance column shows <code>actual − expected</code>:</p>
<ul>
  <li><b style="color:#d1242f;">Red (over budget)</b> — costs more than you AFE'd</li>
  <li><b style="color:#1a7f37;">Green (under budget)</b> — costs less than you AFE'd</li>
  <li><b>—</b> — no actual logged yet</li>
</ul>

<h3>Receipts</h3>
<p>Select a row and click <b>📎 Attach Receipt</b> to attach an invoice
PDF or image. The file is copied into
<code>projects/&lt;project&gt;/costs/&lt;line_id&gt;/</code>, hashed (SHA-256), and
recorded in the database. The Receipts column shows the count.</p>

<h3>The totals strip</h3>
<p>Bottom of the tab. Shows running Expected, Actual, Variance, and total
Receipts count. This number flows into the <b>Reconcile</b> tab where it
becomes "total spent" in the surplus/shortfall calculation.</p>

<h3>Common workflow</h3>
<ol>
  <li>At the start of drilling, enter every line you AFE'd</li>
  <li>As invoices come in, edit the line and fill in Actual + vendor + invoice #
      + flip status to invoiced</li>
  <li>When you pay the invoice, flip status to paid (paid_at is auto-stamped)</li>
  <li>Attach the invoice PDF as a receipt</li>
  <li>At end of drilling, check the Reconcile tab for the surplus / shortfall
      verdict</li>
</ol>
"""

_PAYMENTS = """
<h2>Payments (Incoming Money Tracking)</h2>
<p>The operator's daily dashboard for incoming money from investors.
<b>This is what you COLLECT</b> — every wire and check. The Costs tab
tracks what you SPEND. The Reconcile tab does the math.</p>

<h3>The data model</h3>
<p>Two payment rows per investor: one for <b>LLG</b> (paid to Decker
Exploration) and one for <b>DHC</b> (paid to the operator). They're
created automatically when you add or import an investor — you don't
need to seed them manually.</p>
<p>Expected amounts are computed from the investor's <code>llg_amount</code>
and <code>dhc_amount</code> (= WI% × project totals). When you change an
investor's WI%, unreceived payment rows refresh automatically. Already-
received rows are preserved — historical facts don't get rewritten.</p>

<h3>The status colors</h3>
<ul>
  <li><b>● Expected</b> — no payment received yet</li>
  <li><b>● Partial</b> — received less than expected</li>
  <li><b>● Received</b> — received in full (or more)</li>
  <li><b>● Overdue</b> — past close_deadline and not yet received. Auto-flipped
      every time you open this tab.</li>
</ul>

<h3>The filter dropdown</h3>
<ul>
  <li><b>All payments</b> — every row</li>
  <li><b>Outstanding only</b> — Expected + Partial + Overdue (= "what do I
      still need to collect")</li>
  <li><b>Received only</b> — closed business</li>
  <li><b>Overdue only</b> — pure overdue work</li>
</ul>

<h3>Marking a payment received</h3>
<p>Double-click a row (or select it and click <b>Mark Received…</b>) to
open the payment dialog. Enter:</p>
<ul>
  <li><b>Amount received</b> — defaults to the expected amount, just hit
      Save in the common case</li>
  <li><b>Date received</b> — when the wire/check actually hit the bank</li>
  <li><b>Method</b> — wire or check</li>
  <li><b>Reference number</b> — wire confirmation # or check #</li>
  <li><b>Notes</b> — free text</li>
</ul>
<p>Status auto-derives from the amount delta:</p>
<ul>
  <li>received_amount ≥ expected → <b>Received</b></li>
  <li>0 &lt; received_amount &lt; expected → <b>Partial</b> (needs follow-up)</li>
  <li>0 → <b>Expected</b> (cleared)</li>
</ul>
<p><b>Clear / Reset</b> wipes the received fields and puts the row back
to Expected. Use this only for data entry mistakes — it's destructive.</p>

<h3>The variance column</h3>
<p>Shows <code>received − expected</code>:</p>
<ul>
  <li><b style="color:#1a7f37;">Green positive</b> — they paid more than
      expected (sometimes happens with wire fees)</li>
  <li><b style="color:#d1242f;">Red negative</b> — short, follow up</li>
</ul>

<h3>The totals strip</h3>
<p>Bottom of the tab — three groups:</p>
<ul>
  <li><b>LLG (→ Decker)</b> — received vs expected, with outstanding</li>
  <li><b>DHC (→ Paloma)</b> — received vs expected, with outstanding</li>
  <li><b>Total collected</b> — overall, with outstanding</li>
</ul>
<p>If "outstanding" is amber, you still have money to collect. If green,
you're fully funded.</p>
"""

_RECONCILE = """
<h2>Reconcile (End-of-Drilling Math)</h2>
<p>The end-of-drilling surplus/shortfall calculator. Compares total
raised from investors against total actual cost from the Costs tab,
then splits the variance pro-rata by working interest to produce a
per-investor refund (surplus) or supplemental cash-call amount
(shortfall).</p>

<h3>The summary card</h3>
<p>Three numbers at the top:</p>
<ul>
  <li><b>Raised</b> — total received from investors (sum of received_amount
      from the Payments tab)</li>
  <li><b>Actual</b> — total actual cost (sum of actual_amount from the
      Costs tab)</li>
  <li><b>Variance</b> — Raised − Actual</li>
</ul>
<p>Plus a verdict:</p>
<ul>
  <li><b style="color:#1a7f37;">SURPLUS</b> — collected more than you spent.
      Refund the difference to investors.</li>
  <li><b style="color:#d1242f;">SHORTFALL</b> — spent more than you collected.
      Issue a supplemental cash call.</li>
  <li><b style="color:#1f6feb;">ON TARGET</b> — within $1.00 either way.
      Nothing to do.</li>
  <li><b>INCOMPLETE</b> — you don't have actuals on every cost line yet.
      Wait until drilling closes out.</li>
</ul>

<h3>The per-investor table</h3>
<p>Each row shows what one investor owes or is owed:</p>
<ul>
  <li><b>Investor</b> / <b>Entity</b> / <b>WI %</b> — identification</li>
  <li><b>Contributed</b> — what they actually paid in (LLG + DHC received)</li>
  <li><b>Share</b> — their pro-rata share of the variance, computed as
      <code>WI% × variance</code></li>
  <li><b>Action</b> — Refund (surplus) or Supplemental call (shortfall)</li>
  <li><b>Amount</b> — the dollar value</li>
</ul>

<h3>What it does NOT do (yet)</h3>
<ul>
  <li>It does not generate actual refund payments or supplemental cash
      call PDFs — that's a follow-up. This tab is the math view.</li>
  <li>It does not handle non-uniform splits (where one investor opted
      out of a supplemental). Per-investor election tracking is on the
      roadmap.</li>
</ul>

<h3>When to use it</h3>
<p>After drilling has wrapped and the Costs tab shows actuals on every
line. The verdict tells you whether the project comes out ahead or
needs more capital. If shortfall, use the per-investor amounts to
prepare supplemental cash call documents (manual for now).</p>
"""

_ACTIVITY = """
<h2>Activity</h2>
<p>Project-wide chronological event timeline. Pulls together every
persistence point in the system into one ordered feed so you can see
exactly what happened when, and to whom.</p>

<h3>Event types</h3>
<ul>
  <li>✉ <b>Email</b> — pulled from <code>send_events</code>. "Email sent
      to X" with the subject line.</li>
  <li>📄 <b>Document</b> — pulled from <code>investor_documents</code>.
      "Document generated for X" or "Signed document received from X".</li>
  <li>📜 <b>Stage</b> — pulled from <code>investor_stage_runs</code>.
      "X entered Subscription stage" or "X completed Cash Call stage".</li>
  <li>💰 <b>Payment</b> — pulled from <code>payments.received_at</code>.
      "Payment received from X — $4,000.00 LLG via wire".</li>
  <li>🚩 <b>Phase</b> — pulled from <code>projects.phase_entered_at</code>.
      "Project entered Drilling phase".</li>
  <li>💵 <b>Cost</b> — pulled from <code>cost_line_items.updated_at</code>
      where actual_amount was set. "Actual cost logged: $193,200 to
      Patterson-UTI".</li>
</ul>

<h3>Sort order</h3>
<p>Most-recent first. The top of the table is "what happened today",
the bottom is "where this project started".</p>

<h3>The filter dropdown</h3>
<p>Restrict to a single event type. Common moves:</p>
<ul>
  <li><b>Emails only</b> — see exactly what went out and when</li>
  <li><b>Payments only</b> — chronological cash-in log</li>
  <li><b>Stage events only</b> — workflow timeline</li>
</ul>

<h3>Click actions</h3>
<p>Some events are clickable:</p>
<ul>
  <li>Click a Document event → opens the file in your default PDF viewer</li>
  <li>Click an Email event → shows the rendered subject + body in a dialog</li>
</ul>

<h3>Why this matters</h3>
<p>For Reg D defensibility (see <code>regd-compliance.md</code>) you need
to be able to reconstruct exactly what happened on a deal. The Activity
tab is the operator-facing forensic tool. The deeper backstop is the
append-only <code>audit_log</code> table which the SQL triggers prevent
from ever being modified.</p>
"""

_BURNDOWN = """
<h2>Burndown</h2>
<p>Classic project-management burndown chart for the subscription
phase. Plots outstanding investors over time against the close
deadline so you can see at a glance whether you're going to make it.</p>

<h3>The lines</h3>
<ul>
  <li><b>Ideal (grey dashed)</b> — straight diagonal from your starting
      investor count down to zero at the close deadline. The path you'd
      be on if you closed one investor per equal slice of the timeline.</li>
  <li><b>Outstanding (blue)</b> — actual outstanding investors over time.
      Drops as each investor moves to a closed state.</li>
  <li><b>Today (red dot)</b> — exactly where you are right now.</li>
</ul>

<h3>Reading the chart</h3>
<ul>
  <li><b>Red dot above the grey line</b> → you're behind schedule</li>
  <li><b>Red dot below the grey line</b> → you're ahead of schedule</li>
  <li><b>Red dot on the line</b> → on track</li>
</ul>
<p>The status text below the chart says it in plain English: "Behind —
4 outstanding, ideal would be 1.7 by today" or "On track".</p>

<h3>What counts as "outstanding"</h3>
<p>Any investor whose traffic light is NOT grey (i.e., they have an
active stage run and haven't completed all stages). When their workflow
finishes, they drop out of the count and the line steps down.</p>

<h3>Setup requirements</h3>
<p>The chart needs <code>agreement_date</code> and <code>close_deadline</code>
to be set on the project. If either is missing, you'll see "Set
agreement_date and close_deadline on the project to see the chart".
Fix it on the Project Setup tab via Edit Project…</p>
"""

_DASHBOARD = """
<h2>Dashboard (All Projects)</h2>
<p>The cross-project view shown when "Projects" is selected in the
left navigator. Every project the operator has created, side-by-side,
in one table.</p>

<h3>Columns</h3>
<ul>
  <li><b>Project</b> — display name (matches what's in the navigator)</li>
  <li><b>Well</b> — well name (e.g. Pargmann-Gisler #1)</li>
  <li><b>Region</b> — county / state</li>
  <li><b>Customer</b> — license customer the project was issued to</li>
  <li><b>Status</b> — project lifecycle status (draft / active / closed /
      archived)</li>
  <li><b>Investors</b> — count of investors on the project</li>
  <li><b>Created</b> — date the project was created</li>
</ul>

<h3>+ New Project</h3>
<p>Top right. Opens the New Project dialog where you paste your
<code>.wslicense</code> file, fill in name / region / well / workflow,
and create. Each new project requires a license token issued by
WellSign — without one, you can't create a project.</p>

<h3>Drill into a project</h3>
<p>Click any project in the left navigator (NOT in this table) to open
its workspace. The right pane swaps to the per-project tabbed view.</p>
"""

_DOC_TEMPLATES = """
<h2>Document Templates</h2>
<p>The global library of reusable PDF templates. Set up each template
once, map its form fields to system merge variables once, and reuse
across every project.</p>

<h3>The table</h3>
<p>Every template you've ever created. Columns: name, doc type, page
size, notary required, storage path. Double-click any row to edit it.</p>

<h3>+ New Document Template</h3>
<p>Opens the new-template dialog. You provide:</p>
<ul>
  <li><b>Name</b> — what shows up in the templates table and on the
      Documents tab generation list</li>
  <li><b>Document type</b> — joa, pa, cash_call_c1, cash_call_c2,
      info_sheet, w9, wiring, other. Drives the routing logic (e.g. C-1
      always pays Decker, C-2 always pays the operator)</li>
  <li><b>Page size</b> — letter or legal (the JOA is legal-size)</li>
  <li><b>Notary required</b> — flag for the JOA</li>
  <li><b>PDF file</b> — browse to a blank PDF that already has form
      fields. WellSign reads the field names and shows them in the
      preview list at the bottom of the dialog.</li>
</ul>
<p>The PDF is copied into <code>%APPDATA%/WellSign/templates/documents/</code>
and given a UUID filename so multiple templates can have the same
display name without conflict.</p>

<h3>Map Fields…</h3>
<p>Once a template has a PDF, click <b>Map Fields…</b> to open the
field-mapping editor. Two columns:</p>
<ul>
  <li><b>Left</b> — every AcroForm field discovered in the PDF</li>
  <li><b>Right</b> — every system merge variable, grouped by Investor /
      Project / Constants</li>
</ul>
<p>Pick a field on the left, then double-click a variable on the right
(or hit <b>Bind →</b>) to assign it. The current binding is shown
inline. Hit <b>Save Mapping</b> to persist as JSON in the template's
<code>field_mapping</code> column.</p>

<h3>Required for packet generation</h3>
<p>Templates without a field mapping are SKIPPED by the Documents tab's
<b>+ Generate Packets</b> button (with a warning). You must map every
template you want filled before you can generate packets.</p>

<h3>How merge variables work at fill time</h3>
<p>For each (investor, template) pair, WellSign:</p>
<ol>
  <li>Builds a merge context (investor name, address, WI%, dollars,
      project info)</li>
  <li>Walks the template's field mapping</li>
  <li>For each PDF field in the mapping, looks up the merge variable
      and writes the rendered value into the field</li>
  <li>Writes the filled PDF to the investor's sent/ folder</li>
</ol>
"""

_EMAIL_TEMPLATES = """
<h2>Email Templates</h2>
<p>The global library of reusable email subject + body templates with
merge variable substitution. Set up the message once, attach it to a
workflow stage with a wait_days delay, and let WellSign queue it up.</p>

<h3>The table</h3>
<p>Every email template you've ever created. Columns: name, purpose,
subject, created date. Double-click to edit.</p>

<h3>+ New Email Template</h3>
<ul>
  <li><b>Name</b> — what shows up in pickers and on the Send tab queue</li>
  <li><b>Purpose</b> — invitation, reminder, thank_you, custom. Just for
      categorization in the templates list.</li>
  <li><b>Subject</b> — supports merge variables like
      <code>{{prospect_name}} — Investor Documents for {{investor_name}}</code></li>
  <li><b>Body</b> — full HTML, also supports merge variables in
      <code>{{double_curly}}</code> syntax</li>
</ul>

<h3>Available merge variables</h3>
<p>The same variables work in both PDF templates and email templates.
The big ones are:</p>
<ul>
  <li><code>{{investor_first_name}}</code>, <code>{{investor_name}}</code>,
      <code>{{investor_entity}}</code></li>
  <li><code>{{prospect_name}}</code>, <code>{{well_name}}</code>,
      <code>{{county_state}}</code></li>
  <li><code>{{investor_wi_percent_display}}</code> (e.g. <i>1.000000%</i>),
      <code>{{llg_amount}}</code>, <code>{{dhc_amount}}</code></li>
  <li><code>{{close_deadline}}</code>, <code>{{operator_name}}</code></li>
</ul>
<p>See <b>Document Templates → Map Fields…</b> for the full list with
descriptions.</p>

<h3>Attaching to a workflow stage</h3>
<p>Email templates only fire when they're attached to a workflow stage.
Open the <b>Workflows</b> page in the navigator, pick a workflow, click
<b>+ Add email</b> on a stage card, and pick the template from the
multi-select dialog. Set the wait_days for that attachment (e.g. 0 for
immediate, 7 for "send 7 days after the investor enters this stage").</p>

<h3>How they appear in the Send tab</h3>
<p>The Send tab queue shows every email that's currently due based on
each investor's stage run + the attached email's wait_days. Subject and
body are pre-rendered with the investor's actual data substituted —
the operator never sees raw <code>{{template}}</code> placeholders.</p>
"""

_WORKFLOWS = """
<h2>Workflows</h2>
<p>Reusable per-investor pipelines. A workflow defines an ordered list
of <b>stages</b>, each with an SLA, an exit condition, and a set of
attached document templates and email templates. When an investor is
added to a project that uses a workflow, they enter stage 1
automatically and progress through the stages over time.</p>

<h3>The default workflow</h3>
<p>WellSign ships with <b>Standard Capital Raise</b>, a 3-stage default:</p>
<ul>
  <li><b>Outreach</b> (21 days, exit: investor_committed) — pre-marketing
      to existing relationships, collect verbal commitments. Attached
      docs: Subscription Agreement. Attached emails: Initial Pitch (0d),
      Follow-up (7d), Final Ask (14d).</li>
  <li><b>Subscription</b> (14 days, exit: all_docs_signed) — full investor
      packet sent and signed. Attached docs: JOA, PA, C-1, C-2, Info
      Sheet. Attached emails: Send Packet (0d), Reminder (7d), Final
      Reminder (12d).</li>
  <li><b>Cash Call</b> (10 days, exit: llg_and_dhc_paid) — LLG to Decker,
      DHC to operator. Attached emails: Wire Instructions (0d),
      Reminder (5d), Thank You (0d).</li>
</ul>
<p>Note: <b>Drilling</b> is a project phase, not a workflow stage. Workflow
stages are per-investor; drilling is operator-only activity that
happens after every investor has finished the workflow.</p>

<h3>Editing a workflow</h3>
<p>Each stage is rendered as a card in the list. Drag the card up or
down to reorder. Each card has:</p>
<ul>
  <li><b>SLA spinbox</b> — duration in days (0 = no SLA)</li>
  <li><b>Exit condition dropdown</b> — manual / investor_committed /
      all_docs_signed / llg_paid / dhc_paid / llg_and_dhc_paid</li>
  <li><b>📄 Doc chips</b> — attached document templates. Click <b>+ Add doc</b>
      to attach more (multi-select dialog). Click ✕ on a chip to remove.</li>
  <li><b>✉️ Email chips</b> — attached email templates with their wait_days.
      <b>+ Add email</b> opens the multi-select dialog with a shared
      wait_days at the bottom that applies to every selected email.</li>
  <li><b>✕ Delete</b> — removes the stage entirely</li>
</ul>

<h3>+ New Workflow</h3>
<p>Top right. Creates a fresh empty workflow. You can either build it
from scratch by adding stages, or duplicate an existing workflow by
hand-copying its stages.</p>

<h3>Delete Workflow</h3>
<p>Removes the entire workflow and all its stages. Investors with
active stage runs against the deleted workflow will be left in an
orphaned state — don't delete a workflow that's currently in use by
a project.</p>
"""


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
HELP_TOPICS: dict[str, HelpTopic] = {
    t.key: t for t in [
        HelpTopic("project_setup",  "Project Setup",      _PROJECT_SETUP),
        HelpTopic("investors",      "Investors",          _INVESTORS),
        HelpTopic("documents",      "Documents",          _DOCUMENTS),
        HelpTopic("send",           "Send",               _SEND),
        HelpTopic("status",         "Status",             _STATUS),
        HelpTopic("costs",          "Costs",              _COSTS),
        HelpTopic("payments",       "Payments",           _PAYMENTS),
        HelpTopic("reconcile",      "Reconcile",          _RECONCILE),
        HelpTopic("activity",       "Activity",           _ACTIVITY),
        HelpTopic("burndown",       "Burndown",           _BURNDOWN),
        HelpTopic("dashboard",      "Dashboard",          _DASHBOARD),
        HelpTopic("doc_templates",  "Document Templates", _DOC_TEMPLATES),
        HelpTopic("email_templates","Email Templates",    _EMAIL_TEMPLATES),
        HelpTopic("workflows",      "Workflows",          _WORKFLOWS),
    ]
}


def get_topic(key: str) -> HelpTopic | None:
    return HELP_TOPICS.get(key)


def all_topics() -> list[HelpTopic]:
    return list(HELP_TOPICS.values())
