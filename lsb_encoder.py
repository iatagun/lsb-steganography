"""
lsb_encoder.py — LSB Steganografi Encoder
Mesajı PNG görüntüsünün piksel kanallarının en önemsiz bitine gömer.

Header yapısı (ilk 32 bit):
  [31..0] = mesaj uzunluğu (byte cinsinden, big-endian)

Ardından mesaj bitleri: piksel satır→sütun, kanal R→G→B sırasıyla.
"""

import numpy as np
from PIL import Image
import argparse
import sys


HEADER_BITS = 32          # 4 byte → max 4 GB mesaj uzunluğu tanımlanabilir
BITS_PER_PIXEL = 3        # R, G, B kanallarının her birinin LSB'si


def text_to_bits(text: str) -> list[int]:
    """UTF-8 metin → bit listesi"""
    data = text.encode("utf-8")
    bits = []
    for byte in data:
        for i in range(7, -1, -1):   # MSB önce
            bits.append((byte >> i) & 1)
    return bits


def int_to_bits(value: int, length: int = 32) -> list[int]:
    """Tamsayı → sabit uzunlukta bit listesi (big-endian)"""
    return [(value >> i) & 1 for i in range(length - 1, -1, -1)]


def encode(image_path: str, message: str, output_path: str) -> None:
    """
    Mesajı görüntünün LSB'lerine gömer ve çıktı PNG olarak kaydeder.
    """
    img = Image.open(image_path).convert("RGB")
    pixels = np.array(img, dtype=np.uint8)
    height, width, _ = pixels.shape

    # Kapasite kontrolü
    max_bytes = (height * width * BITS_PER_PIXEL) // 8 - (HEADER_BITS // 8)
    msg_bytes = message.encode("utf-8")
    if len(msg_bytes) > max_bytes:
        raise ValueError(
            f"Mesaj çok büyük! Mesaj: {len(msg_bytes):,} byte, "
            f"Kapasite: {max_bytes:,} byte"
        )

    # Bit dizisini hazırla: [32-bit header] + [mesaj bitleri]
    payload_bits = int_to_bits(len(msg_bytes), HEADER_BITS) + text_to_bits(message)

    # Piksel dizisini düzleştir: (H×W×3,) → kanal başına bir eleman
    flat = pixels.flatten()   # R0,G0,B0, R1,G1,B1, ...

    if len(payload_bits) > len(flat):
        raise ValueError("Payload görüntü kapasitesini aşıyor.")

    # LSB gömme: & 0xFE ile son biti sıfırla, | bit ile yaz
    for i, bit in enumerate(payload_bits):
        flat[i] = (flat[i] & 0xFE) | bit

    # Yeniden şekillendir ve kaydet
    stego_pixels = flat.reshape((height, width, 3))
    stego_img = Image.fromarray(stego_pixels, mode="RGB")
    stego_img.save(output_path, format="PNG")  # PNG zorunlu — JPEG LSB'leri bozar

    msg_kb = len(msg_bytes) / 1024
    print(f"✅ Mesaj gömüldü: {output_path}")
    print(f"   Mesaj boyutu : {len(msg_bytes):,} byte ({msg_kb:.2f} KB)")
    print(f"   Kullanılan   : {len(payload_bits):,} bit / {height*width*3:,} bit")
    print(f"   Doluluk oranı: {len(payload_bits)/(height*width*3)*100:.4f}%")


def main():
    parser = argparse.ArgumentParser(description="LSB Steganografi — Encoder")
    parser.add_argument("image",   help="Kaynak PNG görüntüsü")
    parser.add_argument("message", help="Gizlenecek metin (veya @dosya.txt)")
    parser.add_argument("--output", default="stego.png", help="Çıktı PNG dosyası")
    args = parser.parse_args()

    # @dosya.txt sözdizimi: dosyadan oku
    if args.message.startswith("@"):
        with open(args.message[1:], "r", encoding="utf-8") as f:
            message = f.read()
    else:
        message = args.message

    try:
        encode(args.image, message, args.output)
    except ValueError as e:
        print(f"❌ Hata: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
