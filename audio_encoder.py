"""
audio_encoder.py — WAV LSB Steganografi Encoder (AES-256-GCM + karışık gömme destekli)

Her 16-bit PCM örneğin düşük baytının (little-endian ilk baytı) LSB'sine
gömer — video pipeline'ıyla aynı payload.py/positions.py/embed.py altyapısını
paylaşır, aynı parola-tohumlu konum karıştırmayı ve LSB eşleştirmeyi kullanır.
Yalnızca kayıpsız PCM WAV desteklenir (MP3 gibi lossy formatlar LSB'yi bozar).
"""

import numpy as np
import wave
import os
import sys
import argparse

from payload import build_payload, bytes_to_bits
from positions import block_and_intra_order
from embed import lsb_embed
from crypto import derive_shuffle_seed


def _read_wav(path: str):
    with wave.open(path, "rb") as wf:
        params = wf.getparams()
        raw = wf.readframes(wf.getnframes())
    return np.frombuffer(raw, dtype=np.uint8).copy(), params


def _write_wav(path: str, byte_buf: np.ndarray, params) -> None:
    with wave.open(path, "wb") as wf:
        wf.setparams(params)
        wf.writeframes(byte_buf.tobytes())


def encode(audio_path: str, file_path: str, output_path: str,
           password: str | None = None) -> None:
    with open(file_path, "rb") as f:
        file_data = f.read()
    filename = os.path.basename(file_path)

    if password:
        print("  Sifreleniyor (AES-256-GCM)...")
    raw, flag = build_payload(file_data, filename, password)
    payload_bits = np.array(bytes_to_bits(raw), dtype=np.uint8)

    print(f"Ses yukleniyor: {audio_path}")
    byte_buf, params = _read_wav(audio_path)
    if params.sampwidth != 2:
        raise ValueError("Yalnizca 16-bit PCM WAV destekleniyor.")

    low_bytes_idx = np.arange(0, len(byte_buf), 2)   # her ornegin dusuk baytı (LE)
    capacity_bits = len(low_bytes_idx)
    n_bits = len(payload_bits)
    if n_bits > capacity_bits:
        raise ValueError(
            f"Dosya cok buyuk! Dosya: {len(file_data):,} byte, "
            f"Ses kapasitesi: {capacity_bits//8:,} byte"
        )

    print(f"  Kapasite: {capacity_bits//8:,} byte | Payload: {n_bits//8:,} byte | "
          f"Doluluk: {n_bits/capacity_bits*100:.3f}%")

    if password:
        seed = derive_shuffle_seed(password, capacity_bits)
        _, intra_order = block_and_intra_order(seed, 1, capacity_bits)
        print("  Konum karistirma aktif (parola tohumlu).")
    else:
        intra_order = np.arange(capacity_bits)

    rng = np.random.default_rng()
    targets = low_bytes_idx[intra_order[:n_bits]]
    byte_buf[targets] = lsb_embed(byte_buf[targets], payload_bits, rng)

    _write_wav(output_path, byte_buf, params)
    enc_label = " [AES-256-GCM SIFRELI]" if password else ""
    print(f"Dosya gomuldu{enc_label}: {output_path}")
    print(f"  '{filename}' ({len(file_data):,} byte)")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="WAV LSB Encoder")
    parser.add_argument("audio")
    parser.add_argument("file")
    parser.add_argument("--output",   default="stego_audio.wav")
    parser.add_argument("--password", default=None, help="AES-256-GCM sifresi")
    args = parser.parse_args()
    try:
        encode(args.audio, args.file, args.output, args.password)
    except (ValueError, FileNotFoundError, RuntimeError) as e:
        print(f"HATA: {e}", file=sys.stderr); sys.exit(1)

if __name__ == "__main__":
    main()
