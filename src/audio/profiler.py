"""Speaker Model Detection and Intelligent Acoustic Profiling for BassBridge.

Automatically classifies speaker hardware (Soundbars, Compact Wireless,
Low-Latency Headsets, Studio/Direct Audio) and tunes crossover, latency,
and subsonic infrasonic filters without requiring user brand selection.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class SpeakerProfile:
    """Acoustic profile settings automatically tuned for a detected speaker category."""

    category_id: str              # "soundbar", "compact_wireless", "headset", "direct", "generic"
    display_title: str            # e.g., "Soundbar / Home Theater"
    detected_brand_or_model: str  # Clean display name
    recommended_delay_ms: int     # e.g., 170, 135, 45, 0, 125
    recommended_crossover_hz: int # e.g., 100, 115, 85, 85, 95
    recommended_subsonic_hz: int  # e.g., 38, 52, 35, 40, 50
    recommended_bass_volume: int  # 0 to 150
    dialogue_clarity: bool        # True
    subsonic_guard: bool          # True
    auto_eq: bool                 # True
    description: str              # Human-readable rationale


class SpeakerProfiler:
    """Automatic model detector and acoustic tuning engine."""

    @classmethod
    def clean_device_label(cls, raw_name: str) -> str:
        """Extract a readable speaker model name from OS device strings."""
        if not raw_name:
            return "Default Speaker"

        # Remove parenthetical descriptions including nested ones like (Realtek(R) Audio)
        cleaned = re.sub(r"\s*\((?:[^()]*|\([^()]*\))*\)", "", raw_name)
        # Remove common technical suffixes
        cleaned = re.sub(r"\s*Hands-Free AG Audio", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*Stereo", "", cleaned, flags=re.IGNORECASE)
        cleaned = cleaned.strip()
        return cleaned if cleaned else raw_name.strip()

    @classmethod
    def detect_profile(cls, device_name: str) -> SpeakerProfile:
        """Analyze a device name and return the optimal tuned SpeakerProfile."""
        name_lower = (device_name or "").lower().strip()
        display_name = cls.clean_device_label(device_name)

        # 1. Direct / Wired / Studio DAC / Laptop Internal
        wired_keywords = [
            "realtek", "conexant", "synaptics", "smart sound", "high definition audio",
            "internal", "built-in", "line out", "headphones (realtek", "speakers (realtek",
            "analog", "usb dac", "fiio", "focusrite", "scarlett", "direct", "aux"
        ]
        if any(k in name_lower for k in wired_keywords) and not any(k in name_lower for k in ["bluetooth", "wireless"]):
            return SpeakerProfile(
                category_id="direct",
                display_title="Direct Wired / Studio Audio",
                detected_brand_or_model=display_name,
                recommended_delay_ms=0,
                recommended_crossover_hz=85,
                recommended_subsonic_hz=40,
                recommended_bass_volume=100,
                dialogue_clarity=True,
                subsonic_guard=True,
                auto_eq=True,
                description="Direct wired DAC/analog connection detected. 0ms zero-latency applied."
            )

        # 2. Soundbars / Home Theaters / Smart TVs
        soundbar_keywords = [
            "soundbar", "bar", "theatre", "theater", "tv", "hdmi", "arc", "earc",
            "receiver", "optical", "spdif", "bravia", "vizio", "tcl", "hisense",
            "home theater", "surround", "cinema", "subwoofer", "lg audio"
        ]
        if any(k in name_lower for k in soundbar_keywords):
            return SpeakerProfile(
                category_id="soundbar",
                display_title="Soundbar / Home Theater",
                detected_brand_or_model=display_name,
                recommended_delay_ms=170,
                recommended_crossover_hz=100,
                recommended_subsonic_hz=38,
                recommended_bass_volume=105,
                dialogue_clarity=True,
                subsonic_guard=True,
                auto_eq=True,
                description="Home theater / soundbar detected. 170ms sync tuned for DSP pipeline; 38Hz subsonic floor enabled."
            )

        # 3. Low-Latency Headsets / Earbuds / TWS
        headset_keywords = [
            "headphone", "headset", "earphone", "earbuds", "buds", "airpod",
            "tws", "gaming", "wh-", "wf-", "freebuds", "pixel buds", "galaxy buds"
        ]
        if any(k in name_lower for k in headset_keywords):
            return SpeakerProfile(
                category_id="headset",
                display_title="Low-Latency Headset / Earphones",
                detected_brand_or_model=display_name,
                recommended_delay_ms=45,
                recommended_crossover_hz=85,
                recommended_subsonic_hz=35,
                recommended_bass_volume=95,
                dialogue_clarity=True,
                subsonic_guard=True,
                auto_eq=True,
                description="Low-latency personal headset detected. 45ms sync tuned with tight binaural sub-bass."
            )

        # 4. Compact Wireless / Portable Bluetooth Speakers (Universal match)
        wireless_keywords = [
            "bluetooth", "wireless", "bt", "speaker", "portable", "mini", "go",
            "flip", "charge", "pill", "clip", "boom", "box", "audio", "jbl",
            "sony", "bose", "marshall", "anker", "soundcore", "tribit", "zebronics",
            "mivi", "boat", "stone", "echo", "dot", "nest", "wonderboom", "megaboom"
        ]
        if any(k in name_lower for k in wireless_keywords):
            return SpeakerProfile(
                category_id="compact_wireless",
                display_title="Compact Wireless Speaker",
                detected_brand_or_model=display_name,
                recommended_delay_ms=135,
                recommended_crossover_hz=115,
                recommended_subsonic_hz=52,
                recommended_bass_volume=100,
                dialogue_clarity=True,
                subsonic_guard=True,
                auto_eq=True,
                description="Compact wireless speaker detected. 135ms sync applied; 52Hz subsonic guard active to protect passive radiators."
            )

        # 5. Universal Fallback
        return SpeakerProfile(
            category_id="generic",
            display_title="Universal Audio Profile",
            detected_brand_or_model=display_name,
            recommended_delay_ms=125,
            recommended_crossover_hz=95,
            recommended_subsonic_hz=50,
            recommended_bass_volume=100,
            dialogue_clarity=True,
            subsonic_guard=True,
            auto_eq=True,
            description="Universal speaker profile tuned: 125ms delay, 50Hz rumble cut, and balanced crossover."
        )
