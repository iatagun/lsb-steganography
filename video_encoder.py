"""
video_encoder.py — Video LSB Steganografi Encoder (AES-256-GCM destekli)

Payload formatı:
  [LSTG][flags:1][...rest...]

  flags=0x00 (düz):     [LSTG][0x00][data_size:8][name_len:2][filename][data]
  flags=0x01 (şifreli): [LSTG][0x01][cipher_size:8][salt+nonce+GCM(data_size+name_len+filename+data)]
"""

import numpy as np
import cv2
import struct
import os
import sys
import argparse

MAGIC      = b"LSTG"
FLAG_PLAIN = b"\x00"
FLAG_ENC   = b"\x01"


def _raw_payload(file_data: bytes, filename: str) -> bytes:
    name_bytes = filename.encode("utf-8")
    return (
        struct.pack(">Q", len(file_data))
        + struct.pack(">H", len(name_bytes))
        + name_bytes
        + file_data
    )


def build_payload_bits(file_data: bytes, filename: str,
                       password: str | None = None) -> list[int]:
    inner = _raw_payload(file_data, filename)
    if password:
        from crypto import encrypt as aes_encrypt
        ciphertext = aes_encrypt(inner, password)
        raw = MAGIC + FLAG_ENC + struct.pack(">Q", len(ciphertext)) + ciphertext
    else:
        raw = MAGIC + FLAG_PLAIN + inner

    bits = []
    for byte in raw:
        for i in range(7, -1, -1):
            bits.append((byte >> i) & 1)
    return bits


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
        print(f"  Sifreleniyor (AES-256-GCM)...")
    payload_bits = build_payload_bits(file_data, filename, password)

    print(f"Video yukleniyor: {video_path}")
    frames, fps = read_video_frames(video_path)

    h, w, c = frames[0].shape
    total_lsb_bits = h * w * c * len(frames)
    if len(payload_bits) > total_lsb_bits:
        cap_b = total_lsb_bits // 8
        raise ValueError(
            f"Dosya cok buyuk! Dosya: {len(file_data):,} byte, "
            f"Video kapasitesi: {cap_b:,} byte"
        )

    print(f"  {len(frames)} kare yuklendi ({w}x{h})")
    print(f"  Kapasite: {total_lsb_bits//8:,} byte | "
          f"Payload: {len(payload_bits)//8:,} byte | "
          f"Doluluk: {len(payload_bits)/total_lsb_bits*100:.3f}%")

    bit_idx = 0
    n_bits  = len(payload_bits)
    for frame_i, frame in enumerate(frames):
        if bit_idx >= n_bits:
            break
        flat = frame.flatten()
        end  = min(bit_idx + len(flat), n_bits)
        for j, bit in enumerate(payload_bits[bit_idx:end]):
            flat[j] = (flat[j] & 0xFE) | bit
        frames[frame_i] = flat.reshape(frame.shape)
        bit_idx = end

    write_video_frames(frames, output_path, fps)
    enc_label = " [AES-256-GCM SIFRELI]" if password else ""
    print(f"Dosya gomuldu{enc_label}: {output_path}")
    print(f"  '{filename}' ({len(file_data):,} byte) — {min(frame_i+1, len(frames))}/{len(frames)} kare")


def main():
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
