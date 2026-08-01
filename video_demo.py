"""
video_demo.py — Video LSB Steganografi Uçtan Uca Demo

Adımlar:
  1. Gömülecek örnek metin dosyası oluştur
  2. Karıncalı video üret (noise_video.avi)
  3. Dosyayı videoya göm (stego_video.avi)
  4. Dosyayı videodan çıkar (recovered/)
  5. Orijinal ile karşılaştır — birebir doğrula
  6. İstatistikleri yazdır
"""

import sys
import os
import hashlib

sys.path.insert(0, os.path.dirname(__file__))

from video_noise   import generate_noise_video
from video_encoder import encode
from video_decoder import decode

# ─── Ayarlar ──────────────────────────────────────────────────
NOISE_VIDEO  = "noise_video.avi"
STEGO_VIDEO  = "stego_video.avi"
SECRET_FILE  = "gizli_mesaj.txt"
RECOVER_DIR  = "recovered"

VIDEO_WIDTH    = 256
VIDEO_HEIGHT   = 256
VIDEO_FPS      = 10.0
VIDEO_DURATION = 5.0    # saniye → 50 kare → ~3.8 MB kapasitesi

SECRET_TEXT = """\
Bu bir gizli belgedir.

Steganografi yöntemi: LSB (En Önemsiz Bit)
Taşıyıcı: Hareketli karıncalı ekran videosu
Codec: PNG/AVI (kayıpsız — MPEG/H.264 LSB'leri yok eder!)

Kapasite hesabı:
  256 x 256 piksel x 3 kanal x 50 kare = 9.830.400 bit = 1.228.800 byte ≈ 1.2 MB

Bu metin 50 kareli videonun yalnızca ilk birkaç karesinin
en önemsiz bitlerine gizlenmiştir.

İnsan gözü hiçbir fark göremez.
Matematik her şeyi saklar. 🔐

--- Gizli içerik sonu ---
"""
# ──────────────────────────────────────────────────────────────


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def sep(title: str):
    print()
    print("-" * 60)
    print(f"  {title}")
    print("-" * 60)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print("=" * 60)
    print("  VIDEO LSB STEGANOGRAFI — UCTAN UCA DEMO")
    print("=" * 60)

    # ── 1. Gizlenecek dosyayı oluştur ─────────────────────────
    sep("ADIM 1 — Gizli Dosya Olusturuluyor")
    with open(SECRET_FILE, "w", encoding="utf-8") as f:
        f.write(SECRET_TEXT)
    file_bytes = len(SECRET_TEXT.encode("utf-8"))
    print(f"  '{SECRET_FILE}' olusturuldu: {file_bytes} byte")

    # ── 2. Karıncalı video üret ───────────────────────────────
    sep("ADIM 2 — Karincali Ekran Video Uretiliyor")
    stats = generate_noise_video(
        NOISE_VIDEO, VIDEO_WIDTH, VIDEO_HEIGHT,
        VIDEO_FPS, VIDEO_DURATION, seed=42
    )
    n_frames = stats["frames"]
    cap_bytes = stats["capacity"]
    print(f"  '{NOISE_VIDEO}': {n_frames} kare, {cap_bytes:,} byte kapasitesi")
    print(f"  Dosya {file_bytes} byte — doluluk: {file_bytes/cap_bytes*100:.3f}%")

    if file_bytes > cap_bytes:
        print("  HATA: Dosya videoya sigmaz! Video suresini artirin.")
        sys.exit(1)

    # ── 3. Dosyayı videoya göm ────────────────────────────────
    sep("ADIM 3 — Dosya Videoya Gomulüyor")
    encode(NOISE_VIDEO, SECRET_FILE, STEGO_VIDEO)

    # ── 4. Dosyayı videodan çıkar ─────────────────────────────
    sep("ADIM 4 — Dosya Videodan Cikariliyor")
    recovered_path, _ = decode(STEGO_VIDEO, RECOVER_DIR)

    # ── 5. Doğrulama ──────────────────────────────────────────
    sep("ADIM 5 — Dogrulama")

    orig_hash = sha256(SECRET_FILE)
    recv_hash = sha256(recovered_path)

    with open(recovered_path, "r", encoding="utf-8") as f:
        recovered_text = f.read()

    if orig_hash == recv_hash:
        print(f"  SHA-256 eslesti!")
        print(f"  {orig_hash[:32]}...")
        print()
        print("  DOGRULAMA BASARILI — Dosya birebir ayni!")
    else:
        print(f"  HATA: Hash eslesmiyor!")
        print(f"  Orijinal : {orig_hash}")
        print(f"  Kurtarilan: {recv_hash}")
        sys.exit(1)

    print()
    print("  Kurtarilan icerik:")
    for line in recovered_text.splitlines()[:8]:
        print(f"    {line}")
    if recovered_text.count("\n") > 8:
        print(f"    ... ({recovered_text.count(chr(10))} satir toplam)")

    # ── 6. Özet istatistikler ─────────────────────────────────
    sep("OZET ISTATISTIKLER")
    for fname in [NOISE_VIDEO, STEGO_VIDEO, SECRET_FILE, recovered_path]:
        if os.path.exists(fname):
            size = os.path.getsize(fname)
            print(f"  {os.path.basename(fname):<25} {size/1024:>8.1f} KB")

    noise_size = os.path.getsize(NOISE_VIDEO)
    stego_size = os.path.getsize(STEGO_VIDEO)
    print()
    print(f"  Orijinal video boyutu  : {noise_size/1024:.1f} KB")
    print(f"  Stego video boyutu     : {stego_size/1024:.1f} KB")
    print(f"  Fark                   : {abs(noise_size-stego_size)} byte")
    print()
    print("  Demo tamamlandi!")
    print("  noise_video.avi ve stego_video.avi dosyalarini VLC ile acip karsılastirin.")
    print("=" * 60)


if __name__ == "__main__":
    main()
