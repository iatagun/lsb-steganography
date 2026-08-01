"""
noise_image.py — Karıncalı Ekran Üretici
Analog TV kar efekti: her piksel tamamen rastgele RGB değerine sahip.
Bu görüntü LSB steganografi için ideal "cover image" dir.
"""

import numpy as np
from PIL import Image
import argparse
import os
import sys


def generate_noise_image(width: int = 512, height: int = 512, seed: int | None = None) -> Image.Image:
    """Verilen boyutlarda rastgele gürültü (karıncalı ekran) görüntüsü üretir."""
    rng = np.random.default_rng(seed)
    pixels = rng.integers(0, 256, size=(height, width, 3), dtype=np.uint8)
    return Image.fromarray(pixels, mode="RGB")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Karıncalı ekran PNG üretici")
    parser.add_argument("--width",  type=int, default=512,  help="Genişlik (piksel)")
    parser.add_argument("--height", type=int, default=512,  help="Yükseklik (piksel)")
    parser.add_argument("--seed",   type=int, default=None, help="Rastgelelik tohumu (tekrar üretim için)")
    parser.add_argument("--output", type=str, default="noise.png", help="Çıktı dosyası")
    args = parser.parse_args()

    img = generate_noise_image(args.width, args.height, args.seed)
    img.save(args.output)

    size_kb = os.path.getsize(args.output) / 1024
    capacity_bytes = (args.width * args.height * 3) // 8
    print(f"✅ Karıncalı ekran oluşturuldu: {args.output}")
    print(f"   Boyut       : {args.width}×{args.height} piksel")
    print(f"   Dosya boyutu: {size_kb:.1f} KB")
    print(f"   LSB kapasitesi: {capacity_bytes:,} byte ({capacity_bytes/1024:.1f} KB) gizli veri")


if __name__ == "__main__":
    main()
