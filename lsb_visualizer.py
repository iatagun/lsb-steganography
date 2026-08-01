"""
lsb_visualizer.py — LSB Katmanı Görselleştirici

4 panel gösterir:
  1. Orijinal görüntü
  2. Stego görüntü
  3. Fark haritası (piksel başına |orig - stego|, ×128 büyütülmüş)
  4. LSB katmanı (her kanalın son biti: 0→siyah, 1→beyaz)
"""

import numpy as np
from PIL import Image
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import argparse
import sys


def extract_lsb_layer(pixels: np.ndarray) -> np.ndarray:
    """Her kanal için LSB'yi çıkar → 0 veya 255 olarak görselleştir."""
    return ((pixels & 1) * 255).astype(np.uint8)


def amplified_diff(orig: np.ndarray, stego: np.ndarray, factor: int = 128) -> np.ndarray:
    """Fark görüntüsü: |orig - stego| × factor ile gözle görünür hale getirilir."""
    diff = np.abs(orig.astype(np.int16) - stego.astype(np.int16))
    return np.clip(diff * factor, 0, 255).astype(np.uint8)


def visualize(original_path: str, stego_path: str, output_path: str | None = None) -> None:
    orig_img  = Image.open(original_path).convert("RGB")
    stego_img = Image.open(stego_path).convert("RGB")

    orig_px  = np.array(orig_img,  dtype=np.uint8)
    stego_px = np.array(stego_img, dtype=np.uint8)

    if orig_px.shape != stego_px.shape:
        raise ValueError("Orijinal ve stego görüntü boyutları eşleşmiyor!")

    lsb_layer = extract_lsb_layer(stego_px)
    diff_map   = amplified_diff(orig_px, stego_px)

    # Kaç piksel değişti?
    changed = np.any(orig_px != stego_px, axis=2).sum()
    total   = orig_px.shape[0] * orig_px.shape[1]
    psnr_val = _psnr(orig_px, stego_px)

    fig = plt.figure(figsize=(16, 9), facecolor="#1a1a2e")
    fig.suptitle(
        "LSB Steganografi — Görsel Analiz",
        fontsize=16, color="white", fontweight="bold", y=0.98
    )

    gs = gridspec.GridSpec(2, 4, figure=fig, hspace=0.35, wspace=0.15)

    panels = [
        (orig_px,   "1. Orijinal\n(Cover Image)",            "gray"),
        (stego_px,  "2. Stego\n(Gizli mesaj içeriyor)",      "gray"),
        (diff_map,  f"3. Fark Haritası ×128\n({changed:,} piksel değişti)", "hot"),
        (lsb_layer, "4. LSB Katmanı\n(beyaz=1 bit, siyah=0 bit)", "gray"),
    ]

    axes = []
    for col, (data, title, cmap) in enumerate(panels):
        ax = fig.add_subplot(gs[0, col])
        ax.imshow(data, cmap=cmap if data.ndim == 2 else None)
        ax.set_title(title, color="white", fontsize=9, pad=6)
        ax.axis("off")
        axes.append(ax)

    # Alt panel: istatistikler
    ax_stats = fig.add_subplot(gs[1, :])
    ax_stats.axis("off")

    stats_text = (
        f"Boyut: {orig_px.shape[1]}x{orig_px.shape[0]} piksel    "
        f"Degisen piksel: {changed:,} / {total:,} ({changed/total*100:.3f}%)    "
        f"PSNR: {psnr_val:.2f} dB    "
        f"Insan gozu esigi: ~30-35 dB    "
        f"{'[GORUNMEZ]' if psnr_val > 40 else '[DIKKAT - DUSUK KALITE]'}"
    )
    ax_stats.text(
        0.5, 0.6, stats_text,
        transform=ax_stats.transAxes,
        fontsize=11, color="lightgreen",
        ha="center", va="center",
        bbox=dict(boxstyle="round,pad=0.5", facecolor="#0f3460", edgecolor="#e94560", alpha=0.8)
    )

    # LSB doluluk histogramı
    ax_hist = fig.add_subplot(gs[1, 2:])
    ax_hist.axis("off")

    # Stego LSB dağılımı — beyaz/siyah oranı
    lsb_flat = (stego_px & 1).flatten()
    ones  = lsb_flat.sum()
    zeros = len(lsb_flat) - ones
    ax_bar = fig.add_axes([0.55, 0.05, 0.38, 0.28])
    bars = ax_bar.bar(["0 (siyah)", "1 (beyaz)"], [zeros, ones],
                      color=["#16213e", "#e94560"], edgecolor="white", linewidth=0.8)
    ax_bar.set_facecolor("#1a1a2e")
    ax_bar.tick_params(colors="white")
    ax_bar.set_title("LSB Bit Dağılımı (Stego)", color="white", fontsize=9)
    for bar, val in zip(bars, [zeros, ones]):
        ax_bar.text(bar.get_x() + bar.get_width()/2, bar.get_height() + len(lsb_flat)*0.005,
                    f"{val:,}", ha="center", color="white", fontsize=8)
    ax_bar.spines[:].set_color("#444")

    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches="tight",
                    facecolor=fig.get_facecolor())
        print(f"Görselleştirme kaydedildi: {output_path}")
    else:
        plt.show()

    print(f"   Değişen piksel : {changed:,} / {total:,} ({changed/total*100:.3f}%)")
    print(f"   PSNR           : {psnr_val:.2f} dB  ({'görünmez' if psnr_val > 40 else 'dikkat'})")


def _psnr(orig: np.ndarray, stego: np.ndarray) -> float:
    """Peak Signal-to-Noise Ratio hesaplar (dB)."""
    mse = np.mean((orig.astype(np.float64) - stego.astype(np.float64)) ** 2)
    if mse == 0:
        return float("inf")
    return 10 * np.log10(255 ** 2 / mse)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="LSB Steganografi — Görselleştirici")
    parser.add_argument("original", help="Orijinal PNG görüntüsü")
    parser.add_argument("stego",    help="Stego PNG görüntüsü")
    parser.add_argument("--output", default=None, help="Çıktı PNG (yoksa ekranda göster)")
    args = parser.parse_args()

    try:
        visualize(args.original, args.stego, args.output)
    except (ValueError, FileNotFoundError) as e:
        print(f"❌ Hata: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
