"""
embed.py — LSB Eşleştirme (±1 matching) gömme yardımcısı.

Düz LSB değiştirme (& 0xFE | bit) her zaman değeri en yakın çift/tek sayıya
zorlar; bu, komşu piksel çiftlerinin dağılımını bozar ve Chi-Square saldırısı
tarafından istatistiksel olarak tespit edilir (bkz. lsb-steganography.skill.md).

LSB eşleştirme (±1): bit zaten eşleşiyorsa dokunma, eşleşmiyorsa değeri
rastgele +1 ya da -1 kaydır (0/255 sınırında zorunlu yön). Sonuç yine
hedef LSB'yi taşır ama çift-tek çiftlerinin dağılımını düz değiştirmedeki
kadar öngörülebilir şekilde bozmaz. Decoder tarafında hiçbir değişiklik
gerekmez — okuma her zaman `deger & 1`.
"""

import numpy as np


def lsb_embed(values: np.ndarray, bits: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """
    values : uint8 dizi (piksel kanalı / ses örneği byte'ı)
    bits   : aynı boyutta 0/1 dizisi — gömülecek bitler
    rng    : yön rastgeleliği için np.random.Generator

    Döndürür: aynı şekilde, LSB'si `bits` ile eşleşen uint8 dizi.
    """
    values = values.astype(np.int16, copy=False)
    bits = np.asarray(bits, dtype=np.int16)

    need_flip = (values & 1) != bits
    direction = rng.integers(0, 2, size=values.shape, dtype=np.int16) * 2 - 1  # -1 ya da +1
    direction = np.where(values <= 0, 1, direction)
    direction = np.where(values >= 255, -1, direction)

    out = np.where(need_flip, values + direction, values)
    return np.clip(out, 0, 255).astype(np.uint8)
