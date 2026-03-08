# -*- mode: python ; coding: utf-8 -*-
# ─────────────────────────────────────────────────────────
#  tafrigh.spec  —  PyInstaller build spec
#  Produces:  dist/TafrighPRO/TafrighPRO.exe  (folder mode)
#  Run:       pyinstaller tafrigh.spec
# ─────────────────────────────────────────────────────────

import sys
import os
from pathlib import Path

ROOT = Path(SPECPATH)          # folder where this .spec lives

# ── collect faster-whisper / whisper assets ───────────────
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

datas = []
datas += collect_data_files("faster_whisper")   # VAD model, assets
datas += collect_data_files("whisper")          # fallback assets

# ── bundle ffmpeg & yt-dlp binaries ──────────────────────
#    Put ffmpeg.exe and yt-dlp.exe next to this .spec file,
#    or adjust the paths below.
BIN_DIR = ROOT / "bin"          # bin/ffmpeg.exe  bin/yt-dlp.exe

if sys.platform == "win32":
    extra_bins = [
        (str(BIN_DIR / "ffmpeg.exe"),  "."),
        (str(BIN_DIR / "yt-dlp.exe"), "."),
    ]
else:
    extra_bins = [
        (str(BIN_DIR / "ffmpeg"),  "."),
        (str(BIN_DIR / "yt-dlp"), "."),
    ]

# only include binaries that actually exist
binaries = [(src, dst) for src, dst in extra_bins if Path(src).exists()]

# ── optional: bundle whisper model cache ─────────────────
#    Pre-download once with:
#    python -c "import faster_whisper; faster_whisper.WhisperModel('small')"
#    Then the cache lands in ~/.cache/huggingface/hub/
#    Adjust WHISPER_CACHE below if needed.
import os, shutil

WHISPER_CACHE = Path.home() / ".cache" / "huggingface" / "hub"
if WHISPER_CACHE.exists():
    for model_dir in WHISPER_CACHE.glob("models--Systran--faster-whisper-*"):
        datas.append((str(model_dir), f"whisper_cache/{model_dir.name}"))

# ─────────────────────────────────────────────────────────
a = Analysis(
    ["tafrigh_gui.py"],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=[
        # faster-whisper / ctranslate2
        "ctranslate2",
        "faster_whisper",
        "faster_whisper.audio",
        "faster_whisper.transcribe",
        # openai-whisper fallback
        "whisper",
        "whisper.audio",
        "whisper.model",
        # audio / ffmpeg
        "pydub",
        "pydub.audio_segment",
        "ffmpeg",
        # torch (minimal)
        "torch",
        "torchaudio",
        # tafrigh engine
        "transcribe",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # drop heavy unused stuff
        "matplotlib", "notebook", "IPython",
        "pandas", "scipy", "sklearn",
        "cv2", "PIL",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,       # folder mode (faster startup)
    name="TafrighPRO",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,               # no terminal window
    icon=str(ROOT / "icon.ico") if (ROOT / "icon.ico").exists() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="TafrighPRO",
)
