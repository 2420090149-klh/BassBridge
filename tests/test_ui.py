import os
import sys

os.environ["QT_QPA_PLATFORM"] = "offscreen"

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from src.config import ConfigManager
from src.ui.main_window import MainWindow


@pytest.fixture(scope="session")
def qapp():
    """Ensure QApplication instance exists for tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def test_main_window_initialization(qapp, tmp_path):
    """Verify MainWindow initializes, displays components, and cleans up cleanly."""
    # Headless / offscreen platform for reliable CI/automated test runs
    os.environ["QT_QPA_PLATFORM"] = "offscreen"

    test_cfg_path = tmp_path / "ui_test_settings.json"
    cfg_mgr = ConfigManager(config_path=test_cfg_path)

    window = MainWindow(config_manager=cfg_mgr)
    assert window.windowTitle() == "BassBridge - Wireless Bass Companion"

    # Check widgets exist
    assert window.knob_bass_gain is not None
    assert window.slider_crossover is not None
    assert window.slider_delay is not None
    assert window.meter_main is not None
    assert window.meter_bass is not None
    assert window.spectrum_view is not None
    assert window.btn_toggle_engine is not None
    assert window.btn_true_sync is not None
    assert window.btn_test_sync is not None
    assert window.btn_mic_calib is not None

    # Test preset application via UI
    window._apply_preset("Movies")
    assert window.slider_crossover.value() == 85

    window._apply_preset("Gaming")
    assert window.slider_crossover.value() == 85

    # Test slider interaction
    window.slider_crossover.setValue(140)
    assert window.lbl_crossover_val.text() == "140 Hz"

    window.slider_delay.setValue(180)
    assert window.lbl_delay_val.text() == "180 ms"

    # Test acoustic calibration step
    window._perform_acoustic_calibration_step()
    assert window.slider_delay.value() > 0

    # Test close
    window.close()
