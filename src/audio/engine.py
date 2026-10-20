"""Real-Time Multi-Threaded Audio Engine for BassBridge.

Orchestrates WASAPI loopback capture, precision Linkwitz-Riley crossover DSP,
latency delay compensation, sample rate conversion, and simultaneous dual-device output.
"""

from __future__ import annotations

import logging
import threading
import time
from enum import Enum
from typing import Callable, Optional, Tuple

import numpy as np
import pyaudiowpatch as pyaudio

from .devices import AudioDeviceInfo, DeviceManager
from .dsp import AudioDSPProcessor
from .resampler import AudioResampler
from .ring_buffer import AudioDelayLine, AudioRingBuffer

logger = logging.getLogger("BassBridge.Engine")


class EngineState(Enum):
    STOPPED = "Stopped"
    STARTING = "Starting"
    RUNNING = "Running"
    ERROR = "Error"


class AudioEngine:
    """Core real-time audio pipeline."""

    def __init__(self, device_manager: Optional[DeviceManager] = None) -> None:
        self.device_mgr = device_manager or DeviceManager()
        self.state = EngineState.STOPPED
        self.error_message: str = ""

        # Processing components
        self.dsp = AudioDSPProcessor(sample_rate=48000)
        self.delay_line = AudioDelayLine(max_delay_ms=500.0, sample_rate=48000)

        # Buffers for decoupling capture and outputs
        self.main_buffer = AudioRingBuffer(capacity_frames=48000, channels=2)
        self.bass_buffer = AudioRingBuffer(capacity_frames=48000, channels=2)

        # Resamplers (created when stream sample rates are established)
        self.main_resampler = AudioResampler(48000, 48000)
        self.bass_resampler = AudioResampler(48000, 48000)

        # Active devices
        self.capture_device: Optional[AudioDeviceInfo] = None
        self.main_device: Optional[AudioDeviceInfo] = None
        self.bass_device: Optional[AudioDeviceInfo] = None

        # PyAudio streams and instance
        self._pa: Optional[pyaudio.PyAudio] = None
        self._in_stream: Optional[pyaudio.Stream] = None
        self._main_out_stream: Optional[pyaudio.Stream] = None
        self._bass_out_stream: Optional[pyaudio.Stream] = None

        # Threads and synchronization
        self._stop_event = threading.Event()
        self._capture_thread: Optional[threading.Thread] = None
        self._main_thread: Optional[threading.Thread] = None
        self._bass_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # Engine settings
        self.buffer_size: int = 1024
        self.capture_sample_rate: int = 48000
        self.main_sample_rate: int = 48000
        self.bass_sample_rate: int = 48000

        # Health and status callback
        self.on_state_changed: Optional[Callable[[EngineState, str], None]] = None

    def set_parameters(
        self,
        crossover_freq: float,
        bass_gain_db: float,
        main_volume: float,
        bass_volume: float,
        bass_delay_ms: float,
        bass_muted: bool,
        bass_split_enabled: bool,
        bass_clarity_enabled: bool = True,
        infrasonic_cut_enabled: bool = True,
        bass_phase_inverted: bool = False,
        bass_mono_sum: bool = True,
        dolby_dialogue_boost: bool = True,
        dolby_virtual_sub: bool = True,
        dolby_spatial_widen: bool = True,
        adaptive_bass_enabled: bool = True,
    ) -> None:
        """Update DSP and delay parameters on the fly."""
        self.dsp.update_parameters(
            crossover_freq=crossover_freq,
            bass_gain_db=bass_gain_db,
            main_volume=main_volume,
            bass_volume=bass_volume,
            bass_muted=bass_muted,
            bass_split_enabled=bass_split_enabled,
            bass_clarity_enabled=bass_clarity_enabled,
            infrasonic_cut_enabled=infrasonic_cut_enabled,
            bass_phase_inverted=bass_phase_inverted,
            bass_mono_sum=bass_mono_sum,
            dolby_dialogue_boost=dolby_dialogue_boost,
            dolby_virtual_sub=dolby_virtual_sub,
            dolby_spatial_widen=dolby_spatial_widen,
            adaptive_bass_enabled=adaptive_bass_enabled,
        )
        self.delay_line.set_delay_ms(bass_delay_ms)


    def _set_state(self, new_state: EngineState, err: str = "") -> None:
        self.state = new_state
        self.error_message = err
        if self.on_state_changed:
            try:
                self.on_state_changed(new_state, err)
            except Exception as e:
                logger.error(f"Callback error in on_state_changed: {e}")

    def start(
        self,
        main_device_name: str,
        bass_device_name: str,
        capture_device_name: str = "Default",
        buffer_size: int = 1024,
    ) -> bool:
        """Start the audio engine with specified devices."""
        with self._lock:
            if self.state == EngineState.RUNNING:
                self.stop()

            self._set_state(EngineState.STARTING)
            self.buffer_size = buffer_size

            try:
                self.device_mgr.refresh()
                self._pa = pyaudio.PyAudio()

                # 1. Resolve output devices
                out_devices = self.device_mgr.get_output_devices()
                if not out_devices:
                    raise RuntimeError("No audio playback output devices found on this system.")

                # Resolve Main Device
                self.main_device = self.device_mgr.find_device_by_name(main_device_name)
                if self.main_device is None:
                    # Fallback to default output
                    for d in out_devices:
                        if d.is_default:
                            self.main_device = d
                            break
                    if self.main_device is None:
                        self.main_device = out_devices[0]

                # Resolve Bass Device
                self.bass_device = self.device_mgr.find_device_by_name(bass_device_name)
                if self.bass_device is None:
                    # If not found or not specified, choose secondary output device
                    for d in out_devices:
                        if d.name != self.main_device.name:
                            self.bass_device = d
                            break
                    if self.bass_device is None:
                        self.bass_device = self.main_device

                # 2. Resolve Capture Loopback Device
                loopbacks = self.device_mgr.get_loopback_devices()
                if not loopbacks:
                    raise RuntimeError("No WASAPI loopback capture endpoints found.")

                if capture_device_name and capture_device_name != "Default":
                    self.capture_device = self.device_mgr.find_device_by_name(
                        capture_device_name, is_loopback=True
                    )

                if self.capture_device is None:
                    # Find loopback matching main device or default
                    self.capture_device = self.device_mgr.get_loopback_for_output(self.main_device)

                logger.info(
                    f"Selected devices:\n"
                    f"  Capture: {self.capture_device.name} (idx {self.capture_device.index})\n"
                    f"  Main:    {self.main_device.name} (idx {self.main_device.index})\n"
                    f"  Bass:    {self.bass_device.name} (idx {self.bass_device.index})"
                )

                self.capture_sample_rate = self.capture_device.default_sample_rate
                self.main_sample_rate = self.main_device.default_sample_rate
                self.bass_sample_rate = self.bass_device.default_sample_rate

                # Check if capture device captures the main device's render mix
                self.capture_is_main_output = bool(
                    self.main_device and self.capture_device and (self.main_device.name in self.capture_device.name)
                )

                # Configure DSP and resamplers
                self.dsp.set_sample_rate(self.capture_sample_rate)
                self.delay_line.sample_rate = self.capture_sample_rate

                self.main_resampler = AudioResampler(self.capture_sample_rate, self.main_sample_rate)
                self.bass_resampler = AudioResampler(self.capture_sample_rate, self.bass_sample_rate)

                # Reset and prefill buffers with silence headroom to prevent startup underruns
                self.main_buffer.clear()
                self.bass_buffer.clear()
                self.delay_line.reset()
                self.dsp.reset()

                # Calculate rate-compensated buffer sizes for each output stream
                self.main_buffer_size = max(64, int(round(self.buffer_size * (self.main_sample_rate / self.capture_sample_rate))))
                self.bass_buffer_size = max(64, int(round(self.buffer_size * (self.bass_sample_rate / self.capture_sample_rate))))

                # Pre-roll 2 periods of silence into buffers to eliminate initial starvation
                self.main_buffer.prefill_silence(self.main_buffer_size * 2)
                self.bass_buffer.prefill_silence(self.bass_buffer_size * 2)

                # Open audio streams
                self._in_stream = self._pa.open(
                    format=pyaudio.paFloat32,
                    channels=2,
                    rate=self.capture_sample_rate,
                    input=True,
                    input_device_index=self.capture_device.index,
                    frames_per_buffer=self.buffer_size,
                )

                self._main_out_stream = self._pa.open(
                    format=pyaudio.paFloat32,
                    channels=2,
                    rate=self.main_sample_rate,
                    output=True,
                    output_device_index=self.main_device.index,
                    frames_per_buffer=self.main_buffer_size,
                )

                # If bass device is different, open separate stream
                if self.bass_device.index != self.main_device.index:
                    self._bass_out_stream = self._pa.open(
                        format=pyaudio.paFloat32,
                        channels=2,
                        rate=self.bass_sample_rate,
                        output=True,
                        output_device_index=self.bass_device.index,
                        frames_per_buffer=self.bass_buffer_size,
                    )
                else:
                    self._bass_out_stream = None

                # Launch processing threads
                self._stop_event.clear()

                self._capture_thread = threading.Thread(
                    target=self._capture_worker, name="BassBridge-CaptureThread", daemon=True
                )
                self._main_thread = threading.Thread(
                    target=self._main_worker, name="BassBridge-MainThread", daemon=True
                )
                self._bass_thread = threading.Thread(
                    target=self._bass_worker, name="BassBridge-BassThread", daemon=True
                )

                self._capture_thread.start()
                self._main_thread.start()
                self._bass_thread.start()

                self._set_state(EngineState.RUNNING)
                return True

            except Exception as e:
                err = f"Failed to start audio engine: {e}"
                logger.exception(err)
                self._cleanup_streams()
                self._set_state(EngineState.ERROR, err)
                return False

    def stop(self) -> None:
        """Stop processing and cleanly release all streams."""
        with self._lock:
            if self.state == EngineState.STOPPED:
                return

            self._stop_event.set()

            # Wait for threads to terminate
            for t in (self._capture_thread, self._main_thread, self._bass_thread):
                if t is not None and t.is_alive():
                    t.join(timeout=1.0)

            self._cleanup_streams()
            self._set_state(EngineState.STOPPED)

    def _cleanup_streams(self) -> None:
        """Safely close all audio streams and terminate PyAudio."""
        for stream in (self._in_stream, self._main_out_stream, self._bass_out_stream):
            if stream is not None:
                try:
                    stream.stop_stream()
                except Exception:
                    pass
                try:
                    stream.close()
                except Exception:
                    pass

        self._in_stream = None
        self._main_out_stream = None
        self._bass_out_stream = None

        if self._pa is not None:
            try:
                self._pa.terminate()
            except Exception:
                pass
            self._pa = None

    def _capture_worker(self) -> None:
        """Worker thread: captures loopback audio, applies crossover DSP, and buffers outputs."""
        logger.info("Capture worker started.")
        while not self._stop_event.is_set():
            try:
                if self._in_stream is None or not self._in_stream.is_active():
                    time.sleep(0.01)
                    continue

                # Read raw PCM bytes from WASAPI loopback
                raw_bytes = self._in_stream.read(self.buffer_size, exception_on_overflow=False)
                if not raw_bytes:
                    continue

                # Parse into stereo float32
                audio_block = np.frombuffer(raw_bytes, dtype=np.float32)
                if audio_block.size == 0:
                    continue

                # Reshape to (N, 2)
                if audio_block.size % 2 == 0:
                    audio_block = audio_block.reshape(-1, 2)
                else:
                    audio_block = np.column_stack((audio_block, audio_block))

                # Step 1: Run real-time Linkwitz-Riley 4th-order crossover & DSP
                main_audio, bass_audio = self.dsp.process_block(audio_block)

                # Step 2: Delay compensation
                # Delay the main audio path so laptop speakers wait for Bluetooth latency
                main_audio = self.delay_line.process(main_audio)

                # Step 3: Resample if output sample rate differs
                main_resampled = self.main_resampler.resample(main_audio)
                bass_resampled = self.bass_resampler.resample(bass_audio)

                # Step 4: Write to ring buffers for output threads
                self.main_buffer.write(main_resampled)
                self.bass_buffer.write(bass_resampled)

            except Exception as e:
                if not self._stop_event.is_set():
                    logger.error(f"Error in capture worker: {e}")
                    self._set_state(
                        EngineState.ERROR,
                        f"Capture stream error: {e}. Check if audio device was disconnected.",
                    )
                break
        logger.info("Capture worker terminated.")

    def _main_worker(self) -> None:
        """Worker thread: renders high-pass / main audio to primary playback endpoint."""
        logger.info("Main output worker started.")
        while not self._stop_event.is_set():
            try:
                if self._main_out_stream is None or not self._main_out_stream.is_active():
                    time.sleep(0.01)
                    continue

                # Determine output chunk size
                frames = self.main_buffer_size
                block = self.main_buffer.read(frames)

                # If capture device is the loopback of main_device:
                # The laptop speaker is ALREADY physically playing Windows master audio!
                # Writing back to main_device re-renders the captured audio, creating an infinite echo/feedback loop!
                if self.capture_is_main_output:
                    time.sleep(frames / max(1, self.main_sample_rate))
                    continue

                # If same device is used for both main and bass, mix them
                if self._bass_out_stream is None:
                    bass_block = self.bass_buffer.read(frames)
                    block = block + bass_block

                # Convert to bytes and write to stream
                data_bytes = block.tobytes()
                self._main_out_stream.write(data_bytes)

            except Exception as e:
                if not self._stop_event.is_set():
                    logger.error(f"Error in main output worker: {e}")
                    self._set_state(
                        EngineState.ERROR,
                        f"Main output error: {e}. Audio device may have disconnected.",
                    )
                break
        logger.info("Main output worker terminated.")

    def _bass_worker(self) -> None:
        """Worker thread: renders low-pass / bass audio to Bluetooth endpoint."""
        logger.info("Bass output worker started.")
        while not self._stop_event.is_set():
            try:
                if self._bass_out_stream is None or not self._bass_out_stream.is_active():
                    time.sleep(0.02)
                    continue

                frames = self.bass_buffer_size
                block = self.bass_buffer.read(frames)
                data_bytes = block.tobytes()
                self._bass_out_stream.write(data_bytes)

            except Exception as e:
                if not self._stop_event.is_set():
                    logger.error(f"Error in bass output worker: {e}")
                    self._set_state(
                        EngineState.ERROR,
                        f"Bass output error: {e}. Bluetooth speaker may have disconnected.",
                    )
                break
        logger.info("Bass output worker terminated.")

    def get_metrics(self) -> dict:
        """Return real-time diagnostic information for UI meters and monitors."""
        main_underrun, main_overrun, main_fill = self.main_buffer.get_health_stats()
        bass_underrun, bass_overrun, bass_fill = self.bass_buffer.get_health_stats()

        return {
            "state": self.state.value,
            "error": self.error_message,
            "capture_rate": self.capture_sample_rate,
            "main_rate": self.main_sample_rate,
            "bass_rate": self.bass_sample_rate,
            "buffer_size": self.buffer_size,
            "main_peak": self.dsp.last_main_peak,
            "main_rms": self.dsp.last_main_rms,
            "bass_peak": self.dsp.last_bass_peak,
            "bass_rms": self.dsp.last_bass_rms,
            "main_underruns": main_underrun,
            "main_overruns": main_overrun,
            "bass_underruns": bass_underrun,
            "bass_overruns": bass_overrun,
            "main_buffer_fill": main_fill,
            "bass_buffer_fill": bass_fill,
            "is_split_mode": not getattr(self, "capture_is_main_output", False),
        }

