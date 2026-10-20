# 🔊 BassBridge

> **Turn Any Bluetooth Speaker into a Wireless Dolby Atmos Subwoofer**  
> Split audio in real-time with zero dialogue bleed, zero paper-rumbling distortion, and millisecond-accurate sync calibration.

[![GitHub Pages](https://img.shields.io/badge/Live_Site-GitHub_Pages-00F0FF?style=flat-square&logo=github)](https://2420090149-klh.github.io/BassBridge/)
[![License: MIT](https://img.shields.io/badge/License-MIT-A855F7?style=flat-square)](LICENSE)
[![Platform: Windows | TV | Mobile | Mac](https://img.shields.io/badge/Platform-Windows_%7C_Smart_TV_%7C_Android_%7C_iOS_%7C_macOS-10B981?style=flat-square)](#platform-support)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-3B82F6?style=flat-square&logo=python)](https://python.org)

---

## 🌟 Key Features

- **🗣️ Dolby Atmos Vocal Presence EQ (+2.0 dB @ 2.4 kHz)**:
  Tuned for movie & YouTube streaming (Netflix, Prime, YouTube). Dialogue and speech cut through clearly without being muffled by heavy action scenes or basslines.
- **⚡ Linkwitz-Riley 8th-Order (LR8, 48 dB/octave) Acoustic Crossover**:
  Steeper than standard filters. Provides **>39 dB attenuation at 150 Hz** (<1% amplitude), ending the "voice doubling / echoing" issue in Bluetooth speakers completely.
- **🛡️ Subsonic 55 Hz 8th-Order Infrasonic Cone Protection (48 dB/octave)**:
  Crushes inaudible 20–35 Hz subsonic flutter by **-38 dB**. Eliminates mechanical driver bottoming-out and the fluttering "paper rumbling sound" on compact portable Bluetooth speakers and passive radiators.
- **🎚️ Dynamic Frequency-Dependent Auto-EQ & Bass De-Boomer**:
  Automatically balances master volume and sub-bass volume depending on frequency and dialogue presence. During heavy action explosions, it ducks excessive bass to protect drivers and avoid boomy mud; when dialogue is present, it prioritizes speech intelligibility.
- **🔊 Pure Chebyshev 2nd Harmonic Virtual Sub Synthesizer**:
  Synthesizes clean upper punch (70–140 Hz) without introducing DC offsets or sub-infrasonic beat rumble.
- **🌌 Dolby 3D Spatial Soundstage Widening**:
  Widens ambient sound on laptop and TV speakers while keeping center dialogue firmly locked on screen.
- **⏱️ Universal Latency Sync Calibration**:
  Millisecond delay compensation (0–500 ms) with **Automated Speaker Model Detection**, **1-Tap Mic Acoustic Ping Calibration**, and **Ring Buffer Watermark Lock** to completely eliminate latency drift.

---

## 📺 Smart TV Standalone (No Laptop Needed!)

You don't need a laptop to use BassBridge with your Smart TV:

### 1. Direct Smart TV Web App (PWA) — *Works on ALL Smart TVs*
1. Open your TV browser:
   - **Amazon Fire TV**: Amazon Silk Browser
   - **Samsung Smart TV**: Samsung Internet
   - **LG webOS TV**: WebOS Browser
   - **Android TV / Google TV**: Chrome / JioPages / TV Bro
2. Visit **`https://2420090149-klh.github.io/BassBridge/`**
3. Bookmark or pin it to your TV Home Screen.
4. The real-time Web Audio DSP player runs natively on your TV with live delay sync calibration!

### 2. Standalone Android TV / Fire TV APK
- Install using the **Downloader** app on Fire TV / Google TV:
  - Enter the download URL from GitHub Releases or sideload via USB / ADB.
  - Runs in the background and routes sub-bass to your Bluetooth speaker while TV speakers handle dialogue.

---

## 📱 Mobile App (Android & iPhone)

Install BassBridge directly as an app shortcut on your phone's home screen:

- **Android (Chrome)**: Open `https://2420090149-klh.github.io/BassBridge/` &rarr; Tap the **Install App** banner (or menu &rarr; *Install app*).
- **iPhone / iPad (Safari)**: Open the link &rarr; Tap **Share** (⎋) &rarr; Tap **Add to Home Screen** (+).

---

## 💻 Windows Desktop (Standalone Portable)

### Download & Run
1. Download **`BassBridge-Windows-Portable.zip`** from [GitHub Releases](https://github.com/2420090149-klh/BassBridge/releases).
2. Unzip the folder.
3. Double-click **`BassBridge.exe`** (or run `Launch_BassBridge.bat`).
4. Select:
   - **Main Speaker**: Laptop or Desktop Speakers (plays crystal-clear dialogue & highs)
   - **Bass Speaker**: Connected Bluetooth Speaker (plays deep sub-bass)
5. Click **Start Audio Engine**!

### Developer Setup
```bash
git clone https://github.com/2420090149-klh/BassBridge.git
cd BassBridge
pip install -r requirements.txt
python main.py
```

### Running Unit Tests
```bash
pytest tests/ -v
```

---

## ⚡ Delay Compensation Guide

| Speaker Hardware Category | Recommended Latency Preset | Auto-Detected Settings |
|---|---|---|
| **Compact Wireless Speaker** | `135 ms` | 115 Hz Crossover, 52 Hz Subsonic Guard |
| **Soundbar / Home Theater** | `170 ms` | 100 Hz Crossover, 38 Hz Subsonic Floor |
| **Smart TV Internal + BT Companion** | `180 ms` | 95 Hz Crossover, 50 Hz Subsonic Guard |
| **Low-Latency Gaming Earbuds** | `45 ms` | 85 Hz Crossover, Tight Binaural Sub |
| **Direct Wired / Studio DAC** | `0 ms` | 85 Hz Crossover, Zero-Latency Direct |

Use the built-in **Live Latency Sync Calibrator** on the website or in the desktop app to calibrate your speakers with a single tap.

---

## 📄 License

MIT License • Free & Open Source for everyone.
