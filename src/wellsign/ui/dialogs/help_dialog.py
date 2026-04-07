"""In-app help dialog + help button.

The HelpButton is a tiny "?" pill the operator can drop into any tab's
header HBoxLayout to give context-sensitive help on that tab. Clicking
it opens a HelpDialog scoped to the relevant topic.

The HelpDialog is also reachable from the Help menu in MainWindow with
a topic picker on the left, so the operator can browse all topics
without being on a specific tab.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from wellsign.help.content import HELP_TOPICS, all_topics, get_topic


class HelpDialog(QDialog):
    """Help browser. Optionally scoped to a single topic via ``topic_key``."""

    def __init__(
        self,
        topic_key: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("WellSign Help")
        self.setModal(True)
        self.setMinimumSize(QSize(820, 600))
        self._build()
        if topic_key:
            self._select_topic(topic_key)
        else:
            # Default to the first topic in the list
            topics = all_topics()
            if topics:
                self._select_topic(topics[0].key)

    # ---- layout ---------------------------------------------------------
    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 18, 20, 14)
        outer.setSpacing(12)

        title = QLabel("WellSign Help")
        f = QFont(title.font())
        f.setPointSize(15)
        f.setBold(True)
        title.setFont(f)
        outer.addWidget(title)

        subtitle = QLabel(
            "Pick a topic on the left, or click the ? button on any tab to "
            "jump straight to its help."
        )
        subtitle.setStyleSheet("color: #5b6473;")
        subtitle.setWordWrap(True)
        outer.addWidget(subtitle)

        # Splitter: topic list + content
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)

        self.topic_list = QListWidget()
        self.topic_list.setMinimumWidth(200)
        self.topic_list.setMaximumWidth(280)
        self.topic_list.setStyleSheet(
            "QListWidget { background: #f7f9ff; border: 1px solid #d8dce3; "
            "border-radius: 6px; padding: 4px; }"
            "QListWidget::item { padding: 8px 10px; border-radius: 4px; }"
            "QListWidget::item:selected { background: #1f6feb; color: white; }"
        )
        for topic in all_topics():
            item = QListWidgetItem(topic.title)
            item.setData(Qt.ItemDataRole.UserRole, topic.key)
            self.topic_list.addItem(item)
        self.topic_list.itemSelectionChanged.connect(self._on_topic_selected)
        splitter.addWidget(self.topic_list)

        self.body = QTextBrowser()
        self.body.setOpenExternalLinks(False)
        self.body.setStyleSheet(
            "QTextBrowser { background: #ffffff; border: 1px solid #d8dce3; "
            "border-radius: 6px; padding: 8px 14px; color: #1f2430; }"
        )
        # Set a default style for HTML rendering
        self.body.document().setDefaultStyleSheet(
            "h2 { color: #1f2430; font-size: 16pt; margin-top: 4px; margin-bottom: 8px; }"
            "h3 { color: #1f6feb; font-size: 12pt; margin-top: 16px; margin-bottom: 4px; }"
            "p  { color: #1f2430; font-size: 10pt; line-height: 1.4; }"
            "ul { color: #1f2430; font-size: 10pt; }"
            "ol { color: #1f2430; font-size: 10pt; }"
            "li { margin-bottom: 4px; }"
            "code { background: #f0f3fa; color: #d1242f; padding: 1px 4px; "
            "       border-radius: 3px; font-family: Consolas, monospace; }"
            "b  { color: #1f2430; }"
        )
        splitter.addWidget(self.body)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([220, 600])
        outer.addWidget(splitter, 1)

        # Buttons
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self.buttons.rejected.connect(self.reject)
        self.buttons.accepted.connect(self.accept)
        close_btn = self.buttons.button(QDialogButtonBox.StandardButton.Close)
        close_btn.clicked.connect(self.accept)
        outer.addWidget(self.buttons)

    # ---- handlers -------------------------------------------------------
    def _select_topic(self, topic_key: str) -> None:
        for i in range(self.topic_list.count()):
            item = self.topic_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == topic_key:
                self.topic_list.setCurrentItem(item)
                self._render_topic(topic_key)
                return

    def _on_topic_selected(self) -> None:
        item = self.topic_list.currentItem()
        if item is None:
            return
        key = item.data(Qt.ItemDataRole.UserRole)
        if key:
            self._render_topic(key)

    def _render_topic(self, topic_key: str) -> None:
        topic = get_topic(topic_key)
        if topic is None:
            self.body.setHtml(
                f"<p style='color:#d1242f;'>Unknown help topic: <b>{topic_key}</b></p>"
            )
            return
        self.body.setHtml(topic.body_html)


class HelpButton(QPushButton):
    """Tiny ``?`` button that opens HelpDialog scoped to a specific topic.

    Drop one into any tab's header HBoxLayout::

        header.addWidget(HelpButton("payments"))
    """

    def __init__(self, topic_key: str, parent: QWidget | None = None) -> None:
        super().__init__("?", parent)
        self._topic_key = topic_key
        self.setObjectName("HelpButton")
        self.setFixedSize(28, 28)
        self.setToolTip("Help on this view (or use Help menu → All Topics)")
        self.setStyleSheet(
            "QPushButton#HelpButton { "
            "    background: #f0f3fa; "
            "    color: #1f6feb; "
            "    border: 1px solid #d8dce3; "
            "    border-radius: 14px; "
            "    font-weight: bold; "
            "    font-size: 12pt; "
            "} "
            "QPushButton#HelpButton:hover { "
            "    background: #e2ecff; "
            "    border-color: #1f6feb; "
            "}"
        )
        self.clicked.connect(self._on_click)

    def _on_click(self) -> None:
        # parent() may be None or a transient widget — pass self.window() so
        # the dialog has a sane parent for stacking and modal behaviour.
        HelpDialog(self._topic_key, parent=self.window()).exec()


__all__ = ["HelpDialog", "HelpButton"]
