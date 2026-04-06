"""Send tab — open Outlook with filled packets attached, prefilled body."""

from ._base import PlaceholderTab


class SendTab(PlaceholderTab):
    title = "Send"
    subtitle = (
        "Pick which investors to send to, preview the Outlook draft, and fire. The app "
        "uses the operator's local Outlook install via COM — no SMTP server, no relay. "
        "Sent docs are auto-assigned to each investor and the timeline updates."
    )
