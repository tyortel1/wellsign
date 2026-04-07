"""Per-project tabs hosted inside the ProjectWorkspace page."""

from .burndown_tab import BurndownTab
from .costs_tab import CostsTab
from .documents_tab import DocumentsTab
from .investors_tab import InvestorsTab
from .project_setup_tab import ProjectSetupTab
from .send_tab import SendTab
from .status_tab import StatusTab

__all__ = [
    "ProjectSetupTab",
    "InvestorsTab",
    "DocumentsTab",
    "SendTab",
    "StatusTab",
    "CostsTab",
    "BurndownTab",
]
