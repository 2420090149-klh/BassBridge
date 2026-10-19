"""Rotary Knob Control Widget for professional audio applications.

Provides smooth mouse dragging, wheel adjustment, arc visualization, and customizable range.
"""

from __future__ import annotations

import math
from typing import Optional

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QMouseEvent, QPaintEvent, QPainter, QPen, QWheelEvent
from PySide6.QtWidgets import QWidget


class RotaryKnob(QWidget):
    """Custom rotary dial knob with anti-aliased arc track and numeric readout."""

    valueChanged = Signal(float)

    def __init__(
        self,
        min_val: float = -24.0,
        max_val: float = 12.0,
        init_val: float = 0.0,
        unit: str = "dB",
        decimals: int = 1,
        title: str = "BASS GAIN",
        accent_color: str = "#00e5ff",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.min_val = float(min_val)
        self.max_val = float(max_val)
        self._value = float(init_val)
        self.unit = unit
        self.decimals = decimals
        self.title = title
        self.accent_color = QColor(accent_color)

        self._dragging = False
        self._last_y = 0

        self.setMinimumSize(90, 110)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def value(self) -> float:
        return self._value

    def setValue(self, val: float) -> None:
        clamped = max(self.min_val, min(self.max_val, float(val)))
        if abs(clamped - self._value) > 1e-4:
            self._value = clamped
            self.valueChanged.emit(self._value)
            self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._last_y = event.pos().y()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._dragging:
            dy = self._last_y - event.pos().y()
            self._last_y = event.pos().y()

            span = self.max_val - self.min_val
            step = span / 150.0  # 150 pixels for full sweep
            self.setValue(self._value + dy * step)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False

    def wheelEvent(self, event: QWheelEvent) -> None:
        delta = event.angleDelta().y() / 120.0
        span = self.max_val - self.min_val
        step = span / 50.0
        self.setValue(self._value + delta * step)
        event.accept()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        size = min(w, h - 26) - 10
        cx = w / 2.0
        cy = (h - 20) / 2.0
        radius = size / 2.0

        # Background track arc (-225 degrees to +45 degrees = 270 degree span)
        start_angle = -225.0
        span_angle = 270.0

        # Normalized value (0.0 to 1.0)
        norm = (self._value - self.min_val) / (self.max_val - self.min_val)
        val_span = norm * span_angle

        # 1. Outer Dark Dial Body
        painter.setPen(QPen(QColor("#2c3242"), 4))
        painter.setBrush(QBrush(QColor("#161920")))
        painter.drawEllipse(QPointF(cx, cy), radius - 4, radius - 4)

        # 2. Inactive Arc Track
        track_rect = QRectF(cx - radius + 6, cy - radius + 6, (radius - 6) * 2, (radius - 6) * 2)
        track_pen = QPen(QColor("#232732"), 5)
        track_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(track_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawArc(track_rect, int(start_angle * 16), int(-span_angle * 16))

        # 3. Active Value Arc
        active_pen = QPen(self.accent_color, 5)
        active_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(active_pen)
        painter.drawArc(track_rect, int(start_angle * 16), int(-val_span * 16))

        # 4. Needle Indicator on Dial
        angle_rad = math.radians(start_angle - val_span)
        nx = cx + (radius - 12) * math.cos(angle_rad)
        ny = cy - (radius - 12) * math.sin(angle_rad)
        needle_pen = QPen(QColor("#ffffff"), 3)
        needle_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(needle_pen)
        painter.drawLine(QPointF(cx, cy), QPointF(nx, ny))

        # 5. Center Value Text
        painter.setPen(QColor("#ffffff"))
        val_font = QFont("Segoe UI", 10, QFont.Weight.Bold)
        painter.setFont(val_font)
        val_str = f"{self._value:+.{self.decimals}f}" if self.unit == "dB" else f"{self._value:.{self.decimals}f}"
        val_rect = QRectF(cx - 30, cy - 10, 60, 20)
        painter.drawText(val_rect, Qt.AlignmentFlag.AlignCenter, val_str)

        # 6. Bottom Title & Unit
        title_font = QFont("Segoe UI", 8, QFont.Weight.DemiBold)
        painter.setFont(title_font)
        painter.setPen(QColor("#8c96aa"))
        title_rect = QRectF(0, h - 22, w, 20)
        display_label = f"{self.title} ({self.unit})" if self.unit else self.title
        painter.drawText(title_rect, Qt.AlignmentFlag.AlignCenter, display_label)
