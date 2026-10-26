"""Thread-safe Ring Buffer and Delay Line for real-time audio streams.

Handles variable delay compensation (0-500 ms), underrun and overrun detection,
and bounded buffer management between capture and dual output threads.
"""

from __future__ import annotations

import threading
from typing import Optional, Tuple

import numpy as np


class AudioRingBuffer:
    """Thread-safe circular ring buffer for multi-channel audio data."""

    def __init__(self, capacity_frames: int = 48000, channels: int = 2) -> None:
        self.capacity_frames = int(capacity_frames)
        self.channels = int(channels)
        self._buffer = np.zeros((self.capacity_frames, self.channels), dtype=np.float32)

        self._read_idx: int = 0
        self._write_idx: int = 0
        self._available_frames: int = 0

        self._lock = threading.Lock()

        # Health counters
        self.overrun_count: int = 0
        self.underrun_count: int = 0

    def write(self, data: np.ndarray) -> int:
        """Write audio data to the buffer. Drops oldest or skips if full.

        Returns:
            Number of frames written.
        """
        frames_to_write = data.shape[0]
        if frames_to_write == 0:
            return 0

        with self._lock:
            free_space = self.capacity_frames - self._available_frames
            if frames_to_write > free_space:
                # Buffer overrun occurred
                self.overrun_count += 1
                # Drop oldest data to make room
                drop = frames_to_write - free_space
                self._read_idx = (self._read_idx + drop) % self.capacity_frames
                self._available_frames -= drop

            # Write data (may wrap around circular boundary)
            end_idx = self._write_idx + frames_to_write
            if end_idx <= self.capacity_frames:
                self._buffer[self._write_idx:end_idx] = data
            else:
                first_part = self.capacity_frames - self._write_idx
                self._buffer[self._write_idx:] = data[:first_part]
                self._buffer[:frames_to_write - first_part] = data[first_part:]

            self._write_idx = (self._write_idx + frames_to_write) % self.capacity_frames
            self._available_frames += frames_to_write
            return frames_to_write

    def read(self, num_frames: int) -> np.ndarray:
        """Read audio data from the buffer. Pads with silence if underrun.

        Returns:
            numpy array of shape (num_frames, channels) as float32.
        """
        if num_frames <= 0:
            return np.zeros((0, self.channels), dtype=np.float32)

        with self._lock:
            if self._available_frames < num_frames:
                # Underrun occurred
                self.underrun_count += 1
                out = np.zeros((num_frames, self.channels), dtype=np.float32)
                if self._available_frames > 0:
                    available = self._available_frames
                    end_idx = self._read_idx + available
                    if end_idx <= self.capacity_frames:
                        out[:available] = self._buffer[self._read_idx:end_idx]
                    else:
                        first_part = self.capacity_frames - self._read_idx
                        out[:first_part] = self._buffer[self._read_idx:]
                        out[first_part:available] = self._buffer[:available - first_part]

                    self._read_idx = (self._read_idx + available) % self.capacity_frames
                    self._available_frames = 0
                return out

            out = np.empty((num_frames, self.channels), dtype=np.float32)
            end_idx = self._read_idx + num_frames
            if end_idx <= self.capacity_frames:
                out[:] = self._buffer[self._read_idx:end_idx]
            else:
                first_part = self.capacity_frames - self._read_idx
                out[:first_part] = self._buffer[self._read_idx:]
                out[first_part:] = self._buffer[:num_frames - first_part]

            self._read_idx = (self._read_idx + num_frames) % self.capacity_frames
            self._available_frames -= num_frames
            return out

    def read_drift_locked(
        self,
        num_frames: int,
        target_depth: int,
        tolerance: int = 48,
    ) -> np.ndarray:
        """Read audio data with elastic watermark phase locking to eradicate clock drift.

        Maintains internal buffer fill level strictly centered around target_depth.
        If fill level exceeds target_depth + tolerance (output clock is slower),
        it imperceptibly trims 1 frame per block using smooth linear resampling.
        If fill level drops below target_depth - tolerance (output clock is faster),
        it imperceptibly inserts 1 frame per block using smooth linear resampling.
        """
        if num_frames <= 0:
            return np.zeros((0, self.channels), dtype=np.float32)

        with self._lock:
            avail = self._available_frames

        # Check drift condition
        if avail > target_depth + tolerance and avail >= num_frames + 1:
            raw_block = self.read(num_frames + 1)
            old_indices = np.linspace(0.0, 1.0, num_frames + 1, endpoint=True)
            new_indices = np.linspace(0.0, 1.0, num_frames, endpoint=True)
            out = np.empty((num_frames, self.channels), dtype=np.float32)
            for ch in range(self.channels):
                out[:, ch] = np.interp(new_indices, old_indices, raw_block[:, ch])
            return out

        elif avail < target_depth - tolerance and avail >= max(2, num_frames - 1):
            raw_block = self.read(num_frames - 1)
            in_len = raw_block.shape[0]
            if in_len < 2:
                out = np.zeros((num_frames, self.channels), dtype=np.float32)
                out[:in_len] = raw_block
                return out
            old_indices = np.linspace(0.0, 1.0, in_len, endpoint=True)
            new_indices = np.linspace(0.0, 1.0, num_frames, endpoint=True)
            out = np.empty((num_frames, self.channels), dtype=np.float32)
            for ch in range(self.channels):
                out[:, ch] = np.interp(new_indices, old_indices, raw_block[:, ch])
            return out

        else:
            return self.read(num_frames)

    def available(self) -> int:
        """Return number of frames currently buffered."""
        with self._lock:
            return self._available_frames

    def clear(self) -> None:
        """Clear all buffered data and reset pointers and health counters."""
        with self._lock:
            self._buffer.fill(0.0)
            self._read_idx = 0
            self._write_idx = 0
            self._available_frames = 0
            self.underrun_count = 0
            self.overrun_count = 0

    def prefill_silence(self, num_frames: int) -> None:
        """Prefill buffer with silence frames to prevent startup starvation underruns."""
        with self._lock:
            count = min(int(num_frames), self.capacity_frames)
            self._buffer[:count].fill(0.0)
            self._write_idx = count % self.capacity_frames
            self._read_idx = 0
            self._available_frames = count
            self.underrun_count = 0
            self.overrun_count = 0

    def get_health_stats(self) -> Tuple[int, int, float]:
        """Return (underruns, overruns, fill_ratio)."""
        with self._lock:
            fill = self._available_frames / max(1, self.capacity_frames)
            return self.underrun_count, self.overrun_count, fill


class AudioDelayLine:
    """Configurable delay line for audio synchronization (0 to 500 ms)."""

    def __init__(self, max_delay_ms: float = 500.0, sample_rate: int = 48000, channels: int = 2) -> None:
        self.sample_rate = int(sample_rate)
        self.channels = int(channels)
        self.max_delay_ms = float(max_delay_ms)
        self.max_delay_frames = int(np.ceil((self.max_delay_ms / 1000.0) * self.sample_rate)) + 4096

        self._buffer = np.zeros((self.max_delay_frames, self.channels), dtype=np.float32)
        self._write_idx: int = 0
        self.delay_ms: float = 0.0
        self._delay_frames: int = 0
        self._lock = threading.Lock()

    def set_delay_ms(self, delay_ms: float) -> None:
        """Set delay duration in milliseconds."""
        with self._lock:
            self.delay_ms = max(0.0, min(self.max_delay_ms, float(delay_ms)))
            self._delay_frames = int(round((self.delay_ms / 1000.0) * self.sample_rate))

    def process(self, input_block: np.ndarray) -> np.ndarray:
        """Process an audio block through the delay line."""
        frames = input_block.shape[0]
        if frames == 0 or self._delay_frames == 0:
            return input_block.copy()

        with self._lock:
            delay_f = self._delay_frames
            cap = self.max_delay_frames
            out = np.empty_like(input_block)

            # Vectorized circular write
            w = self._write_idx
            if w + frames <= cap:
                self._buffer[w:w + frames] = input_block
            else:
                p1 = cap - w
                self._buffer[w:] = input_block[:p1]
                self._buffer[:frames - p1] = input_block[p1:]

            # Vectorized circular read with delay_f offset
            r = (w - delay_f) % cap
            if r + frames <= cap:
                out[:] = self._buffer[r:r + frames]
            else:
                p1 = cap - r
                out[:p1] = self._buffer[r:]
                out[p1:] = self._buffer[:frames - p1]

            self._write_idx = (w + frames) % cap
            return out

    def reset(self) -> None:
        """Reset internal buffer state."""
        with self._lock:
            self._buffer.fill(0.0)
            self._write_idx = 0
