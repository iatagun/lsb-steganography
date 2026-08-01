"""
crypto.py — AES-256-GCM Şifreleme Modülü

Şema:
  encrypt(data, password) → salt(16) + nonce(12) + ciphertext
  decrypt(blob, password) → data

Anahtar türetme : PBKDF2-HMAC-SHA256 (600_000 iterasyon, OWASP önerisi)
Şifreleme       : AES-256-GCM (kimlik doğrulamalı — bütünlük garantili)
"""

import os
import struct
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

SALT_SIZE   = 16    # byte
NONCE_SIZE  = 12    # byte  (AES-GCM standart)
KEY_SIZE    = 32    # byte  (AES-256)
ITERATIONS  = 600_000


def _derive_key(password: str, salt: bytes) -> bytes:
    """Şifreden 256-bit anahtar türet (PBKDF2-HMAC-SHA256)."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=KEY_SIZE,
        salt=salt,
        iterations=ITERATIONS,
    )
    return kdf.derive(password.encode("utf-8"))


def encrypt(data: bytes, password: str) -> bytes:
    """
    Veriyi AES-256-GCM ile şifreler.
    Döndürür: salt(16) + nonce(12) + ciphertext(len(data)+16)
    """
    salt  = os.urandom(SALT_SIZE)
    nonce = os.urandom(NONCE_SIZE)
    key   = _derive_key(password, salt)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, data, None)   # +16 byte GCM tag
    return salt + nonce + ciphertext


def decrypt(blob: bytes, password: str) -> bytes:
    """
    AES-256-GCM ile şifresi çözülür.
    Yanlış şifre veya bozuk veri → InvalidTag (ValueError alt sınıfı)
    """
    if len(blob) < SALT_SIZE + NONCE_SIZE + 16:
        raise ValueError("Şifreli veri çok kısa — bozulmuş ya da geçersiz.")
    salt       = blob[:SALT_SIZE]
    nonce      = blob[SALT_SIZE:SALT_SIZE + NONCE_SIZE]
    ciphertext = blob[SALT_SIZE + NONCE_SIZE:]
    key        = _derive_key(password, salt)
    aesgcm     = AESGCM(key)
    try:
        return aesgcm.decrypt(nonce, ciphertext, None)
    except Exception:
        raise ValueError("Şifre çözme başarısız — yanlış şifre veya bozuk veri.")


# ── Konum Karıştırma Anahtarı ────────────────────────────────────────────────
# Gömme sırasını (hangi piksel/örnek hangi payload bitini taşır) şifreleme
# anahtarından TAMAMEN bağımsız türetilir — aynı anahtar iki farklı amaç için
# (gizlilik + konum) tekrar kullanılmaz. Taşıyıcının bit kapasitesi context'e
# dahil edilir ki aynı şifre farklı boyuttaki taşıyıcılarda farklı sıralama
# üretsin (aksi halde aynı şifre + aynı boyut ürünlerinde desen tekrar eder —
# ponytail: kalan risk düşük çünkü içerik zaten AES-GCM ile şifreli).
SHUFFLE_DOMAIN = b"LSTG-shuffle-v1"


def derive_shuffle_seed(password: str, capacity_bits: int) -> int:
    """Şifreden, taşıyıcı kapasitesine bağlı 64-bit bir RNG tohumu türetir."""
    salt = SHUFFLE_DOMAIN + struct.pack(">Q", capacity_bits)
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=8,
        salt=salt,
        iterations=ITERATIONS,
    )
    seed_bytes = kdf.derive(password.encode("utf-8"))
    return int.from_bytes(seed_bytes, "big")
