"""
video_noise.py — Hareketli Karıncalı Ekran Video Üretici
Her kare tamamen farklı rastgele piksellerden oluşur → gerçek TV kar efekti.
Kayıpsız codec (png/AVI) kullanır — LSB'leri korumak için zorunlu.
"""

import numpy as np
import cv2
import argparse
import os
import sys


# Kayıpsız codec — JPEG/H.264/MP4 LSB'leri yok eder!
LOSSLESS_FOURCC = "RGBA"   # Kayıpsız uncompressed — Windows'ta FFV1 kadar güvenli


def generate_noise_video(
    output_path: str,
    width: int = 256,
    height: int = 256,
    fps: float = 10.0,
    duration_sec: float = 5.0,
    seed: int | None = None,
) -> dict:
    """
    Karıncalı ekran videosu üretir.
    Döndürür: video istatistiklerini içeren dict
    """
    n_frames = int(fps * duration_sec)
    fourcc   = cv2.VideoWriter_fourcc(*LOSSLESS_FOURCC)
    writer   = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    if not writer.isOpened():
        raise RuntimeError(
            f"Video yazıcı açılamadı: {output_path}\n"
            "Codec desteklenmiyor olabilir."
        )

    rng = np.random.default_rng(seed)

    for _ in range(n_frames):
        # Her kare bağımsız rastgele — gerçek karıncalı ekran efekti
        frame_rgb = rng.integers(0, 256, (height, width, 3), dtype=np.uint8)
        frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)  # OpenCV BGR bekler
        writer.write(frame_bgr)

    writer.release()

    file_size = os.path.getsize(output_path)
    capacity_bytes = (width * height * 3 * n_frames) // 8

    return {
        "frames":    n_frames,
        "width":     width,
        "height":    height,
        "fps":       fps,
        "duration":  duration_sec,
        "file_size": file_size,
        "capacity":  capacity_bytes,
    }


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Hareketli karıncalı ekran video üretici")
    parser.add_argument("--output",   default="noise_video.avi", help="Çıktı AVI dosyası")
    parser.add_argument("--width",    type=int,   default=256,  help="Genişlik")
    parser.add_argument("--height",   type=int,   default=256,  help="Yükseklik")
    parser.add_argument("--fps",      type=float, default=10.0, help="Kare/saniye")
    parser.add_argument("--duration", type=float, default=5.0,  help="Süre (saniye)")
    parser.add_argument("--seed",     type=int,   default=None, help="Rastgelelik tohumu")
    args = parser.parse_args()

    print(f"Karıncalı ekran video üretiliyor: {args.output}")
    stats = generate_noise_video(
        args.output, args.width, args.height, args.fps, args.duration, args.seed
    )

    print(f"  Kare sayisi  : {stats['frames']} kare ({args.fps} fps x {args.duration}s)")
    print(f"  Cozunurluk   : {stats['width']}x{stats['height']} piksel")
    print(f"  Dosya boyutu : {stats['file_size']/1024/1024:.1f} MB")
    print(f"  LSB kapasitesi: {stats['capacity']:,} byte ({stats['capacity']/1024:.1f} KB)")
    print(f"  Kare basina  : {stats['capacity']//stats['frames']:,} byte gizli veri")


if __name__ == "__main__":
    main()
