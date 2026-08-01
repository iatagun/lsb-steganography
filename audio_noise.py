"""
audio_noise.py — Beyaz Gürültü WAV Üretici
CD kalitesinde (44100 Hz, 16-bit, stereo) rastgele örneklerden oluşan "hiss"
sesi üretir — video karıncalı ekranının ses karşılığı. Zaten gürültü olduğu
için istatistiksel olarak LSB gömmeyi tespit etmek en zor olan taşıyıcı türü.
Yalnızca stdlib `wave` modülü kullanılır — kayıpsız PCM, ek bağımlılık yok.
"""

import wave
import numpy as np
import argparse
import os
import sys

SAMPLE_RATE  = 44100
CHANNELS     = 2
SAMPLE_WIDTH = 2   # byte (16-bit PCM) — LSB gömme için gereken format


def generate_noise_wav(output_path: str, duration_sec: float = 10.0,
                        seed: int | None = None) -> dict:
    rng = np.random.default_rng(seed)
    n_samples = int(SAMPLE_RATE * duration_sec) * CHANNELS
    samples = rng.integers(-32768, 32768, size=n_samples, dtype=np.int16)

    with wave.open(output_path, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(SAMPLE_WIDTH)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(samples.tobytes())

    file_size = os.path.getsize(output_path)
    capacity_bytes = n_samples // 8   # 1 bit/örnek (düşük baytın LSB'si)

    return {
        "samples":   n_samples,
        "duration":  duration_sec,
        "file_size": file_size,
        "capacity":  capacity_bytes,
    }


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Beyaz gürültü WAV üretici")
    parser.add_argument("--output",   default="noise_audio.wav")
    parser.add_argument("--duration", type=float, default=10.0)
    parser.add_argument("--seed",     type=int,   default=None)
    args = parser.parse_args()

    stats = generate_noise_wav(args.output, args.duration, args.seed)
    print(f"Gürültü WAV üretildi: {args.output}")
    print(f"  Süre: {args.duration}s | Örnek: {stats['samples']:,} | "
          f"Dosya boyutu: {stats['file_size']/1024:.1f} KB")
    print(f"  LSB kapasitesi: {stats['capacity']:,} byte ({stats['capacity']/1024:.1f} KB)")


if __name__ == "__main__":
    main()
