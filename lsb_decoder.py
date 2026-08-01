"""
lsb_decoder.py — LSB Steganografi Decoder
Görüntünün LSB'lerinden gömülü mesajı geri çıkarır.

Beklenen format (encoder ile birebir uyumlu):
  [İlk 32 bit] → mesaj uzunluğu (byte)
  [Sonraki N×8 bit] → UTF-8 mesaj
"""

import numpy as np
from PIL import Image
import argparse
import sys


HEADER_BITS = 32


def bits_to_int(bits: list[int]) -> int:
    """Bit listesi → tamsayı (big-endian)"""
    value = 0
    for bit in bits:
        value = (value << 1) | bit
    return value


def bits_to_text(bits: list[int]) -> str:
    """Bit listesi → UTF-8 metin"""
    if len(bits) % 8 != 0:
        raise ValueError(f"Bit sayısı 8'in katı olmalı, alınan: {len(bits)}")
    byte_array = bytearray()
    for i in range(0, len(bits), 8):
        byte_val = bits_to_int(bits[i:i+8])
        byte_array.append(byte_val)
    return byte_array.decode("utf-8")


def decode(image_path: str) -> str:
    """
    Görüntüdeki LSB'leri okuyarak gömülü mesajı döndürür.
    """
    img = Image.open(image_path).convert("RGB")
    pixels = np.array(img, dtype=np.uint8)
    flat = pixels.flatten()   # R0,G0,B0, R1,G1,B1, ...

    # 1. Header oku: ilk 32 LSB → mesaj uzunluğu (byte)
    header_bits = [int(flat[i] & 1) for i in range(HEADER_BITS)]
    msg_length = bits_to_int(header_bits)  # byte cinsinden

    # Mantıklılık kontrolü
    max_possible = (len(flat) - HEADER_BITS) // 8
    if msg_length == 0 or msg_length > max_possible:
        raise ValueError(
            f"Geçersiz header: {msg_length} byte okundu "
            f"(max olası: {max_possible} byte). "
            "Bu görüntüde gömülü mesaj olmayabilir."
        )

    # 2. Mesaj bitlerini oku
    msg_bit_count = msg_length * 8
    start = HEADER_BITS
    end   = start + msg_bit_count

    if end > len(flat):
        raise ValueError("Görüntü, header'da belirtilen mesaj boyutunu karşılamıyor.")

    msg_bits = [int(flat[i] & 1) for i in range(start, end)]

    # 3. Binary → metin
    return bits_to_text(msg_bits)


def main():
    parser = argparse.ArgumentParser(description="LSB Steganografi — Decoder")
    parser.add_argument("image", help="Stego PNG görüntüsü")
    parser.add_argument("--output", default=None, help="Mesajı dosyaya yaz (opsiyonel)")
    args = parser.parse_args()

    try:
        message = decode(args.image)
    except (ValueError, UnicodeDecodeError) as e:
        print(f"❌ Hata: {e}", file=sys.stderr)
        sys.exit(1)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(message)
        print(f"✅ Mesaj çıkarıldı ve kaydedildi: {args.output}")
        print(f"   Uzunluk: {len(message.encode('utf-8')):,} byte")
    else:
        print("=" * 50)
        print("🔓 Gizli Mesaj:")
        print("=" * 50)
        print(message)
        print("=" * 50)
        print(f"   Uzunluk: {len(message.encode('utf-8')):,} byte")


if __name__ == "__main__":
    main()
