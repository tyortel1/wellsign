"""Modal dialogs (New Project, New Document Template, New Email Template, ...)."""

from .cost_line_dialog import CostLineDialog
from .investor_dialog import InvestorDialog
from .new_doc_template_dialog import NewDocTemplateDialog
from .new_email_template_dialog import NewEmailTemplateDialog
from .new_project_dialog import NewProjectDialog
from .template_picker_dialog import PickerMode, TemplatePickerDialog, TemplatePickerResult

__all__ = [
    "NewProjectDialog",
    "NewDocTemplateDialog",
    "NewEmailTemplateDialog",
    "TemplatePickerDialog",
    "TemplatePickerResult",
    "PickerMode",
    "CostLineDialog",
    "InvestorDialog",
]
