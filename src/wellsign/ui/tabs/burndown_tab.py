"""Burndown tab — outstanding work remaining vs. close deadline.

Plots a classic burndown:
  * X axis — dates from the project's ``agreement_date`` to its ``close_deadline``
  * Y axis — number of investors not yet in the Funded / Closed state
  * Ideal line: straight diagonal from start-count to 0 at close
  * Current point: today's outstanding count (based on the active stage runs)

Uses PySide6.QtCharts — available out-of-the-box in PySide6-Addons.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from PySide6.QtCharts import (
    QChart,
    QChartView,
    QDateTimeAxis,
    QLineSeries,
    QScatterSeries,
    QValueAxis,
)
from PySide6.QtCore import QDateTime, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from wellsign.db.investors import count_investors, list_investors
from wellsign.db.migrate import connect
from wellsign.db.projects import ProjectRow
from wellsign.db.workflows import TrafficLight, compute_traffic_light


class BurndownTab(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._project: ProjectRow | None = None
        self._build()

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 24, 28, 24)
        outer.setSpacing(14)

        header = QHBoxLayout()
        title = QLabel("Burndown")
        f = title.font()
        f.setPointSize(18)
        f.setBold(True)
        title.setFont(f)
        header.addWidget(title)
        header.addStretch(1)

        subtitle = QLabel(
            "Outstanding investors vs. the close deadline. The grey ideal line is a "
            "straight path from the original investor count down to zero at close. "
            "Red dot = where you actually are today. If the dot is above the line, "
            "you're running behind."
        )
        subtitle.setStyleSheet("color: #5b6473;")
        subtitle.setWordWrap(True)

        self.summary_label = QLabel("")
        self.summary_label.setStyleSheet("color: #5b6473;")

        # Chart
        self.chart = QChart()
        self.chart.setBackgroundBrush(QColor("#ffffff"))
        self.chart.setPlotAreaBackgroundBrush(QColor("#ffffff"))
        self.chart.setPlotAreaBackgroundVisible(True)
        self.chart.legend().setVisible(True)
        self.chart.legend().setAlignment(Qt.AlignmentFlag.AlignBottom)
        self.chart.setAnimationOptions(QChart.AnimationOption.NoAnimation)
        self.chart.setMargins(type(self.chart.margins())(8, 8, 8, 8))

        self.chart_view = QChartView(self.chart)
        self.chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.chart_view.setStyleSheet("background: #ffffff; border: 1px solid #d8dce3;")

        outer.addLayout(header)
        outer.addWidget(subtitle)
        outer.addWidget(self.summary_label)
        outer.addWidget(self.chart_view, 1)

    # ---- public api ------------------------------------------------------
    def set_project(self, project: ProjectRow | None) -> None:
        self._project = project
        self.refresh()

    def refresh(self) -> None:
        self.chart.removeAllSeries()
        for ax in list(self.chart.axes()):
            self.chart.removeAxis(ax)

        if self._project is None:
            self.chart.setTitle("No project selected")
            self.summary_label.setText("")
            return

        start_date = self._parse_date(self._agreement_date())
        end_date   = self._parse_date(self._close_deadline())
        total_investors = count_investors(self._project.id)

        if start_date is None or end_date is None or end_date <= start_date:
            self.chart.setTitle("Not enough date info to draw the burndown")
            self.summary_label.setText(
                "Set agreement_date and close_deadline on the project to see the chart."
            )
            return

        # Count investors not yet in final state (anything other than a completed run
        # whose stage was the last stage — we approximate by "currently in a stage")
        outstanding = self._count_outstanding()

        # Ideal line: total at start → 0 at end
        ideal = QLineSeries()
        ideal.setName("Ideal")
        ideal_pen = QPen(QColor("#aab1bd"))
        ideal_pen.setWidth(2)
        ideal_pen.setStyle(Qt.PenStyle.DashLine)
        ideal.setPen(ideal_pen)
        ideal.append(QDateTime(start_date, _zero_time()).toMSecsSinceEpoch(), total_investors)
        ideal.append(QDateTime(end_date, _zero_time()).toMSecsSinceEpoch(), 0)

        # Actual line (flat from start until today, then the current point)
        actual = QLineSeries()
        actual.setName("Outstanding")
        actual_pen = QPen(QColor("#1f6feb"))
        actual_pen.setWidth(3)
        actual.setPen(actual_pen)
        actual.append(QDateTime(start_date, _zero_time()).toMSecsSinceEpoch(), total_investors)
        actual.append(QDateTime(date.today(), _zero_time()).toMSecsSinceEpoch(), outstanding)

        # Today's marker
        today_marker = QScatterSeries()
        today_marker.setName("Today")
        today_marker.setMarkerSize(14)
        today_marker.setColor(QColor("#d1242f"))
        today_marker.append(QDateTime(date.today(), _zero_time()).toMSecsSinceEpoch(), outstanding)

        self.chart.addSeries(ideal)
        self.chart.addSeries(actual)
        self.chart.addSeries(today_marker)

        axis_x = QDateTimeAxis()
        axis_x.setFormat("MMM dd")
        axis_x.setTitleText("Date")
        axis_x.setLabelsColor(QColor("#5b6473"))
        axis_x.setTitleBrush(QColor("#5b6473"))
        axis_x.setGridLineColor(QColor("#eef0f4"))
        pad = max((end_date - start_date).days // 20, 1)
        axis_x.setRange(
            QDateTime(start_date - timedelta(days=pad), _zero_time()),
            QDateTime(end_date + timedelta(days=pad), _zero_time()),
        )
        self.chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)

        axis_y = QValueAxis()
        axis_y.setLabelFormat("%d")
        axis_y.setTitleText("Investors Outstanding")
        axis_y.setLabelsColor(QColor("#5b6473"))
        axis_y.setTitleBrush(QColor("#5b6473"))
        axis_y.setGridLineColor(QColor("#eef0f4"))
        axis_y.setRange(0, max(total_investors, 1) + 1)
        axis_y.setTickInterval(1)
        axis_y.setTickType(QValueAxis.TickType.TicksFixed)
        axis_y.setTickCount(min(max(total_investors + 2, 2), 12))
        self.chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)

        for s in (ideal, actual, today_marker):
            s.attachAxis(axis_x)
            s.attachAxis(axis_y)

        self.chart.setTitle(
            f"{self._project.name}  ·  {total_investors} investors  ·  "
            f"close {end_date.isoformat()}"
        )

        # On-track vs behind summary
        days_total = (end_date - start_date).days
        days_elapsed = (date.today() - start_date).days
        ideal_today = max(
            0.0,
            total_investors * (1 - (days_elapsed / days_total if days_total else 1)),
        )
        delta = outstanding - ideal_today
        if delta > 0.5:
            status_line = (
                f"<span style='color:#d1242f;'><b>Behind</b> — {outstanding} outstanding, "
                f"ideal would be {ideal_today:.1f} by today</span>"
            )
        elif delta < -0.5:
            status_line = (
                f"<span style='color:#1a7f37;'><b>Ahead</b> — {outstanding} outstanding, "
                f"ideal would be {ideal_today:.1f} by today</span>"
            )
        else:
            status_line = (
                f"<span style='color:#1f6feb;'><b>On track</b> — {outstanding} outstanding</span>"
            )
        self.summary_label.setText(status_line)

    # ---- helpers ---------------------------------------------------------
    def _agreement_date(self) -> str | None:
        if self._project is None:
            return None
        with connect() as conn:
            row = conn.execute(
                "SELECT agreement_date FROM projects WHERE id = ?",
                (self._project.id,),
            ).fetchone()
        return row["agreement_date"] if row else None

    def _close_deadline(self) -> str | None:
        if self._project is None:
            return None
        with connect() as conn:
            row = conn.execute(
                "SELECT close_deadline FROM projects WHERE id = ?",
                (self._project.id,),
            ).fetchone()
        return row["close_deadline"] if row else None

    def _count_outstanding(self) -> int:
        if self._project is None:
            return 0
        n = 0
        for inv in list_investors(self._project.id):
            t = compute_traffic_light(inv.id)
            # Anyone who isn't GREY (no active run) AND isn't on their last run
            # counts as outstanding for the POC.
            if t.light != TrafficLight.GREY:
                n += 1
        return n

    @staticmethod
    def _parse_date(iso: str | None) -> date | None:
        if not iso:
            return None
        try:
            return date.fromisoformat(iso[:10])
        except ValueError:
            return None


def _zero_time():
    """Return a Qt 00:00:00 time object for date axes."""
    from PySide6.QtCore import QTime

    return QTime(0, 0, 0)
