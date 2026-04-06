"""Documents tab — generate, preview, regenerate filled packets per investor."""

from ._base import PlaceholderTab


class DocumentsTab(PlaceholderTab):
    title = "Documents"
    subtitle = (
        "Generate filled PDF packets for every investor on the active project. Preview, "
        "regenerate, or open the file. Documents are auto-assigned to investors and "
        "stored in the project's local document folder."
    )
