"""
video_encoder.py — Video LSB Steganografi Encoder (AES-256-GCM + karışık gömme destekli)

Şifresizken : payload sıralı gömülür (kare 0'dan başlar), LSB eşleştirme (±1) kullanılır.
Şifreliyken : payload parola+kapasiteden türeyen bir sırayla (kare sırası + kare-içi
              konum sırası karışık) gömülür — LSTG imzası bile sabit bir konumda
              bulunmaz. Bkz. positions.py, payload.py, embed.py, crypto.py.
"""

import numpy as np
import cv2
import os
import sys
import argparse

from payload import build_payload, bytes_to_bits
from positions import block_and_intra_order
from embed import lsb_embed
from crypto import derive_shuffle_seed


def read_video_frames(path: str) -> tuple[list[np.ndarray], float]:
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise FileNotFoundError(f"Video acılamadı: {path}")
    fps = cap.get(cv2.CAP_PROP_FPS)
    frames = []
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frames.append(frame)
    cap.release()
    return frames, fps


def write_video_frames(frames: list[np.ndarray], output_path: str, fps: float) -> None:
    h, w = frames[0].shape[:2]
    fourcc = cv2.VideoWriter_fourcc(*"RGBA")
    writer = cv2.VideoWriter(output_path, fourcc, fps, (w, h))
    if not writer.isOpened():
        raise RuntimeError(f"Video yazıcı acılamadı: {output_path}")
    for frame in frames:
        writer.write(frame)
    writer.release()


def encode(video_path: str, file_path: str, output_path: str,
           password: str | None = None) -> None:
    with open(file_path, "rb") as f:
        file_data = f.read()
    filename = os.path.basename(file_path)

    if password:
        print("  Sifreleniyor (AES-256-GCM)...")
    raw, flag = build_payload(file_data, filename, password)
    payload_bits = np.array(bytes_to_bits(raw), dtype=np.uint8)

    print(f"Video yukleniyor: {video_path}")
    frames, fps = read_video_frames(video_path)
    if not frames:
        raise ValueError("Video bos (0 kare) — kapasite hesaplanamaz.")

    h, w, c = frames[0].shape
    frame_size = h * w * c
    n_frames = len(frames)
    total_lsb_bits = frame_size * n_frames
    n_bits = len(payload_bits)
    if n_bits > total_lsb_bits:
        cap_b = total_lsb_bits // 8
        raise ValueError(
            f"Dosya cok buyuk! Dosya: {len(file_data):,} byte, "
            f"Video kapasitesi: {cap_b:,} byte"
        )

    print(f"  {n_frames} kare yuklendi ({w}x{h})")
    print(f"  Kapasite: {total_lsb_bits//8:,} byte | "
          f"Payload: {n_bits//8:,} byte | "
          f"Doluluk: {n_bits/total_lsb_bits*100:.3f}%")

    if password:
        seed = derive_shuffle_seed(password, total_lsb_bits)
        block_order, intra_order = block_and_intra_order(seed, n_frames, frame_size)
        print("  Konum karistirma aktif (parola tohumlu) — imza sabit yerde degil.")
    else:
        block_order = np.arange(n_frames)
        intra_order = np.arange(frame_size)

    rng = np.random.default_rng()  # yalnizca LSB eslestirme yon rastgeleligi icin
    bit_idx = 0
    frames_touched = 0
    for f in block_order:
        if bit_idx >= n_bits:
            break
        flat = frames[f].flatten()
        take = min(frame_size, n_bits - bit_idx)
        idxs = intra_order[:take]
        flat[idxs] = lsb_embed(flat[idxs], payload_bits[bit_idx:bit_idx + take], rng)
        frames[f] = flat.reshape(frames[f].shape)
        bit_idx += take
        frames_touched += 1

    write_video_frames(frames, output_path, fps)
    enc_label = " [AES-256-GCM SIFRELI]" if password else ""
    print(f"Dosya gomuldu{enc_label}: {output_path}")
    print(f"  '{filename}' ({len(file_data):,} byte) — {frames_touched}/{n_frames} kare kullanildi")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Video LSB Encoder")
    parser.add_argument("video")
    parser.add_argument("file")
    parser.add_argument("--output",   default="stego_video.avi")
    parser.add_argument("--password", default=None, help="AES-256-GCM sifresi")
    args = parser.parse_args()
    try:
        encode(args.video, args.file, args.output, args.password)
    except (ValueError, FileNotFoundError, RuntimeError) as e:
        print(f"HATA: {e}", file=sys.stderr); sys.exit(1)

if __name__ == "__main__":
    main()
