"""
video_decoder.py — Video LSB Steganografi Decoder (AES-256-GCM + karışık gömme destekli)

Parola verilmişse önce karışık (parola-tohumlu) sırayla okumayı dener; imza
bulunamazsa sıralı (eski/düz format) okumaya düşer. Parola verilmemişse
yalnızca sıralı okuma denenir. Bkz. payload.decode_payload.
"""

import numpy as np
import cv2
import sys
import argparse

from payload import decode_payload
from positions import block_and_intra_order
from crypto import derive_shuffle_seed


def _sequential_reader(frames):
    def read_bits(n):
        bits = []
        for frame in frames:
            flat = frame.flatten()
            for val in flat:
                bits.append(int(val & 1))
                if len(bits) >= n:
                    return bits
        return bits
    return read_bits


def _shuffled_reader(frames, frame_size, seed):
    block_order, intra_order = block_and_intra_order(seed, len(frames), frame_size)

    def read_bits(n):
        bits = []
        for f in block_order:
            flat = frames[f].flatten()
            for idx in intra_order:
                bits.append(int(flat[idx] & 1))
                if len(bits) >= n:
                    return bits
        return bits
    return read_bits


def decode(video_path: str, output_dir: str = ".",
           password: str | None = None) -> tuple[str, bool]:
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise FileNotFoundError(f"Video acılamadı: {video_path}")
    frames = []
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frames.append(frame)
    cap.release()

    if not frames:
        raise ValueError("Video bos.")

    h, w, c = frames[0].shape
    frame_size = h * w * c
    total_bits = frame_size * len(frames)
    print(f"Video yuklendi: {len(frames)} kare {w}x{h} — {total_bits//8:,} byte LSB")

    readers = []
    if password:
        seed = derive_shuffle_seed(password, total_bits)
        readers.append(_shuffled_reader(frames, frame_size, seed))
    readers.append(_sequential_reader(frames))

    return decode_payload(readers, total_bits, output_dir, password)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Video LSB Decoder")
    parser.add_argument("video")
    parser.add_argument("--outdir",   default=".")
    parser.add_argument("--password", default=None, help="Sifre (sifrelenmis videolar icin)")
    args = parser.parse_args()
    try:
        path, was_enc = decode(args.video, args.outdir, args.password)
        print(f"Dosya cikarildi: {path}")
        if was_enc:
            print("[AES-256-GCM] sifre basariyla cozuldu.")
    except (ValueError, FileNotFoundError) as e:
        print(f"HATA: {e}", file=sys.stderr); sys.exit(1)

if __name__ == "__main__":
    main()
