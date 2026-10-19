"""Real-Time FFT Frequency Spectrum Analyzer Widget.

Renders logarithmic frequency distribution (20 Hz to 20,000 Hz) with an overlay
marking the configured Linkwitz-Riley crossover cutoff frequency.
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QLinearGradient,
    QPaintEvent,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import QWidget


class SpectrumAnalyzer(QWidget):
    """Logarithmic real-time spectrum analyzer with crossover cutoff line overlay."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.crossover_freq: float = 120.0

        # Frequency bins and dB magnitudes
        self._freqs: np.ndarray = np.array([])
        self._magnitudes_db: np.ndarray = np.array([])
        self._smoothed_db: np.ndarray = np.zeros(128, dtype=np.float32) - 80.0

        self.setMinimumHeight(140)

    def set_crossover_freq(self, fc: float) -> None:
        self.crossover_freq = max(20.0, min(1000.0, float(fc)))
        self.update()

    def update_spectrum(self, freqs: np.ndarray, mags_db: np.ndarray) -> None:
        """Update spectrum display with live FFT output."""
        if freqs.size == 0 or mags_db.size == 0:
            return

        self._freqs = freqs
        self._magnitudes_db = mags_db

        # Map to 128 log-spaced bins between 20 Hz and 20 kHz
        log_freqs = np.logspace(np.log10(20.0), np.log10(20000.0), 128)
        current_bins = np.interp(log_freqs, self._freqs, self._magnitudes_db, left=-80.0, right=-80.0)

        # Smooth falloff for pro audio feel
        alpha = 0.4
        self._smoothed_db = (1.0 - alpha) * self._smoothed_db + alpha * current_bins
        self.update()

    @staticmethod
    def _freq_to_x(f: float, w: float) -> float:
        min_log = math.log10(20.0)
        max_log = math.log10(20000.0)
        f_clamped = max(20.0, min(20000.0, f))
        norm = (math.log10(f_clamped) - min_log) / (max_log - min_log)
        return norm * w

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = float(self.width())
        h = float(self.height())
        plot_h = h - 22.0

        # 1. Background Frame
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor("#13151b")))
        painter.drawRoundedRect(QRectF(0, 0, w, h), 6, 6)

        # 2. Grid lines & Frequency Markers
        grid_freqs = [50, 100, 250, 500, 1000, 2500, 5000, 10000]
        grid_pen = QPen(QColor("#202532"), 1, Qt.PenStyle.DotLine)
        painter.setPen(grid_pen)
        painter.setFont(QFont("Segoe UI", 7))

        for f in grid_freqs:
            x = self._freq_to_x(float(f), w)
            painter.drawLine(QPointF(x, 0), QPointF(x, plot_h))
            label = f"{f}" if f < 1000 else f"{f//1000}k"
            painter.setPen(QColor("#555f74"))
            painter.drawText(QRectF(x - 15, plot_h + 3, 30, 16), Qt.AlignmentFlag.AlignCenter, label)
            painter.setPen(grid_pen)

        # 3. Spectrum Area Curve
        num_bins = len(self._smoothed_db)
        if num_bins > 1:
            path = QPainterPath()
            path.moveTo(0, plot_h)

            for i in range(num_bins):
                x = (i / (num_bins - 1)) * w
                db = self._smoothed_db[i]
                # Map -80 dB to plot_h, 0 dB to 5.0
                norm_y = (db - (-80.0)) / (0.0 - (-80.0))
                norm_y = max(0.0, min(1.0, norm_y))
                y = plot_h - norm_y * (plot_h - 10.0)
                path.lineTo(x, y)

            path.lineTo(w, plot_h)
            path.closeSubpath()

            # Dynamic gradient fill
            grad = QLinearGradient(0, 0, w, 0)
            fc_x = self._freq_to_x(self.crossover_freq, w)
            fc_norm = max(0.01, min(0.99, fc_x / w))

            # Warm amber/orange for bass band, cool cyan for main band
            grad.setColorAt(0.0, QColor(255, 112, 67, 160))
            grad.setColorAt(fc_norm, QColor(255, 112, 67, 100))
            grad.setColorAt(min(1.0, fc_norm + 0.05), QColor(0, 229, 255, 80))
            grad.setColorAt(1.0, QColor(0, 229, 255, 140))

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(grad))
            painter.drawPath(path)

            # Outline stroke
            stroke_pen = QPen(QColor(0, 229, 255, 200), 1.5)
            painter.setPen(stroke_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)

        # 4. Crossover Cutoff Line Marker
        fc_x = self._freq_to_x(self.crossover_freq, w)
        fc_pen = QPen(QColor("#ff7043"), 2, Qt.PenStyle.DashLine)
        painter.setPen(fc_pen)
        painter.drawLine(QPointF(fc_x, 0), QPointF(fc_x, plot_h))

        # Marker Badge
        badge_rect = QRectF(fc_x - 30, 4, 60, 16)
        painter.setBrush(QBrush(QColor("#ff7043")))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(badge_rect, 3, 3)

        painter.setPen(QColor("#ffffff"))
        painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, f"{int(self.crossover_freq)} Hz")
