"""Configuration management for BassBridge.

Handles persistent application settings, audio presets, and parameter validation.
Settings are stored in the user's AppData directory in JSON format.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class Preset:
    """Preset parameters for audio processing."""
    name: str
    crossover_freq: float
    bass_gain_db: float
    main_volume: float
    bass_volume: float
    bass_split_enabled: bool
    description: str = ""


DEFAULT_PRESETS: Dict[str, Preset] = {
    "Music": Preset(
        name="Music",
        crossover_freq=120.0,
        bass_gain_db=1.5,
        main_volume=1.0,
        bass_volume=1.0,
        bass_split_enabled=True,
        description="Balanced crossover for stereo music playback with warm low-end."
    ),
    "Movies": Preset(
        name="Movies",
        crossover_freq=100.0,
        bass_gain_db=3.5,
        main_volume=1.0,
        bass_volume=1.2,
        bass_split_enabled=True,
        description="Deep cinematic sub-bass boost for explosions and atmospheric effects."
    ),
    "Gaming": Preset(
        name="Gaming",
        crossover_freq=90.0,
        bass_gain_db=0.0,
        main_volume=1.0,
        bass_volume=1.0,
        bass_split_enabled=False,
        description="Tight sub-bass reinforcement; full-range laptop audio for low latency."
    ),
    "Custom": Preset(
        name="Custom",
        crossover_freq=120.0,
        bass_gain_db=0.0,
        main_volume=1.0,
        bass_volume=1.0,
        bass_split_enabled=True,
        description="User-defined custom parameters."
    ),
}


@dataclass
class AppConfig:
    """Application configuration and persistent state."""
    # Selected audio endpoints
    main_device_name: str = ""
    bass_device_name: str = ""
    capture_device_name: str = "Default"

    # Audio DSP parameters
    crossover_freq: float = 120.0  # Range: 40.0 - 250.0 Hz
    bass_gain_db: float = 0.0      # Range: -24.0 to +12.0 dB
    main_volume: float = 1.0       # Range: 0.0 to 1.5
    bass_volume: float = 1.0       # Range: 0.0 to 1.5
    bass_delay_ms: float = 120.0   # Range: 0.0 to 500.0 ms
    bass_muted: bool = False
    bass_split_enabled: bool = True
    bass_clarity_enabled: bool = True    # Tight punch & vocal mud reduction
    infrasonic_cut_enabled: bool = True  # Cut < 35 Hz sub-rumble for speaker protection
    bass_phase_inverted: bool = False    # 0 deg vs 180 deg acoustic phase flip


    # Performance and buffer
    buffer_size: int = 1024        # Frames per buffer: 512, 1024, 2048
    target_sample_rate: int = 48000

    # Active preset name
    active_preset: str = "Music"

    # Calibration offset estimate
    calibrated_delay_ms: float = 0.0

    def validate(self) -> None:
        """Clamp parameters to valid ranges."""
        self.crossover_freq = max(40.0, min(250.0, float(self.crossover_freq)))
        self.bass_gain_db = max(-24.0, min(18.0, float(self.bass_gain_db)))
        self.main_volume = max(0.0, min(1.5, float(self.main_volume)))
        self.bass_volume = max(0.0, min(1.5, float(self.bass_volume)))
        self.bass_delay_ms = max(0.0, min(500.0, float(self.bass_delay_ms)))
        self.bass_clarity_enabled = bool(self.bass_clarity_enabled)
        self.infrasonic_cut_enabled = bool(self.infrasonic_cut_enabled)
        self.bass_phase_inverted = bool(self.bass_phase_inverted)
        if self.buffer_size not in (256, 512, 1024, 2048, 4096):
            self.buffer_size = 1024


class ConfigManager:
    """Manages loading, saving, and restoring application settings."""

    def __init__(self, config_path: Optional[Path] = None) -> None:
        if config_path is None:
            appdata = os.environ.get("APPDATA")
            if appdata:
                base_dir = Path(appdata) / "BassBridge"
            else:
                base_dir = Path.home() / ".bassbridge"
            base_dir.mkdir(parents=True, exist_ok=True)
            self.config_path = base_dir / "settings.json"
        else:
            self.config_path = config_path

        self.current_config = AppConfig()
        self._previous_config = AppConfig()
        self.load()

    def get_config(self) -> AppConfig:
        """Get the current active configuration."""
        return self.current_config

    def save(self) -> bool:
        """Save current configuration to JSON file."""
        try:
            self.current_config.validate()
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(asdict(self.current_config), f, indent=2)
            return True
        except Exception as e:
            print(f"[ConfigManager] Failed to save config: {e}")
            return False

    def load(self) -> bool:
        """Load configuration from JSON file."""
        if not self.config_path.is_file():
            self.current_config = AppConfig()
            self._previous_config = AppConfig()
            return False

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Store previous copy for restore functionality
            self._previous_config = AppConfig(**{
                k: data[k] for k in data if hasattr(AppConfig, k)
            })
            self.current_config = AppConfig(**{
                k: data[k] for k in data if hasattr(AppConfig, k)
            })
            self.current_config.validate()
            return True
        except Exception as e:
            print(f"[ConfigManager] Failed to load config: {e}")
            self.current_config = AppConfig()
            self._previous_config = AppConfig()
            return False

    def reset_to_defaults(self) -> None:
        """Reset all parameters to default state."""
        self._previous_config = AppConfig(**asdict(self.current_config))
        self.current_config = AppConfig()
        self.save()

    def restore_previous(self) -> None:
        """Restore the settings from before the last change/reset."""
        self.current_config = AppConfig(**asdict(self._previous_config))
        self.save()

    def apply_preset(self, preset_name: str) -> bool:
        """Apply a named preset to current settings."""
        if preset_name not in DEFAULT_PRESETS:
            return False
        preset = DEFAULT_PRESETS[preset_name]
        self._previous_config = AppConfig(**asdict(self.current_config))
        self.current_config.active_preset = preset_name
        self.current_config.crossover_freq = preset.crossover_freq
        self.current_config.bass_gain_db = preset.bass_gain_db
        self.current_config.main_volume = preset.main_volume
        self.current_config.bass_volume = preset.bass_volume
        self.current_config.bass_split_enabled = preset.bass_split_enabled
        self.current_config.validate()
        self.save()
        return True
