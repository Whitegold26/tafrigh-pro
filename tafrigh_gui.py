#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════╗
║        🎙️  TAFRIGH PRO  —  GUI Launcher                  ║
║        Tkinter wrapper over the CLI engine               ║
╚══════════════════════════════════════════════════════════╝
Requirements: Python 3.10+, tkinter (bundled with Python)
Run:  python tafrigh_gui.py
"""

import sys
import threading
import queue
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

# ── make sure transcribe.py is importable from same folder ──
sys.path.insert(0, str(Path(__file__).parent))


# ─────────────────────────────────────────────────────────────
# THEME  (dark, minimal, clean)
# ─────────────────────────────────────────────────────────────
BG        = "#0f0f12"
BG_CARD   = "#18181f"
BG_INPUT  = "#1e1e28"
FG        = "#e8e8f0"
FG_DIM    = "#6b6b80"
ACCENT    = "#7c6af7"          # violet
ACCENT2   = "#3ecf8e"          # green (success)
RED       = "#f76060"
BORDER    = "#2a2a38"
FONT_MONO = ("Courier New", 10)
FONT_UI   = ("Segoe UI", 10) if sys.platform == "win32" else ("SF Pro Display", 10)
FONT_HEAD = ("Segoe UI", 13, "bold") if sys.platform == "win32" else ("SF Pro Display", 13, "bold")


def styled_btn(parent, text, cmd, accent=False, danger=False):
    bg = ACCENT if accent else (RED if danger else BG_INPUT)
    fg = "#fff" if (accent or danger) else FG
    btn = tk.Button(
        parent, text=text, command=cmd,
        bg=bg, fg=fg, activebackground=ACCENT2 if accent else bg,
        activeforeground="#fff", relief="flat", bd=0,
        font=FONT_UI, padx=14, pady=6, cursor="hand2"
    )
    btn.bind("<Enter>", lambda e: btn.config(bg=ACCENT2 if accent else "#2a2a38"))
    btn.bind("<Leave>", lambda e: btn.config(bg=bg))
    return btn


def sep(parent):
    return tk.Frame(parent, bg=BORDER, height=1)


# ─────────────────────────────────────────────────────────────
# LOG QUEUE  (thread → GUI)
# ─────────────────────────────────────────────────────────────
log_queue: queue.Queue = queue.Queue()


def patch_print():
    """Redirect print() output to log_queue so it appears in the GUI log."""
    import builtins
    _real_print = builtins.print

    def _gui_print(*args, **kwargs):
        msg = " ".join(str(a) for a in args)
        # strip ANSI escape codes
        import re
        msg = re.sub(r'\x1b\[[0-9;]*m', '', msg)
        log_queue.put(("log", msg))
        # also write to real stdout for debugging
        kwargs.pop("end", None)
        kwargs.pop("flush", None)
        _real_print(*args, **kwargs, end="\n", flush=True)

    builtins.print = _gui_print


# ─────────────────────────────────────────────────────────────
# MAIN WINDOW
# ─────────────────────────────────────────────────────────────
class TafrighApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Tafrigh PRO")
        self.configure(bg=BG)
        self.resizable(True, True)
        self.minsize(640, 580)

        # state
        self.source_type   = tk.StringVar(value="file")
        self.input_path    = tk.StringVar()
        self.lang          = tk.StringVar(value="arabic")
        self.model_size    = tk.StringVar(value="small")
        self.use_whisper   = tk.BooleanVar(value=True)
        self.embed_subs    = tk.BooleanVar(value=False)
        self.force_redo    = tk.BooleanVar(value=False)
        self.output_dir    = tk.StringVar(value="./output")
        self.chunk_min     = tk.IntVar(value=10)
        self.running       = False

        self._build_ui()
        self._poll_log()
        patch_print()

    # ── UI CONSTRUCTION ──────────────────────────────────────
    def _build_ui(self):
        # ── Header ───────────────────────────────────────────
        hdr = tk.Frame(self, bg=BG, pady=18)
        hdr.pack(fill="x", padx=28)

        tk.Label(hdr, text="🎙", font=("", 26), bg=BG, fg=ACCENT).pack(side="left", padx=(0,10))
        title_box = tk.Frame(hdr, bg=BG)
        title_box.pack(side="left")
        tk.Label(title_box, text="TAFRIGH PRO", font=FONT_HEAD,
                 bg=BG, fg=FG).pack(anchor="w")
        tk.Label(title_box, text="Audio & Video Transcription",
                 font=(FONT_UI[0], 9), bg=BG, fg=FG_DIM).pack(anchor="w")

        sep(self).pack(fill="x", padx=28)

        # ── Source card ──────────────────────────────────────
        card = self._card(self, "المصدر  /  Source")

        src_row = tk.Frame(card, bg=BG_CARD)
        src_row.pack(fill="x", pady=(0, 10))

        for val, lbl in [("file", "📁  ملف / File"),
                         ("batch","📂  مجلد / Folder"),
                         ("youtube","▶  YouTube")]:
            rb = tk.Radiobutton(
                src_row, text=lbl, variable=self.source_type, value=val,
                bg=BG_CARD, fg=FG, selectcolor=BG_INPUT,
                activebackground=BG_CARD, activeforeground=ACCENT,
                font=FONT_UI, command=self._on_src_change
            )
            rb.pack(side="left", padx=(0,18))

        path_row = tk.Frame(card, bg=BG_CARD)
        path_row.pack(fill="x")
        self._path_entry = tk.Entry(
            path_row, textvariable=self.input_path,
            bg=BG_INPUT, fg=FG, insertbackground=FG,
            relief="flat", font=FONT_UI, bd=6
        )
        self._path_entry.pack(side="left", fill="x", expand=True)
        self._browse_btn = styled_btn(path_row, "Browse", self._browse)
        self._browse_btn.pack(side="left", padx=(8,0))

        # ── Settings card ────────────────────────────────────
        cfg = self._card(self, "الإعدادات  /  Settings")

        row1 = tk.Frame(cfg, bg=BG_CARD)
        row1.pack(fill="x", pady=(0,10))

        self._labeled_option(row1, "اللغة / Language", self.lang,
            ["arabic","english","french","darija"])
        self._labeled_option(row1, "النموذج / Model", self.model_size,
            ["tiny","base","small","medium","large","large-v2"])
        self._labeled_option(row1, "Chunk (min)", self.chunk_min,
            [5, 10, 15, 20], width=5)

        row2 = tk.Frame(cfg, bg=BG_CARD)
        row2.pack(fill="x")

        for var, lbl in [(self.use_whisper, "⚡ Whisper (local)"),
                         (self.embed_subs,  "🎬 Embed subtitles"),
                         (self.force_redo,  "🔁 Force redo")]:
            tk.Checkbutton(
                row2, text=lbl, variable=var,
                bg=BG_CARD, fg=FG, selectcolor=BG_INPUT,
                activebackground=BG_CARD, activeforeground=ACCENT,
                font=FONT_UI
            ).pack(side="left", padx=(0, 20))

        # Output dir row
        out_row = tk.Frame(cfg, bg=BG_CARD)
        out_row.pack(fill="x", pady=(10, 0))
        tk.Label(out_row, text="Output folder:", bg=BG_CARD,
                 fg=FG_DIM, font=FONT_UI).pack(side="left")
        tk.Entry(out_row, textvariable=self.output_dir,
                 bg=BG_INPUT, fg=FG, insertbackground=FG,
                 relief="flat", font=FONT_UI, bd=6, width=28).pack(side="left", padx=8)
        styled_btn(out_row, "Browse", self._browse_out).pack(side="left")

        # ── Progress ─────────────────────────────────────────
        prog_card = self._card(self, "التقدم  /  Progress")
        self.progress_var = tk.DoubleVar(value=0)
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("T.Horizontal.TProgressbar",
                        troughcolor=BG_INPUT, background=ACCENT,
                        bordercolor=BG_CARD, lightcolor=ACCENT,
                        darkcolor=ACCENT, thickness=14)
        self.progress_bar = ttk.Progressbar(
            prog_card, variable=self.progress_var,
            maximum=100, style="T.Horizontal.TProgressbar"
        )
        self.progress_bar.pack(fill="x", pady=(0, 6))
        self.status_lbl = tk.Label(
            prog_card, text="جاهز  /  Ready",
            bg=BG_CARD, fg=FG_DIM, font=FONT_UI, anchor="w"
        )
        self.status_lbl.pack(fill="x")

        # ── Log ──────────────────────────────────────────────
        log_card = self._card(self, "السجل  /  Log", expand=True)
        self.log_text = tk.Text(
            log_card, bg=BG_INPUT, fg=FG_DIM, font=FONT_MONO,
            relief="flat", state="disabled", height=9,
            insertbackground=FG, wrap="word", bd=0
        )
        scrollbar = tk.Scrollbar(log_card, command=self.log_text.yview,
                                  bg=BG_INPUT, troughcolor=BG_INPUT)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.log_text.pack(fill="both", expand=True)

        # ── Action buttons ───────────────────────────────────
        btn_row = tk.Frame(self, bg=BG, pady=16)
        btn_row.pack(fill="x", padx=28)

        self.start_btn = styled_btn(btn_row, "▶  START TRANSCRIPTION",
                                     self._start, accent=True)
        self.start_btn.pack(side="left")

        self.stop_btn = styled_btn(btn_row, "■  Stop", self._stop, danger=True)
        self.stop_btn.pack(side="left", padx=(10, 0))
        self.stop_btn.config(state="disabled")

        styled_btn(btn_row, "Clear Log", self._clear_log).pack(side="right")

    # ── HELPERS ──────────────────────────────────────────────
    def _card(self, parent, title="", expand=False):
        outer = tk.Frame(parent, bg=BG, padx=28, pady=0)
        outer.pack(fill="both", expand=expand, pady=(12, 0))
        if title:
            tk.Label(outer, text=title, bg=BG, fg=FG_DIM,
                     font=(FONT_UI[0], 9)).pack(anchor="w", pady=(0,4))
        inner = tk.Frame(outer, bg=BG_CARD, padx=16, pady=12)
        inner.pack(fill="both", expand=expand)
        return inner

    def _labeled_option(self, parent, label, var, choices, width=10):
        box = tk.Frame(parent, bg=BG_CARD)
        box.pack(side="left", padx=(0, 20))
        tk.Label(box, text=label, bg=BG_CARD, fg=FG_DIM,
                 font=(FONT_UI[0], 9)).pack(anchor="w")
        om = tk.OptionMenu(box, var, *choices)
        om.config(bg=BG_INPUT, fg=FG, activebackground=ACCENT,
                  activeforeground="#fff", relief="flat",
                  font=FONT_UI, width=width, bd=0,
                  highlightthickness=0)
        om["menu"].config(bg=BG_INPUT, fg=FG, activebackground=ACCENT,
                          activeforeground="#fff", relief="flat", bd=0)
        om.pack(anchor="w")

    def _on_src_change(self):
        src = self.source_type.get()
        self.input_path.set("")
        if src == "youtube":
            self._path_entry.config(state="normal")
            self._browse_btn.config(state="disabled")
            self._path_entry.insert(0, "https://youtube.com/watch?v=...")
        else:
            self._path_entry.config(state="normal")
            self._browse_btn.config(state="normal")

    def _browse(self):
        src = self.source_type.get()
        if src == "batch":
            p = filedialog.askdirectory(title="اختر مجلد الفيديوهات")
        else:
            p = filedialog.askopenfilename(
                title="اختر الملف",
                filetypes=[
                    ("Media files", "*.mp4 *.mkv *.avi *.mov *.webm *.mp3 *.wav *.m4a *.ogg *.flac"),
                    ("All files", "*.*")
                ]
            )
        if p:
            self.input_path.set(p)

    def _browse_out(self):
        p = filedialog.askdirectory(title="مجلد الإخراج")
        if p:
            self.output_dir.set(p)

    # ── LOG ──────────────────────────────────────────────────
    def _log(self, msg, tag=None):
        self.log_text.config(state="normal")
        self.log_text.insert("end", msg + "\n", tag or "")
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def _clear_log(self):
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.config(state="disabled")

    # tag colours
    def _setup_tags(self):
        self.log_text.tag_config("ok",   foreground=ACCENT2)
        self.log_text.tag_config("warn", foreground="#f0b860")
        self.log_text.tag_config("err",  foreground=RED)
        self.log_text.tag_config("info", foreground=FG_DIM)

    # ── POLL QUEUE  (runs every 80ms in main thread) ─────────
    def _poll_log(self):
        try:
            while True:
                kind, msg = log_queue.get_nowait()
                if kind == "log":
                    tag = ("ok"   if any(c in msg for c in ["✓","v  ","OK","ok"]) else
                           "err"  if any(c in msg for c in ["✗","x  ","ERROR","فشل"]) else
                           "warn" if any(c in msg for c in ["⚠","! ","warn","تحذير"]) else
                           "info")
                    self._log(msg.strip(), tag)
                elif kind == "progress":
                    self.progress_var.set(msg)
                elif kind == "status":
                    self.status_lbl.config(text=msg)
                elif kind == "done":
                    self._on_done(msg)
                elif kind == "error":
                    self._on_error(msg)
        except queue.Empty:
            pass
        self.after(80, self._poll_log)

    # ── RUN ──────────────────────────────────────────────────
    def _start(self):
        inp = self.input_path.get().strip()
        if not inp:
            messagebox.showwarning("تنبيه", "اختر ملف أو أدخل رابط YouTube أولاً")
            return

        self.running = True
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.progress_var.set(0)
        self._clear_log()
        log_queue.put(("status", "جاري التفريغ...  /  Processing..."))

        args = {
            "source_type":  self.source_type.get(),
            "input_path":   inp,
            "lang":         self.lang.get(),
            "model_size":   self.model_size.get(),
            "use_whisper":  self.use_whisper.get(),
            "embed":        self.embed_subs.get(),
            "force":        self.force_redo.get(),
            "output_dir":   self.output_dir.get(),
            "chunk":        self.chunk_min.get(),
        }
        self._worker_thread = threading.Thread(
            target=self._worker, args=(args,), daemon=True
        )
        self._worker_thread.start()

    def _stop(self):
        self.running = False
        log_queue.put(("status", "إيقاف...  /  Stopping..."))
        log_queue.put(("log", "⚠  تم طلب الإيقاف. ينتهي الجزء الحالي أولاً."))

    def _worker(self, args):
        """Runs in background thread — imports and calls the engine."""
        try:
            # lazy import so GUI opens instantly
            import transcribe as engine

            engine.load_env()
            engine.check_deps(args["use_whisper"])

            # build file list
            src  = args["source_type"]
            inp  = args["input_path"]
            odir = args["output_dir"]
            Path(odir).mkdir(parents=True, exist_ok=True)

            if src == "youtube":
                files = [engine.download_youtube(inp, odir)]
            elif src == "batch":
                import glob
                files = []
                for ext in list(engine.VIDEO_EXTS | engine.AUDIO_EXTS):
                    files += glob.glob(str(Path(inp) / f"*{ext}"))
                if not files:
                    log_queue.put(("error", "لم تُوجد ملفات فـ هذا المجلد"))
                    return
            else:
                if not Path(inp).exists():
                    log_queue.put(("error", f"الملف غير موجود: {inp}"))
                    return
                files = [inp]

            lang = args["lang"]
            eng  = engine.build_engine(
                args["use_whisper"], args["model_size"], "auto", lang
            )

            total = len(files)
            for i, f in enumerate(files):
                if not self.running:
                    break
                file_lang = lang if lang != "auto" else engine.detect_language(f)
                log_queue.put(("status",
                    f"[{i+1}/{total}] {Path(f).name}"))
                engine.process_one(
                    f, file_lang, eng, odir,
                    chunk_minutes=args["chunk"],
                    workers=engine._auto_workers(),
                    embed=args["embed"],
                    force=args["force"]
                )
                log_queue.put(("progress", int(100 * (i+1) / total)))

            log_queue.put(("done", odir))

        except Exception as exc:
            import traceback
            log_queue.put(("error", traceback.format_exc()))

    def _on_done(self, odir):
        self.running = False
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.progress_var.set(100)
        log_queue.put(("status", f"✅  انتهى!  الملفات في: {odir}"))
        self._log(f"\n✅  انتهى التفريغ!  الملفات في: {odir}", "ok")
        messagebox.showinfo("تم ✅", f"انتهى التفريغ!\n\nالملفات في:\n{odir}")

    def _on_error(self, msg):
        self.running = False
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self._log(f"\n✗  خطأ:\n{msg}", "err")
        log_queue.put(("status", "خطأ  /  Error"))
        messagebox.showerror("خطأ", "وقع خطأ، شوف السجل للتفاصيل.")


# ─────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────
def main():
    app = TafrighApp()
    app._setup_tags()

    # center on screen
    app.update_idletasks()
    w, h = 700, 660
    sw   = app.winfo_screenwidth()
    sh   = app.winfo_screenheight()
    app.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

    app.mainloop()


if __name__ == "__main__":
    main()
