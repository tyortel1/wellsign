"""End-of-drilling reconciliation calculator.

Takes the project's:
  * total raised from investors (sum of expected llg + dhc per investor)
  * total actual well costs (sum of ``actual_amount`` from cost_line_items)

…and computes the surplus (refund pro-rata) or shortfall (supplemental
cash-call pro-rata) owed to / from each investor.

Pro-rata split uses each investor's WI% — which, by definition, is their
share of both the raise and the final costs. If WI% doesn't sum to 100%
(operator retained interest) we still split on each investor's own WI% so
the operator eats their own share.

This is a pure computation — no DB writes. Persisting the reconciliation
result (generating actual refund / supplemental-call records) is a
follow-up feature.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from wellsign.db.costs import list_cost_lines, totals_for
from wellsign.db.investors import list_investors
from wellsign.db.migrate import connect
from wellsign.db.projects import ProjectRow, get_project


@dataclass
class InvestorReconciliation:
    investor_id: str
    name: str
    entity_name: str | None
    wi_percent: float                # 0.05 = 5%
    contributed: float               # llg + dhc expected (what they paid in)
    share_of_variance: float         # signed — positive = refund owed TO investor
    action: str                      # 'refund' | 'owe' | 'none'
    amount: float                    # absolute amount of the action


@dataclass
class ProjectReconciliation:
    project_id: str
    project_name: str
    total_raised: float              # sum of llg + dhc across all investors
    total_expected_costs: float      # sum of cost_line_items.expected_amount
    total_actual_costs: float        # sum of cost_line_items.actual_amount
    variance: float                  # raised - actual; + = surplus, - = shortfall
    status: str                      # 'surplus' | 'shortfall' | 'on_target' | 'incomplete'
    operator_share_pct: float        # 1 - sum(wi_percent) — retained interest
    per_investor: list[InvestorReconciliation] = field(default_factory=list)

    @property
    def summary_label(self) -> str:
        if self.status == "surplus":
            return f"Surplus — refund ${abs(self.variance):,.2f} pro-rata"
        if self.status == "shortfall":
            return f"Shortfall — supplemental call ${abs(self.variance):,.2f} pro-rata"
        if self.status == "on_target":
            return "On target — no refund or supplemental call"
        return "Incomplete — not all actuals are in yet"


def compute_reconciliation(project_id: str) -> ProjectReconciliation | None:
    project = get_project(project_id)
    if project is None:
        return None

    investors = list_investors(project_id)
    cost_lines = list_cost_lines(project_id)
    totals = totals_for(project_id)

    total_raised = sum((inv.llg_amount or 0) + (inv.dhc_amount or 0) for inv in investors)
    total_actual = totals.actual
    total_expected = totals.expected

    # Incomplete: if any cost line still has no actual_amount, the reconciliation
    # is a projection not a final number. We still compute it but flag status.
    incomplete = any(c.actual_amount is None for c in cost_lines)

    variance = total_raised - total_actual

    if incomplete:
        status = "incomplete"
    elif abs(variance) < 0.01:
        status = "on_target"
    elif variance > 0:
        status = "surplus"
    else:
        status = "shortfall"

    # Per-investor share
    wi_sum = sum(inv.wi_percent for inv in investors)
    operator_pct = max(0.0, 1.0 - wi_sum)

    per_inv: list[InvestorReconciliation] = []
    for inv in investors:
        share = variance * inv.wi_percent
        if status == "surplus":
            action, amount = "refund", share
        elif status == "shortfall":
            action, amount = "owe", -share
        else:
            action, amount = "none", 0.0

        per_inv.append(
            InvestorReconciliation(
                investor_id=inv.id,
                name=inv.display_name,
                entity_name=inv.entity_name,
                wi_percent=inv.wi_percent,
                contributed=(inv.llg_amount or 0) + (inv.dhc_amount or 0),
                share_of_variance=share,
                action=action,
                amount=round(abs(amount), 2),
            )
        )

    return ProjectReconciliation(
        project_id=project_id,
        project_name=project.name,
        total_raised=round(total_raised, 2),
        total_expected_costs=round(total_expected, 2),
        total_actual_costs=round(total_actual, 2),
        variance=round(variance, 2),
        status=status,
        operator_share_pct=operator_pct,
        per_investor=per_inv,
    )
