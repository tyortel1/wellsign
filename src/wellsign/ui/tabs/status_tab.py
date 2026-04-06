"""Status tab — per-investor status grid + payment tracking."""

from ._base import PlaceholderTab


class StatusTab(PlaceholderTab):
    title = "Status"
    subtitle = (
        "Per-investor status grid: Info / PA / C-1 / C-2 / W-9 / JOA / LLG paid / DHC "
        "paid. Drop a signed PDF onto an investor row to record it. Tracks LLG payments "
        "to Decker and DHC payments to Paloma against the expected amounts."
    )
