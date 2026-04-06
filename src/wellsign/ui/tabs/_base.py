"""Shared placeholder base for tabs that haven't been built out yet.

Each real tab will replace its body with actual widgets. Until then this
keeps the main window navigable and lets us iterate on the chrome.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QSizePolicy, QVBoxLayout, QWidget


class PlaceholderTab(QWidget):
    """Empty tab body with a friendly title + subtitle."""

    title: str = ""
    subtitle: str = ""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build()

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 24, 28, 24)
        outer.setSpacing(14)

        card = QFrame()
        card.setObjectName("PlaceholderCard")
        card.setFrameShape(QFrame.Shape.NoFrame)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(32, 32, 32, 32)
        card_layout.setSpacing(10)

        title = QLabel(self.title or self.__class__.__name__)
        title_font = title.font()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)

        subtitle = QLabel(self.subtitle or "Coming soon.")
        subtitle.setStyleSheet("color: #5b6473;")
        subtitle.setWordWrap(True)

        todo = QLabel("This tab is a placeholder while the scaffold is being built.")
        todo.setStyleSheet("color: #8a93a3; font-style: italic;")
        todo.setAlignment(Qt.AlignmentFlag.AlignTop)

        card_layout.addWidget(title)
        card_layout.addWidget(subtitle)
        card_layout.addSpacing(12)
        card_layout.addWidget(todo)
        card_layout.addStretch(1)

        outer.addWidget(card)
