"""Modal dialogs (New Project, New Document Template, New Email Template, ...)."""

from .new_doc_template_dialog import NewDocTemplateDialog
from .new_email_template_dialog import NewEmailTemplateDialog
from .new_project_dialog import NewProjectDialog

__all__ = ["NewProjectDialog", "NewDocTemplateDialog", "NewEmailTemplateDialog"]
