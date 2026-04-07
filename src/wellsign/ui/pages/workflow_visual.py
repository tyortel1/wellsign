"""Visual workflow flowchart — horizontal pipeline of stage boxes + arrows.

Uses QGraphicsScene/View so boxes can pan and scroll. Each stage is rendered
as a rounded rectangle with:
  * stage number badge (top-left, colored circle)
  * stage name (bold, large)
  * SLA line ("14 days")
  * exit-condition line
  * counters: N docs · M emails

Arrows between stages show flow order. The widget is read-only — all editing
still happens in the Edit tab's list view.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QPainter,
    QPainterPath,
    QPen,
    QPolygonF,
)
from PySide6.QtWidgets import (
    QGraphicsItemGroup,
    QGraphicsPathItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QVBoxLayout,
    QWidget,
)

from wellsign.db.workflows import EXIT_LABELS, list_stages

# Layout constants
_BOX_W = 250
_BOX_H = 160
_GAP   = 60
_TOP_MARGIN = 40
_LEFT_MARGIN = 40

# Stage card colors (cycles through these in order)
_STAGE_PALETTE = [
    ("#e2ecff", "#1f6feb"),  # blue
    ("#def7e6", "#1a7f37"),  # green
    ("#fef3c7", "#d97706"),  # amber
    ("#f3e8ff", "#7c3aed"),  # purple
    ("#fde2e4", "#d1242f"),  # red
    ("#ccfbf1", "#0a958e"),  # teal
]


class WorkflowVisualWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._workflow_id: str | None = None
        self._build()

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.scene = QGraphicsScene(self)
        self.scene.setBackgroundBrush(QBrush(QColor("#ffffff")))

        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.view.setFrameShape(QGraphicsView.Shape.NoFrame)
        self.view.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.view.setStyleSheet("QGraphicsView { background: #ffffff; }")
        outer.addWidget(self.view)

    # ---- public api ------------------------------------------------------
    def show_workflow(self, workflow_id: str | None) -> None:
        self._workflow_id = workflow_id
        self._render()

    def refresh(self) -> None:
        self._render()

    # ---- rendering -------------------------------------------------------
    def _render(self) -> None:
        self.scene.clear()
        if self._workflow_id is None:
            self._draw_empty("No workflow selected")
            return

        stages = list_stages(self._workflow_id)
        if not stages:
            self._draw_empty("This workflow has no stages yet.")
            return

        x = _LEFT_MARGIN
        y = _TOP_MARGIN
        box_centers: list[tuple[float, float, float, float]] = []  # (left_x, center_y, right_x, center_y)

        for i, stage in enumerate(stages):
            bg, fg = _STAGE_PALETTE[i % len(_STAGE_PALETTE)]
            box = self._make_stage_box(stage, i, bg_hex=bg, accent_hex=fg)
            box.setPos(x, y)
            self.scene.addItem(box)
            box_centers.append((x, y + _BOX_H / 2, x + _BOX_W, y + _BOX_H / 2))
            x += _BOX_W + _GAP

        # Arrows between consecutive boxes
        for i in range(len(box_centers) - 1):
            _, _, right_x, right_y = box_centers[i]
            next_left_x, next_y, _, _ = box_centers[i + 1]
            arrow = self._make_arrow(
                QPointF(right_x + 4, right_y),
                QPointF(next_left_x - 4, next_y),
            )
            self.scene.addItem(arrow)

        total_w = x - _GAP + _LEFT_MARGIN
        total_h = _TOP_MARGIN * 2 + _BOX_H
        self.scene.setSceneRect(0, 0, total_w, total_h)

    def _draw_empty(self, message: str) -> None:
        text = QGraphicsSimpleTextItem(message)
        f = QFont()
        f.setPointSize(14)
        f.setItalic(True)
        text.setFont(f)
        text.setBrush(QBrush(QColor("#aab1bd")))
        text.setPos(_LEFT_MARGIN, _TOP_MARGIN)
        self.scene.addItem(text)
        self.scene.setSceneRect(0, 0, 600, 200)

    # ---- stage box -------------------------------------------------------
    def _make_stage_box(
        self,
        stage,
        index: int,
        bg_hex: str,
        accent_hex: str,
    ) -> QGraphicsItemGroup:
        group = QGraphicsItemGroup()

        # Background rect
        rect = QGraphicsRectItem(QRectF(0, 0, _BOX_W, _BOX_H))
        bg = QColor(bg_hex)
        rect.setBrush(QBrush(bg))
        pen = QPen(QColor(accent_hex))
        pen.setWidth(2)
        rect.setPen(pen)
        # Fake rounded corners via painter path
        rect.setData(0, 10)  # ignored; kept for potential custom paint later
        group.addToGroup(rect)

        # Stage number badge (circle in top-left)
        badge_radius = 14
        badge = QGraphicsPathItem()
        path = QPainterPath()
        path.addEllipse(12, 12, badge_radius * 2, badge_radius * 2)
        badge.setPath(path)
        badge.setBrush(QBrush(QColor(accent_hex)))
        badge.setPen(QPen(QColor(accent_hex)))
        group.addToGroup(badge)

        badge_text = QGraphicsSimpleTextItem(str(index + 1))
        badge_font = QFont()
        badge_font.setPointSize(11)
        badge_font.setBold(True)
        badge_text.setFont(badge_font)
        badge_text.setBrush(QBrush(QColor("#ffffff")))
        badge_bounds = badge_text.boundingRect()
        badge_text.setPos(
            12 + badge_radius - badge_bounds.width() / 2,
            12 + badge_radius - badge_bounds.height() / 2,
        )
        group.addToGroup(badge_text)

        # Stage name (bold, large)
        name = QGraphicsSimpleTextItem(stage.name)
        name_font = QFont()
        name_font.setPointSize(13)
        name_font.setBold(True)
        name.setFont(name_font)
        name.setBrush(QBrush(QColor("#1f2430")))
        name.setPos(48, 16)
        group.addToGroup(name)

        # SLA line
        sla_text = (
            f"{stage.duration_days} day SLA" if stage.duration_days else "No SLA"
        )
        sla = QGraphicsSimpleTextItem(sla_text)
        sla_font = QFont()
        sla_font.setPointSize(10)
        sla_font.setBold(True)
        sla.setFont(sla_font)
        sla.setBrush(QBrush(QColor(accent_hex)))
        sla.setPos(18, 60)
        group.addToGroup(sla)

        # Exit condition (wrapped manually if long)
        exit_label = EXIT_LABELS.get(stage.exit_condition, stage.exit_condition)
        exit_text = QGraphicsSimpleTextItem(f"Exit: {exit_label}")
        exit_font = QFont()
        exit_font.setPointSize(9)
        exit_text.setFont(exit_font)
        exit_text.setBrush(QBrush(QColor("#5b6473")))
        # Trim if too wide
        fm = exit_text.boundingRect()
        if fm.width() > _BOX_W - 36:
            # Progressive trim
            raw = f"Exit: {exit_label}"
            while fm.width() > _BOX_W - 36 and len(raw) > 10:
                raw = raw[:-4] + "…"
                exit_text.setText(raw)
                fm = exit_text.boundingRect()
        exit_text.setPos(18, 84)
        group.addToGroup(exit_text)

        # Counters (docs · emails) at bottom
        counters = QGraphicsSimpleTextItem(
            f"📄 {len(stage.docs)} doc{'s' if len(stage.docs) != 1 else ''}"
            f"     ✉ {len(stage.emails)} email{'s' if len(stage.emails) != 1 else ''}"
        )
        counters_font = QFont()
        counters_font.setPointSize(10)
        counters.setFont(counters_font)
        counters.setBrush(QBrush(QColor("#5b6473")))
        counters.setPos(18, _BOX_H - 32)
        group.addToGroup(counters)

        return group

    # ---- arrow -----------------------------------------------------------
    def _make_arrow(self, start: QPointF, end: QPointF) -> QGraphicsPathItem:
        path = QPainterPath()
        path.moveTo(start)
        path.lineTo(end)

        # Arrowhead polygon at the end
        angle = math.atan2(end.y() - start.y(), end.x() - start.x())
        size = 10
        p1 = QPointF(
            end.x() - size * math.cos(angle - math.pi / 6),
            end.y() - size * math.sin(angle - math.pi / 6),
        )
        p2 = QPointF(
            end.x() - size * math.cos(angle + math.pi / 6),
            end.y() - size * math.sin(angle + math.pi / 6),
        )
        head = QPolygonF([end, p1, p2])
        path.addPolygon(head)

        item = QGraphicsPathItem(path)
        pen = QPen(QColor("#aab1bd"))
        pen.setWidth(2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        item.setPen(pen)
        item.setBrush(QBrush(QColor("#aab1bd")))
        return item
