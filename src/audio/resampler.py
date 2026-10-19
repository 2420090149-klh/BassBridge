"""Sample rate conversion utility for audio streams with different sampling frequencies.

Handles conversions between standard Windows audio rates (e.g. 44.1 kHz, 48 kHz, 96 kHz)
with continuous fractional-phase tracking, zero drift, and click-free block boundary continuity.
"""

from __future__ import annotations

import numpy as np


class AudioResampler:
    """Real-time sample rate converter with exact fractional phase tracking and block-boundary preservation."""

    def __init__(self, in_rate: int, out_rate: int, channels: int = 2) -> None:
        self.in_rate = int(in_rate)
        self.out_rate = int(out_rate)
        self.channels = int(channels)
        self.is_passthrough = (self.in_rate == self.out_rate)
        self.ratio = (self.in_rate / float(self.out_rate)) if self.out_rate > 0 else 1.0
        self.cursor: float = 0.0
        self.last_frame: np.ndarray = np.zeros((1, self.channels), dtype=np.float32)

    def resample(self, audio: np.ndarray) -> np.ndarray:
        """Resample audio block smoothly from in_rate to out_rate with zero boundary clicks and zero phase drift.

        Args:
            audio: numpy float32 array of shape (N, channels) or (N,).

        Returns:
            numpy float32 array of shape (M, channels) or (M,).
        """
        if self.is_passthrough or audio.size == 0:
            return audio

        is_1d = (audio.ndim == 1)
        if is_1d:
            audio_2d = np.column_stack((audio, audio))
        else:
            audio_2d = audio

        n_in = audio_2d.shape[0]
        channels = audio_2d.shape[1]

        if self.last_frame.shape[1] != channels:
            self.last_frame = np.zeros((1, channels), dtype=np.float32)

        # Prepend last frame from preceding block for boundary continuity
        # In padded coordinates: index 0 is t = -1.0, index 1 is t = 0.0, ..., index n_in is t = n_in - 1.0
        padded = np.vstack([self.last_frame, audio_2d])
        self.last_frame = audio_2d[-1:, :].copy()

        # Maximum time t we can interpolate without exceeding padded boundary is n_in - 1.0
        max_span = (n_in - 1.0) - self.cursor
        if max_span < 0:
            n_out = 0
        else:
            n_out = int(np.floor(max_span / self.ratio)) + 1

        if n_out > 0:
            t_out = self.cursor + np.arange(n_out, dtype=np.float64) * self.ratio
            # In padded coordinates: t_pad = t_out + 1.0
            t_pad = t_out + 1.0
            idx0 = np.floor(t_pad).astype(np.int64)
            idx1 = idx0 + 1
            idx0 = np.clip(idx0, 0, len(padded) - 2)
            idx1 = np.clip(idx1, 1, len(padded) - 1)
            frac = (t_pad - idx0).astype(np.float32)[:, None]
            out = (1.0 - frac) * padded[idx0] + frac * padded[idx1]
            next_t = float(self.cursor + n_out * self.ratio)
        else:
            out = np.zeros((0, channels), dtype=np.float32)
            next_t = float(self.cursor)

        # Advance cursor relative to the new block boundary
        self.cursor = float(next_t - n_in)

        if is_1d:
            return out[:, 0].astype(np.float32)
        return out.astype(np.float32)

    def reset(self) -> None:
        """Reset phase cursor and boundary history."""
        self.cursor = 0.0
        self.last_frame.fill(0.0)
