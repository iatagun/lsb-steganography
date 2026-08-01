# Skill: LSB Steganografi — En Önemsiz Bit Yöntemi

## Amaç
Piksel değerlerinin **en önemsiz bitlerini (LSB)** kullanarak bir görüntüye gizli mesaj gömmek ve geri çıkarmak.  
Temel fikir: insan gözü 1-bitlik renk değişikliğini algılayamaz → mükemmel gizleme alanı.

---

## Teori

### Bit yapısı (RGB piksel başına 3 byte = 24 bit)
```
Kırmızı kanalı: 10110110   (182)
                        ↑ LSB — bu biti değiştirmek rengi 181 ya da 183 yapar
                          → fark GÖRÜNMEZ
```

### Kapasite hesabı
- 1 piksel = 3 kanal × 1 LSB = **3 gizli bit**
- 1024×1024 px görüntü → 1024 × 1024 × 3 = **3,145,728 bit = ~384 KB metin**

### Karıncalı Ekran Avantajı
Analog TV "kar" görüntüsü: her pikselin zaten rastgele değeri var.  
LSB değişikliği istatistiksel olarak **tespit edilmesi en zor** olan alt kümedir çünkü zaten gürültü içerir.

---

## Uygulama Planı

### Dosyalar
| Dosya | Görev |
|---|---|
| `noise_image.py` | Karıncalı ekran üretici |
| `lsb_encoder.py` | Mesajı LSB'lere göm |
| `lsb_decoder.py` | LSB'lerden mesajı çıkar |
| `lsb_visualizer.py` | LSB katmanını görselleştir (fark haritası) |
| `demo.py` | Uçtan uca demo |

---

## Algoritma: Encoding

```
1. Mesajı binary'e çevir (UTF-8)
2. Mesaj uzunluğunu header olarak ekle (32 bit)
3. Her bit için:
   a. Sıradaki pikseli al (R→G→B→sonraki piksel)
   b. Kanal değerinin LSB'sini temizle: value & 0xFE
   c. Gizli biti yaz:              value | secret_bit
4. Görüntüyü kayıpsız formatla kaydet (PNG zorunlu, JPEG yasak!)
```

## Algoritma: Decoding

```
1. Her pikselin her kanalından LSB'yi oku
2. İlk 32 biti topla → mesaj uzunluğu
3. Sonraki N biti topla → mesaj
4. Binary → UTF-8 çevir
```

---

## Kritik Kurallar

| Kural | Neden |
|---|---|
| PNG kullan, JPEG kullanma | JPEG lossy sıkıştırma LSB'leri bozar |
| Mesaj boyutunu başa göm | Decoder nerede durduğunu bilmeli |
| Kapasite kontrolü yap | Görüntü yetmezse hata ver |
| Sıralamayı koru | Piksel sırası deterministik olmalı |

---

## Tespit (Steganalysis) ve Savunma

### Chi-Square Saldırısı
LSB gömme: çift-tek piksel çiftlerinin dağılımını bozar.  
Savunma: rastgele piksel sırası (seed ile karıştır).

### RS (Regular-Singular) Analizi
Daha güçlü istatistiksel test.  
Savunma: sadece bazı kanalları kullan, tüm pikseli değil.

---

## Örnek Akış

```
[Ham mesaj]  →  binary  →  [Header + Data bitleri]
                                    ↓
[Karıncalı PNG]  →  LSB göm  →  [Stego PNG]
                                    ↓
                             LSB oku  →  binary  →  [Mesaj]
```

---

## Geliştirme Ortamı

```bash
pip install pillow numpy matplotlib
```

### Bağımlılıklar
- `Pillow` — görüntü okuma/yazma
- `numpy` — piksel dizisi işlemleri
- `matplotlib` — görselleştirme

---

## Test Senaryoları

1. Kısa mesaj (< 100 karakter) — doğruluk testi
2. Uzun mesaj (~1000 karakter) — kapasite testi  
3. JPEG'e kaydet → geri yükle → bozulma kanıtı
4. LSB katmanını görselleştir → insan gözü testi
5. Orijinal vs stego görüntü farkı (diff) → piksel değişim haritası

---

## Referanslar
- Petitcolas, F.A.P., Anderson, R.J., Kuhn, M.G. (1999). *Information Hiding — A Survey*. Proceedings of the IEEE.
- Westfeld, A. & Pfitzmann, A. (1999). *Attacks on Steganographic Systems*. ISSA.
- Wikipedia: [Steganography](https://en.wikipedia.org/wiki/Steganography), [LSB](https://en.wikipedia.org/wiki/Least_significant_bit#Least_significant_bit_in_digital_steganography)
