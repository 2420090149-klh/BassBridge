"""Unit tests for SpeakerProfiler auto-detection and intelligent acoustic profiling."""

from src.audio.profiler import SpeakerProfiler


def test_profiler_wired_dac():
    """Verify internal Realtek and DAC hardware profile detection."""
    p1 = SpeakerProfiler.detect_profile("Speakers (Realtek High Definition Audio)")
    assert p1.category_id == "direct"
    assert p1.recommended_delay_ms == 0
    assert p1.recommended_crossover_hz == 85

    p2 = SpeakerProfiler.detect_profile("USB Audio DAC Line Out")
    assert p2.category_id == "direct"
    assert p2.recommended_delay_ms == 0


def test_profiler_soundbar():
    """Verify soundbar and home theater profile detection."""
    p1 = SpeakerProfiler.detect_profile("Sony HT-S20R Soundbar (Bluetooth)")
    assert p1.category_id == "soundbar"
    assert p1.recommended_delay_ms == 170
    assert p1.recommended_crossover_hz == 100
    assert p1.recommended_subsonic_hz == 38

    p2 = SpeakerProfiler.detect_profile("LG TV HDMI eARC Audio")
    assert p2.category_id == "soundbar"
    assert p2.recommended_delay_ms == 170


def test_profiler_compact_wireless():
    """Verify compact wireless portable speaker detection."""
    p1 = SpeakerProfiler.detect_profile("JBL Flip 6 Stereo")
    assert p1.category_id == "compact_wireless"
    assert p1.recommended_delay_ms == 135
    assert p1.recommended_crossover_hz == 115
    assert p1.recommended_subsonic_hz == 52

    p2 = SpeakerProfiler.detect_profile("Marshall Emberton II")
    assert p2.category_id == "compact_wireless"
    assert p2.recommended_delay_ms == 135

    p3 = SpeakerProfiler.detect_profile("Bluetooth Audio Device")
    assert p3.category_id == "compact_wireless"
    assert p3.recommended_delay_ms == 135


def test_profiler_low_latency_headset():
    """Verify low-latency gaming headset and earbud detection."""
    p1 = SpeakerProfiler.detect_profile("WH-1000XM5 Stereo")
    assert p1.category_id == "headset"
    assert p1.recommended_delay_ms == 45
    assert p1.recommended_crossover_hz == 85

    p2 = SpeakerProfiler.detect_profile("Gaming Headset Wireless")
    assert p2.category_id == "headset"
    assert p2.recommended_delay_ms == 45


def test_clean_device_label():
    """Verify readable device label formatting."""
    cleaned = SpeakerProfiler.clean_device_label("Speakers (Realtek(R) Audio)")
    assert cleaned == "Speakers"

    cleaned_bt = SpeakerProfiler.clean_device_label("boAt Stone 1010 Hands-Free AG Audio")
    assert "Hands-Free" not in cleaned_bt
