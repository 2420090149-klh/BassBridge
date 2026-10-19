"""Unit tests for configuration persistence and presets."""

import json
from pathlib import Path
import pytest
from src.config import AppConfig, ConfigManager, DEFAULT_PRESETS


def test_config_validation():
    """Verify parameters are safely clamped to valid ranges."""
    cfg = AppConfig(
        crossover_freq=10.0,    # too low (min 40)
        bass_gain_db=50.0,      # too high (max 18)
        main_volume=2.5,        # too high (max 1.5)
        bass_delay_ms=900.0,    # too high (max 500)
        buffer_size=12345       # invalid buffer size
    )
    cfg.validate()

    assert cfg.crossover_freq == 40.0
    assert cfg.bass_gain_db == 18.0
    assert cfg.main_volume == 1.5
    assert cfg.bass_delay_ms == 500.0
    assert cfg.buffer_size == 1024


def test_config_save_load(tmp_path: Path):
    """Verify saving to and loading from JSON file."""
    config_file = tmp_path / "test_settings.json"
    mgr = ConfigManager(config_path=config_file)

    cfg = mgr.get_config()
    cfg.crossover_freq = 150.0
    cfg.bass_gain_db = 4.5
    cfg.main_device_name = "Realtek Laptop Speakers"
    cfg.bass_device_name = "Echo Dot"
    assert mgr.save() is True

    # Reload in a new manager instance
    mgr2 = ConfigManager(config_path=config_file)
    cfg2 = mgr2.get_config()

    assert cfg2.crossover_freq == 150.0
    assert cfg2.bass_gain_db == 4.5
    assert cfg2.main_device_name == "Realtek Laptop Speakers"
    assert cfg2.bass_device_name == "Echo Dot"


def test_apply_presets(tmp_path: Path):
    """Verify applying predefined presets updates settings properly."""
    config_file = tmp_path / "preset_settings.json"
    mgr = ConfigManager(config_path=config_file)

    assert mgr.apply_preset("Movies") is True
    cfg = mgr.get_config()
    assert cfg.active_preset == "Movies"
    assert cfg.crossover_freq == DEFAULT_PRESETS["Movies"].crossover_freq
    assert cfg.bass_gain_db == DEFAULT_PRESETS["Movies"].bass_gain_db

    assert mgr.apply_preset("NonExistent") is False


def test_restore_previous_settings(tmp_path: Path):
    """Verify restoring previous settings works after changes."""
    config_file = tmp_path / "restore_settings.json"
    mgr = ConfigManager(config_path=config_file)

    mgr.apply_preset("Music")
    orig_crossover = mgr.get_config().crossover_freq

    mgr.apply_preset("Movies")
    assert mgr.get_config().crossover_freq == DEFAULT_PRESETS["Movies"].crossover_freq

    # Restore
    mgr.restore_previous()
    assert mgr.get_config().crossover_freq == orig_crossover
