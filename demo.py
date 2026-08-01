"""
demo.py — LSB Steganografi Uçtan Uca Demo
Şu adımları otomatik çalıştırır:
  1. 512×512 karıncalı ekran üret  (noise.png)
  2. Gizli mesajı göm              (stego.png)
  3. Mesajı geri çıkar ve doğrula
  4. Görsel analizi kaydet          (analysis.png)
"""

import sys
import os

# Aynı klasördeki modülleri import et
sys.path.insert(0, os.path.dirname(__file__))

from noise_image import generate_noise_image
from lsb_encoder import encode
from lsb_decoder import decode
from lsb_visualizer import visualize

# ─── Ayarlar ──────────────────────────────────────────────────
NOISE_FILE   = "noise.png"
STEGO_FILE   = "stego.png"
ANALYSIS_FILE = "analysis.png"
IMAGE_SIZE   = (512, 512)
SEED         = 42          # Tekrarlanabilir sonuçlar için

SECRET_MESSAGE = """\
Steganografi: Gizli mesaj burada!

"Bir sır, söylendiği anda artık sır olmaktan çıkar."
                                         — Jean-Paul Sartre

Bu mesaj 512×512 piksellik karıncalı ekran görüntüsünün
LSB (En Önemsiz Bit) katmanına gömülmüştür.

Her pikselin R, G ve B kanallarının son biti değiştirildi.
Gözle fark etmek imkânsız — ama matematiksel olarak kanıtlanabilir.

🔐 LSB Steganografi Demo | github.com/iatagun
"""
# ──────────────────────────────────────────────────────────────


def separator(title: str):
    width = 60
    print()
    print("─" * width)
    print(f"  {title}")
    print("─" * width)


def main():
    print("=" * 60)
    print("  LSB STEGANOGRAFİ — UÇTAN UCA DEMO")
    print("=" * 60)

    # ── Adım 1: Karıncalı ekran üret ──────────────────────────
    separator("ADIM 1 — Karıncalı Ekran Üretiliyor")
    w, h = IMAGE_SIZE
    img = generate_noise_image(w, h, seed=SEED)
    img.save(NOISE_FILE)
    capacity = (w * h * 3) // 8
    print(f"  📺 {NOISE_FILE} oluşturuldu ({w}×{h} piksel)")
    print(f"  💾 LSB kapasitesi: {capacity:,} byte ({capacity/1024:.1f} KB)")

    # ── Adım 2: Mesajı göm ────────────────────────────────────
    separator("ADIM 2 — Gizli Mesaj Gömülüyor")
    msg_bytes = len(SECRET_MESSAGE.encode("utf-8"))
    print(f"  📝 Mesaj uzunluğu : {msg_bytes} byte")
    print(f"  📊 Doluluk oranı  : {msg_bytes/capacity*100:.3f}%")
    encode(NOISE_FILE, SECRET_MESSAGE, STEGO_FILE)

    # ── Adım 3: Mesajı çıkar ve doğrula ──────────────────────
    separator("ADIM 3 — Mesaj Çıkarılıyor & Doğrulanıyor")
    recovered = decode(STEGO_FILE)

    if recovered == SECRET_MESSAGE:
        print("  ✅ DOĞRULAMA BAŞARILI — Mesaj birebir aynı!")
    else:
        print("  ❌ DOĞRULAMA BAŞARISIZ!")
        print(f"  Beklenen  : {repr(SECRET_MESSAGE[:80])}...")
        print(f"  Çıkarılan : {repr(recovered[:80])}...")
        sys.exit(1)

    print("\n  🔓 Çıkarılan Mesaj:")
    print("  " + "\n  ".join(recovered.splitlines()))

    # ── Adım 4: Görsel analiz ────────────────────────────────
    separator("ADIM 4 — Görsel Analiz Oluşturuluyor")
    visualize(NOISE_FILE, STEGO_FILE, ANALYSIS_FILE)

    # ── Özet ─────────────────────────────────────────────────
    separator("ÖZET")
    for fname in [NOISE_FILE, STEGO_FILE, ANALYSIS_FILE]:
        if os.path.exists(fname):
            size = os.path.getsize(fname) / 1024
            print(f"  📁 {fname:<20} {size:>8.1f} KB")

    print()
    print("  Demo tamamlandı! 🎉")
    print("  Görsel analiz için 'analysis.png' dosyasını açın.")
    print("=" * 60)


if __name__ == "__main__":
    main()
