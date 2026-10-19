import numpy as np
from src.audio.dsp import AudioDSPProcessor

dsp = AudioDSPProcessor(sample_rate=48000)
dsp.update_parameters(
    crossover_freq=120.0,
    bass_gain_db=0.0,
    main_volume=1.0,
    bass_volume=1.0,
    bass_muted=False,
    bass_split_enabled=True
)

# Generate 1 sec of audio containing:
# 60 Hz (Bass) + 1000 Hz (Mids/Vocals) + 5000 Hz (Highs)
fs = 48000
t = np.linspace(0, 1.0, fs, endpoint=False)
s_bass = 0.5 * np.sin(2 * np.pi * 60 * t)
s_vocal = 0.5 * np.sin(2 * np.pi * 1000 * t)
s_treble = 0.5 * np.sin(2 * np.pi * 5000 * t)
full_mix = np.column_stack((s_bass + s_vocal + s_treble, s_bass + s_vocal + s_treble)).astype(np.float32)

# Process in blocks of 1024
main_accum = []
bass_accum = []
for i in range(0, fs, 1024):
    chunk = full_mix[i:i+1024]
    m, b = dsp.process_block(chunk)
    main_accum.append(m)
    bass_accum.append(b)

main_out = np.vstack(main_accum)
bass_out = np.vstack(bass_accum)

# Compute FFT of bass_out
fft_bass = np.abs(np.fft.rfft(bass_out[:, 0]))
freqs = np.fft.rfftfreq(len(bass_out), 1.0 / fs)

# Check energy at 60Hz vs 1000Hz vs 5000Hz in bass_out
idx_60 = np.argmin(np.abs(freqs - 60))
idx_1000 = np.argmin(np.abs(freqs - 1000))
idx_5000 = np.argmin(np.abs(freqs - 5000))

print(f"Energy in bass_out at 60 Hz:   {fft_bass[idx_60]:.2f}")
print(f"Energy in bass_out at 1000 Hz: {fft_bass[idx_1000]:.4f}")
print(f"Energy in bass_out at 5000 Hz: {fft_bass[idx_5000]:.6f}")
print(f"Attenuation at 1000 Hz: {20 * np.log10(fft_bass[idx_60] / max(1e-12, fft_bass[idx_1000])):.1f} dB")
print(f"Attenuation at 5000 Hz: {20 * np.log10(fft_bass[idx_60] / max(1e-12, fft_bass[idx_5000])):.1f} dB")
