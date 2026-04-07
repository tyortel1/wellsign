"""Per-project tabs hosted inside the ProjectWorkspace page."""

from .burndown_tab import BurndownTab
from .costs_tab import CostsTab
from .documents_tab import DocumentsTab
from .investors_tab import InvestorsTab
from .payments_tab import PaymentsTab
from .project_setup_tab import ProjectSetupTab
from .reconcile_tab import ReconcileTab
from .send_tab import SendTab
from .status_tab import StatusTab

__all__ = [
    "ProjectSetupTab",
    "InvestorsTab",
    "DocumentsTab",
    "SendTab",
    "StatusTab",
    "CostsTab",
    "PaymentsTab",
    "ReconcileTab",
    "BurndownTab",
]
