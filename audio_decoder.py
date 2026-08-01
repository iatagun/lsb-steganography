"""
audio_decoder.py — WAV LSB Steganografi Decoder (AES-256-GCM + karışık gömme destekli)

Parola verilmişse önce karışık (parola-tohumlu) sırayla okumayı dener; imza
bulunamazsa sıralı okumaya düşer. Bkz. payload.decode_payload.
"""

import numpy as np
import wave
import sys
import argparse

from payload import decode_payload
from positions import block_and_intra_order
from crypto import derive_shuffle_seed


def _read_wav(path: str):
    with wave.open(path, "rb") as wf:
        params = wf.getparams()
        raw = wf.readframes(wf.getnframes())
    return np.frombuffer(raw, dtype=np.uint8), params


def _sequential_reader(byte_buf, low_bytes_idx):
    def read_bits(n):
        vals = byte_buf[low_bytes_idx[:n]]
        return [int(v) & 1 for v in vals]
    return read_bits


def _shuffled_reader(byte_buf, low_bytes_idx, seed, capacity_bits):
    _, intra_order = block_and_intra_order(seed, 1, capacity_bits)

    def read_bits(n):
        vals = byte_buf[low_bytes_idx[intra_order[:n]]]
        return [int(v) & 1 for v in vals]
    return read_bits


def decode(audio_path: str, output_dir: str = ".",
           password: str | None = None) -> tuple[str, bool]:
    byte_buf, params = _read_wav(audio_path)
    if params.sampwidth != 2:
        raise ValueError("Yalnizca 16-bit PCM WAV destekleniyor.")

    low_bytes_idx = np.arange(0, len(byte_buf), 2)
    capacity_bits = len(low_bytes_idx)
    print(f"Ses yuklendi: {capacity_bits//8:,} byte LSB kapasitesi")

    readers = []
    if password:
        seed = derive_shuffle_seed(password, capacity_bits)
        readers.append(_shuffled_reader(byte_buf, low_bytes_idx, seed, capacity_bits))
    readers.append(_sequential_reader(byte_buf, low_bytes_idx))

    return decode_payload(readers, capacity_bits, output_dir, password)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="WAV LSB Decoder")
    parser.add_argument("audio")
    parser.add_argument("--outdir",   default=".")
    parser.add_argument("--password", default=None, help="Sifre (sifrelenmis dosyalar icin)")
    args = parser.parse_args()
    try:
        path, was_enc = decode(args.audio, args.outdir, args.password)
        print(f"Dosya cikarildi: {path}")
        if was_enc:
            print("[AES-256-GCM] sifre basariyla cozuldu.")
    except (ValueError, FileNotFoundError) as e:
        print(f"HATA: {e}", file=sys.stderr); sys.exit(1)

if __name__ == "__main__":
    main()
