"""
audio_demo.py — Ses LSB Steganografi Uçtan Uca Demo

Adımlar:
  1. Gömülecek örnek metin dosyası oluştur
  2. Gürültü WAV üret (noise_audio.wav)
  3. Dosyayı sese göm (stego_audio.wav) — parola korumalı
  4. Dosyayı sesten çıkar (recovered/)
  5. SHA-256 ile birebir doğrula
"""

import sys
import os
import hashlib

sys.path.insert(0, os.path.dirname(__file__))

from audio_noise   import generate_noise_wav
from audio_encoder import encode
from audio_decoder import decode

NOISE_AUDIO  = "noise_audio.wav"
STEGO_AUDIO  = "stego_audio.wav"
SECRET_FILE  = "gizli_mesaj_ses.txt"
RECOVER_DIR  = "recovered"
PASSWORD     = "demo-parola-123"

AUDIO_DURATION = 8.0

SECRET_TEXT = """\
Bu gizli mesaj bir gürültü WAV dosyasının içine gömülmüştür.

Yöntem : LSB (En Önemsiz Bit) — her örneğin düşük baytı
Konum  : parola-tohumlu karışık sıra (sabit bir yerde değil)
Şifre  : AES-256-GCM

Kulakla hiçbir fark duyulmaz.
"""


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
    print("  SES LSB STEGANOGRAFI — UCTAN UCA DEMO")
    print("=" * 60)

    sep("ADIM 1 — Gizli Dosya Olusturuluyor")
    with open(SECRET_FILE, "w", encoding="utf-8") as f:
        f.write(SECRET_TEXT)
    print(f"  '{SECRET_FILE}' olusturuldu: {len(SECRET_TEXT.encode('utf-8'))} byte")

    sep("ADIM 2 — Gurultu WAV Uretiliyor")
    stats = generate_noise_wav(NOISE_AUDIO, AUDIO_DURATION, seed=42)
    print(f"  '{NOISE_AUDIO}': {stats['samples']:,} ornek, "
          f"{stats['capacity']:,} byte kapasite")

    sep("ADIM 3 — Dosya Sese Gomuluyor (AES-256-GCM)")
    encode(NOISE_AUDIO, SECRET_FILE, STEGO_AUDIO, password=PASSWORD)

    sep("ADIM 4 — Dosya Sesten Cikariliyor")
    recovered_path, was_enc = decode(STEGO_AUDIO, RECOVER_DIR, password=PASSWORD)

    sep("ADIM 5 — Dogrulama")
    orig_hash = sha256(SECRET_FILE)
    recv_hash = sha256(recovered_path)
    if orig_hash == recv_hash:
        print(f"  SHA-256 eslesti! DOGRULAMA BASARILI (sifreli: {was_enc})")
    else:
        print("  HATA: Hash eslesmiyor!")
        sys.exit(1)

    print()
    print("  Demo tamamlandi!")
    print("=" * 60)


if __name__ == "__main__":
    main()
