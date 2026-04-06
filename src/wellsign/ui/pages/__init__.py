"""Right-pane pages of the main window."""

from .dashboard_page import DashboardPage
from .doc_templates_page import DocTemplatesPage
from .email_templates_page import EmailTemplatesPage
from .project_workspace import ProjectWorkspace
from .workflows_page import WorkflowsPage

__all__ = [
    "DashboardPage",
    "DocTemplatesPage",
    "EmailTemplatesPage",
    "ProjectWorkspace",
    "WorkflowsPage",
]
