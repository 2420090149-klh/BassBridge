"""Windows Audio Endpoint discovery and device management.

Uses PyAudioWPatch for high-performance WASAPI device enumeration,
loopback detection, and format querying. Provides fallbacks and helpers
for identifying Bluetooth endpoints and opening Windows Bluetooth settings.
"""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from typing import List, Optional, Tuple

import pyaudiowpatch as pyaudio


@dataclass
class AudioDeviceInfo:
    """Information about an audio endpoint."""
    index: int
    name: str
    host_api: int
    host_api_name: str
    max_input_channels: int
    max_output_channels: int
    default_sample_rate: int
    is_loopback: bool
    is_default: bool = False
    is_bluetooth: bool = False
    is_laptop_speaker: bool = False
    is_virtual_sink: bool = False


class DeviceManager:
    """Discovers and tracks Windows audio playback and loopback endpoints."""

    def __init__(self) -> None:
        self._pa: Optional[pyaudio.PyAudio] = None
        self._wasapi_host_api_index: Optional[int] = None
        self._initialize_pyaudio()

    def _initialize_pyaudio(self) -> None:
        """Initialize or re-initialize PyAudio instance."""
        if self._pa is not None:
            try:
                self._pa.terminate()
            except Exception:
                pass
            self._pa = None

        self._pa = pyaudio.PyAudio()
        self._wasapi_host_api_index = None
        try:
            wasapi_info = self._pa.get_host_api_info_by_type(pyaudio.paWASAPI)
            self._wasapi_host_api_index = wasapi_info["index"]
        except Exception as e:
            print(f"[DeviceManager] WASAPI host API not found via paWASAPI type: {e}")
            for i in range(self._pa.get_host_api_count()):
                info = self._pa.get_host_api_info_by_index(i)
                if "WASAPI" in info.get("name", "").upper():
                    self._wasapi_host_api_index = i
                    break

    def refresh(self) -> None:
        """Refresh device lists by re-initializing the underlying audio system."""
        self._initialize_pyaudio()

    def get_output_devices(self) -> List[AudioDeviceInfo]:
        """Return all available WASAPI playback output devices (speakers, headphones, BT)."""
        devices: List[AudioDeviceInfo] = []
        if self._pa is None or self._wasapi_host_api_index is None:
            return devices

        try:
            wasapi_info = self._pa.get_host_api_info_by_index(self._wasapi_host_api_index)
            default_out_idx = wasapi_info.get("defaultOutputDevice", -1)
        except Exception:
            default_out_idx = -1

        for i in range(self._pa.get_device_count()):
            try:
                info = self._pa.get_device_info_by_index(i)
            except Exception:
                continue

            if info.get("hostApi") != self._wasapi_host_api_index:
                continue

            # Output devices have maxOutputChannels > 0 and are NOT loopbacks
            if info.get("maxOutputChannels", 0) > 0 and not info.get("isLoopbackDevice", False):
                name = info.get("name", f"Output Device {i}")
                rate = int(info.get("defaultSampleRate", 48000))
                is_bt = self._is_likely_bluetooth(name)
                is_laptop = self._is_likely_laptop_speaker(name)
                is_sink = self._is_likely_virtual_sink(name)

                devices.append(
                    AudioDeviceInfo(
                        index=i,
                        name=name,
                        host_api=self._wasapi_host_api_index,
                        host_api_name="WASAPI",
                        max_input_channels=0,
                        max_output_channels=int(info.get("maxOutputChannels", 2)),
                        default_sample_rate=rate,
                        is_loopback=False,
                        is_default=(i == default_out_idx),
                        is_bluetooth=is_bt,
                        is_laptop_speaker=is_laptop,
                        is_virtual_sink=is_sink,
                    )
                )

        return devices

    def get_default_output_device(self) -> Optional[AudioDeviceInfo]:
        """Return the current Windows default playback output device."""
        outputs = self.get_output_devices()
        for d in outputs:
            if d.is_default:
                return d
        return outputs[0] if outputs else None

    def get_loopback_devices(self) -> List[AudioDeviceInfo]:
        """Return all available WASAPI loopback capture endpoints."""
        devices: List[AudioDeviceInfo] = []
        if self._pa is None or self._wasapi_host_api_index is None:
            return devices

        try:
            wasapi_info = self._pa.get_host_api_info_by_index(self._wasapi_host_api_index)
            default_out_idx = wasapi_info.get("defaultOutputDevice", -1)
            default_out_name = ""
            if default_out_idx >= 0:
                default_out_name = self._pa.get_device_info_by_index(default_out_idx).get("name", "")
        except Exception:
            default_out_name = ""

        for i in range(self._pa.get_device_count()):
            try:
                info = self._pa.get_device_info_by_index(i)
            except Exception:
                continue

            if info.get("hostApi") != self._wasapi_host_api_index:
                continue

            # PyAudioWPatch marks WASAPI loopback devices with isLoopbackDevice=True
            if info.get("isLoopbackDevice", False):
                name = info.get("name", f"Loopback Device {i}")
                rate = int(info.get("defaultSampleRate", 48000))
                is_def = (default_out_name != "") and (default_out_name in name)
                is_sink = self._is_likely_virtual_sink(name)

                devices.append(
                    AudioDeviceInfo(
                        index=i,
                        name=name,
                        host_api=self._wasapi_host_api_index,
                        host_api_name="WASAPI",
                        max_input_channels=int(info.get("maxInputChannels", 2)),
                        max_output_channels=0,
                        default_sample_rate=rate,
                        is_loopback=True,
                        is_default=is_def,
                        is_bluetooth=False,
                        is_laptop_speaker=False,
                        is_virtual_sink=is_sink,
                    )
                )

        return devices

    def find_device_by_name(self, name: str, is_loopback: bool = False) -> Optional[AudioDeviceInfo]:
        """Look up a device by exact name or substring match."""
        candidates = self.get_loopback_devices() if is_loopback else self.get_output_devices()
        if not candidates:
            return None

        # 1. Exact match
        for dev in candidates:
            if dev.name == name:
                return dev

        # 2. Case-insensitive exact match
        for dev in candidates:
            if dev.name.lower() == name.lower():
                return dev

        # 3. Substring match
        for dev in candidates:
            if name.lower() in dev.name.lower() or dev.name.lower() in name.lower():
                return dev

        return None

    def get_loopback_for_output(self, output_device: AudioDeviceInfo) -> Optional[AudioDeviceInfo]:
        """Find the corresponding loopback device for a given playback output device."""
        loopbacks = self.get_loopback_devices()
        # Clean device name (e.g. remove trailing [Loopback] if any)
        clean_name = output_device.name.strip()
        for lb in loopbacks:
            if clean_name in lb.name:
                return lb
        # Fallback: if only 1 loopback or default
        for lb in loopbacks:
            if lb.is_default:
                return lb
        return loopbacks[0] if loopbacks else None

    @staticmethod
    def _is_likely_bluetooth(name: str) -> bool:
        """Heuristic check to detect Bluetooth devices (Echo, JBL, Sony, Buds, boAt, etc.)."""
        n = name.lower()
        # Laptop internal speakers should never be identified as bluetooth
        laptop_keywords = ["realtek", "conexant", "synaptics", "smart sound", "high definition audio", "internal"]
        if any(k in n for k in laptop_keywords):
            return False

        keywords = [
            "bluetooth", "echo", "dot", "jbl", "sony", "bose", "anker", "soundcore",
            "buds", "airpods", "wireless", "bt", "marshall", "harman", "beats",
            "boat", "stone", "headphone", "headset", "earphone"
        ]
        return any(k in n for k in keywords)

    @staticmethod
    def _is_likely_laptop_speaker(name: str) -> bool:
        """Heuristic check to detect internal laptop speakers (Realtek, Conexant, Intel, etc.)."""
        n = name.lower()
        keywords = ["realtek", "conexant", "synaptics", "smart sound", "high definition audio", "internal"]
        return any(k in n for k in keywords)

    @staticmethod
    def _is_likely_virtual_sink(name: str) -> bool:
        """Heuristic check to detect virtual / software audio sinks (OMEN Cam & Voice, Cable, etc.)."""
        n = name.lower()
        keywords = ["omen", "voice", "virtual", "cable", "vb-audio", "voicemeeter", "stereo mix", "streaming", "sink"]
        return any(k in n for k in keywords)

    @staticmethod
    def open_windows_bluetooth_settings() -> bool:
        """Launch Windows Bluetooth & Devices settings page."""
        try:
            os.system("start ms-settings:bluetooth")
            return True
        except Exception as e:
            print(f"[DeviceManager] Failed to launch Bluetooth settings: {e}")
            return False

    @staticmethod
    def open_windows_sound_settings() -> bool:
        """Launch Windows Sound Settings page."""
        try:
            os.system("start ms-settings:sound")
            return True
        except Exception as e:
            print(f"[DeviceManager] Failed to launch Sound settings: {e}")
            return False

    def close(self) -> None:
        """Release PyAudio resources."""
        if self._pa is not None:
            try:
                self._pa.terminate()
            except Exception:
                pass
            self._pa = None
