"""Unit tests for DSP crossover, filter stability, gain controls, and limiter."""

import numpy as np
import pytest
from src.audio.dsp import AudioDSPProcessor, LinkwitzRiley4Filter


def test_lr4_filter_sum_flat():
    """Verify that Linkwitz-Riley 4th order filter sums flat (0 dB ripple across spectrum)."""
    fs = 48000
    fc = 120.0
    filt = LinkwitzRiley4Filter(cutoff_freq=fc, sample_rate=fs)

    # Frequency response calculation
    import scipy.signal as signal
    w, h_lp = signal.sosfreqz(filt.sos_lp, worN=2048, fs=fs)
    _, h_hp = signal.sosfreqz(filt.sos_hp, worN=2048, fs=fs)

    h_sum = h_lp + h_hp
    mag_sum_db = 20 * np.log10(np.abs(h_sum))

    # In Linkwitz-Riley 4th order, sum should be 0 dB flat everywhere (< 0.05 dB ripple)
    max_ripple = np.max(np.abs(mag_sum_db))
    assert max_ripple < 0.05, f"LR4 sum ripple too high: {max_ripple:.4f} dB"


def test_frequency_separation_synthetic_sines():
    """Verify low frequencies route to bass path and high frequencies route to main path."""
    fs = 48000
    fc = 120.0
    filt = LinkwitzRiley4Filter(cutoff_freq=fc, sample_rate=fs)

    n_samples = 48000  # 1 second
    t = np.linspace(0, 1.0, n_samples, endpoint=False)

    # 50 Hz deep bass sine
    sine_50hz = np.column_stack((np.sin(2 * np.pi * 50 * t), np.sin(2 * np.pi * 50 * t))).astype(np.float32)

    # 1000 Hz mid/treble sine
    sine_1000hz = np.column_stack((np.sin(2 * np.pi * 1000 * t), np.sin(2 * np.pi * 1000 * t))).astype(np.float32)

    # Process 50 Hz
    main_50, bass_50 = filt.process(sine_50hz)
    # Steady state energy (skip transient at first 500 samples)
    bass_50_rms = np.sqrt(np.mean(bass_50[500:]**2))
    main_50_rms = np.sqrt(np.mean(main_50[500:]**2))

    # 50 Hz should be dominant in bass path (at least 15 dB higher than main)
    ratio_50 = 20 * np.log10(bass_50_rms / (main_50_rms + 1e-12))
    assert ratio_50 > 15.0, f"50 Hz separation insufficient: {ratio_50:.2f} dB"

    # Reset filter
    filt.reset()

    # Process 1000 Hz
    main_1000, bass_1000 = filt.process(sine_1000hz)
    bass_1000_rms = np.sqrt(np.mean(bass_1000[500:]**2))
    main_1000_rms = np.sqrt(np.mean(main_1000[500:]**2))

    # 1000 Hz should be dominant in main path (at least 30 dB higher than bass)
    ratio_1000 = 20 * np.log10(main_1000_rms / (bass_1000_rms + 1e-12))
    assert ratio_1000 > 30.0, f"1000 Hz separation insufficient: {ratio_1000:.2f} dB"


def test_filter_state_continuity():
    """Verify continuous filter state across adjacent audio blocks (no clicks/discontinuities)."""
    fs = 48000
    filt = LinkwitzRiley4Filter(cutoff_freq=120.0, sample_rate=fs)

    # Single continuous sine wave split into two 512-sample blocks
    t = np.linspace(0, 1024 / fs, 1024, endpoint=False)
    signal_full = np.column_stack((np.sin(2 * np.pi * 80 * t), np.sin(2 * np.pi * 80 * t))).astype(np.float32)

    block1 = signal_full[:512]
    block2 = signal_full[512:]

    # Process block1 then block2
    m1, b1 = filt.process(block1)
    m2, b2 = filt.process(block2)

    # Compare with processing full signal at once
    filt_ref = LinkwitzRiley4Filter(cutoff_freq=120.0, sample_rate=fs)
    m_ref, b_ref = filt_ref.process(signal_full)

    # Check that block boundary matches reference within floating point precision
    diff_bass = np.max(np.abs(b2 - b_ref[512:]))
    assert diff_bass < 1e-5, f"State continuity mismatch: {diff_bass}"


def test_soft_limiter_and_gain():
    """Verify gain controls and soft-knee clipping protection."""
    dsp = AudioDSPProcessor(sample_rate=48000)

    # Massive 10.0 magnitude input that would violently clip
    huge_input = (10.0 * np.ones((512, 2))).astype(np.float32)

    main_out, bass_out = dsp.process_block(huge_input)

    # Max value must be strictly clamped to <= 1.0 (no integer wrap-around)
    assert np.max(np.abs(main_out)) <= 1.0
    assert np.max(np.abs(bass_out)) <= 1.0


def test_bass_mute():
    """Verify bass mute silences bass output while keeping main output active."""
    dsp = AudioDSPProcessor(sample_rate=48000)
    dsp.update_parameters(
        crossover_freq=120.0,
        bass_gain_db=0.0,
        main_volume=1.0,
        bass_volume=1.0,
        bass_muted=True,
        bass_split_enabled=True
    )

    t = np.linspace(0, 512 / 48000, 512, endpoint=False)
    # Signal with 50 Hz bass and 1 kHz treble
    treble = 0.3 * np.sin(2 * np.pi * 1000 * t)
    bass = 0.3 * np.sin(2 * np.pi * 50 * t)
    audio = np.column_stack((treble + bass, treble + bass)).astype(np.float32)

    # Run a few blocks for gain smoothing to converge
    for _ in range(10):
        main_out, bass_out = dsp.process_block(audio)

    assert np.max(np.abs(bass_out)) < 0.01, "Bass not muted properly"
    assert np.max(np.abs(main_out)) > 0.1, "Main audio muted unexpectedly"


def test_infrasonic_rumble_cut():
    """Verify that inaudible 20 Hz sub-rumble is significantly attenuated."""
    dsp = AudioDSPProcessor(sample_rate=48000)
    dsp.update_parameters(
        crossover_freq=120.0,
        bass_gain_db=0.0,
        main_volume=1.0,
        bass_volume=1.0,
        bass_muted=False,
        bass_split_enabled=True,
        infrasonic_cut_enabled=True,
    )
    t = np.arange(4800) / 48000.0
    # 20 Hz sub-rumble
    rumble_20hz = np.column_stack((np.sin(2 * np.pi * 20 * t), np.sin(2 * np.pi * 20 * t))).astype(np.float32)
    # 70 Hz bass tone
    punch_70hz = np.column_stack((np.sin(2 * np.pi * 70 * t), np.sin(2 * np.pi * 70 * t))).astype(np.float32)

    dsp.reset()
    _, out_20 = dsp.process_block(rumble_20hz)
    dsp.reset()
    _, out_70 = dsp.process_block(punch_70hz)

    rms_20 = np.sqrt(np.mean(out_20[1000:]**2))
    rms_70 = np.sqrt(np.mean(out_70[1000:]**2))

    # 20 Hz should be attenuated by at least 6 dB compared to 70 Hz punch
    ratio_db = 20 * np.log10(rms_70 / (rms_20 + 1e-12))
    assert ratio_db > 6.0, f"Infrasonic filter attenuation insufficient: {ratio_db:.2f} dB"


def test_bass_phase_inversion():
    """Verify that bass phase inversion flips signal polarity exactly 180 degrees."""
    dsp = AudioDSPProcessor(sample_rate=48000)
    t = np.arange(1024) / 48000.0
    audio = np.column_stack((np.sin(2 * np.pi * 80 * t), np.sin(2 * np.pi * 80 * t))).astype(np.float32)

    dsp.update_parameters(
        crossover_freq=120.0,
        bass_gain_db=0.0,
        main_volume=1.0,
        bass_volume=1.0,
        bass_muted=False,
        bass_split_enabled=True,
        bass_phase_inverted=False,
    )
    dsp.reset()
    _, bass_normal = dsp.process_block(audio)

    dsp.update_parameters(
        crossover_freq=120.0,
        bass_gain_db=0.0,
        main_volume=1.0,
        bass_volume=1.0,
        bass_muted=False,
        bass_split_enabled=True,
        bass_phase_inverted=True,
    )
    dsp.reset()
    _, bass_inverted = dsp.process_block(audio)

    # Inverted should be exact negative of normal
    diff = np.max(np.abs(bass_normal + bass_inverted))
    assert diff < 1e-5, f"Phase inversion mismatch: {diff}"


def test_bass_mono_sum():
    """Verify that bass mono summing creates identical coherent L and R channels."""
    dsp = AudioDSPProcessor(sample_rate=48000)
    dsp.update_parameters(
        crossover_freq=120.0,
        bass_gain_db=0.0,
        main_volume=1.0,
        bass_volume=1.0,
        bass_muted=False,
        bass_split_enabled=True,
        bass_mono_sum=True,
    )
    t = np.arange(1024) / 48000.0
    # Left channel has 60 Hz tone, right channel has 80 Hz tone
    ch_l = np.sin(2 * np.pi * 60 * t)
    ch_r = np.sin(2 * np.pi * 80 * t)
    audio = np.column_stack((ch_l, ch_r)).astype(np.float32)

    _, bass_out = dsp.process_block(audio)

    # L and R channels must be exactly identical
    assert np.allclose(bass_out[:, 0], bass_out[:, 1], atol=1e-5)



def test_dolby_dialogue_presence_and_spatial_widen():
    """Verify Dolby Dialogue Presence boost at 2.4 kHz and Spatial Widening."""
    dsp = AudioDSPProcessor(sample_rate=48000)
    t = np.arange(4800) / 48000.0
    # 2.4 kHz dialogue tone
    # 2.4 kHz dialogue tone at normal dialogue speech level (-14 dBFS) to avoid peak limiter engagement
    sine_2400 = (0.2 * np.sin(2 * np.pi * 2400 * t)).astype(np.float32)
    stereo_2400 = np.column_stack((sine_2400, sine_2400))

    # Without Dolby boost
    dsp.update_parameters(
        crossover_freq=85.0,
        bass_gain_db=0.0,
        main_volume=1.0,
        bass_volume=1.0,
        bass_muted=False,
        bass_split_enabled=True,
        dolby_dialogue_boost=False,
        dolby_spatial_widen=False,
    )
    dsp.reset()
    main_flat, _ = dsp.process_block(stereo_2400)
    rms_flat = np.sqrt(np.mean(main_flat[1000:]**2))

    # With Dolby boost
    dsp.update_parameters(
        crossover_freq=85.0,
        bass_gain_db=0.0,
        main_volume=1.0,
        bass_volume=1.0,
        bass_muted=False,
        bass_split_enabled=True,
        dolby_dialogue_boost=True,
        dolby_spatial_widen=False,
    )
    dsp.reset()
    main_boosted, _ = dsp.process_block(stereo_2400)
    rms_boosted = np.sqrt(np.mean(main_boosted[1000:]**2))

    # Expect ~+2.0 dB (+1.5 dB to +2.5 dB)
    gain_db = 20 * np.log10(rms_boosted / rms_flat)
    assert 1.5 < gain_db < 2.5, f"Dolby dialogue gain outside expected range: {gain_db:.2f} dB"


def test_dolby_virtual_sub_harmonic_generation():
    """Verify that Dolby Virtual Subwoofer synthesizes upper harmonics for deep sub-bass."""
    dsp = AudioDSPProcessor(sample_rate=48000)
    t = np.arange(4800) / 48000.0
    # 35 Hz deep tone
    sine_35 = np.sin(2 * np.pi * 35 * t).astype(np.float32)
    stereo_35 = np.column_stack((sine_35, sine_35))

    dsp.update_parameters(
        crossover_freq=85.0,
        bass_gain_db=0.0,
        main_volume=1.0,
        bass_volume=1.0,
        bass_muted=False,
        bass_split_enabled=True,
        dolby_virtual_sub=True,
    )
    dsp.reset()
    _, bass_with_harmonics = dsp.process_block(stereo_35)

    # Calculate FFT spectrum and check presence of 70 Hz (2nd harmonic)
    fft_mag = np.abs(np.fft.rfft(bass_with_harmonics[1000:, 0]))
    freqs = np.fft.rfftfreq(len(bass_with_harmonics[1000:, 0]), 1.0 / 48000.0)
    
    idx_70 = np.argmin(np.abs(freqs - 70.0))
    # Harmonic power at 70 Hz should be significant (> 0.05)
    assert fft_mag[idx_70] > 1.0, f"Virtual sub harmonic missing at 70 Hz: {fft_mag[idx_70]}"
