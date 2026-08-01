"""
video_decoder.py — Video LSB Steganografi Decoder (AES-256-GCM destekli)

Payload formatı (encoder ile uyumlu):
  [LSTG][0x00][data_size:8][name_len:2][filename][data]           -- düz
  [LSTG][0x01][cipher_size:8][salt+nonce+GCM(...)]               -- şifreli
"""

import numpy as np
import cv2
import struct
import sys
import argparse
import os

MAGIC         = b"LSTG"
MIN_HDR_BYTES = 5   # magic(4) + flags(1)


def bits_to_bytes(bits: list[int]) -> bytes:
    out = bytearray()
    for i in range(0, len(bits), 8):
        val = 0
        for bit in bits[i:i+8]:
            val = (val << 1) | bit
        out.append(val)
    return bytes(out)


def extract_lsb_stream(frames: list[np.ndarray], n_bits: int) -> list[int]:
    bits = []
    for frame in frames:
        flat = frame.flatten()
        for val in flat:
            bits.append(int(val & 1))
            if len(bits) >= n_bits:
                return bits
    return bits


def _parse_inner(inner: bytes, output_dir: str) -> str:
    """data_size+name_len+filename+data bloğunu dosyaya yaz."""
    if len(inner) < 10:
        raise ValueError("Ic veri cok kisa.")
    data_size = struct.unpack(">Q", inner[:8])[0]
    name_len  = struct.unpack(">H", inner[8:10])[0]
    if len(inner) < 10 + name_len + data_size:
        raise ValueError("Ic veri tutarsiz.")
    filename  = os.path.basename(inner[10:10+name_len].decode("utf-8"))
    file_data = inner[10+name_len:10+name_len+data_size]
    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, filename)
    with open(out_path, "wb") as f:
        f.write(file_data)
    print(f"Dosya cikarildi: {out_path}")
    print(f"  Ad: {filename} | Boyut: {len(file_data):,} byte")
    return out_path


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
    total_bits = h * w * c * len(frames)
    print(f"Video yuklendi: {len(frames)} kare {w}x{h} — {total_bits//8:,} byte LSB")

    # 1. Minimum header (5 byte = 40 bit)
    hdr_bits = extract_lsb_stream(frames, MIN_HDR_BYTES * 8)
    hdr_raw  = bits_to_bytes(hdr_bits)

    if hdr_raw[:4] != MAGIC:
        raise ValueError(
            f"LSTG imzası bulunamadı (okunan: {hdr_raw[:4]}). "
            "Bu videoda gömülü veri yok veya bozulmuş."
        )

    flag = hdr_raw[4]

    # 2a. Düz (şifresiz)
    if flag == 0x00:
        # data_size(8) + name_len(2) = 10 byte daha oku
        more_bits = extract_lsb_stream(frames, (MIN_HDR_BYTES + 10) * 8)
        more_raw  = bits_to_bytes(more_bits)
        data_size = struct.unpack(">Q", more_raw[5:13])[0]
        name_len  = struct.unpack(">H", more_raw[13:15])[0]
        total_payload = MIN_HDR_BYTES + 10 + name_len + data_size
        all_bits  = extract_lsb_stream(frames, total_payload * 8)
        all_bytes = bits_to_bytes(all_bits)
        inner     = all_bytes[5:]   # magic+flag atla
        return _parse_inner(inner, output_dir), False

    # 2b. Şifreli (AES-256-GCM)
    elif flag == 0x01:
        if not password:
            raise ValueError(
                "Bu video sifrelenmis (AES-256-GCM). "
                "--password ile sifre girin."
            )
        # cipher_size(8) oku
        cs_bits  = extract_lsb_stream(frames, (MIN_HDR_BYTES + 8) * 8)
        cs_raw   = bits_to_bytes(cs_bits)
        cipher_size = struct.unpack(">Q", cs_raw[5:13])[0]
        total_payload = MIN_HDR_BYTES + 8 + cipher_size
        if total_payload * 8 > total_bits:
            raise ValueError("Video kapasitesi sifreli payload icin yetersiz.")
        all_bits   = extract_lsb_stream(frames, total_payload * 8)
        all_bytes  = bits_to_bytes(all_bits)
        ciphertext = all_bytes[MIN_HDR_BYTES + 8:]
        print(f"  Sifreyi cozuyor (AES-256-GCM)...")
        from crypto import decrypt as aes_decrypt
        inner = aes_decrypt(ciphertext, password)
        return _parse_inner(inner, output_dir), True

    else:
        raise ValueError(f"Bilinmeyen flag: 0x{flag:02x}")


def main():
    parser = argparse.ArgumentParser(description="Video LSB Decoder")
    parser.add_argument("video")
    parser.add_argument("--outdir",   default=".")
    parser.add_argument("--password", default=None, help="Sifre (sifrelenmis videolar icin)")
    args = parser.parse_args()
    try:
        path, was_enc = decode(args.video, args.outdir, args.password)
        if was_enc:
            print("[AES-256-GCM] sifre basariyla cozuldu.")
    except (ValueError, FileNotFoundError) as e:
        print(f"HATA: {e}", file=sys.stderr); sys.exit(1)

if __name__ == "__main__":
    main()
