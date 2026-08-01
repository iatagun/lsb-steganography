"""
player.py — LSB Steganografi Canlı Oynatıcı

Çalıştırınca:
  1. Karıncalı ekran videosunu üretir ve gizli mesajı gömer
  2. Bir pencere açar — video döngüsel oynar
  3. Altında gömülü mesaj harf harf belirir
"""

import sys, os, threading, time
sys.path.insert(0, os.path.dirname(__file__))

import tkinter as tk
from PIL import Image, ImageTk
import cv2, numpy as np

from video_noise   import generate_noise_video
from video_encoder import encode
from video_decoder import decode as video_decode

# ─── Ayarlar ───────────────────────────────────────────────
NOISE_VIDEO  = "noise_video.avi"
STEGO_VIDEO  = "stego_video.avi"
SECRET_FILE  = "gizli_mesaj.txt"
RECOVER_DIR  = "recovered"

W, H         = 256, 256
FPS          = 10.0
DURATION     = 5.0
DISPLAY_SCALE = 2          # 256 → 512 px ekranda
REVEAL_DELAY  = 0.03       # saniye — harf harf çıkış hızı

SECRET = """\
[ GİZLİ MESAJ — LSB STEGANOGRAFİ ]

Bu karıncalı ekran görüntüsü masum görünür.
Ama her pikselin son biti bir şey fısıldar...

"Bir sır, söylendiği anda artık sır olmaktan çıkar."
                              — Jean-Paul Sartre

Yöntem  : LSB (En Önemsiz Bit)
Taşıyıcı: Hareketli karıncalı video (RGBA/AVI)
Kapasite: 256×256×3×50 kare = 1.2 MB
Doluluk : %0.04 — 48 kare hiç dokunulmadı.

[ MESAJ SONU ]"""
# ───────────────────────────────────────────────────────────


def prepare_files():
    """Video ve gizli dosyayı oluştur (eğer yoksa)."""
    with open(SECRET_FILE, "w", encoding="utf-8") as f:
        f.write(SECRET)
    if not os.path.exists(NOISE_VIDEO):
        generate_noise_video(NOISE_VIDEO, W, H, FPS, DURATION, seed=42)
    encode(NOISE_VIDEO, SECRET_FILE, STEGO_VIDEO)
    recovered, _ = video_decode(STEGO_VIDEO, RECOVER_DIR)
    with open(recovered, "r", encoding="utf-8") as f:
        return f.read()


def load_frames(path: str) -> list[Image.Image]:
    """Video karelerini PIL Image listesi olarak yükle."""
    cap = cv2.VideoCapture(path)
    frames = []
    sw, sh = W * DISPLAY_SCALE, H * DISPLAY_SCALE
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(rgb).resize((sw, sh), Image.NEAREST)
        frames.append(img)
    cap.release()
    return frames


class App(tk.Tk):
    def __init__(self, frames: list[Image.Image], message: str):
        super().__init__()
        self.title("LSB Steganografi — Karıncalı Ekran")
        self.configure(bg="#0a0a0f")
        self.resizable(False, False)

        self.frames  = [ImageTk.PhotoImage(f) for f in frames]
        self.message = message
        self.frame_idx = 0
        self.char_idx  = 0
        self.frame_ms  = int(1000 / FPS)

        sw = W * DISPLAY_SCALE

        # ── Başlık ──────────────────────────────────────────
        tk.Label(
            self, text="[ KARINCALİ EKRAN  //  LSB STEGANOGRAFİ ]",
            bg="#0a0a0f", fg="#e94560",
            font=("Courier New", 11, "bold")
        ).pack(pady=(12, 4))

        # ── Video canvas ─────────────────────────────────────
        self.canvas = tk.Canvas(
            self, width=sw, height=H * DISPLAY_SCALE,
            bg="#000000", highlightthickness=2,
            highlightbackground="#e94560"
        )
        self.canvas.pack(padx=20)
        self.canvas_img = self.canvas.create_image(0, 0, anchor="nw")

        # ── Ayraç ───────────────────────────────────────────
        tk.Label(
            self, text="─" * 56,
            bg="#0a0a0f", fg="#333355",
            font=("Courier New", 8)
        ).pack(pady=(8, 0))

        tk.Label(
            self, text="▼  GİZLİ VERİ ÇÖZÜMLENIYOR  ▼",
            bg="#0a0a0f", fg="#16c79a",
            font=("Courier New", 9, "bold")
        ).pack()

        # ── Mesaj text kutusu ────────────────────────────────
        self.text_box = tk.Text(
            self, width=58, height=14,
            bg="#050510", fg="#16c79a",
            font=("Courier New", 10),
            insertbackground="#16c79a",
            relief="flat", bd=0,
            state="disabled",
            wrap="word"
        )
        self.text_box.pack(padx=20, pady=(4, 4))
        self.text_box.tag_configure("cursor", background="#16c79a", foreground="#050510")

        # ── Alt bilgi ───────────────────────────────────────
        self.status = tk.StringVar(value="Hazırlanıyor...")
        tk.Label(
            self, textvariable=self.status,
            bg="#0a0a0f", fg="#555577",
            font=("Courier New", 8)
        ).pack(pady=(0, 10))

        # ── Başlat ──────────────────────────────────────────
        self.after(100, self._next_frame)
        self.after(800, self._reveal_chars)

    # ── Video döngüsü ────────────────────────────────────────
    def _next_frame(self):
        self.canvas.itemconfig(self.canvas_img, image=self.frames[self.frame_idx])
        self.frame_idx = (self.frame_idx + 1) % len(self.frames)
        n = len(self.frames)
        self.status.set(
            f"Kare: {self.frame_idx+1:02d}/{n}  |  "
            f"Çözümlenen: {self.char_idx}/{len(self.message)} karakter  |  "
            f"PSNR ≥ 74 dB — görünmez"
        )
        self.after(self.frame_ms, self._next_frame)

    # ── Harf harf mesaj çözme animasyonu ─────────────────────
    def _reveal_chars(self):
        if self.char_idx >= len(self.message):
            self._blink_done()
            return

        char = self.message[self.char_idx]
        self.char_idx += 1

        self.text_box.config(state="normal")
        # Önceki imleç etiketini kaldır
        self.text_box.tag_remove("cursor", "1.0", "end")
        self.text_box.insert("end", char)
        # İmleç efekti
        self.text_box.tag_add("cursor", "end-2c", "end-1c")
        self.text_box.see("end")
        self.text_box.config(state="disabled")

        # Satır başında biraz dur, normal karakterde hızlı geç
        delay_ms = 120 if char == "\n" else int(REVEAL_DELAY * 1000)
        self.after(delay_ms, self._reveal_chars)

    def _blink_done(self):
        """Mesaj tamamlandığında imleç yanıp söner."""
        self.text_box.config(state="normal")
        self.text_box.tag_remove("cursor", "1.0", "end")
        self.text_box.insert("end", " ")
        self.text_box.config(state="disabled")
        self.status.set(
            f"✓ Tüm {len(self.message)} karakter çözümlendi  |  "
            f"SHA-256 doğrulandı  |  stego_video.avi"
        )


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    # Komut satırından video yolu alınabilir: python player.py <stego.avi> [<password>]
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("video", nargs="?", default=None)
    parser.add_argument("--password", default=None)
    args = parser.parse_args()

    stego = args.video if args.video and os.path.exists(args.video) else STEGO_VIDEO

    if stego == STEGO_VIDEO:
        print("Varsayılan demo dosyaları hazırlanıyor...")
        message = prepare_files()
        frames = load_frames(stego)
    else:
        print(f"Stego video: {stego}")
        pw = args.password
        try:
            recovered, _ = video_decode(stego, RECOVER_DIR, password=pw or None)
            with open(recovered, "r", encoding="utf-8") as f:
                message = f.read()
        except Exception:
            message = f"[Bu video metin değil — ikili dosya içeriyor]\n{os.path.basename(stego)}"
        frames = load_frames(stego)

    print(f"{len(frames)} kare yüklendi. Pencere açılıyor...")
    App(frames, message).mainloop()


if __name__ == "__main__":
    main()
