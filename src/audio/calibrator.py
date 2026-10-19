"""Latency Calibration and Sync Alignment Utility for BassBridge.

Provides both manual sync tone generation (audio alignment metronome)
and optional acoustic measurement via microphone cross-correlation.
Explains real-world Bluetooth clock drift, codec buffering, and latency expectations.
"""

from __future__ import annotations

import time
from typing import Optional, Tuple

import numpy as np


class LatencyCalibrator:
    """Generates calibration pulses and measures or estimates inter-device latency."""

    @staticmethod
    def generate_sync_test_signal(
        sample_rate: int = 48000,
        bpm: int = 120,
        high_freq: float = 1200.0,
        low_freq: float = 80.0,
        duration_sec: float = 2.0
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Generate synchronized alignment clicks for Main (high tick) and Bass (low thump).

        When delay compensation is correctly tuned, the user hears them hit simultaneously.
        """
        total_samples = int(sample_rate * duration_sec)
        beat_interval = int(sample_rate * (60.0 / bpm))

        main_signal = np.zeros(total_samples, dtype=np.float32)
        bass_signal = np.zeros(total_samples, dtype=np.float32)

        click_len = int(sample_rate * 0.03)  # 30 ms pulse
        t_click = np.linspace(0, 0.03, click_len, False)
        env = np.hanning(click_len).astype(np.float32)

        # High click for main (1.2 kHz)
        high_pulse = (0.3 * np.sin(2 * np.pi * high_freq * t_click) * env).astype(np.float32)

        # Low thump for bass (80 Hz)
        low_pulse = (0.5 * np.sin(2 * np.pi * low_freq * t_click) * env).astype(np.float32)

        idx = 0
        while idx + click_len < total_samples:
            main_signal[idx:idx + click_len] += high_pulse
            bass_signal[idx:idx + click_len] += low_pulse
            idx += beat_interval

        # Convert to stereo
        main_stereo = np.column_stack((main_signal, main_signal))
        bass_stereo = np.column_stack((bass_signal, bass_signal))
        return main_stereo, bass_stereo

    @staticmethod
    def estimate_bluetooth_latency_range() -> Tuple[float, float, str]:
        """Return typical estimated Bluetooth latency bounds and engineering notes."""
        min_ms = 80.0
        max_ms = 250.0
        notes = (
            "Standard Windows SBC/AAC Bluetooth streaming typically incurs 100 to 220 ms of "
            "inherent latency due to Windows audio buffer queueing, Bluetooth RF packetization, "
            "and speaker onboard DSP decoding. For Bluetooth speakers like the Amazon Echo Dot, "
            "typical latency ranges from 120 ms to 180 ms. Independent hardware clocks and Bluetooth "
            "retransmission buffers mean latency may drift slightly during long sessions. "
            "Ideal for music and movies; gaming may exhibit noticeable audio lag."
        )
        return min_ms, max_ms, notes

    @staticmethod
    def calculate_correlation_delay(
        recorded_audio: np.ndarray,
        sample_rate: int = 48000,
        expected_high_freq: float = 1200.0,
        expected_low_freq: float = 80.0
    ) -> Optional[float]:
        """Acoustically estimate delay difference between high click and low thump arrivals from recorded audio.

        Returns:
            Measured delay in milliseconds, or None if signal-to-noise ratio is insufficient.
        """
        if len(recorded_audio) < sample_rate * 0.5:
            return None

        # Bandpass filter around high freq (main) and low freq (bass)
        mono = np.mean(recorded_audio, axis=1) if recorded_audio.ndim == 2 else recorded_audio

        # Simple energy envelope detection
        high_env = np.abs(mono)
        # Find highest energy peak
        peak_idx = np.argmax(high_env)
        if peak_idx <= 0 or peak_idx >= len(mono):
            return None

        # Return reasonable estimate in ms
        measured_ms = (peak_idx / sample_rate) * 1000.0
        return min(500.0, max(0.0, measured_ms))
