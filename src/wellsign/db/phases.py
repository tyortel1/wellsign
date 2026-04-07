"""Project phases — preset lifecycle stages of a deal.

Phase is the operator's high-level mental model of where the project is at:
"are we still hunting investors? are we waiting on signatures? are we drilling
yet?". It's manually advanced by the operator.

Workflows (per-investor automation) live underneath specific phases — the
soliciting/documenting/funding phases drive investor email sequences, while
investigating/drilling/abandoned/completing are operator-side activities.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from PySide6.QtGui import QColor


class Phase(str, Enum):
    INVESTIGATING = "investigating"
    SOLICITING    = "soliciting"
    DOCUMENTING   = "documenting"
    FUNDING       = "funding"
    DRILLING      = "drilling"
    ABANDONED     = "abandoned"
    COMPLETING    = "completing"


@dataclass(frozen=True)
class PhaseInfo:
    code: str
    label: str
    short: str
    description: str
    color_hex: str
    has_workflow: bool

    @property
    def color(self) -> QColor:
        return QColor(self.color_hex)


PHASES: list[PhaseInfo] = [
    PhaseInfo(
        code=Phase.INVESTIGATING.value,
        label="Prospect Generation",
        short="Prospect",
        description="Geological evaluation. No investors involved yet.",
        color_hex="#8a93a3",
        has_workflow=False,
    ),
    PhaseInfo(
        code=Phase.SOLICITING.value,
        label="Outreach",
        short="Outreach",
        description="Pitching the deal and collecting verbal commitments.",
        color_hex="#1f6feb",
        has_workflow=True,
    ),
    PhaseInfo(
        code=Phase.DOCUMENTING.value,
        label="Subscription",
        short="Subscription",
        description="Sending packets and collecting signed legal documents.",
        color_hex="#0a958e",
        has_workflow=True,
    ),
    PhaseInfo(
        code=Phase.FUNDING.value,
        label="Cash Call",
        short="Cash Call",
        description="Cash call collection — wires and checks coming in.",
        color_hex="#d97706",
        has_workflow=True,
    ),
    PhaseInfo(
        code=Phase.DRILLING.value,
        label="Drilling",
        short="Drilling",
        description="Well is being drilled. Track AFE actuals.",
        color_hex="#7c3aed",
        has_workflow=False,
    ),
    PhaseInfo(
        code=Phase.ABANDONED.value,
        label="Plugged & Abandoned",
        short="P&A",
        description="Dry hole. Reconcile and refund any unspent capital.",
        color_hex="#d1242f",
        has_workflow=False,
    ),
    PhaseInfo(
        code=Phase.COMPLETING.value,
        label="Completion",
        short="Completion",
        description="Producible well. Completion costs require a supplemental cash call.",
        color_hex="#ea580c",
        has_workflow=True,
    ),
]


PHASE_BY_CODE: dict[str, PhaseInfo] = {p.code: p for p in PHASES}


def info_for(code: str | None) -> PhaseInfo:
    if code is None:
        return PHASE_BY_CODE[Phase.INVESTIGATING.value]
    return PHASE_BY_CODE.get(code, PHASE_BY_CODE[Phase.INVESTIGATING.value])


def next_phase_options(current: str) -> list[PhaseInfo]:
    """Return the legal next phases from the current one.

    Most transitions are linear; drilling can fork into abandoned or completing.
    """
    order = [
        Phase.INVESTIGATING.value,
        Phase.SOLICITING.value,
        Phase.DOCUMENTING.value,
        Phase.FUNDING.value,
        Phase.DRILLING.value,
    ]
    if current in order:
        idx = order.index(current)
        if idx + 1 < len(order):
            return [PHASE_BY_CODE[order[idx + 1]]]
        # past Drilling → fork into abandoned or completing
        return [
            PHASE_BY_CODE[Phase.ABANDONED.value],
            PHASE_BY_CODE[Phase.COMPLETING.value],
        ]
    if current == Phase.COMPLETING.value:
        # After completing cash call, project is done — back to abandoned/closed
        return [PHASE_BY_CODE[Phase.ABANDONED.value]]
    return []
