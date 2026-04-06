"""Burndown tab — investor completion and payment progress over time."""

from ._base import PlaceholderTab


class BurndownTab(PlaceholderTab):
    title = "Burndown"
    subtitle = (
        "Burndown chart of outstanding investor signatures and payments vs. the project "
        "close deadline. Filter by project or compare across all active projects to see "
        "which prospects are at risk of missing close."
    )
