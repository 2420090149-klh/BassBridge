"""Unit tests for Windows audio endpoint management and detection."""

import pytest
from src.audio.devices import AudioDeviceInfo, DeviceManager


def test_device_manager_initialization():
    """Verify DeviceManager discovers playback outputs and loopbacks."""
    mgr = DeviceManager()
    outputs = mgr.get_output_devices()
    loopbacks = mgr.get_loopback_devices()

    # On this Windows system, there should be at least one output and loopback
    assert len(outputs) >= 1, "At least one output device should exist"
    assert len(loopbacks) >= 1, "At least one loopback device should exist"

    # Verify device properties
    for d in outputs:
        assert d.max_output_channels > 0
        assert not d.is_loopback
        assert d.default_sample_rate > 0

    for lb in loopbacks:
        assert lb.is_loopback
        assert lb.max_input_channels > 0

    mgr.close()


def test_device_lookup_by_name():
    """Verify exact, case-insensitive, and substring device lookups."""
    mgr = DeviceManager()
    outputs = mgr.get_output_devices()
    if outputs:
        first_name = outputs[0].name
        # Exact lookup
        found = mgr.find_device_by_name(first_name)
        assert found is not None
        assert found.name == first_name

        # Case-insensitive lookup
        found_lower = mgr.find_device_by_name(first_name.lower())
        assert found_lower is not None

        # Missing device returns None
        not_found = mgr.find_device_by_name("NonExistentAudioDevice123456")
        assert not_found is None

    mgr.close()


def test_bluetooth_and_laptop_heuristics():
    """Verify device categorization heuristics."""
    assert DeviceManager._is_likely_bluetooth("Echo Dot-9F3") is True
    assert DeviceManager._is_likely_bluetooth("JBL Flip 6 Stereo") is True
    assert DeviceManager._is_likely_bluetooth("Headphones (boAt Stone 1010)") is True
    assert DeviceManager._is_likely_bluetooth("Realtek(R) Audio") is False

    assert DeviceManager._is_likely_laptop_speaker("Speaker (Realtek(R) Audio)") is True
    assert DeviceManager._is_likely_laptop_speaker("Echo Dot") is False

    assert DeviceManager._is_likely_virtual_sink("Speakers (OMEN Cam & Voice)") is True
    assert DeviceManager._is_likely_virtual_sink("VB-Audio Cable") is True
    assert DeviceManager._is_likely_virtual_sink("Speaker (Realtek(R) Audio)") is False

