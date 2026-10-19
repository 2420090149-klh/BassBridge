"""Pro Audio Dark Theme and styling for BassBridge."""

from __future__ import annotations

# Color Palette Constants
COLOR_BG_DARK = "#0e1014"
COLOR_BG_SURFACE = "#161920"
COLOR_BG_CARD = "#1c202a"
COLOR_BG_HOVER = "#262b38"
COLOR_BORDER = "#2c3242"
COLOR_TEXT_PRIMARY = "#f0f3f8"
COLOR_TEXT_SECONDARY = "#8c96aa"
COLOR_TEXT_MUTED = "#555f74"

COLOR_ACCENT_CYAN = "#00e5ff"
COLOR_ACCENT_BLUE = "#2979ff"
COLOR_ACCENT_ORANGE = "#ff6d00"
COLOR_ACCENT_RED = "#ff1744"
COLOR_ACCENT_GREEN = "#00e676"
COLOR_ACCENT_PURPLE = "#7c4dff"

THEME_QSS = f"""
QMainWindow {{
    background-color: {COLOR_BG_DARK};
}}

QWidget {{
    font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
    color: {COLOR_TEXT_PRIMARY};
    font-size: 13px;
}}

QFrame#Card {{
    background-color: {COLOR_BG_CARD};
    border: 1px solid {COLOR_BORDER};
    border-radius: 8px;
    padding: 12px;
}}

QFrame#HeaderCard {{
    background-color: {COLOR_BG_SURFACE};
    border-bottom: 1px solid {COLOR_BORDER};
    padding: 14px 20px;
}}

QLabel#TitleLabel {{
    font-size: 20px;
    font-weight: 700;
    color: {COLOR_ACCENT_CYAN};
    letter-spacing: 1px;
}}

QLabel#SubtitleLabel {{
    font-size: 11px;
    color: {COLOR_TEXT_SECONDARY};
}}

QLabel#SectionHeader {{
    font-size: 13px;
    font-weight: 700;
    color: {COLOR_TEXT_PRIMARY};
    text-transform: uppercase;
    letter-spacing: 0.8px;
}}

QLabel#ValueLabel {{
    font-size: 12px;
    font-weight: 600;
    color: {COLOR_ACCENT_CYAN};
}}

QComboBox {{
    background-color: {COLOR_BG_SURFACE};
    border: 1px solid {COLOR_BORDER};
    border-radius: 6px;
    padding: 6px 12px;
    color: {COLOR_TEXT_PRIMARY};
    min-height: 24px;
}}

QComboBox:hover {{
    border: 1px solid {COLOR_ACCENT_CYAN};
}}

QComboBox::drop-down {{
    border: none;
    width: 24px;
}}

QComboBox QAbstractItemView {{
    background-color: {COLOR_BG_SURFACE};
    border: 1px solid {COLOR_BORDER};
    selection-background-color: {COLOR_BG_HOVER};
    selection-color: {COLOR_ACCENT_CYAN};
    outline: none;
    padding: 4px;
}}

QPushButton {{
    background-color: {COLOR_BG_SURFACE};
    border: 1px solid {COLOR_BORDER};
    border-radius: 6px;
    padding: 7px 16px;
    font-weight: 600;
    color: {COLOR_TEXT_PRIMARY};
}}

QPushButton:hover {{
    background-color: {COLOR_BG_HOVER};
    border-color: {COLOR_ACCENT_CYAN};
    color: {COLOR_ACCENT_CYAN};
}}

QPushButton:pressed {{
    background-color: {COLOR_BORDER};
}}

QPushButton#PrimaryButton {{
    background-color: {COLOR_ACCENT_CYAN};
    color: #000000;
    border: none;
    font-weight: 700;
}}

QPushButton#PrimaryButton:hover {{
    background-color: #33ebff;
}}

QPushButton#DangerButton {{
    background-color: {COLOR_ACCENT_RED};
    color: #ffffff;
    border: none;
    font-weight: 700;
}}

QPushButton#DangerButton:hover {{
    background-color: #ff4569;
}}

QPushButton#PresetActive {{
    background-color: {COLOR_ACCENT_BLUE};
    color: #ffffff;
    border: 1px solid {COLOR_ACCENT_CYAN};
}}

QSlider::groove:horizontal {{
    height: 6px;
    background: {COLOR_BG_SURFACE};
    border-radius: 3px;
}}

QSlider::sub-page:horizontal {{
    background: {COLOR_ACCENT_CYAN};
    border-radius: 3px;
}}

QSlider::handle:horizontal {{
    background: #ffffff;
    border: 2px solid {COLOR_ACCENT_CYAN};
    width: 16px;
    margin-top: -5px;
    margin-bottom: -5px;
    border-radius: 8px;
}}

QSlider::handle:horizontal:hover {{
    background: {COLOR_ACCENT_CYAN};
    border: 2px solid #ffffff;
}}

QCheckBox {{
    spacing: 8px;
    font-weight: 600;
}}

QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 1px solid {COLOR_BORDER};
    background-color: {COLOR_BG_SURFACE};
}}

QCheckBox::indicator:checked {{
    background-color: {COLOR_ACCENT_CYAN};
    border-color: {COLOR_ACCENT_CYAN};
}}

QStatusBar {{
    background-color: {COLOR_BG_SURFACE};
    color: {COLOR_TEXT_SECONDARY};
    border-top: 1px solid {COLOR_BORDER};
    font-size: 11px;
}}
"""
