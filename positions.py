"""
positions.py — Parola-tohumlu, bellek-sınırlı gömme sırası.

Tüm taşıyıcıyı (ör. 500 karelik video ~ yüz milyonlarca byte) tek bir
permütasyon dizisine almak GB'lerce bellek ister. Bunun yerine iki seviyeli
bir karıştırma kullanılır:

  1. Blok sırası   — bloklar (video karesi / ses parçası) rastgele sırada
                      ziyaret edilir.  (dizi boyu = blok sayısı, küçük)
  2. Blok-içi sıra — her blok içinde byte/örnek konumları aynı rastgele
                      düzende ziyaret edilir. (dizi boyu = tek blok boyu)

İkisi de aynı tohumdan (parola + taşıyıcı kapasitesi → crypto.derive_shuffle_seed)
türediği için şifreleyen ve çözen taraf, hiçbir konum bilgisini taşıyıcıya
gömmeden aynı sırayı yeniden üretir.

Toplam bellek: O(blok_sayısı + blok_boyu) — taşıyıcı boyutundan bağımsız.
"""

import numpy as np


def block_and_intra_order(seed: int, n_blocks: int, block_size: int):
    """(blok_ziyaret_sırası, blok_içi_ziyaret_sırası) döndürür."""
    block_order = np.random.default_rng(seed).permutation(n_blocks)
    # Aynı tohumdan iki bağımsız permütasyon için tohumu ayır.
    intra_order = np.random.default_rng(seed ^ 0x5A5A5A5A5A5A5A5A).permutation(block_size)
    return block_order, intra_order
