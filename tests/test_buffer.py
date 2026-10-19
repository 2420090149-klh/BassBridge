"""Unit tests for Ring Buffer, Delay Line, and Resampler."""

import numpy as np
import pytest
from src.audio.resampler import AudioResampler
from src.audio.ring_buffer import AudioDelayLine, AudioRingBuffer


def test_ring_buffer_read_write():
    """Verify normal read and write operations."""
    buf = AudioRingBuffer(capacity_frames=1024, channels=2)
    assert buf.available() == 0

    data = (np.ones((256, 2)) * 0.5).astype(np.float32)
    written = buf.write(data)
    assert written == 256
    assert buf.available() == 256

    out = buf.read(256)
    assert out.shape == (256, 2)
    assert np.allclose(out, 0.5)
    assert buf.available() == 0


def test_ring_buffer_underrun():
    """Verify underrun detection and zero padding when reading past available frames."""
    buf = AudioRingBuffer(capacity_frames=1024, channels=2)

    # Write 100 frames
    data = (np.ones((100, 2)) * 0.7).astype(np.float32)
    buf.write(data)

    # Read 200 frames (causes underrun)
    out = buf.read(200)
    assert out.shape == (200, 2)
    # First 100 should be data, next 100 should be zero
    assert np.allclose(out[:100], 0.7)
    assert np.allclose(out[100:], 0.0)

    underruns, overruns, fill = buf.get_health_stats()
    assert underruns == 1
    assert overruns == 0


def test_ring_buffer_overrun():
    """Verify overrun detection and drop when writing beyond capacity."""
    buf = AudioRingBuffer(capacity_frames=500, channels=2)

    # Write 300 frames
    buf.write((np.ones((300, 2)) * 0.1).astype(np.float32))
    # Write another 300 frames (total 600 > 500 capacity)
    buf.write((np.ones((300, 2)) * 0.2).astype(np.float32))

    underruns, overruns, fill = buf.get_health_stats()
    assert overruns == 1
    assert buf.available() == 500


def test_delay_line_timing():
    """Verify delay line delays signal by exact requested milliseconds."""
    fs = 48000
    delay_line = AudioDelayLine(max_delay_ms=500.0, sample_rate=fs, channels=2)

    # Set delay to 10 ms (480 samples)
    delay_line.set_delay_ms(10.0)

    # Feed an impulse at sample 0
    impulse_block = np.zeros((1000, 2), dtype=np.float32)
    impulse_block[0, :] = 1.0

    delayed = delay_line.process(impulse_block)

    # The peak should be at index 480
    peak_idx = np.argmax(delayed[:, 0])
    assert peak_idx == 480, f"Expected delay at index 480, got {peak_idx}"


def test_resampler():
    """Verify resampler converts sample rates correctly."""
    resampler = AudioResampler(in_rate=48000, out_rate=24000)
    data = np.ones((1000, 2), dtype=np.float32)
    out = resampler.resample(data)
    assert out.shape == (500, 2)


def test_resampler_streaming_multi_block():
    """Verify continuous streaming across 200 blocks with fractional ratio (48k -> 44.1k) has zero phase drift."""
    resampler = AudioResampler(in_rate=48000, out_rate=44100)
    total_in = 0
    total_out = 0
    all_blocks = []

    for b in range(200):
        t_in = (b * 1024 + np.arange(1024)) / 48000.0
        sig = np.sin(2 * np.pi * 60 * t_in).astype(np.float32)[:, None]
        block = np.repeat(sig, 2, axis=1)
        out = resampler.resample(block)
        all_blocks.append(out)
        total_in += len(block)
        total_out += len(out)

    # Total in = 204,800 frames. At 44.1k/48k, ideal out = 188,160 frames.
    assert total_in == 204800
    assert total_out == 188160

    # Ensure waveform across block boundaries is smooth with no flatlining or phase drift
    streamed = np.vstack(all_blocks)
    assert not np.all(streamed[-1024:] == streamed[-1, :]), "Resampler output flatlined!"
    max_step = np.max(np.abs(np.diff(streamed[1000:, 0])))
    expected_step = 2 * np.pi * 60 / 44100.0
    assert np.abs(max_step - expected_step) < 1e-4, f"Discontinuity at block boundary: {max_step}"


def test_ring_buffer_prefill_and_clear():
    """Verify prefilling silence and resetting health counters."""
    buf = AudioRingBuffer(capacity_frames=1024, channels=2)
    buf.prefill_silence(512)
    assert buf.available() == 512
    underruns, overruns, fill = buf.get_health_stats()
    assert underruns == 0
    assert overruns == 0

    # Read the prefilled silence
    out = buf.read(512)
    assert out.shape == (512, 2)
    assert np.all(out == 0.0)
    assert buf.available() == 0

    # Test clear
    buf.write((np.ones((100, 2))).astype(np.float32))
    buf.clear()
    assert buf.available() == 0
    underruns, overruns, _ = buf.get_health_stats()
    assert underruns == 0
    assert overruns == 0

