"""Stereo Peak & RMS Audio Level Meter Widget.

Visualizes real-time decibel levels (-60 dB to 0 dB) with smooth peak decay,
RMS bars, and clipping indicators.
"""

from __future__ import annotations

import math
from typing import Optional

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPaintEvent, QPainter, QPen
from PySide6.QtWidgets import QWidget


class AudioLevelMeter(QWidget):
    """Vertical stereo peak and RMS level meter with dBFS scale."""

    def __init__(self, title: str = "MAIN", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.title = title

        self._peak_val: float = 0.0
        self._rms_val: float = 0.0
        self._peak_hold: float = 0.0
        self._clipped: bool = False
        self._clip_counter: int = 0

        self.setMinimumSize(45, 160)

    def set_levels(self, peak: float, rms: float) -> None:
        """Update meter with linear amplitude (0.0 to 1.0+)."""
        self._peak_val = max(0.0, float(peak))
        self._rms_val = max(0.0, float(rms))

        # Check clipping
        if self._peak_val >= 0.99:
            self._clipped = True
            self._clip_counter = 30  # Hold clip red indicator for ~30 frames
        elif self._clip_counter > 0:
            self._clip_counter -= 1
        else:
            self._clipped = False

        # Peak hold decay
        if self._peak_val > self._peak_hold:
            self._peak_hold = self._peak_val
        else:
            self._peak_hold = max(0.0, self._peak_hold * 0.93)  # smooth decay

        self.update()

    @staticmethod
    def _linear_to_db(val: float) -> float:
        if val <= 1e-4:
            return -60.0
        return max(-60.0, min(3.0, 20.0 * math.log10(val)))

    @staticmethod
    def _db_to_y(db: float, top: float, bottom: float) -> float:
        # Maps -60 dB to bottom, 0 dB to top + 15
        norm = (db - (-60.0)) / (0.0 - (-60.0))
        norm = max(0.0, min(1.0, norm))
        return bottom - norm * (bottom - top)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        bar_width = 10
        x_left = (w - bar_width * 2 - 4) / 2.0
        x_right = x_left + bar_width + 4
        y_top = 30.0
        y_bottom = h - 25.0
        bar_height = y_bottom - y_top

        # 1. Background Frame
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor("#161920")))
        painter.drawRoundedRect(QRectF(x_left - 3, y_top - 3, bar_width * 2 + 10, bar_height + 6), 4, 4)

        # 2. Draw Title Header
        painter.setPen(QColor("#8c96aa"))
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        painter.drawText(QRectF(0, 5, w, 18), Qt.AlignmentFlag.AlignCenter, self.title)

        # 3. Clip Indicator LED
        clip_rect = QRectF(w / 2.0 - 5, y_top - 12, 10, 5)
        clip_color = QColor("#ff1744") if self._clipped else QColor("#3a151b")
        painter.setBrush(QBrush(clip_color))
        painter.drawRoundedRect(clip_rect, 2, 2)

        # 4. Draw RMS Bars (Solid Gradient Fill)
        rms_db = self._linear_to_db(self._rms_val)
        y_rms = self._db_to_y(rms_db, y_top, y_bottom)
        rms_height = y_bottom - y_rms

        # Segments for left and right bars
        for bx in (x_left, x_right):
            # Bar background
            painter.setBrush(QBrush(QColor("#232732")))
            painter.drawRect(QRectF(bx, y_top, bar_width, bar_height))

            if rms_height > 0:
                # Color based on level
                if rms_db > -3.0:
                    bar_color = QColor("#ff1744")
                elif rms_db > -12.0:
                    bar_color = QColor("#ff9100")
                else:
                    bar_color = QColor("#00e676")

                painter.setBrush(QBrush(bar_color))
                painter.drawRect(QRectF(bx, y_rms, bar_width, rms_height))

            # 5. Peak Hold Line
            peak_db = self._linear_to_db(self._peak_hold)
            y_peak = self._db_to_y(peak_db, y_top, y_bottom)
            painter.setPen(QPen(QColor("#ffffff"), 2))
            painter.drawLine(QPointF(bx, y_peak), QPointF(bx + bar_width, y_peak))

        # 6. dB Label at bottom
        db_str = f"{rms_db:.0f} dB" if rms_db > -55 else "-∞"
        painter.setFont(QFont("Segoe UI", 7))
        painter.setPen(QColor("#555f74"))
        painter.drawText(QRectF(0, h - 20, w, 16), Qt.AlignmentFlag.AlignCenter, db_str)
