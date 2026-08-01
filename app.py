"""
app.py  —  LSTG Steganografi  v4
Widget yönetimi:
  - AppState: merkezi reaktif durum (observer pattern)
  - DebouncedCfg: disk yazımı gecikmeli, tuş vuruşunda değil
  - MouseWheel: tek bağlama, aktif panelin canvas'ına yönlendirilir
  - Klavye kısayolları: Entry/Text odaklanıldığında tetiklenmez
  - Paneller arası senkronizasyon: GİZLE → ÇIKAR otomatik
  - ActionBtn: bağımsız durum makinesi (idle/busy/done/error)
  - CapBar: canvas boyut değişimine reaktif
"""

import sys, os, json, threading, queue, subprocess
sys.path.insert(0, os.path.dirname(__file__))

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

# ── Renk Paleti ──────────────────────────────────────────────────────────────
BG     = "#0b0b12"
BG2    = "#11111c"
BG3    = "#18182a"
BG4    = "#1e1e32"
BORDER = "#26264a"
ACC    = "#e84393"
ACC2   = "#ff6ec7"
GRN    = "#1de9b6"
GRN2   = "#69ffda"
CYAN   = "#7ee8fa"
GOLD   = "#f7c948"
DIM    = "#42426a"
DIM2   = "#6a6a9a"
FG     = "#d0d0ee"
FG2    = "#eeeeff"

FONT_L = ("Courier New", 11, "bold")
FONT_M = ("Courier New", 10)
FONT_B = ("Courier New", 10, "bold")
FONT_T = ("Courier New", 9)
FONT_S = ("Courier New", 8)

CFG_FILE     = os.path.join(os.path.dirname(__file__), ".lstg_config.json")
MAX_VIDEO_MB = 100
LOSSLESS_EXT = {".avi"}
LOSSY_EXT    = {".mp4", ".mov", ".mkv", ".wmv", ".flv", ".webm"}

# ── Workspace ─────────────────────────────────────────────────────────────────
DEFAULT_WORKSPACE = os.path.join(os.path.dirname(__file__), "workspace")

def ws_root() -> str:
    return cfg.get("workspace", DEFAULT_WORKSPACE)

def ws_stego()     -> str: return os.path.join(ws_root(), "stego")
def ws_recovered() -> str: return os.path.join(ws_root(), "recovered")
def ws_inbox()     -> str: return os.path.join(ws_root(), "inbox")

def ensure_workspace():
    for d in [ws_stego(), ws_recovered(), ws_inbox()]:
        os.makedirs(d, exist_ok=True)

def ws_auto_stego() -> str:
    """Zaman damgalı benzersiz stego çıktı yolu üretir."""
    import datetime
    ts   = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    name = f"stego_{ts}.avi"
    return os.path.join(ws_stego(), name)

def inside_workspace(path: str) -> bool:
    """Yolun workspace içinde olup olmadığını kontrol eder."""
    try:
        root = os.path.realpath(ws_root())
        tgt  = os.path.realpath(path)
        return os.path.commonpath([root, tgt]) == root
    except ValueError:
        return False


# ════════════════════════════════════════════════════════════════
#  KATMAN 1 — Altyapı
# ════════════════════════════════════════════════════════════════

# ── Reaktif Durum Yöneticisi ─────────────────────────────────────────────────
class AppState:
    """
    Uygulama genelinde tek kaynaklı gerçek (single source of truth).
    state.set(key, value) → tüm watchers çağrılır.
    """
    def __init__(self):
        self._data: dict     = {}
        self._cb:   dict     = {}   # key → [callback, ...]

    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value):
        if self._data.get(key) == value:
            return
        self._data[key] = value
        for cb in list(self._cb.get(key, [])):
            try:
                cb(value)
            except Exception:
                pass

    def watch(self, key, callback):
        self._cb.setdefault(key, []).append(callback)

    def unwatch(self, key, callback):
        self._cb[key] = [c for c in self._cb.get(key, []) if c is not callback]


# ── Gecikmeli Disk Yazımı ────────────────────────────────────────────────────
class DebouncedCfg:
    """Config'i belirtilen gecikmeyle yazar; her değişiklikte zamanlayıcı sıfırlanır."""
    def __init__(self, delay_ms: int = 600):
        self._delay = delay_ms
        self._job   = None
        self._root  = None
        self._data: dict = {}
        try:
            with open(CFG_FILE, "r", encoding="utf-8") as f:
                self._data = json.load(f)
        except Exception:
            pass

    def bind_root(self, root: tk.Tk):
        self._root = root

    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value):
        self._data[key] = value
        if self._root:
            if self._job:
                self._root.after_cancel(self._job)
            self._job = self._root.after(self._delay, self._flush)

    def _flush(self):
        self._job = None
        try:
            with open(CFG_FILE, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def flush_now(self):
        if self._job and self._root:
            self._root.after_cancel(self._job)
            self._job = None
        self._flush()


cfg = DebouncedCfg()


# ── Thread Yardımcısı ────────────────────────────────────────────────────────
def run_in_thread(tk_widget, fn, on_done=None):
    """fn'i arka planda çalıştır; on_done(result, err) Tk ana thread'inde çalışır."""
    def _worker():
        try:
            result = fn()
            if on_done:
                tk_widget.after(0, lambda r=result: on_done(r, None))
        except Exception as exc:
            if on_done:
                tk_widget.after(0, lambda e=exc: on_done(None, e))
    threading.Thread(target=_worker, daemon=True).start()


# ── Yardımcı Fonksiyonlar ────────────────────────────────────────────────────
def _p(name=""):
    return os.path.join(os.path.dirname(__file__), name)

def estimate_payload_bytes(file_path: str, password: str | None) -> int:
    try:
        data_size  = os.path.getsize(file_path)
        name_bytes = len(os.path.basename(file_path).encode("utf-8"))
        if password:
            inner = 8 + 2 + name_bytes + data_size
            return 4 + 1 + 8 + 16 + 12 + inner + 16
        return 4 + 1 + 8 + 2 + name_bytes + data_size
    except Exception:
        return 0

def pw_strength(pw: str) -> tuple[str, str]:
    if not pw:
        return "—", DIM
    score = sum([
        len(pw) >= 8,
        len(pw) >= 14,
        any(c.isupper() for c in pw),
        any(c.isdigit() for c in pw),
        any(not c.isalnum() for c in pw),
    ])
    if score <= 1: return "ZAYIF",  ACC
    if score <= 3: return "ORTA",   GOLD
    return "GÜÇLÜ", GRN

def file_type_label(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    return {
        ".txt": "Metin", ".md": "Metin", ".csv": "Tablo",
        ".pdf": "PDF", ".zip": "Arşiv", ".rar": "Arşiv", ".7z": "Arşiv",
        ".png": "Görüntü", ".jpg": "Görüntü", ".jpeg": "Görüntü",
        ".mp3": "Ses", ".wav": "Ses",
        ".py": "Python", ".js": "JavaScript", ".json": "JSON",
        ".doc": "Word", ".docx": "Word", ".xlsx": "Excel",
        ".avi": "AVI Video", ".mp4": "MP4 Video",
    }.get(ext, "Dosya")

def is_text_file(path: str) -> bool:
    try:
        with open(path, "rb") as f:
            f.read(512).decode("utf-8")
        return True
    except Exception:
        return False

def focus_is_text(widget) -> bool:
    """Odaklanılan widget metin girişi mi?"""
    try:
        w = widget.focus_get()
        return isinstance(w, (tk.Entry, tk.Text, scrolledtext.ScrolledText))
    except Exception:
        return False


# ════════════════════════════════════════════════════════════════
#  KATMAN 2 — Bileşenler
# ════════════════════════════════════════════════════════════════

# ── Hover Yardımcısı ─────────────────────────────────────────────────────────
def hover(w, bg_n, bg_h, fg_n=None, fg_h=None):
    def _on(e):  w.config(bg=bg_h, **({"fg": fg_h} if fg_h else {}))
    def _off(e): w.config(bg=bg_n, **({"fg": fg_n} if fg_n else {}))
    w.bind("<Enter>", _on); w.bind("<Leave>", _off)


# ── Tooltip ──────────────────────────────────────────────────────────────────
class Tooltip:
    def __init__(self, widget, text: str):
        self._w    = widget
        self._text = text
        self._tw   = None
        self._job  = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._cancel,   add="+")

    def _schedule(self, _=None):
        self._cancel()
        self._job = self._w.after(850, self._show)

    def _cancel(self, _=None):
        if self._job:
            self._w.after_cancel(self._job)
            self._job = None
        if self._tw:
            self._tw.destroy()
            self._tw = None

    def _show(self):
        x = self._w.winfo_rootx() + 20
        y = self._w.winfo_rooty() + self._w.winfo_height() + 4
        self._tw = tw = tk.Toplevel(self._w)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tk.Label(tw, text=self._text, bg=BG4, fg=CYAN, font=FONT_S,
                 relief="flat", bd=0, padx=8, pady=4).pack()


# ── LogBox ───────────────────────────────────────────────────────────────────
class LogBox(tk.Frame):
    def __init__(self, parent, **kw):
        super().__init__(parent, bg=BORDER, **kw)
        inner = tk.Frame(self, bg=BG3)
        inner.pack(fill="both", expand=True, padx=1, pady=1)

        hdr = tk.Frame(inner, bg=BG3)
        hdr.pack(fill="x", padx=10, pady=(5, 0))
        tk.Label(hdr, text="▸ İşlem Günlüğü", bg=BG3, fg=DIM2, font=FONT_T).pack(side="left")
        self._count_lbl = tk.Label(hdr, text="", bg=BG3, fg=DIM, font=FONT_S)
        self._count_lbl.pack(side="right")
        clr = tk.Label(hdr, text=" temizle ", bg=BG3, fg=DIM, font=FONT_S, cursor="hand2")
        clr.pack(side="right", padx=4)
        clr.bind("<Button-1>", lambda _: self.clear())
        hover(clr, BG3, BG4, DIM, CYAN)
        tk.Frame(inner, bg=BORDER, height=1).pack(fill="x", padx=10, pady=(3, 0))

        self._text = scrolledtext.ScrolledText(
            inner, height=8, bg=BG3, fg=FG, font=FONT_T,
            relief="flat", bd=0, state="disabled",
            insertbackground=GRN, selectbackground=BG4,
        )
        self._text.pack(fill="both", expand=True, padx=2, pady=4)
        for tag, color in [("ok", GRN), ("err", ACC), ("warn", GOLD),
                            ("info", FG), ("dim", DIM2), ("cyan", CYAN)]:
            self._text.tag_configure(tag, foreground=color)

        self._count = 0
        self._q: queue.Queue = queue.Queue()
        self._poll()

    def _poll(self):
        try:
            while True:
                tag, msg = self._q.get_nowait()
                self._text.config(state="normal")
                self._text.insert("end", msg + "\n", tag)
                self._text.see("end")
                self._text.config(state="disabled")
                self._count += 1
                self._count_lbl.config(text=f"{self._count} satır")
        except queue.Empty:
            pass
        self.after(60, self._poll)

    def log(self, msg: str, tag: str = "info"):
        self._q.put((tag, msg))

    def clear(self):
        self._text.config(state="normal")
        self._text.delete("1.0", "end")
        self._text.config(state="disabled")
        self._count = 0
        self._count_lbl.config(text="")


# ── Kart ─────────────────────────────────────────────────────────────────────
def card(parent, title=None, title_color=None, padx=14, pady=8):
    outer = tk.Frame(parent, bg=BORDER)
    outer.pack(fill="x", padx=16, pady=5)
    inner = tk.Frame(outer, bg=BG2)
    inner.pack(fill="x", padx=1, pady=1)
    if title:
        th = tk.Frame(inner, bg=BG2)
        th.pack(fill="x")
        tk.Label(th, text=f"  {title}", bg=BG2, fg=title_color or DIM2,
                 font=FONT_T, anchor="w").pack(side="left", padx=(4, 0), pady=(6, 0))
        tk.Frame(inner, bg=BORDER, height=1).pack(fill="x", pady=(3, 0))
    body = tk.Frame(inner, bg=BG2)
    body.pack(fill="x", padx=padx, pady=pady)
    return body


# ── Dosya Satırı ─────────────────────────────────────────────────────────────
def file_row(parent, label: str, var: tk.StringVar, filetypes,
             save=False, lbl_w=15, on_change=None, initialdir=None):
    row = tk.Frame(parent, bg=BG2)
    row.pack(fill="x", pady=2)
    tk.Label(row, text=label, bg=BG2, fg=DIM2, font=FONT_T,
             width=lbl_w, anchor="w").pack(side="left")
    entry = tk.Entry(row, textvariable=var, bg=BG4, fg=FG, font=FONT_T,
                     insertbackground=GRN, relief="flat", bd=0,
                     highlightthickness=1, highlightbackground=BORDER,
                     highlightcolor=CYAN)
    entry.pack(side="left", fill="x", expand=True, ipady=4)

    def _browse(*_):
        idir = initialdir or (os.path.dirname(var.get()) if var.get() else None)
        p = (filedialog.asksaveasfilename(filetypes=filetypes,
                                          defaultextension=filetypes[0][1],
                                          initialdir=idir)
             if save else filedialog.askopenfilename(filetypes=filetypes,
                                                     initialdir=idir))
        if p:
            var.set(p)

    btn = tk.Label(row, text=" Gözat ", bg=BG4, fg=DIM2, font=FONT_T,
                   cursor="hand2", relief="flat", bd=0)
    btn.pack(side="left", padx=(3, 0), ipady=4)
    btn.bind("<Button-1>", _browse)
    hover(btn, BG4, BG3, DIM2, CYAN)

    if on_change:
        var.trace_add("write", lambda *_: on_change(var.get()))
    return entry, btn


# ── Kapasite Çubuğu ──────────────────────────────────────────────────────────
class CapBar(tk.Frame):
    def __init__(self, parent, **kw):
        super().__init__(parent, bg=BG2, **kw)
        self._canvas = tk.Canvas(self, bg=BG4, height=10, highlightthickness=0)
        self._canvas.pack(fill="x", pady=(4, 2))
        self._lbl = tk.Label(self, text="", bg=BG2, fg=DIM2, font=FONT_S)
        self._lbl.pack(anchor="w")
        self._used  = 0
        self._total = 0
        # Canvas boyutu değişince yeniden çiz
        self._canvas.bind("<Configure>", self._redraw)

    def update(self, used: int, total: int):
        self._used  = used
        self._total = total
        self._redraw()

    def _redraw(self, _=None):
        self._canvas.delete("all")
        used, total = self._used, self._total
        if total <= 0:
            self._lbl.config(text="", fg=DIM2)
            return
        pct   = min(used / total, 1.0)
        color = GRN if pct < 0.6 else (GOLD if pct < 0.9 else ACC)
        w     = self._canvas.winfo_width()
        if w > 4:
            self._canvas.create_rectangle(0, 0, int(w * pct), 10, fill=color, width=0)
        if used > total:
            diff = used - total
            self._lbl.config(
                text=f"✗  Sığmıyor!  {used/1024:.0f} KB / {total/1024:.0f} KB  "
                     f"(+{diff/1024:.0f} KB taşıyor)",
                fg=ACC)
        else:
            self._lbl.config(
                text=f"{pct*100:.1f}%  —  {used/1024:.1f} KB / {total/1024:.0f} KB  "
                     f"({(total-used)/1024:.0f} KB boş)",
                fg=color)


# ── Şifre Güç Göstergesi ─────────────────────────────────────────────────────
class PwStrengthBar(tk.Frame):
    def __init__(self, parent, **kw):
        super().__init__(parent, bg=BG2, **kw)
        row = tk.Frame(self, bg=BG2)
        row.pack(fill="x")
        tk.Label(row, text="Güç :", bg=BG2, fg=DIM2, font=FONT_S).pack(side="left")
        self._dots = []
        for _ in range(5):
            d = tk.Frame(row, bg=DIM, width=22, height=5)
            d.pack(side="left", padx=2, pady=4)
            self._dots.append(d)
        self._lbl = tk.Label(row, text="—", bg=BG2, fg=DIM, font=FONT_S)
        self._lbl.pack(side="left", padx=6)

    def update(self, pw: str):
        label, color = pw_strength(pw)
        filled = {"—": 0, "ZAYIF": 1, "ORTA": 3, "GÜÇLÜ": 5}.get(label, 0)
        for i, d in enumerate(self._dots):
            d.config(bg=color if i < filled else DIM)
        self._lbl.config(text=label, fg=color)


# ── Aksiyon Butonu (durum makinesi) ──────────────────────────────────────────
class ActionBtn(tk.Frame):
    """
    Durum makinesi: idle → busy → idle (ya da hata log'a yazılır)
    set_busy(True/False) ile yönetilir; çift tıklamayı engeller.
    """
    def __init__(self, parent, text: str, cmd, color=GRN, **kw):
        super().__init__(parent, bg=BG, **kw)
        self._color     = color
        self._cmd       = cmd
        self._busy      = False
        self._idle_text = text

        outer = tk.Frame(self, bg=color)
        outer.pack(fill="x", padx=16, pady=6)
        self._inner = tk.Frame(outer, bg=BG3)
        self._inner.pack(fill="x", padx=1, pady=1)
        self._lbl = tk.Label(self._inner, text=text, bg=BG3, fg=color,
                             font=FONT_L, pady=10, cursor="hand2")
        self._lbl.pack(fill="x")
        for w in [self._inner, self._lbl]:
            w.bind("<Button-1>", self._click)
            w.bind("<Enter>",    lambda _, i=self._inner: i.config(bg=BG4)
                                 if not self._busy else None)
            w.bind("<Leave>",    lambda _, i=self._inner: i.config(bg=BG3)
                                 if not self._busy else None)

    def _click(self, _=None):
        if not self._busy:
            self._cmd()

    def set_busy(self, busy: bool, text: str = ""):
        self._busy = busy
        if busy:
            t = text or "İşleniyor..."
            self._lbl.config(text=t, fg=DIM2, cursor="watch")
            self._inner.config(bg=BG2)
        else:
            self._lbl.config(text=self._idle_text, fg=self._color, cursor="hand2")
            self._inner.config(bg=BG3)


# ── Scrollable Panel Tabanı ──────────────────────────────────────────────────
class ScrollPanel(tk.Frame):
    """
    İçeriğini kaydırılabilir canvas içinde barındıran temel panel.
    canvas referansı App'e açılır; App MouseWheel olayını buraya yönlendirir.
    """
    def __init__(self, parent, **kw):
        super().__init__(parent, bg=BG, **kw)
        self._canvas = tk.Canvas(self, bg=BG, highlightthickness=0)
        sb = ttk.Scrollbar(self, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=sb.set)
        self._canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        self._inner = tk.Frame(self._canvas, bg=BG)
        self._win   = self._canvas.create_window((0, 0), window=self._inner, anchor="nw")
        self._canvas.bind("<Configure>", self._on_canvas_resize)
        self._inner.bind("<Configure>",  self._on_inner_resize)

    def _on_canvas_resize(self, e):
        self._canvas.itemconfig(self._win, width=e.width)

    def _on_inner_resize(self, e):
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def scroll(self, delta: int):
        """App'in MouseWheel olayını ilettiği metot."""
        self._canvas.yview_scroll(-1 * (delta // 120), "units")

    def scroll_to_top(self):
        self._canvas.yview_moveto(0.0)


# ── Sidebar Nav Butonu ────────────────────────────────────────────────────────
class NavBtn(tk.Frame):
    def __init__(self, parent, icon: str, label: str, cmd, **kw):
        super().__init__(parent, bg=BG, cursor="hand2", **kw)
        self._cmd    = cmd
        self._active = False

        self._bar = tk.Frame(self, bg=BG, width=3)
        self._bar.pack(side="left", fill="y")
        body = tk.Frame(self, bg=BG)
        body.pack(side="left", fill="both", expand=True, padx=6, pady=10)
        self._icon = tk.Label(body, text=icon, bg=BG, fg=DIM2, font=("Courier New", 14))
        self._icon.pack()
        self._lbl  = tk.Label(body, text=label, bg=BG, fg=DIM, font=FONT_S)
        self._lbl.pack()

        for w in [self, body, self._icon, self._lbl]:
            w.bind("<Button-1>", lambda _: self._cmd())
            w.bind("<Enter>",    self._enter)
            w.bind("<Leave>",    self._leave)

    def _enter(self, _=None):
        if not self._active:
            self._icon.config(fg=FG); self._lbl.config(fg=DIM2)

    def _leave(self, _=None):
        if not self._active:
            self._icon.config(fg=DIM2); self._lbl.config(fg=DIM)

    def set_active(self, v: bool):
        self._active = v
        self._bar.config(bg=ACC if v else BG)
        self._icon.config(fg=ACC if v else DIM2)
        self._lbl.config(fg=FG if v else DIM)


# ════════════════════════════════════════════════════════════════
#  KATMAN 3 — Paneller
# ════════════════════════════════════════════════════════════════

PRESETS = {
    "Hızlı":    (128, 128, 10,  5),
    "Standart": (256, 256, 10, 10),
    "Yüksek":   (512, 512, 15, 15),
}


class HidePanel(ScrollPanel):
    def __init__(self, parent, state: AppState, status_cb):
        super().__init__(parent)
        self._state  = state
        self._status = status_cb
        self._build(self._inner)

    def on_activate(self):
        self.scroll_to_top()

    # ── UI ────────────────────────────────────────────────────────────────────
    def _build(self, p):
        # Başlık
        hdr = tk.Frame(p, bg=BG)
        hdr.pack(fill="x", padx=20, pady=(16, 2))
        tk.Label(hdr, text="Veriyi Gizle", bg=BG, fg=FG2,
                 font=("Courier New", 13, "bold")).pack(side="left")
        tk.Label(hdr, text="  dosyayı karıncalı videoya göm",
                 bg=BG, fg=DIM2, font=FONT_T).pack(side="left", pady=(3, 0))
        tk.Frame(p, bg=BORDER, height=1).pack(fill="x", padx=20, pady=(2, 4))

        # ── KART 1: Video Konfigürasyonu ──────────────────────────────────────
        c1 = card(p, "①  VIDEO KONFİGÜRASYONU", CYAN)

        preset_row = tk.Frame(c1, bg=BG2)
        preset_row.pack(fill="x", pady=(0, 4))
        tk.Label(preset_row, text="Boyut & Süre :", bg=BG2, fg=DIM2, font=FONT_T,
                 width=15, anchor="w").pack(side="left")
        self._preset      = tk.StringVar(value=cfg.get("preset", "Standart"))
        self._preset_btns = {}
        for name in list(PRESETS.keys()) + ["Özel"]:
            b = tk.Label(preset_row, text=f" {name} ", bg=BG4, fg=DIM2,
                         font=FONT_T, cursor="hand2", relief="flat", bd=0)
            b.pack(side="left", padx=2, ipady=3)
            b.bind("<Button-1>", lambda _, n=name: self._set_preset(n))
            self._preset_btns[name] = b
            tip = (f"{'×'.join(map(str, PRESETS[name][:2]))}  {PRESETS[name][3]}s"
                   if name in PRESETS else "Özel kaydırıcı")
            Tooltip(b, tip)

        # Özel slider alanı
        self._custom_frame = tk.Frame(c1, bg=BG2)
        self.vid_w   = tk.IntVar(value=cfg.get("vid_w",   256))
        self.vid_h   = tk.IntVar(value=cfg.get("vid_h",   256))
        self.vid_fps = tk.DoubleVar(value=cfg.get("vid_fps", 10.0))
        self.vid_dur = tk.DoubleVar(value=cfg.get("vid_dur", 10.0))

        for lbl, var, lo, hi, res in [
            ("Genişlik",  self.vid_w,   128, 512, 128),
            ("Yükseklik", self.vid_h,   128, 512, 128),
            ("FPS",       self.vid_fps,   5,  30,   5),
            ("Süre(sn)",  self.vid_dur,   2,  60,   2),
        ]:
            sf = tk.Frame(self._custom_frame, bg=BG2)
            sf.pack(side="left", expand=True, padx=6)
            vl = tk.Label(sf, text="", bg=BG2, fg=CYAN, font=FONT_T)
            vl.pack()
            def _mk(v=var, vl=vl, l=lbl):
                def _t(*_):
                    vl.config(text=f"{l}\n{v.get()}")
                    self._refresh_cap()
                v.trace_add("write", _t); _t()
            _mk()
            tk.Scale(sf, from_=lo, to=hi, resolution=res, variable=var,
                     orient="vertical", bg=BG2, fg=FG, troughcolor=BG4,
                     highlightthickness=0, activebackground=ACC,
                     showvalue=False, length=70, sliderlength=12, relief="flat").pack()

        self._vid_summary = tk.Label(c1, text="", bg=BG2, fg=DIM2, font=FONT_T)
        self._vid_summary.pack(anchor="w", pady=(4, 0))

        avi = [("AVI Video", "*.avi"), ("Tüm", "*.*")]
        self.stego_out = tk.StringVar(value=cfg.get("stego_out", ws_auto_stego()))
        file_row(c1, "Stego çıktısı :", self.stego_out, avi, save=True,
                 initialdir=ws_stego(), on_change=self._on_stego_out_change)

        self._set_preset(self._preset.get())

        # ── KART 2: Gizlenecek Dosya ──────────────────────────────────────────
        c2 = card(p, "②  GİZLENECEK DOSYA", GOLD)
        self.embed_file = tk.StringVar(value=cfg.get("embed_file", ""))
        file_row(c2, "Dosya seç :", self.embed_file,
                 [("Tüm Dosyalar", "*.*")], on_change=self._on_file_change)
        self._file_info = tk.Label(c2, text="", bg=BG2, fg=DIM2, font=FONT_T)
        self._file_info.pack(anchor="w", pady=(2, 0))
        self._capbar = CapBar(c2)
        self._capbar.pack(fill="x", pady=(4, 0))
        Tooltip(self._capbar, "Payload boyutunu video kapasitesiyle karşılaştırır (başlık + şifreleme dahil)")

        # ── KART 3: Şifre ─────────────────────────────────────────────────────
        c3 = card(p, "③  ŞİFRE KORUMASI  (isteğe bağlı)", ACC)
        self.password  = tk.StringVar()
        self.password2 = tk.StringVar()
        self._show_pw  = tk.BooleanVar(value=False)

        for lbl, var, attr in [("Şifre  :", self.password, "_pw1"),
                                ("Tekrar :", self.password2, "_pw2")]:
            r = tk.Frame(c3, bg=BG2)
            r.pack(fill="x", pady=2)
            tk.Label(r, text=lbl, bg=BG2, fg=DIM2, font=FONT_T,
                     width=10, anchor="w").pack(side="left")
            e = tk.Entry(r, textvariable=var, show="●", bg=BG4, fg=ACC2,
                         font=FONT_M, insertbackground=ACC2, relief="flat", bd=0,
                         highlightthickness=1, highlightbackground=BORDER, highlightcolor=ACC)
            e.pack(side="left", fill="x", expand=True, ipady=4)
            setattr(self, attr, e)

        self.password.trace_add("write",  self._on_pw_change)
        self.password2.trace_add("write", self._on_pw_change)

        def _toggle():
            s = "" if self._show_pw.get() else "●"
            self._pw1.config(show=s); self._pw2.config(show=s)
        tk.Checkbutton(c3, text=" Şifreyi göster", variable=self._show_pw, command=_toggle,
                       bg=BG2, fg=DIM2, font=FONT_T, selectcolor=BG4,
                       activebackground=BG2, relief="flat", bd=0, cursor="hand2").pack(anchor="w", pady=(2, 0))
        self._pw_match = tk.Label(c3, text="", bg=BG2, fg=DIM, font=FONT_S)
        self._pw_match.pack(anchor="w")
        self._pw_strength = PwStrengthBar(c3)
        self._pw_strength.pack(anchor="w", pady=(2, 0))
        tk.Label(c3, text="  Boş bırakırsan şifreleme uygulanmaz",
                 bg=BG2, fg=DIM, font=FONT_S).pack(anchor="w")
        Tooltip(self._pw1, "AES-256-GCM · PBKDF2-HMAC-SHA256 · 600.000 iter · 16B salt · 12B nonce")

        # ── Aksiyon ───────────────────────────────────────────────────────────
        self._act = ActionBtn(p, "⬆  GİZLE", self._run, color=ACC)
        self._act.pack(fill="x")
        Tooltip(self._act, "Video üretimi + gömme tek adımda gerçekleşir")

        # Oynatıcı
        play_row = tk.Frame(p, bg=BG)
        play_row.pack(fill="x", padx=16, pady=(0, 6))
        pb = tk.Label(play_row, text=" ▶  Stego Videoyu Oynat ",
                      bg=BG3, fg=DIM2, font=FONT_T, cursor="hand2", relief="flat", bd=0)
        pb.pack(side="left", ipady=5, padx=(0, 4))
        pb.bind("<Button-1>", lambda _: self._open_player())
        hover(pb, BG3, BG4, DIM2, CYAN)
        Tooltip(pb, "Seçili stego videoyu animasyonlu oynatıcıda açar")

        # Log
        self.log_box = LogBox(p)
        self.log_box.pack(fill="x", padx=16, pady=(4, 16))
        self.log("Hazır — dosya seç ve GİZLE butonuna bas.", "dim")
        self.log("Uyarı: yalnızca kayıpsız AVI codec LSB'yi korur.", "warn")

        if self.embed_file.get():
            self._on_file_change(self.embed_file.get())
        self._refresh_cap()

    # ── Preset ───────────────────────────────────────────────────────────────
    def _set_preset(self, name: str):
        self._preset.set(name)
        cfg.set("preset", name)
        for n, b in self._preset_btns.items():
            b.config(bg=ACC if n == name else BG4, fg=FG2 if n == name else DIM2)
        if name in PRESETS:
            w, h, fps, dur = PRESETS[name]
            self.vid_w.set(w); self.vid_h.set(h)
            self.vid_fps.set(fps); self.vid_dur.set(dur)
            self._custom_frame.pack_forget()
        else:
            self._custom_frame.pack(fill="x", pady=4)
        self._refresh_cap()

    def _refresh_cap(self, *_):
        try:
            w, h   = self.vid_w.get(), self.vid_h.get()
            fps    = self.vid_fps.get()
            dur    = self.vid_dur.get()
            n      = max(1, int(fps * dur))
            cap    = (w * h * 3 * n) // 8
            est_mb = w * h * 4 * n / 1024 / 1024
            warn   = "  ⚠ ÇOK BÜYÜK!" if est_mb > 100 else \
                     "  ⚠ Büyük" if est_mb > 30 else ""
            self._vid_summary.config(
                text=f"{n} kare  |  Kapasite: {cap/1024:.0f} KB  |  "
                     f"Video ≈ {est_mb:.0f} MB{warn}",
                fg=ACC if "ÇOK" in warn else (GOLD if warn else DIM2))
            fp = self.embed_file.get()
            if fp and os.path.exists(fp):
                used = estimate_payload_bytes(fp, self.password.get() or None)
                self._capbar.update(used, cap)
        except Exception:
            pass

    def _on_file_change(self, path: str):
        cfg.set("embed_file", path)
        if path and os.path.exists(path):
            size  = os.path.getsize(path)
            self._file_info.config(
                text=f"  {os.path.basename(path)}  ·  {size:,} byte  ·  {file_type_label(path)}",
                fg=CYAN)
        else:
            self._file_info.config(text="", fg=DIM2)
        self._refresh_cap()

    def _on_stego_out_change(self, path: str):
        cfg.set("stego_out", path)
        # Paneller arası senkronizasyon: RevealPanel otomatik güncellenir
        self._state.set("stego_path", path)

    def _on_pw_change(self, *_):
        pw1 = self.password.get()
        pw2 = self.password2.get()
        self._pw_strength.update(pw1)
        if not pw1:
            self._pw_match.config(text="", fg=DIM)
        elif pw2 and pw1 == pw2:
            self._pw_match.config(text="  ✓ Eşleşiyor", fg=GRN)
        elif pw2:
            self._pw_match.config(text="  ✗ Eşleşmiyor", fg=ACC)
        else:
            self._pw_match.config(text="", fg=DIM)
        self._refresh_cap()

    def log(self, msg, tag="info"):
        self.log_box.log(msg, tag)

    # ── Çalıştır ──────────────────────────────────────────────────────────────
    def _run(self):
        from video_noise   import generate_noise_video
        from video_encoder import encode

        fpath = self.embed_file.get()
        dst   = self.stego_out.get()
        pw    = self.password.get()
        pw2   = self.password2.get()

        if not fpath or not os.path.exists(fpath):
            messagebox.showerror("Eksik", "Gömülecek dosyayı seçin."); return
        if pw and pw != pw2:
            messagebox.showerror("Şifre", "Şifreler eşleşmiyor!"); return
        if not dst.lower().endswith(".avi"):
            messagebox.showwarning("Format", "Çıktı .avi olmalı — diğer formatlar LSB'yi bozar."); return
        if not inside_workspace(dst):
            if not messagebox.askyesno("Güvenlik Uyarısı",
                    f"Çıktı workspace dışına yazılacak:\n{dst}\n\nDevam etmek istiyor musun?"):
                return

        w, h  = self.vid_w.get(), self.vid_h.get()
        fps   = self.vid_fps.get()
        dur   = self.vid_dur.get()
        n     = max(1, int(fps * dur))
        cap   = (w * h * 3 * n) // 8
        need  = estimate_payload_bytes(fpath, pw or None)

        if need > cap:
            messagebox.showerror("Kapasite",
                f"Dosya sığmıyor!\n\nGerekli : {need:,} byte\nMevcut  : {cap:,} byte\n\n"
                "Daha yüksek çözünürlük veya uzun süre seçin."); return

        est_mb = w * h * 4 * n / 1024 / 1024
        if est_mb > MAX_VIDEO_MB:
            if not messagebox.askyesno("Büyük Dosya", f"Video ≈ {est_mb:.0f} MB. Devam?"):
                return

        if os.path.exists(dst):
            if not messagebox.askyesno("Üzerine Yaz", f"{os.path.basename(dst)} mevcut.\nÜzerine yazılsın mı?"):
                return

        noise_tmp = os.path.join(ws_stego(), "_noise_tmp.avi")
        enc_tag   = " [AES-256-GCM]" if pw else " [şifresiz]"
        self.log_box.clear()
        self.log(f"Başlatılıyor — {w}×{h}  {fps}fps  {dur}s  →  {n} kare", "dim")
        self.log(f"Dosya: {os.path.basename(fpath)}  ({os.path.getsize(fpath):,} byte){enc_tag}", "dim")
        self._act.set_busy(True, "⏳  Video üretiliyor...")
        self._status("Karıncalı video oluşturuluyor...")

        def work():
            stats = generate_noise_video(noise_tmp, w, h, fps, dur)
            self.after(0, lambda: self.log(
                f"  ✓ {stats['frames']} kare — {stats['file_size']/1024/1024:.1f} MB", "ok"))
            self.after(0, lambda: self._act.set_busy(True, "⏳  Dosya gömülüyor..."))
            self.after(0, lambda: self._status("Dosya LSB kanalına gömülüyor..."))
            encode(noise_tmp, fpath, dst, password=pw or None)
            try: os.remove(noise_tmp)
            except Exception: pass
            return dst, bool(pw)

        def done(res, err):
            self._act.set_busy(False)
            if err:
                self.log(f"HATA: {err}", "err"); self._status("Hata.")
            else:
                path, encrypted = res
                label = " [AES-256-GCM şifreli]" if encrypted else " [şifresiz]"
                self.log(f"✓  Gömüldü{label}", "ok")
                self.log(f"   Çıktı  : {path}", "info")
                self.log(f"   Doluluk: {need/cap*100:.1f}%", "dim")
                self._status(f"Gömüldü — {os.path.basename(path)}")
                # Durumu tüm dinleyicilere yayınla
                self._state.set("stego_path",      path)
                self._state.set("stego_password",  pw)
                self._state.set("stego_encrypted", encrypted)

        run_in_thread(self, work, done)

    def _open_player(self):
        stego = self.stego_out.get()
        pw    = self.password.get()
        args  = [sys.executable, _p("player.py")]
        if stego and os.path.exists(stego):
            args.append(stego)
            if pw:
                args += ["--password", pw]
        self.log("Oynatıcı açılıyor...", "dim")
        try:
            subprocess.Popen(args, cwd=_p())
        except Exception as e:
            self.log(f"HATA: {e}", "err")


class RevealPanel(ScrollPanel):
    def __init__(self, parent, state: AppState, status_cb):
        super().__init__(parent)
        self._state       = state
        self._status      = status_cb
        self._result_path = None
        self._build(self._inner)

        # AppState'den gelen stego_path değişince otomatik güncelle
        state.watch("stego_path",     self._on_state_stego)
        state.watch("stego_password", self._on_state_pw)

    def _on_state_stego(self, path: str):
        """GİZLE paneli başarıyla bitirince burası otomatik güncellenir."""
        if path:
            self.stego_in.set(path)
            self.log(f"↺  GİZLE panelinden aktarıldı: {os.path.basename(path)}", "cyan")

    def _on_state_pw(self, pw: str):
        self.password.set(pw or "")

    def on_activate(self):
        self.scroll_to_top()

    # ── UI ────────────────────────────────────────────────────────────────────
    def _build(self, p):
        hdr = tk.Frame(p, bg=BG)
        hdr.pack(fill="x", padx=20, pady=(16, 2))
        tk.Label(hdr, text="Veriyi Ortaya Çıkar", bg=BG, fg=FG2,
                 font=("Courier New", 13, "bold")).pack(side="left")
        tk.Label(hdr, text="  stego videodan gizli dosyayı çıkar",
                 bg=BG, fg=DIM2, font=FONT_T).pack(side="left", pady=(3, 0))
        tk.Frame(p, bg=BORDER, height=1).pack(fill="x", padx=20, pady=(2, 4))

        # ── KART 1: Stego Video ───────────────────────────────────────────────
        c1 = card(p, "①  STEGO VİDEO", CYAN)
        self.stego_in = tk.StringVar(value=cfg.get("stego_out", ""))
        self._fmt_warn = tk.Label(c1, text="", bg=BG2, fg=ACC, font=FONT_T)
        file_row(c1, "Stego AVI :", self.stego_in,
                 [("AVI Video", "*.avi"), ("Tüm", "*.*")],
                 initialdir=ws_inbox(),
                 on_change=self._on_stego_change)
        self._fmt_warn.pack(anchor="w")
        inbox_hint = tk.Label(c1,
            text=f"  İpucu: alınan stego videoları workspace/inbox/ klasörüne koyun",
            bg=BG2, fg=DIM, font=FONT_S)
        inbox_hint.pack(anchor="w", pady=(0, 2))

        # ── KART 2: Şifre ─────────────────────────────────────────────────────
        c2 = card(p, "②  ŞİFRE  (şifrelenmişse)", ACC)
        self.password  = tk.StringVar()
        self._show_pw2 = tk.BooleanVar(value=False)
        pw_row = tk.Frame(c2, bg=BG2)
        pw_row.pack(fill="x")
        tk.Label(pw_row, text="Şifre :", bg=BG2, fg=DIM2, font=FONT_T,
                 width=10, anchor="w").pack(side="left")
        self._pw_entry = tk.Entry(pw_row, textvariable=self.password, show="●",
                                  bg=BG4, fg=ACC2, font=FONT_M,
                                  insertbackground=ACC2, relief="flat", bd=0,
                                  highlightthickness=1, highlightbackground=BORDER, highlightcolor=ACC)
        self._pw_entry.pack(side="left", fill="x", expand=True, ipady=4)
        def _toggle2():
            self._pw_entry.config(show="" if self._show_pw2.get() else "●")
        tk.Checkbutton(c2, text=" Göster", variable=self._show_pw2, command=_toggle2,
                       bg=BG2, fg=DIM2, font=FONT_T, selectcolor=BG4,
                       activebackground=BG2, relief="flat", bd=0, cursor="hand2").pack(anchor="w", pady=(2, 0))
        tk.Label(c2, text="  Şifresiz gömüldüyse boş bırak", bg=BG2, fg=DIM, font=FONT_S).pack(anchor="w")

        # ── KART 3: Çıktı ─────────────────────────────────────────────────────
        c3 = card(p, "③  ÇIKTI  (otomatik: workspace/recovered/)", GOLD)
        self.out_dir = tk.StringVar(value=ws_recovered())
        row = tk.Frame(c3, bg=BG2)
        row.pack(fill="x")
        tk.Label(row, text="Klasör :", bg=BG2, fg=DIM2, font=FONT_T,
                 width=10, anchor="w").pack(side="left")
        tk.Entry(row, textvariable=self.out_dir, bg=BG4, fg=FG, font=FONT_T,
                 insertbackground=GRN, relief="flat", bd=0,
                 highlightthickness=1, highlightbackground=BORDER,
                 highlightcolor=CYAN).pack(side="left", fill="x", expand=True, ipady=4)
        dir_btn = tk.Label(row, text=" Klasörü Aç ", bg=BG4, fg=DIM2, font=FONT_T,
                           cursor="hand2", relief="flat", bd=0)
        dir_btn.pack(side="left", padx=(3, 0), ipady=4)
        hover(dir_btn, BG4, BG3, DIM2, CYAN)
        dir_btn.bind("<Button-1>", lambda _: subprocess.Popen(
            f'explorer "{os.path.normpath(ws_recovered())}"'))

        # ── Aksiyon ───────────────────────────────────────────────────────────
        self._act = ActionBtn(p, "🔍  ORTAYA ÇIKAR", self._run, color=GRN)
        self._act.pack(fill="x")

        # ── Sonuç alanı ───────────────────────────────────────────────────────
        self._result_outer = tk.Frame(p, bg=BG)
        self._result_outer.pack(fill="x", padx=16, pady=(2, 4))

        # Log
        self.log_box = LogBox(p)
        self.log_box.pack(fill="x", padx=16, pady=(4, 16))
        self.log("Hazır — stego videoyu seç ve ORTAYA ÇIKAR butonuna bas.", "dim")

    def _on_stego_change(self, path: str):
        ext = os.path.splitext(path)[1].lower()
        if ext in LOSSY_EXT:
            self._fmt_warn.config(
                text=f"  ⚠  {ext.upper()} kayıplı sıkıştırma — LSB'ler bozulmuş olabilir!", fg=ACC)
        elif ext in LOSSLESS_EXT:
            self._fmt_warn.config(text="  ✓  AVI kayıpsız — LSB korunur", fg=GRN)
        else:
            self._fmt_warn.config(text="", fg=DIM2)

    def log(self, msg, tag="info"):
        self.log_box.log(msg, tag)

    def _run(self):
        from video_decoder import decode as vid_decode
        src  = self.stego_in.get()
        outd = self.out_dir.get()
        pw   = self.password.get()

        if not src or not os.path.exists(src):
            messagebox.showerror("Eksik", f"Stego AVI bulunamadı:\n{src}"); return

        ext = os.path.splitext(src)[1].lower()
        if ext in LOSSY_EXT:
            if not messagebox.askyesno("Format Uyarısı",
                    f"{ext.upper()} kayıplı format.\nLSB'ler bozulmuş olabilir. Deneyelim mi?"): return

        os.makedirs(outd, exist_ok=True)
        self.log_box.clear()
        self._clear_result()
        self.log(f"Analiz ediliyor: {os.path.basename(src)}", "dim")
        self._act.set_busy(True, "⏳  Çıkarılıyor...")
        self._status("Stego video analiz ediliyor...")

        def work():
            return vid_decode(src, outd, password=pw or None)

        def done(res, err):
            self._act.set_busy(False)
            if err:
                self.log(f"HATA: {err}", "err")
                msg = str(err)
                if any(k in msg.lower() for k in ("şifre", "mac", "decrypt", "password")):
                    self.log("  → Yanlış şifre veya video şifresiz gömüldü", "warn")
                self._status("Çıkarma başarısız.")
            else:
                path, was_enc = res if isinstance(res, tuple) else (res, False)
                size  = os.path.getsize(path)
                label = " [AES-256-GCM çözüldü]" if was_enc else " [şifresiz]"
                self.log(f"✓  Çıkarıldı{label}  —  {size:,} byte", "ok")
                self.log(f"   Yol: {path}", "info")
                if pw and not was_enc:
                    self.log("  ⚠ Şifre girildi ama video şifresizdi", "warn")
                self._result_path = path
                self._status(f"Çıkarıldı — {os.path.basename(path)}")
                self._show_result(path, was_enc)

        run_in_thread(self, work, done)

    def _clear_result(self):
        for w in self._result_outer.winfo_children():
            w.destroy()

    def _show_result(self, path: str, was_enc: bool):
        self._clear_result()
        name  = os.path.basename(path)
        size  = os.path.getsize(path)
        enc_t = "AES-256-GCM" if was_enc else "Şifresiz"

        # Başlık
        outer = tk.Frame(self._result_outer, bg=GRN)
        outer.pack(fill="x")
        inner = tk.Frame(outer, bg=BG2)
        inner.pack(fill="x", padx=1, pady=1)

        th = tk.Frame(inner, bg=BG2)
        th.pack(fill="x")
        tk.Label(th, text="  ✓  BULUNAN DOSYA", bg=BG2, fg=GRN, font=FONT_T,
                 anchor="w").pack(side="left", padx=(4, 0), pady=(6, 0))
        tk.Frame(inner, bg=GRN, height=1).pack(fill="x", pady=(3, 0))

        info = tk.Frame(inner, bg=BG2)
        info.pack(fill="x", padx=14, pady=8)
        tk.Label(info, text=name, bg=BG2, fg=GRN2, font=FONT_B, anchor="w").pack(anchor="w")
        tk.Label(info, text=f"{size:,} byte  ·  {file_type_label(path)}  ·  {enc_t}",
                 bg=BG2, fg=DIM2, font=FONT_T).pack(anchor="w", pady=(2, 0))

        # Metin önizleme
        if is_text_file(path):
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    preview = f.read(600)
                tk.Frame(inner, bg=BORDER, height=1).pack(fill="x", padx=14)
                tk.Label(inner, text="  Önizleme", bg=BG2, fg=DIM2,
                         font=FONT_S, anchor="w").pack(fill="x", padx=14, pady=(4, 0))
                txt = tk.Text(inner, height=6, bg=BG3, fg=CYAN, font=FONT_T,
                              relief="flat", bd=0, wrap="word", state="normal")
                txt.insert("1.0", preview)
                txt.config(state="disabled")
                txt.pack(fill="x", padx=14, pady=(0, 4))
            except Exception:
                pass

        # Aksiyon butonları
        btn_row = tk.Frame(inner, bg=BG2)
        btn_row.pack(fill="x", padx=14, pady=(4, 10))

        def _mk(text, cmd, color=DIM2):
            b = tk.Label(btn_row, text=f"  {text}  ", bg=BG3, fg=color,
                         font=FONT_T, cursor="hand2", relief="flat", bd=0)
            b.pack(side="left", padx=3, ipady=4)
            b.bind("<Button-1>", lambda _: cmd())
            hover(b, BG3, BG4, color, FG)

        _mk("Dosyayı Aç", lambda: os.startfile(path), GRN)
        _mk("Konumunu Göster",
            lambda: subprocess.Popen(f'explorer /select,"{os.path.normpath(path)}"'), CYAN)
        if is_text_file(path):
            def _copy():
                try:
                    with open(path, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read()
                    self.clipboard_clear(); self.clipboard_append(content)
                    self.log("✓ İçerik panoya kopyalandı.", "ok")
                except Exception as e:
                    self.log(f"Kopyalama hatası: {e}", "err")
            _mk("Panoya Kopyala", _copy, GOLD)


class AboutPanel(ScrollPanel):
    def __init__(self, parent):
        super().__init__(parent)
        self._build(self._inner)

    def on_activate(self):
        self.scroll_to_top()

    def _build(self, p):
        hdr = tk.Frame(p, bg=BG)
        hdr.pack(fill="x", padx=20, pady=(16, 4))
        tk.Label(hdr, text="LSB Steganografisi", bg=BG, fg=FG2,
                 font=("Courier New", 13, "bold")).pack(side="left")
        tk.Label(hdr, text="  teknik kılavuz", bg=BG, fg=DIM2, font=FONT_T).pack(side="left", pady=(3, 0))
        tk.Frame(p, bg=BORDER, height=1).pack(fill="x", padx=20, pady=(0, 6))

        sections = [
            (CYAN, "Temel Fikir",
             "Her pikselin R, G, B kanalı 8 bitten oluşur.\n"
             "Son bit (LSB) rengi yalnızca 1/255 birim değiştirir — insan gözü algılayamaz.\n"
             "Bu bite gizli veri yazarız."),
            (GOLD, "İki Kullanım Senaryosu",
             "1. Güvenli Aktarım: dosyayı videoya göm → karşı tarafa ilet → çözsün.\n"
             "   Şifre ile ek güvenlik — yanlış şifre = veri okunamaz.\n\n"
             "2. Gizli Depolama: bilgisayarına el geçirilse de karıncalı video\n"
             "   tamamen masum görünür. İçerik tamamen gizlidir."),
            (GRN, "Kapasite Formülü",
             "Video: genişlik × yükseklik × 3 × kare ÷ 8  =  byte\n"
             "256×256 × 100 kare  →  2.4 MB kapasite\n"
             "Payload < %5 tutmak istatistiksel tespiti güçleştirir."),
            (ACC, "AES-256-GCM Şifreleme",
             "• PBKDF2-HMAC-SHA256 anahtar türetme (600.000 iter)\n"
             "• 16 byte rastgele salt  +  12 byte rastgele nonce\n"
             "• AES-256-GCM kimlik doğrulama etiketi (MAC)\n"
             "• Yanlış şifre → MAC hatası → veri tamamen okunamaz\n"
             "Steganografi + Şifreleme = iki katmanlı güvenlik"),
            (DIM2, "Codec Kritik Önemi",
             "AVI (RGBA/FFV1)  ✓  kayıpsız  — LSB korunur\n"
             "JPEG             ✗  DCT sıkıştırma  — LSB silinir\n"
             "MP4 / H.264      ✗  motion compensation  — LSB tamamen yok olur"),
            (GRN, "PSNR ve Görünmezlik",
             "İnsan gözü eşiği  : ~30–35 dB\n"
             "Bu araç           : >74 dB  → tamamen algılanamaz\n"
             "Değişen piksel    : %0.04 (gürültüde kaybolur)"),
            (DIM2, "Steganaliz (Tespit)",
             "Chi-Square saldırısı: çift-tek dağılımı inceler.\n"
             "Savunma: karıncalı ekran zaten rastgele → anomali yok.\n"
             "AES-GCM şifreleme LSB dağılımını ilave olarak rasgeleleştirir."),
        ]

        for color, title, body in sections:
            outer = tk.Frame(p, bg=BORDER)
            outer.pack(fill="x", padx=16, pady=5)
            box = tk.Frame(outer, bg=BG2)
            box.pack(fill="x", padx=1, pady=1)
            th = tk.Frame(box, bg=BG2)
            th.pack(fill="x")
            tk.Label(th, text=f"  {title}", bg=BG2, fg=color, font=FONT_B,
                     anchor="w").pack(side="left", padx=(4, 0), pady=(8, 2))
            tk.Frame(box, bg=color, height=1).pack(fill="x", padx=12)
            tk.Label(box, text=body, bg=BG3, fg=FG, font=FONT_T,
                     justify="left", anchor="w", padx=16, pady=10).pack(fill="x", padx=12, pady=(0, 8))
        tk.Label(p, text="", bg=BG).pack()


# ════════════════════════════════════════════════════════════════
#  ANA UYGULAMA
# ════════════════════════════════════════════════════════════════
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("LSTG — LSB Steganografi")
        self.configure(bg=BG)
        self.geometry("880x740")
        self.minsize(780, 600)
        self.resizable(True, True)

        cfg.bind_root(self)
        ensure_workspace()
        self._state    = AppState()
        self._panels: dict[str, ScrollPanel] = {}
        self._nav_btns: dict[str, NavBtn]    = {}
        self._current: str | None            = None

        self._style()
        self._build()
        self._refresh_ws_bar()
        self._bind_mousewheel()
        self._bind_shortcuts()
        self._switch("hide")
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _style(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure("TScrollbar", background=BG3, troughcolor=BG,
                    borderwidth=0, arrowcolor=DIM)
        s.map("TScrollbar", background=[("active", BG4)])

    def _build(self):
        # Üst çubuk
        top = tk.Frame(self, bg=BG, height=46)
        top.pack(fill="x", side="top")
        top.pack_propagate(False)
        tk.Frame(top, bg=ACC, width=4).pack(side="left", fill="y")
        tk.Label(top, text="  LSTG", bg=BG, fg=ACC,
                 font=("Courier New", 14, "bold")).pack(side="left", padx=(8, 2))
        tk.Label(top, text="Steganografi", bg=BG, fg=DIM2, font=FONT_T).pack(side="left")
        tk.Label(top, text="Ctrl+H  Gizle  |  Ctrl+R  Çıkar  |  Ctrl+I  Bilgi",
                 bg=BG, fg=DIM, font=FONT_S).pack(side="right", padx=16)
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x")

        # Workspace çubuğu
        self._ws_bar = tk.Frame(self, bg=BG3, height=24)
        self._ws_bar.pack(fill="x")
        self._ws_bar.pack_propagate(False)
        tk.Frame(self._ws_bar, bg=GOLD, width=3).pack(side="left", fill="y")
        tk.Label(self._ws_bar, text=" WORKSPACE:", bg=BG3, fg=GOLD,
                 font=FONT_S).pack(side="left", padx=(6, 2))
        self._ws_lbl = tk.Label(self._ws_bar, text="", bg=BG3, fg=DIM2, font=FONT_S)
        self._ws_lbl.pack(side="left")
        ws_open = tk.Label(self._ws_bar, text=" Klasörü Aç ", bg=BG3, fg=DIM,
                           font=FONT_S, cursor="hand2")
        ws_open.pack(side="right", padx=6)
        ws_open.bind("<Button-1>", lambda _: subprocess.Popen(
            f'explorer "{os.path.normpath(ws_root())}"'))
        hover(ws_open, BG3, BG4, DIM, CYAN)
        ws_chg = tk.Label(self._ws_bar, text=" Değiştir ", bg=BG3, fg=DIM,
                          font=FONT_S, cursor="hand2")
        ws_chg.pack(side="right")
        ws_chg.bind("<Button-1>", lambda _: self._change_workspace())
        hover(ws_chg, BG3, BG4, DIM, GOLD)

        tk.Frame(self, bg=BORDER, height=1).pack(fill="x")

        # Gövde
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True)

        # Durum ve içerik önce oluşturulur (paneller parent olarak kullanır)
        self._status_var = tk.StringVar(value="Hazır")
        self._content    = tk.Frame(body, bg=BG)   # henüz pack etme

        # Sidebar — içerikten ÖNCE pack edilmeli ki sol kenarda görünsün
        sidebar = tk.Frame(body, bg=BG, width=88)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        tk.Frame(sidebar, bg=BORDER, width=1).pack(side="right", fill="y")

        # İçerik — sidebar'dan SONRA pack edilir
        self._content.pack(side="left", fill="both", expand=True)

        status_cb = lambda msg: self._status_var.set(msg)

        nav_defs = [
            ("hide",   "⬆",  "GİZLE",  lambda: HidePanel(self._content,  self._state, status_cb)),
            ("reveal", "🔍", "ÇIKAR",  lambda: RevealPanel(self._content, self._state, status_cb)),
            ("about",  "ⓘ",  "BİLGİ",  lambda: AboutPanel(self._content)),
        ]
        for key, icon, label, factory in nav_defs:
            nb = NavBtn(sidebar, icon, label, lambda k=key: self._switch(k))
            nb.pack(fill="x")
            self._nav_btns[key] = nb
            self._panels[key]   = factory()

        tk.Label(sidebar, text="v4.0", bg=BG, fg=DIM, font=FONT_S).pack(side="bottom", pady=8)
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", side="bottom")
        sb = tk.Frame(self, bg=BG2, height=22)
        sb.pack(fill="x", side="bottom")
        sb.pack_propagate(False)
        tk.Frame(sb, bg=GRN, width=3).pack(side="left", fill="y")
        tk.Label(sb, textvariable=self._status_var, bg=BG2, fg=DIM2, font=FONT_S).pack(side="left", padx=8)
        tk.Label(sb, text="AVI+RGBA  ·  LSB 1 bit/kanal  ·  AES-256-GCM",
                 bg=BG2, fg=DIM, font=FONT_S).pack(side="right", padx=12)

    # ── MouseWheel — tek bağlama, aktif panele yönlendirilir ─────────────────
    def _bind_mousewheel(self):
        self.bind_all("<MouseWheel>", self._on_mousewheel)

    def _on_mousewheel(self, e: tk.Event):
        if self._current and self._current in self._panels:
            self._panels[self._current].scroll(e.delta)

    # ── Workspace Yönetimi ────────────────────────────────────────────────────
    def _refresh_ws_bar(self):
        path = ws_root()
        short = path if len(path) < 60 else "…" + path[-57:]
        self._ws_lbl.config(text=short)

    def _change_workspace(self):
        new = filedialog.askdirectory(
            title="Workspace Klasörü Seç",
            initialdir=ws_root())
        if new:
            cfg.set("workspace", new)
            ensure_workspace()
            self._refresh_ws_bar()
            # Panellere bildir
            hp = self._panels.get("hide")
            rp = self._panels.get("reveal")
            if hp:
                hp.stego_out.set(ws_auto_stego())
            if rp:
                rp.out_dir.set(ws_recovered())
            messagebox.showinfo("Workspace",
                f"Workspace değiştirildi:\n{new}\n\nAlt klasörler oluşturuldu:\n"
                f"  stego/   — üretilen videolar\n"
                f"  inbox/   — alınan stego videolar\n"
                f"  recovered/ — çıkarılan dosyalar")

    # ── Panel Geçişi ──────────────────────────────────────────────────────────
    def _switch(self, key: str):
        if self._current == key:
            return
        if self._current:
            self._panels[self._current].pack_forget()
            self._nav_btns[self._current].set_active(False)
        panel = self._panels[key]
        panel.pack(in_=self._content, fill="both", expand=True)
        self._nav_btns[key].set_active(True)
        self._current = key
        if hasattr(panel, "on_activate"):
            panel.on_activate()

    # ── Klavye Kısayolları — Entry/Text odaklanıldığında tetiklenmez ──────────
    def _bind_shortcuts(self):
        def _guard(key):
            def _handler(e):
                if not focus_is_text(self):
                    self._switch(key)
            return _handler
        self.bind_all("<Control-h>", _guard("hide"))
        self.bind_all("<Control-r>", _guard("reveal"))
        self.bind_all("<Control-i>", _guard("about"))

    # ── Kapatma ───────────────────────────────────────────────────────────────
    def _on_close(self):
        cfg.flush_now()
        self.destroy()


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    App().mainloop()


if __name__ == "__main__":
    main()
