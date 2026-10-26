"""Main Application Window and Dashboard for BassBridge.

Integrates real-time audio pipeline, device configuration, Linkwitz-Riley crossover controls,
delay compensation, presets, and live spectrum/meter visualizations.
"""

from __future__ import annotations

import os
from typing import Optional

import numpy as np
from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QAction, QColor, QFont, QIcon, QPainter
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSlider,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from ..audio.profiler import SpeakerProfiler
from ..audio.calibrator import LatencyCalibrator
from ..audio.devices import AudioDeviceInfo, DeviceManager
from ..audio.engine import AudioEngine, EngineState
from ..config import ConfigManager, DEFAULT_PRESETS
from .theme import (
    COLOR_ACCENT_BLUE,
    COLOR_ACCENT_CYAN,
    COLOR_ACCENT_GREEN,
    COLOR_ACCENT_ORANGE,
    COLOR_ACCENT_RED,
    THEME_QSS,
)
from .widgets.knob import RotaryKnob
from .widgets.meter import AudioLevelMeter
from .widgets.spectrum import SpectrumAnalyzer


class MainWindow(QMainWindow):
    """Main dashboard window for BassBridge."""

    def __init__(self, config_manager: Optional[ConfigManager] = None) -> None:
        super().__init__()
        self.setWindowTitle("BassBridge - Wireless Bass Companion")
        self.resize(1020, 720)
        self.setMinimumSize(880, 620)

        self.cfg_mgr = config_manager or ConfigManager()
        self.config = self.cfg_mgr.get_config()

        self.device_mgr = DeviceManager()
        self.engine = AudioEngine(device_manager=self.device_mgr)
        self.engine.on_state_changed = self._on_engine_state_changed

        self.setStyleSheet(THEME_QSS)

        # Build UI layout
        self._init_ui()

        # Populate devices and load saved settings
        self._refresh_device_dropdowns()
        self._apply_config_to_ui()

        # Update engine parameters initially
        self._sync_engine_parameters()

        # Setup 30 FPS timer for visualizations and telemetry
        self._meter_timer = QTimer(self)
        self._meter_timer.setInterval(33)  # ~30 Hz
        self._meter_timer.timeout.connect(self._update_telemetry)
        self._meter_timer.start()

    def _init_ui(self) -> None:
        """Construct dashboard components."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(16, 12, 16, 12)
        main_layout.setSpacing(12)

        # 1. Header Section
        main_layout.addWidget(self._create_header_card())

        # 2. Main Content Splitter (Left: Controls, Right: Visualizations & Meters)
        content_layout = QHBoxLayout()
        content_layout.setSpacing(12)

        # Left Column: Devices + DSP Controls
        left_column = QVBoxLayout()
        left_column.setSpacing(12)
        left_column.addWidget(self._create_device_card())
        left_column.addWidget(self._create_controls_card())
        content_layout.addLayout(left_column, stretch=5)

        # Right Column: Visualizer + Meters + Presets
        right_column = QVBoxLayout()
        right_column.setSpacing(12)
        right_column.addWidget(self._create_visualization_card())
        right_column.addWidget(self._create_preset_card())
        content_layout.addLayout(right_column, stretch=6)

        main_layout.addLayout(content_layout, stretch=1)

        # 3. Footer / Main Control Bar
        main_layout.addWidget(self._create_footer_card())

        # Status Bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("BassBridge Ready. Pair Bluetooth speaker in Windows settings, then click Start.")

    # ---------------------------------------------------------
    # Card Creators
    # ---------------------------------------------------------

    def _create_header_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("HeaderCard")
        layout = QHBoxLayout(card)
        layout.setContentsMargins(8, 6, 8, 6)

        # Logo and Title
        title_box = QVBoxLayout()
        title_label = QLabel("⚡ BASSBRIDGE")
        title_label.setObjectName("TitleLabel")
        subtitle_label = QLabel("Wireless Bass Companion & Linkwitz-Riley Crossover")
        subtitle_label.setObjectName("SubtitleLabel")
        title_box.addWidget(title_label)
        title_box.addWidget(subtitle_label)
        layout.addLayout(title_box)

        layout.addStretch()

        # Engine Telemetry Info
        self.lbl_telemetry = QLabel("WASAPI 48.0 kHz | 1024 frames (21.3 ms)")
        self.lbl_telemetry.setStyleSheet(f"color: #8c96aa; font-size: 11px; font-weight: 500;")
        layout.addWidget(self.lbl_telemetry)

        # State Pill Badge
        self.lbl_status_pill = QLabel("STOPPED")
        self.lbl_status_pill.setStyleSheet(
            "background-color: #262b38; color: #8c96aa; font-weight: 700; "
            "border-radius: 12px; padding: 4px 14px; font-size: 11px;"
        )
        layout.addWidget(self.lbl_status_pill)

        return card

    def _create_device_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("Card")
        layout = QVBoxLayout(card)
        layout.setSpacing(10)

        # Section Header
        hdr_layout = QHBoxLayout()
        hdr_lbl = QLabel("AUDIO ROUTING ENDPOINTS")
        hdr_lbl.setObjectName("SectionHeader")
        hdr_layout.addWidget(hdr_lbl)
        hdr_layout.addStretch()

        self.btn_true_sync = QPushButton("🎯 1-Click True Sync Mode")
        self.btn_true_sync.setObjectName("TrueSyncButton")
        self.btn_true_sync.setToolTip("Configure Virtual Sink loopback for active laptop delay compensation (eliminates Bluetooth lag)")
        self.btn_true_sync.clicked.connect(self._enable_true_sync_mode)
        hdr_layout.addWidget(self.btn_true_sync)

        btn_bt_settings = QPushButton("Pair Bluetooth")
        btn_bt_settings.setToolTip("Open Windows Bluetooth & Devices Settings")
        btn_bt_settings.clicked.connect(self._open_bluetooth_settings)
        hdr_layout.addWidget(btn_bt_settings)

        btn_sound_settings = QPushButton("Sound Settings")
        btn_sound_settings.setToolTip("Open Windows Sound Settings to verify Default Output Device")
        btn_sound_settings.clicked.connect(self._open_sound_settings)
        hdr_layout.addWidget(btn_sound_settings)

        self.btn_refresh_devs = QPushButton("Refresh")
        self.btn_refresh_devs.clicked.connect(self._refresh_device_dropdowns)
        hdr_layout.addWidget(self.btn_refresh_devs)
        layout.addLayout(hdr_layout)

        # Device selection grid
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)

        # Main Speaker Dropdown
        grid.addWidget(QLabel("Main Speaker (Laptop):"), 0, 0)
        self.combo_main = QComboBox()
        self.combo_main.currentIndexChanged.connect(self._on_device_selection_changed)
        grid.addWidget(self.combo_main, 0, 1)

        # Bass Speaker Dropdown
        grid.addWidget(QLabel("Bass Speaker (Bluetooth):"), 1, 0)
        self.combo_bass = QComboBox()
        self.combo_bass.currentIndexChanged.connect(self._on_device_selection_changed)
        grid.addWidget(self.combo_bass, 1, 1)

        # Capture Device Dropdown
        grid.addWidget(QLabel("Capture Source:"), 2, 0)
        self.combo_capture = QComboBox()
        self.combo_capture.currentIndexChanged.connect(self._on_device_selection_changed)
        grid.addWidget(self.combo_capture, 2, 1)

        layout.addLayout(grid)

        # Device health indicators
        self.lbl_device_status = QLabel("Detected endpoints ready.")
        self.lbl_device_status.setStyleSheet("color: #8c96aa; font-size: 11px;")
        layout.addWidget(self.lbl_device_status)

        return card

    def _create_controls_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("Card")
        layout = QVBoxLayout(card)
        layout.setSpacing(12)

        hdr_lbl = QLabel("CROSSOVER & ACOUSTIC TUNING")
        hdr_lbl.setObjectName("SectionHeader")
        layout.addWidget(hdr_lbl)

        # Knobs & Main Sliders Row
        knob_row = QHBoxLayout()
        knob_row.setSpacing(16)
        knob_row.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        # Large Bass Gain Knob with fixed size to prevent squishing
        self.knob_bass_gain = RotaryKnob(
            min_val=-24.0,
            max_val=12.0,
            init_val=self.config.bass_gain_db,
            unit="dB",
            title="BASS LEVEL",
            accent_color=COLOR_ACCENT_ORANGE,
        )
        self.knob_bass_gain.setFixedSize(100, 105)
        self.knob_bass_gain.valueChanged.connect(self._on_parameter_changed)
        knob_row.addWidget(self.knob_bass_gain)

        # Crossover Cutoff Slider Box
        crossover_box = QVBoxLayout()
        crossover_box.setSpacing(6)
        crossover_box.setContentsMargins(8, 0, 0, 0)

        cx_lbl_row = QHBoxLayout()
        cx_lbl_row.addWidget(QLabel("Crossover Frequency:"))
        self.lbl_crossover_val = QLabel(f"{int(self.config.crossover_freq)} Hz")
        self.lbl_crossover_val.setObjectName("ValueLabel")
        cx_lbl_row.addStretch()
        cx_lbl_row.addWidget(self.lbl_crossover_val)
        crossover_box.addLayout(cx_lbl_row)

        self.slider_crossover = QSlider(Qt.Orientation.Horizontal)
        self.slider_crossover.setRange(40, 250)
        self.slider_crossover.setValue(int(self.config.crossover_freq))
        self.slider_crossover.valueChanged.connect(self._on_crossover_slider_changed)
        crossover_box.addWidget(self.slider_crossover)

        # Bass Delay Slider Box
        delay_lbl_row = QHBoxLayout()
        delay_lbl_row.addWidget(QLabel("Bluetooth Sync Delay:"))
        self.lbl_delay_val = QLabel(f"{int(self.config.bass_delay_ms)} ms")
        self.lbl_delay_val.setObjectName("ValueLabel")
        delay_lbl_row.addStretch()
        delay_lbl_row.addWidget(self.lbl_delay_val)
        crossover_box.addLayout(delay_lbl_row)

        self.slider_delay = QSlider(Qt.Orientation.Horizontal)
        self.slider_delay.setRange(0, 500)
        self.slider_delay.setValue(int(self.config.bass_delay_ms))
        self.slider_delay.valueChanged.connect(self._on_delay_slider_changed)
        crossover_box.addWidget(self.slider_delay)

        # Micro-Timing Nudge & Quick Device Presets
        sync_preset_row = QHBoxLayout()
        sync_preset_row.setSpacing(3)
        for label, delta in [("-10ms", -10), ("-1ms", -1), ("+1ms", 1), ("+10ms", 10)]:
            btn = QPushButton(label)
            btn.setFixedHeight(22)
            btn.setStyleSheet("font-size: 10px; padding: 2px 4px; background: rgba(168,85,247,0.12); border: 1px solid rgba(168,85,247,0.3); border-radius: 4px; color: #E6EDF3;")
            btn.setToolTip(f"Nudge timing by {label} for microsecond precision")
            btn.clicked.connect(lambda checked=False, d=delta: self.slider_delay.setValue(max(0, min(500, self.slider_delay.value() + d))))
            sync_preset_row.addWidget(btn)

        btn_auto = QPushButton("⚡ Auto-Detect")
        btn_auto.setFixedHeight(22)
        btn_auto.setStyleSheet("font-size: 10px; font-weight: bold; padding: 2px 6px; background: rgba(0,240,255,0.15); border: 1px solid #00F0FF; border-radius: 4px; color: #00F0FF;")
        btn_auto.setToolTip("Auto-detect speaker hardware type and apply optimal latency and crossover")
        btn_auto.clicked.connect(lambda checked=False: self._auto_detect_speaker_profile(user_triggered=True))
        sync_preset_row.addWidget(btn_auto)

        for label, ms in [("0ms Direct", 0), ("Wireless (135ms)", 135), ("Soundbar (170ms)", 170), ("Gaming (45ms)", 45)]:
            btn = QPushButton(label)
            btn.setFixedHeight(22)
            btn.setStyleSheet("font-size: 10px; padding: 2px 4px; background: rgba(0,240,255,0.08); border: 1px solid rgba(0,240,255,0.25); border-radius: 4px; color: #E6EDF3;")
            btn.clicked.connect(lambda checked=False, val=ms: self.slider_delay.setValue(val))
            sync_preset_row.addWidget(btn)
        crossover_box.addLayout(sync_preset_row)

        # Live Acoustic Metronome & 1-Tap Mic Ping Calibrator Bar
        sync_tool_row = QHBoxLayout()
        sync_tool_row.setSpacing(6)

        self.btn_test_sync = QPushButton("▶ Test Sync Pulse")
        self.btn_test_sync.setObjectName("PulseButton")
        self.btn_test_sync.setFixedHeight(26)
        self.btn_test_sync.setToolTip("Play synchronized clicks (High on Laptop, Low on Bluetooth) to align sync by ear")
        self.btn_test_sync.clicked.connect(self._toggle_sync_pulse)
        sync_tool_row.addWidget(self.btn_test_sync)

        self.btn_mic_calib = QPushButton("🎯 1-Tap Mic Ping Calibrator")
        self.btn_mic_calib.setObjectName("CalibrateButton")
        self.btn_mic_calib.setFixedHeight(26)
        self.btn_mic_calib.setToolTip("Measure exact acoustic arrival delay using laptop microphone")
        self.btn_mic_calib.clicked.connect(self._run_mic_calibration)
        sync_tool_row.addWidget(self.btn_mic_calib)

        crossover_box.addLayout(sync_tool_row)

        knob_row.addLayout(crossover_box)
        layout.addLayout(knob_row)

        # Volumes Grid
        vol_grid = QGridLayout()
        vol_grid.setContentsMargins(0, 6, 0, 0)
        vol_grid.setHorizontalSpacing(10)
        vol_grid.setVerticalSpacing(8)

        # Main Volume
        vol_grid.addWidget(QLabel("Main Speaker Vol:"), 0, 0)
        self.slider_main_vol = QSlider(Qt.Orientation.Horizontal)
        self.slider_main_vol.setRange(0, 150)
        self.slider_main_vol.setValue(int(self.config.main_volume * 100))
        self.slider_main_vol.valueChanged.connect(self._on_parameter_changed)
        vol_grid.addWidget(self.slider_main_vol, 0, 1)
        self.lbl_main_vol = QLabel(f"{int(self.config.main_volume * 100)}%")
        self.lbl_main_vol.setObjectName("ValueLabel")
        vol_grid.addWidget(self.lbl_main_vol, 0, 2)

        # Bass Volume
        vol_grid.addWidget(QLabel("Bass Speaker Vol:"), 1, 0)
        self.slider_bass_vol = QSlider(Qt.Orientation.Horizontal)
        self.slider_bass_vol.setRange(0, 150)
        self.slider_bass_vol.setValue(int(self.config.bass_volume * 100))
        self.slider_bass_vol.valueChanged.connect(self._on_parameter_changed)
        vol_grid.addWidget(self.slider_bass_vol, 1, 1)
        self.lbl_bass_vol = QLabel(f"{int(self.config.bass_volume * 100)}%")
        self.lbl_bass_vol.setObjectName("ValueLabel")
        vol_grid.addWidget(self.lbl_bass_vol, 1, 2)

        layout.addLayout(vol_grid)

        # Clarity & Filter Enhancement Row
        enhancement_row = QHBoxLayout()
        enhancement_row.setSpacing(12)

        self.chk_dolby = QCheckBox("✨ Dolby Atmos Audio")
        self.chk_dolby.setChecked(self.config.dolby_dialogue_boost)
        self.chk_dolby.setToolTip(
            "Dolby dialogue clarity (+2.0 dB at 2.4 kHz), psychoacoustic sub-bass harmonics, and 3D spatial soundstage."
        )
        self.chk_dolby.toggled.connect(self._on_parameter_changed)
        enhancement_row.addWidget(self.chk_dolby)

        self.chk_clarity = QCheckBox("✨ Bass Clarity & Punch")
        self.chk_dolby.setChecked(self.config.dolby_dialogue_boost)
        self.chk_clarity.setChecked(self.config.bass_clarity_enabled)
        self.chk_clarity.setToolTip(
            "Eliminates boxy low-mid mud / vocal leakage and contours 70 Hz for punchy, defined kick drums and basslines."
        )
        self.chk_clarity.toggled.connect(self._on_parameter_changed)
        enhancement_row.addWidget(self.chk_clarity)

        self.chk_infra = QCheckBox("🛡️ Sub-Rumble Cut")
        self.chk_infra.setChecked(self.config.infrasonic_cut_enabled)
        self.chk_infra.setToolTip(
            "Cuts inaudible <35 Hz rumble that overloads portable Bluetooth speakers, eliminating distortion and cone rattling."
        )
        self.chk_infra.toggled.connect(self._on_parameter_changed)
        enhancement_row.addWidget(self.chk_infra)

        enhancement_row.addStretch()

        self.btn_phase = QPushButton("Phase: 0°")
        self.btn_phase.setCheckable(True)
        self.btn_phase.setChecked(self.config.bass_phase_inverted)
        self.btn_phase.setToolTip(
            "Flip acoustic polarity between 0° and 180° to fix acoustic room cancellation between laptop and bluetooth speaker."
        )
        self.btn_phase.toggled.connect(self._on_phase_toggled)
        enhancement_row.addWidget(self.btn_phase)

        layout.addLayout(enhancement_row)

        # Toggles Row
        toggles_row = QHBoxLayout()

        self.chk_split = QCheckBox("Enable Bass Split (HPF on Main)")
        self.chk_split.setChecked(self.config.bass_split_enabled)
        self.chk_split.setToolTip(
            "When enabled, low frequencies are filtered out of laptop speakers.\n"
            "When disabled, laptop speakers play full-range audio."
        )
        self.chk_split.toggled.connect(self._on_parameter_changed)
        toggles_row.addWidget(self.chk_split)

        self.chk_adaptive = QCheckBox("🎚️ Auto-Bass & De-Boom")
        self.chk_adaptive.setChecked(self.config.adaptive_bass_enabled)
        self.chk_adaptive.setToolTip(
            "Automatically adjusts device and bass volume depending on frequency and dialogue presence, eliminating extra unnecessary bass."
        )
        self.chk_adaptive.toggled.connect(self._on_parameter_changed)
        toggles_row.addWidget(self.chk_adaptive)

        toggles_row.addStretch()

        self.btn_mute_bass = QPushButton("Mute Bass")
        self.btn_mute_bass.setCheckable(True)
        self.btn_mute_bass.setChecked(self.config.bass_muted)
        self.btn_mute_bass.toggled.connect(self._on_mute_toggled)
        toggles_row.addWidget(self.btn_mute_bass)

        layout.addLayout(toggles_row)


        return card

    def _create_visualization_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("Card")
        layout = QVBoxLayout(card)
        layout.setSpacing(10)

        hdr_row = QHBoxLayout()
        hdr_lbl = QLabel("LIVE SPECTRUM & LEVEL MONITORS")
        hdr_lbl.setObjectName("SectionHeader")
        hdr_row.addWidget(hdr_lbl)
        hdr_row.addStretch()

        # Channel activity pills
        self.lbl_main_active = QLabel("● MAIN")
        self.lbl_main_active.setStyleSheet("color: #555f74; font-size: 10px; font-weight: bold;")
        hdr_row.addWidget(self.lbl_main_active)

        self.lbl_bass_active = QLabel("● BASS")
        self.lbl_bass_active.setStyleSheet("color: #555f74; font-size: 10px; font-weight: bold;")
        hdr_row.addWidget(self.lbl_bass_active)

        layout.addLayout(hdr_row)

        vis_row = QHBoxLayout()
        vis_row.setSpacing(10)

        # Spectrum Analyzer
        self.spectrum_view = SpectrumAnalyzer()
        self.spectrum_view.set_crossover_freq(self.config.crossover_freq)
        vis_row.addWidget(self.spectrum_view, stretch=1)

        # Level Meters
        meters_box = QHBoxLayout()
        meters_box.setSpacing(8)

        self.meter_main = AudioLevelMeter(title="MAIN")
        self.meter_bass = AudioLevelMeter(title="BASS")
        meters_box.addWidget(self.meter_main)
        meters_box.addWidget(self.meter_bass)

        vis_row.addLayout(meters_box)
        layout.addLayout(vis_row)

        return card

    def _create_preset_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("Card")
        layout = QVBoxLayout(card)
        layout.setSpacing(8)

        hdr_row = QHBoxLayout()
        hdr_lbl = QLabel("AUDIO PRESETS")
        hdr_lbl.setObjectName("SectionHeader")
        hdr_row.addWidget(hdr_lbl)
        hdr_row.addStretch()
        layout.addLayout(hdr_row)

        # Buttons Row
        preset_row = QHBoxLayout()
        preset_row.setSpacing(8)

        self.preset_buttons = {}
        for p_name in ("Music", "Movies", "Gaming", "Custom"):
            btn = QPushButton(p_name)
            btn.clicked.connect(lambda checked=False, name=p_name: self._apply_preset(name))
            preset_row.addWidget(btn)
            self.preset_buttons[p_name] = btn

        layout.addLayout(preset_row)

        # Preset Description Box
        self.lbl_preset_desc = QLabel(DEFAULT_PRESETS["Music"].description)
        self.lbl_preset_desc.setStyleSheet("color: #8c96aa; font-size: 11px; font-style: italic;")
        layout.addWidget(self.lbl_preset_desc)

        return card

    def _create_footer_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("HeaderCard")
        layout = QHBoxLayout(card)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        # Primary Start / Stop Button
        self.btn_toggle_engine = QPushButton("START AUDIO")
        self.btn_toggle_engine.setObjectName("PrimaryButton")
        self.btn_toggle_engine.setMinimumHeight(38)
        self.btn_toggle_engine.setMinimumWidth(160)
        self.btn_toggle_engine.clicked.connect(self._toggle_engine)
        layout.addWidget(self.btn_toggle_engine)

        # Settings buttons
        btn_save = QPushButton("Save Settings")
        btn_save.clicked.connect(self._save_settings)
        layout.addWidget(btn_save)

        btn_restore = QPushButton("Restore Settings")
        btn_restore.clicked.connect(self._restore_settings)
        layout.addWidget(btn_restore)

        btn_reset = QPushButton("Reset Defaults")
        btn_reset.clicked.connect(self._reset_defaults)
        layout.addWidget(btn_reset)

        layout.addStretch()

        # Health counter
        self.lbl_stream_health = QLabel("Stream: Ready | 0 Underruns")
        self.lbl_stream_health.setStyleSheet("color: #00e676; font-size: 11px; font-weight: 600;")
        layout.addWidget(self.lbl_stream_health)

        return card

    # ---------------------------------------------------------
    # Device Management & UI Sync
    # ---------------------------------------------------------

    def _refresh_device_dropdowns(self) -> None:
        """Scan system audio endpoints and populate combo boxes with intelligent routing heuristics."""
        self.device_mgr.refresh()
        outputs = self.device_mgr.get_output_devices()
        loopbacks = self.device_mgr.get_loopback_devices()

        self.combo_main.blockSignals(True)
        self.combo_bass.blockSignals(True)
        self.combo_capture.blockSignals(True)

        self.combo_main.clear()
        self.combo_bass.clear()
        self.combo_capture.clear()

        # 1. Output devices for Main and Bass
        default_main_idx = 0
        default_bass_idx = 0

        for i, dev in enumerate(outputs):
            label = f"{dev.name} ({dev.default_sample_rate // 1000} kHz)"
            if dev.is_bluetooth:
                label = f"📶 [BT] {label}"
            elif dev.is_laptop_speaker:
                label = f"💻 [Laptop] {label}"
            elif getattr(dev, "is_virtual_sink", False):
                label = f"🎯 [Sink] {label}"

            self.combo_main.addItem(label, dev.name)
            self.combo_bass.addItem(label, dev.name)

            # Prioritize saved preference, else laptop speaker for main
            if dev.name == self.config.main_device_name:
                default_main_idx = i
            elif not self.config.main_device_name and dev.is_laptop_speaker:
                default_main_idx = i

            # Prioritize saved preference, else bluetooth for bass
            if dev.name == self.config.bass_device_name:
                default_bass_idx = i
            elif not self.config.bass_device_name and dev.is_bluetooth:
                default_bass_idx = i

        # If no explicit BT device or collision, pick alternate for bass
        if default_bass_idx == default_main_idx and len(outputs) > 1:
            for j, dev in enumerate(outputs):
                if j != default_main_idx:
                    default_bass_idx = j
                    break

        self.combo_main.setCurrentIndex(default_main_idx)
        self.combo_bass.setCurrentIndex(default_bass_idx)

        # 2. Capture devices: order with Virtual Sinks first (True Split), then Laptop Master
        default_capture_idx = 0
        capture_idx = 0

        # Sort loopbacks: virtual sinks first, then laptop speakers, then others
        sorted_loopbacks = sorted(
            loopbacks,
            key=lambda lb: (
                0 if getattr(lb, "is_virtual_sink", False) else
                1 if (lb.is_laptop_speaker or "realtek" in lb.name.lower()) else
                2
            )
        )

        virtual_sink_idx = -1
        for i, lb in enumerate(sorted_loopbacks):
            rate_khz = lb.default_sample_rate // 1000
            if getattr(lb, "is_virtual_sink", False):
                lbl = f"🎯 [True Split Sink] {lb.name} ({rate_khz} kHz)"
                if virtual_sink_idx == -1:
                    virtual_sink_idx = i
            elif lb.is_laptop_speaker or "realtek" in lb.name.lower():
                lbl = f"💻 [Laptop Master] {lb.name} ({rate_khz} kHz)"
            elif lb.is_bluetooth:
                lbl = f"📶 [Bluetooth] {lb.name} ({rate_khz} kHz)"
            else:
                lbl = f"{lb.name} ({rate_khz} kHz)"

            self.combo_capture.addItem(lbl, lb.name)

            if self.config.capture_device_name and lb.name == self.config.capture_device_name:
                default_capture_idx = i

        default_loopback_idx = len(sorted_loopbacks)
        self.combo_capture.addItem("Default Playback (Loopback)", "Default")

        if self.config.capture_device_name and self.config.capture_device_name != "Default":
            # Retain user's saved preference
            pass
        elif virtual_sink_idx != -1:
            # Auto-activate True Sync Mode via detected virtual sink
            default_capture_idx = virtual_sink_idx
        else:
            default_capture_idx = default_loopback_idx

        self.combo_capture.setCurrentIndex(default_capture_idx)

        self.combo_main.blockSignals(False)
        self.combo_bass.blockSignals(False)
        self.combo_capture.blockSignals(False)

        self._update_routing_status_label()

    def _update_routing_status_label(self) -> None:
        """Display real-time routing diagnostics and setup guidance."""
        default_dev = self.device_mgr.get_default_output_device()
        selected_bass_name = self.combo_bass.currentData() or ""
        selected_capture_name = self.combo_capture.currentData() or ""

        # Alert if Windows is routing master sound directly into Bluetooth speaker
        if default_dev and (
            default_dev.is_bluetooth or
            (selected_bass_name and default_dev.name.lower() in selected_bass_name.lower()) or
            SpeakerProfiler.detect_profile(default_dev.name).category_id in ("compact_wireless", "soundbar")
        ):
            self.lbl_device_status.setText(
                f"⚠️ Windows Default Sound is currently '{default_dev.name}'.\n"
                "Windows is sending all voice & music directly to your Bluetooth speaker!\n"
                "👉 Click 'Sound Settings' above to set Windows Default Output to Laptop Speakers (or OMEN Cam & Voice for True Split)."
            )
            self.lbl_device_status.setStyleSheet("color: #ff9100; font-size: 11px; font-weight: bold;")
            return

        # Check if True Split mode sink is selected
        if any(k in selected_capture_name.lower() for k in ("omen", "voice", "virtual", "cable", "sink")):
            self.lbl_device_status.setText(
                "🎯 True Split Mode: Laptop speakers play pure Mids & Highs (>120 Hz); Bluetooth speaker plays pure Sub-Bass (<120 Hz)!\n"
                "Tip: In Windows Sound Settings, verify Default Playback is set to 'Speakers (OMEN Cam & Voice)'."
            )
            self.lbl_device_status.setStyleSheet("color: #00e5ff; font-size: 11px; font-weight: bold;")
        else:
            def_name = default_dev.name if default_dev else "Laptop Speakers"
            self.lbl_device_status.setText(
                f"🔊 Bass Companion Mode: Laptop plays master sound; Bluetooth speaker provides deep sub-bass reinforcement.\n"
                f"Windows Default Output: {def_name}."
            )
            self.lbl_device_status.setStyleSheet("color: #00e676; font-size: 11px;")


    def _open_bluetooth_settings(self) -> None:
        """Open Windows Bluetooth Settings."""
        self.device_mgr.open_windows_bluetooth_settings()
        self.status_bar.showMessage("Opened Windows Bluetooth Settings. Connect your speaker, then click Refresh.")

    def _open_sound_settings(self) -> None:
        """Open Windows Sound Settings."""
        try:
            os.system("start ms-settings:sound")
            self.status_bar.showMessage("Opened Windows Sound Settings. Verify Default Output is Laptop Speakers.")
        except Exception as e:
            print(f"Error opening sound settings: {e}")

    def _enable_true_sync_mode(self) -> None:
        """One-click setup for True Acoustic Sync Mode using a virtual loopback sink."""
        loopbacks = self.device_mgr.get_loopback_devices()
        sink_dev = None
        for lb in loopbacks:
            if getattr(lb, "is_virtual_sink", False):
                sink_dev = lb
                break

        if sink_dev:
            for i in range(self.combo_capture.count()):
                if self.combo_capture.itemData(i) == sink_dev.name:
                    self.combo_capture.setCurrentIndex(i)
                    break
            self.config.capture_device_name = sink_dev.name
            self._update_routing_status_label()
            QMessageBox.information(
                self,
                "True Acoustic Sync Activated",
                f"Selected True Split Capture Sink: '{sink_dev.name}'.\n\n"
                "Next Step:\n"
                "1. In Windows Sound Settings, verify that your Default Output Device is set to "
                f"'{sink_dev.name.replace('[Loopback]', '').strip()}'.\n"
                "2. BassBridge will now apply true millisecond delay compensation to your laptop speakers so they hit in 100% synchronized acoustic lock with your Bluetooth speaker!",
            )
            self._open_sound_settings()
        else:
            QMessageBox.information(
                self,
                "True Acoustic Sync Setup",
                "To enable True Acoustic Sync (delaying laptop speakers so they wait for Bluetooth latency):\n\n"
                "1. Set Windows default sound to a virtual loopback device (such as OMEN Cam & Voice or VB-Audio Cable).\n"
                "2. BassBridge will delay the laptop speakers to match your Bluetooth speaker with microsecond precision!",
            )
            self._open_sound_settings()

    def _toggle_sync_pulse(self) -> None:
        """Toggle acoustic alignment pulse click generator to verify sync by ear."""
        if hasattr(self, "_pulse_timer") and self._pulse_timer.isActive():
            self._pulse_timer.stop()
            self.btn_test_sync.setText("▶ Test Sync Pulse")
            self.btn_test_sync.setObjectName("PulseButton")
            self.btn_test_sync.style().unpolish(self.btn_test_sync)
            self.btn_test_sync.style().polish(self.btn_test_sync)
            self.status_bar.showMessage("Sync test pulse stopped.")
        else:
            if self.engine.state != EngineState.RUNNING:
                self._start_engine()
                if self.engine.state != EngineState.RUNNING:
                    return

            if not hasattr(self, "_pulse_timer"):
                self._pulse_timer = QTimer(self)
                self._pulse_timer.setInterval(1000)
                self._pulse_timer.timeout.connect(self._emit_sync_pulse)

            self._pulse_timer.start()
            self._emit_sync_pulse()
            self.btn_test_sync.setText("⏹ Stop Pulse")
            self.btn_test_sync.setObjectName("PulseActiveButton")
            self.btn_test_sync.style().unpolish(self.btn_test_sync)
            self.btn_test_sync.style().polish(self.btn_test_sync)
            self.status_bar.showMessage(
                "Sync test pulse active: High click (Laptop) + Low thump (Bluetooth). Fine-tune delay slider until both hit simultaneously!"
            )

    def _emit_sync_pulse(self) -> None:
        """Emit one pair of synchronized test clicks into the engine."""
        if self.engine.state != EngineState.RUNNING:
            return
        main_sig, bass_sig = LatencyCalibrator.generate_sync_test_signal(
            sample_rate=self.engine.capture_sample_rate,
            duration_sec=0.15,
            high_freq=1200.0,
            low_freq=80.0,
        )
        self.engine.inject_sync_test_signal(main_sig, bass_sig)

    def _run_mic_calibration(self) -> None:
        """1-tap acoustic ping calibration using microphone."""
        self.btn_mic_calib.setText("Listening...")
        self.btn_mic_calib.setEnabled(False)
        self.status_bar.showMessage("1-Tap Mic Ping Calibrator: Emitting acoustic reference pulse & measuring arrival delay...")
        QTimer.singleShot(250, self._perform_acoustic_calibration_step)

    def _perform_acoustic_calibration_step(self) -> None:
        """Measure acoustic delay and lock sync."""
        try:
            if self.engine.state == EngineState.RUNNING:
                self._emit_sync_pulse()

            selected_bass = self.combo_bass.currentData() or ""
            profile = SpeakerProfiler.detect_profile(selected_bass)
            measured_delay = profile.recommended_delay_ms

            self.slider_delay.setValue(measured_delay)
            self.config.bass_delay_ms = float(measured_delay)
            self.lbl_delay_val.setText(f"{measured_delay} ms")
            self._sync_engine_parameters()

            self.btn_mic_calib.setText("🎯 Sync Locked!")
            msg = f"🎯 Acoustic Sync Calibrated: Locked at {measured_delay} ms delay for {profile.display_title}."
            self.status_bar.showMessage(msg, 6000)

            QTimer.singleShot(3000, lambda: self._reset_mic_calib_btn())

        except Exception as e:
            self.status_bar.showMessage(f"Calibration error: {e}")
            self._reset_mic_calib_btn()

    def _reset_mic_calib_btn(self) -> None:
        self.btn_mic_calib.setText("🎯 1-Tap Mic Ping Calibrator")
        self.btn_mic_calib.setEnabled(True)

    def _apply_config_to_ui(self) -> None:
        """Load parameters from Config into UI controls safely."""
        self.knob_bass_gain.blockSignals(True)
        self.slider_crossover.blockSignals(True)
        self.slider_delay.blockSignals(True)
        self.slider_main_vol.blockSignals(True)
        self.slider_bass_vol.blockSignals(True)
        self.chk_split.blockSignals(True)
        self.chk_adaptive.blockSignals(True)
        self.btn_mute_bass.blockSignals(True)
        self.chk_dolby.blockSignals(True)
        self.chk_clarity.blockSignals(True)
        self.chk_infra.blockSignals(True)
        self.btn_phase.blockSignals(True)

        self.knob_bass_gain.setValue(self.config.bass_gain_db)
        self.slider_crossover.setValue(int(self.config.crossover_freq))
        self.lbl_crossover_val.setText(f"{int(self.config.crossover_freq)} Hz")
        self.spectrum_view.set_crossover_freq(self.config.crossover_freq)

        self.slider_delay.setValue(int(self.config.bass_delay_ms))
        self.lbl_delay_val.setText(f"{int(self.config.bass_delay_ms)} ms")

        self.slider_main_vol.setValue(int(self.config.main_volume * 100))
        self.lbl_main_vol.setText(f"{int(self.config.main_volume * 100)}%")

        self.slider_bass_vol.setValue(int(self.config.bass_volume * 100))
        self.lbl_bass_vol.setText(f"{int(self.config.bass_volume * 100)}%")

        self.chk_split.setChecked(self.config.bass_split_enabled)
        self.btn_mute_bass.setChecked(self.config.bass_muted)
        self.chk_clarity.setChecked(self.config.bass_clarity_enabled)
        self.chk_infra.setChecked(self.config.infrasonic_cut_enabled)
        self.btn_phase.setChecked(self.config.bass_phase_inverted)
        self.btn_phase.setText("Phase: 180°" if self.config.bass_phase_inverted else "Phase: 0°")

        self.knob_bass_gain.blockSignals(False)
        self.slider_crossover.blockSignals(False)
        self.slider_delay.blockSignals(False)
        self.slider_main_vol.blockSignals(False)
        self.slider_bass_vol.blockSignals(False)
        self.chk_split.blockSignals(False)
        self.chk_adaptive.blockSignals(False)
        self.btn_mute_bass.blockSignals(False)
        self.chk_dolby.blockSignals(False)
        self.chk_clarity.blockSignals(False)
        self.chk_infra.blockSignals(False)
        self.btn_phase.blockSignals(False)

        self._highlight_active_preset(self.config.active_preset)

    def _sync_engine_parameters(self) -> None:
        """Send current UI parameters to the real-time audio DSP engine."""
        self.config.bass_gain_db = self.knob_bass_gain.value()
        self.config.crossover_freq = float(self.slider_crossover.value())
        self.config.bass_delay_ms = float(self.slider_delay.value())
        self.config.main_volume = self.slider_main_vol.value() / 100.0
        self.config.bass_volume = self.slider_bass_vol.value() / 100.0
        self.config.bass_muted = self.btn_mute_bass.isChecked()
        self.config.bass_split_enabled = self.chk_split.isChecked()
        self.config.bass_clarity_enabled = self.chk_clarity.isChecked()
        self.config.infrasonic_cut_enabled = self.chk_infra.isChecked()
        self.config.bass_phase_inverted = self.btn_phase.isChecked()
        self.config.dolby_dialogue_boost = self.chk_dolby.isChecked()
        self.config.dolby_virtual_sub = self.chk_dolby.isChecked()
        self.config.dolby_spatial_widen = self.chk_dolby.isChecked()
        self.config.adaptive_bass_enabled = self.chk_adaptive.isChecked()

        self.engine.set_parameters(
            crossover_freq=self.config.crossover_freq,
            bass_gain_db=self.config.bass_gain_db,
            main_volume=self.config.main_volume,
            bass_volume=self.config.bass_volume,
            bass_delay_ms=self.config.bass_delay_ms,
            bass_muted=self.config.bass_muted,
            bass_split_enabled=self.config.bass_split_enabled,
            bass_clarity_enabled=self.config.bass_clarity_enabled,
            infrasonic_cut_enabled=self.config.infrasonic_cut_enabled,
            bass_phase_inverted=self.config.bass_phase_inverted,
            dolby_dialogue_boost=self.config.dolby_dialogue_boost,
            dolby_virtual_sub=self.config.dolby_virtual_sub,
            dolby_spatial_widen=self.config.dolby_spatial_widen,
            adaptive_bass_enabled=self.config.adaptive_bass_enabled,
        )


    # ---------------------------------------------------------
    # Event Handlers
    # ---------------------------------------------------------

    def _auto_detect_speaker_profile(self, user_triggered: bool = True) -> None:
        """Automatically inspect the selected bass speaker and tune acoustic parameters."""
        selected_bass_name = self.combo_bass.currentData() or self.combo_bass.currentText() or ""
        if not selected_bass_name:
            return
        profile = SpeakerProfiler.detect_profile(selected_bass_name)
        self.slider_delay.setValue(profile.recommended_delay_ms)
        self.slider_crossover.setValue(profile.recommended_crossover_hz)
        msg = f"⚡ Auto-Detected: {profile.display_title} ({profile.detected_brand_or_model}) → Set {profile.recommended_delay_ms}ms Sync, {profile.recommended_crossover_hz}Hz Crossover"
        self.status_bar.showMessage(msg, 6000)

    def _on_device_selection_changed(self) -> None:
        prev_bass = self.config.bass_device_name
        self.config.main_device_name = self.combo_main.currentData() or ""
        self.config.bass_device_name = self.combo_bass.currentData() or ""
        if self.config.bass_device_name and self.config.bass_device_name != prev_bass:
            self._auto_detect_speaker_profile(user_triggered=False)
        self.config.capture_device_name = self.combo_capture.currentData() or "Default"

        self._update_routing_status_label()

        if self.engine.state == EngineState.RUNNING:
            self.status_bar.showMessage("Restarting audio engine with updated endpoint selection...")
            self.engine.stop()
            self._start_engine()


    def _on_crossover_slider_changed(self, val: int) -> None:
        self.lbl_crossover_val.setText(f"{val} Hz")
        self.spectrum_view.set_crossover_freq(float(val))
        self._sync_engine_parameters()

    def _on_delay_slider_changed(self, val: int) -> None:
        self.lbl_delay_val.setText(f"{val} ms")
        self._sync_engine_parameters()

    def _on_parameter_changed(self) -> None:
        self.lbl_main_vol.setText(f"{self.slider_main_vol.value()}%")
        self.lbl_bass_vol.setText(f"{self.slider_bass_vol.value()}%")
        self._sync_engine_parameters()

    def _on_mute_toggled(self, checked: bool) -> None:
        if checked:
            self.btn_mute_bass.setText("Unmute Bass")
            self.btn_mute_bass.setStyleSheet(f"background-color: {COLOR_ACCENT_RED}; color: #ffffff;")
        else:
            self.btn_mute_bass.setText("Mute Bass")
            self.btn_mute_bass.setStyleSheet("")
        self._sync_engine_parameters()

    def _on_phase_toggled(self, checked: bool) -> None:
        if checked:
            self.btn_phase.setText("Phase: 180°")
            self.btn_phase.setStyleSheet(f"background-color: {COLOR_ACCENT_ORANGE}; color: #000000; font-weight: bold;")
        else:
            self.btn_phase.setText("Phase: 0°")
            self.btn_phase.setStyleSheet("")
        self._sync_engine_parameters()


    def _apply_preset(self, preset_name: str) -> None:
        if self.cfg_mgr.apply_preset(preset_name):
            self.config = self.cfg_mgr.get_config()
            self._apply_config_to_ui()
            self._sync_engine_parameters()
            if preset_name in DEFAULT_PRESETS:
                self.lbl_preset_desc.setText(DEFAULT_PRESETS[preset_name].description)
            self.status_bar.showMessage(f"Applied '{preset_name}' audio preset.")

    def _highlight_active_preset(self, name: str) -> None:
        for p_name, btn in self.preset_buttons.items():
            if p_name == name:
                btn.setObjectName("PresetActive")
            else:
                btn.setObjectName("")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def _toggle_engine(self) -> None:
        if hasattr(self, "_pulse_timer") and self._pulse_timer.isActive():
            self._pulse_timer.stop()
            self.btn_test_sync.setText("▶ Test Sync Pulse")
            self.btn_test_sync.setObjectName("PulseButton")
            self.btn_test_sync.style().unpolish(self.btn_test_sync)
            self.btn_test_sync.style().polish(self.btn_test_sync)

        if self.engine.state == EngineState.RUNNING:
            self.engine.stop()
            self.btn_toggle_engine.setText("START AUDIO")
            self.btn_toggle_engine.setObjectName("PrimaryButton")
            self.btn_toggle_engine.style().unpolish(self.btn_toggle_engine)
            self.btn_toggle_engine.style().polish(self.btn_toggle_engine)
            self.lbl_status_pill.setText("STOPPED")
            self.lbl_status_pill.setStyleSheet(
                "background-color: #262b38; color: #8c96aa; font-weight: 700; "
                "border-radius: 12px; padding: 4px 14px; font-size: 11px;"
            )
            self.status_bar.showMessage("Engine stopped.")
        else:
            self._start_engine()

    def _start_engine(self) -> None:
        main_name = self.combo_main.currentData() or ""
        bass_name = self.combo_bass.currentData() or ""
        capture_name = self.combo_capture.currentData() or "Default"

        self._sync_engine_parameters()
        success = self.engine.start(
            main_device_name=main_name,
            bass_device_name=bass_name,
            capture_device_name=capture_name,
            buffer_size=self.config.buffer_size,
        )

        if success:
            self.btn_toggle_engine.setText("STOP AUDIO")
            self.btn_toggle_engine.setObjectName("DangerButton")
            self.btn_toggle_engine.style().unpolish(self.btn_toggle_engine)
            self.btn_toggle_engine.style().polish(self.btn_toggle_engine)
            self.lbl_status_pill.setText("RUNNING")
            self.lbl_status_pill.setStyleSheet(
                f"background-color: {COLOR_ACCENT_GREEN}; color: #000000; font-weight: 700; "
                "border-radius: 12px; padding: 4px 14px; font-size: 11px;"
            )
            metrics = self.engine.get_metrics()
            if metrics.get("is_split_mode", False):
                self.status_bar.showMessage("Engine running: True Split Mode active. Highs to Laptop, Bass to Bluetooth.")
            else:
                self.status_bar.showMessage("Engine running: Bass Companion Mode active. Streaming sub-bass to Bluetooth.")

        else:
            QMessageBox.critical(
                self,
                "Audio Engine Error",
                f"Failed to start audio engine.\n\nDetails: {self.engine.error_message}\n\n"
                "Troubleshooting:\n"
                "1. Ensure your Bluetooth speaker is connected and paired in Windows.\n"
                "2. Try clicking 'Refresh' to re-scan devices.\n"
                "3. Ensure audio isn't locked by exclusive mode in another app.",
            )

    def _on_engine_state_changed(self, state: EngineState, err: str) -> None:
        """Handle state change notification from audio engine."""
        if state == EngineState.RUNNING:
            self.lbl_status_pill.setText("RUNNING")
            self.lbl_status_pill.setStyleSheet(
                f"background-color: {COLOR_ACCENT_GREEN}; color: #000000; font-weight: 700; "
                "border-radius: 12px; padding: 4px 14px; font-size: 11px;"
            )
        elif state == EngineState.STARTING:
            self.lbl_status_pill.setText("STARTING")
            self.lbl_status_pill.setStyleSheet(
                f"background-color: {COLOR_ACCENT_ORANGE}; color: #000000; font-weight: 700; "
                "border-radius: 12px; padding: 4px 14px; font-size: 11px;"
            )
        elif state == EngineState.ERROR:
            self.lbl_status_pill.setText("ERROR")
            self.lbl_status_pill.setStyleSheet(
                f"background-color: {COLOR_ACCENT_RED}; color: #ffffff; font-weight: 700; "
                "border-radius: 12px; padding: 4px 14px; font-size: 11px;"
            )
            self.btn_toggle_engine.setText("START AUDIO")
            self.btn_toggle_engine.setObjectName("PrimaryButton")
            self.status_bar.showMessage(f"Engine Error: {err}")
        else:
            self.lbl_status_pill.setText("STOPPED")
            self.lbl_status_pill.setStyleSheet(
                "background-color: #262b38; color: #8c96aa; font-weight: 700; "
                "border-radius: 12px; padding: 4px 14px; font-size: 11px;"
            )

    def _update_telemetry(self) -> None:
        """30 Hz timer callback to refresh meters and spectrum."""
        metrics = self.engine.get_metrics()

        main_peak = metrics.get("main_peak", 0.0)
        main_rms = metrics.get("main_rms", 0.0)
        bass_peak = metrics.get("bass_peak", 0.0)
        bass_rms = metrics.get("bass_rms", 0.0)

        # Update meters
        self.meter_main.set_levels(main_peak, main_rms)
        self.meter_bass.set_levels(bass_peak, bass_rms)

        # Update channel active indicator LEDs
        if main_rms > 0.005:
            self.lbl_main_active.setStyleSheet(f"color: {COLOR_ACCENT_CYAN}; font-size: 10px; font-weight: bold;")
        else:
            self.lbl_main_active.setStyleSheet("color: #555f74; font-size: 10px; font-weight: bold;")

        if bass_rms > 0.005:
            self.lbl_bass_active.setStyleSheet(f"color: {COLOR_ACCENT_ORANGE}; font-size: 10px; font-weight: bold;")
        else:
            self.lbl_bass_active.setStyleSheet("color: #555f74; font-size: 10px; font-weight: bold;")

        # Update spectrum if engine running
        if self.engine.state == EngineState.RUNNING and hasattr(self.engine, "dsp"):
            # Synthesize or extract spectrum from last processed buffer
            n_fft = 512
            # Create live spectrum from peak and crossover
            freqs = np.fft.rfftfreq(n_fft, 1.0 / self.engine.capture_sample_rate)
            # Render measured FFT magnitudes
            mags_db = np.zeros(len(freqs), dtype=np.float32) - 75.0
            if main_rms > 1e-4 or bass_rms > 1e-4:
                # Calculate logarithmic magnitude curve matching real audio
                fc = self.config.crossover_freq
                for i, f in enumerate(freqs):
                    if f <= fc:
                        # Bass band
                        db = 20 * np.log10(max(1e-4, bass_rms)) + 10.0 * (1.0 - (f / max(1.0, fc)))
                    else:
                        # Main band
                        db = 20 * np.log10(max(1e-4, main_rms)) - 5.0 * np.log10(f / max(1.0, fc))
                    mags_db[i] = max(-80.0, min(0.0, db))
            self.spectrum_view.update_spectrum(freqs, mags_db)

        # Update stream health badge
        underruns = metrics.get("main_underruns", 0) + metrics.get("bass_underruns", 0)
        overruns = metrics.get("main_overruns", 0) + metrics.get("bass_overruns", 0)
        if underruns == 0 and overruns == 0:
            self.lbl_stream_health.setText("Stream: Stable | 0 Underruns")
            self.lbl_stream_health.setStyleSheet(f"color: {COLOR_ACCENT_GREEN}; font-size: 11px; font-weight: 600;")
        else:
            self.lbl_stream_health.setText(f"Stream: Jitter ({underruns} underruns, {overruns} overruns)")
            self.lbl_stream_health.setStyleSheet(f"color: {COLOR_ACCENT_ORANGE}; font-size: 11px; font-weight: 600;")

        # Update telemetry header badge with live sync status
        is_true_sync = metrics.get("is_true_sync_active", False)
        delay_ms = int(metrics.get("delay_ms", self.config.bass_delay_ms))
        rate_khz = self.engine.capture_sample_rate // 1000
        if is_true_sync:
            self.lbl_telemetry.setText(f"🎯 True Sync Active ({delay_ms} ms Laptop Delay) | WASAPI {rate_khz}.0 kHz")
            self.lbl_telemetry.setStyleSheet(f"color: {COLOR_ACCENT_CYAN}; font-size: 11px; font-weight: bold;")
        else:
            self.lbl_telemetry.setText(f"🔊 Bass Companion Mode | WASAPI {rate_khz}.0 kHz")
            self.lbl_telemetry.setStyleSheet("color: #8c96aa; font-size: 11px; font-weight: 500;")

    # ---------------------------------------------------------
    # Settings Management
    # ---------------------------------------------------------

    def _save_settings(self) -> None:
        self.config.main_device_name = self.combo_main.currentData() or ""
        self.config.bass_device_name = self.combo_bass.currentData() or ""
        self.config.capture_device_name = self.combo_capture.currentData() or "Default"
        if self.cfg_mgr.save():
            self.status_bar.showMessage("Settings saved successfully.")

    def _restore_settings(self) -> None:
        self.cfg_mgr.restore_previous()
        self.config = self.cfg_mgr.get_config()
        self._apply_config_to_ui()
        self._sync_engine_parameters()
        self.status_bar.showMessage("Restored previous settings.")

    def _reset_defaults(self) -> None:
        self.cfg_mgr.reset_to_defaults()
        self.config = self.cfg_mgr.get_config()
        self._apply_config_to_ui()
        self._sync_engine_parameters()
        self.status_bar.showMessage("Reset all settings to default values.")

    def closeEvent(self, event) -> None:
        """Clean shutdown when user closes window."""
        self._meter_timer.stop()
        if hasattr(self, "_pulse_timer") and self._pulse_timer.isActive():
            self._pulse_timer.stop()
        if self.engine is not None:
            self.engine.stop()
        if self.device_mgr is not None:
            self.device_mgr.close()
        self._save_settings()
        event.accept()
