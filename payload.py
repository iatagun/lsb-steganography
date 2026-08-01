"""
payload.py — Taşıyıcıdan bağımsız payload çerçeveleme.

video_encoder/decoder ve audio_encoder/decoder aynı formatı paylaşır; bu
modül ikisinin de tekrar yazmaması için ortak.

Format:
  [LSTG][flag:1][...]
  flag=0x00 (düz):            data_size:8 | name_len:2 | filename | data
  flag=0x01 (şifreli, ESKİ):  cipher_size:8 | AES-256-GCM(...)   — sıralı gömme (geriye dönük çözme için)
  flag=0x02 (şifreli, YENİ):  cipher_size:8 | AES-256-GCM(...)   — parola-tohumlu karışık gömme

flag 0x01 ve 0x02 aynı iç yapıyı taşır; fark yalnızca *hangi konum sırasıyla*
gömüldükleri — onu seçen taraf (encoder/decoder) reader/writer'ı seçer, bu
modül flag'in anlamını bilir ama konum sırasından habersizdir.
"""

import struct
import os

MAGIC              = b"LSTG"
FLAG_PLAIN         = 0x00
FLAG_ENC_SEQUENTIAL = 0x01   # eski format — yalnızca çözmede desteklenir
FLAG_ENC_SHUFFLED   = 0x02   # güncel format — parola varsa varsayılan
MIN_HDR_BYTES      = 5        # magic(4) + flag(1)


def _raw_inner(file_data: bytes, filename: str) -> bytes:
    name_bytes = filename.encode("utf-8")
    return (
        struct.pack(">Q", len(file_data))
        + struct.pack(">H", len(name_bytes))
        + name_bytes
        + file_data
    )


def bytes_to_bits(data: bytes) -> list[int]:
    bits = []
    for byte in data:
        for i in range(7, -1, -1):
            bits.append((byte >> i) & 1)
    return bits


def bits_to_bytes(bits: list[int]) -> bytes:
    out = bytearray()
    for i in range(0, len(bits), 8):
        val = 0
        for bit in bits[i:i + 8]:
            val = (val << 1) | bit
        out.append(val)
    return bytes(out)


def build_payload(file_data: bytes, filename: str, password: str | None = None) -> tuple[bytes, int]:
    """
    Döner: (ham_bayt, flag). flag çağırana söylenir ki hangi konum sırasıyla
    (sıralı / karışık) gömüleceğine karar versin.
    """
    inner = _raw_inner(file_data, filename)
    if password:
        from crypto import encrypt as aes_encrypt
        ciphertext = aes_encrypt(inner, password)
        raw = MAGIC + bytes([FLAG_ENC_SHUFFLED]) + struct.pack(">Q", len(ciphertext)) + ciphertext
        return raw, FLAG_ENC_SHUFFLED
    raw = MAGIC + bytes([FLAG_PLAIN]) + inner
    return raw, FLAG_PLAIN


def _extract_inner_to_file(inner: bytes, output_dir: str) -> str:
    if len(inner) < 10:
        raise ValueError("İç veri çok kısa.")
    data_size = struct.unpack(">Q", inner[:8])[0]
    name_len  = struct.unpack(">H", inner[8:10])[0]
    if len(inner) < 10 + name_len + data_size:
        raise ValueError("İç veri tutarsız.")
    filename  = os.path.basename(inner[10:10 + name_len].decode("utf-8"))
    file_data = inner[10 + name_len:10 + name_len + data_size]
    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, filename)
    with open(out_path, "wb") as f:
        f.write(file_data)
    return out_path


def _decode_from_reader(read_bits, total_bits: int, output_dir: str,
                         password: str | None) -> tuple[str, bool]:
    hdr_bits = read_bits(MIN_HDR_BYTES * 8)
    hdr_raw  = bits_to_bytes(hdr_bits)

    if hdr_raw[:4] != MAGIC:
        raise ValueError(
            f"LSTG imzası bulunamadı (okunan: {hdr_raw[:4]!r})."
        )

    flag = hdr_raw[4]

    if flag == FLAG_PLAIN:
        more_bits = read_bits((MIN_HDR_BYTES + 10) * 8)
        more_raw  = bits_to_bytes(more_bits)
        data_size = struct.unpack(">Q", more_raw[5:13])[0]
        name_len  = struct.unpack(">H", more_raw[13:15])[0]
        total_payload = MIN_HDR_BYTES + 10 + name_len + data_size
        if total_payload * 8 > total_bits:
            raise ValueError("Taşıyıcı, header'da belirtilen boyutu karşılamıyor.")
        all_bytes = bits_to_bytes(read_bits(total_payload * 8))
        return _extract_inner_to_file(all_bytes[5:], output_dir), False

    if flag in (FLAG_ENC_SEQUENTIAL, FLAG_ENC_SHUFFLED):
        if not password:
            raise ValueError(
                "Bu veri şifrelenmiş (AES-256-GCM). Parola girin."
            )
        cs_bits = read_bits((MIN_HDR_BYTES + 8) * 8)
        cs_raw  = bits_to_bytes(cs_bits)
        cipher_size   = struct.unpack(">Q", cs_raw[5:13])[0]
        total_payload = MIN_HDR_BYTES + 8 + cipher_size
        if total_payload * 8 > total_bits:
            raise ValueError("Taşıyıcı kapasitesi şifreli payload için yetersiz.")
        all_bytes  = bits_to_bytes(read_bits(total_payload * 8))
        ciphertext = all_bytes[MIN_HDR_BYTES + 8:]
        from crypto import decrypt as aes_decrypt
        inner = aes_decrypt(ciphertext, password)
        return _extract_inner_to_file(inner, output_dir), True

    raise ValueError(f"Bilinmeyen flag: 0x{flag:02x}")


def decode_payload(readers: list, total_bits: int, output_dir: str,
                    password: str | None) -> tuple[str, bool]:
    """
    `readers`, denenecek sırada `read_bits(n) -> list[int]` fonksiyonlarının
    listesidir (ör. önce karışık sıra, sonra sıralı — parola verilmişse ilk
    denemede bulunamazsa eski/düz formatlara düşer). İlk başarılı sonucu
    döndürür; hiçbiri MAGIC bulamazsa son hatayı fırlatır.
    """
    last_err: Exception | None = None
    for read_bits in readers:
        try:
            return _decode_from_reader(read_bits, total_bits, output_dir, password)
        except ValueError as e:
            last_err = e
            continue
    hint = "" if password else " (şifreliyse --password ile deneyin)"
    raise ValueError(f"{last_err}{hint}")
