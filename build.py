#!/usr/bin/env python3
"""
build.py  —  One-command portable build for Tafrigh PRO
────────────────────────────────────────────────────────
Usage:
    python build.py               # full build
    python build.py --skip-deps   # skip downloading ffmpeg/yt-dlp
    python build.py --model small # pre-bundle a whisper model

What it does:
    1. Installs required Python packages
    2. Downloads ffmpeg + yt-dlp into ./bin/
    3. (Optional) pre-downloads Whisper model
    4. Runs PyInstaller → dist/TafrighPRO/
"""

import sys
import os
import subprocess
import argparse
import platform
import urllib.request
import zipfile
import shutil
from pathlib import Path

ROOT    = Path(__file__).parent
BIN_DIR = ROOT / "bin"

# ─────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────
def run(cmd: list, **kw):
    print(f"\n  $ {' '.join(str(c) for c in cmd)}")
    result = subprocess.run(cmd, **kw)
    if result.returncode != 0:
        print(f"  ✗  command failed (exit {result.returncode})")
        sys.exit(result.returncode)

def download(url: str, dest: Path):
    print(f"  ↓  {url}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url) as r, open(dest, "wb") as f:
        total = int(r.headers.get("Content-Length", 0))
        done  = 0
        chunk = 1024 * 256
        while True:
            data = r.read(chunk)
            if not data:
                break
            f.write(data)
            done += len(data)
            if total:
                pct = int(50 * done / total)
                print(f"\r  [{'█'*pct}{'░'*(50-pct)}] {done//1024}KB", end="", flush=True)
    print()

# ─────────────────────────────────────────────────────────
# STEP 1 — Python packages
# ─────────────────────────────────────────────────────────
def install_packages():
    print("\n[1/4]  Installing Python packages...")
    pkgs = [
        "faster-whisper",
        "openai-whisper",      # fallback
        "ffmpeg-python",
        "pydub",
        "yt-dlp",
        "pyinstaller",
    ]
    run([sys.executable, "-m", "pip", "install", "--upgrade"] + pkgs)

# ─────────────────────────────────────────────────────────
# STEP 2 — Download ffmpeg + yt-dlp binaries
# ─────────────────────────────────────────────────────────
FFMPEG_WIN  = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
YTDLP_WIN   = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"
YTDLP_LINUX = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp"
YTDLP_MAC   = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp_macos"


def download_binaries():
    print("\n[2/4]  Downloading ffmpeg + yt-dlp binaries...")
    BIN_DIR.mkdir(exist_ok=True)
    system = platform.system()

    # ── ffmpeg ────────────────────────────────────────────
    ffmpeg_bin = BIN_DIR / ("ffmpeg.exe" if system == "Windows" else "ffmpeg")
    if ffmpeg_bin.exists():
        print(f"  ✓  ffmpeg already in {ffmpeg_bin}")
    else:
        if system == "Windows":
            zip_path = BIN_DIR / "ffmpeg.zip"
            download(FFMPEG_WIN, zip_path)
            print("  Extracting ffmpeg...")
            with zipfile.ZipFile(zip_path) as zf:
                for member in zf.namelist():
                    if member.endswith("ffmpeg.exe"):
                        data = zf.read(member)
                        ffmpeg_bin.write_bytes(data)
                        break
            zip_path.unlink()
        elif system == "Darwin":
            print("  macOS: install ffmpeg via Homebrew:  brew install ffmpeg")
            print("         then copy the binary to ./bin/ffmpeg")
        else:
            print("  Linux: install ffmpeg via apt:  sudo apt install ffmpeg")
            print("         then copy the binary to ./bin/ffmpeg")

    # ── yt-dlp ────────────────────────────────────────────
    ytdlp_bin = BIN_DIR / ("yt-dlp.exe" if system == "Windows" else "yt-dlp")
    if ytdlp_bin.exists():
        print(f"  ✓  yt-dlp already in {ytdlp_bin}")
    else:
        url = {"Windows": YTDLP_WIN,
               "Darwin":  YTDLP_MAC}.get(system, YTDLP_LINUX)
        download(url, ytdlp_bin)
        if system != "Windows":
            ytdlp_bin.chmod(0o755)

    print("  ✓  binaries ready")

# ─────────────────────────────────────────────────────────
# STEP 3 — Pre-download Whisper model
# ─────────────────────────────────────────────────────────
def download_model(model_size: str):
    print(f"\n[3/4]  Pre-downloading Whisper model '{model_size}'...")
    script = f"""
from faster_whisper import WhisperModel
print("  downloading {model_size}...")
WhisperModel("{model_size}", device="cpu", compute_type="int8")
print("  model cached OK")
"""
    run([sys.executable, "-c", script])

# ─────────────────────────────────────────────────────────
# STEP 4 — PyInstaller
# ─────────────────────────────────────────────────────────
def build_exe():
    print("\n[4/4]  Building executable with PyInstaller...")
    spec = ROOT / "tafrigh.spec"
    if not spec.exists():
        print(f"  ✗  tafrigh.spec not found at {spec}")
        sys.exit(1)

    # clean previous build
    for d in ["build", str(ROOT / "dist" / "TafrighPRO")]:
        if Path(d).exists():
            shutil.rmtree(d)
            print(f"  cleaned {d}")

    run(["pyinstaller", "--noconfirm", str(spec)])

    dist = ROOT / "dist" / "TafrighPRO"
    if dist.exists():
        print(f"""
  ╔══════════════════════════════════════════════╗
  ║  ✅  Build successful!                        ║
  ║  📁  dist/TafrighPRO/                        ║
  ║      TafrighPRO.exe  ← share this folder     ║
  ╚══════════════════════════════════════════════╝
""")
    else:
        print("  ✗  Build failed — dist/TafrighPRO not found")
        sys.exit(1)

# ─────────────────────────────────────────────────────────
# STARTUP CHECK  (injected into GUI at runtime)
# ─────────────────────────────────────────────────────────
STARTUP_CHECK = '''
# auto-generated by build.py — injected PATH fix for portable mode
import sys, os
from pathlib import Path

def _fix_portable_path():
    """Add bundled bin/ to PATH so ffmpeg & yt-dlp are found."""
    # when running as PyInstaller bundle
    if getattr(sys, "_MEIPASS", None):
        bundle = Path(sys._MEIPASS)
    else:
        bundle = Path(__file__).parent

    bin_dir = bundle
    os.environ["PATH"] = str(bin_dir) + os.pathsep + os.environ.get("PATH", "")

    # also fix whisper model cache location
    cache = bundle / "whisper_cache"
    if cache.exists():
        os.environ["HF_HOME"] = str(bundle)

_fix_portable_path()
'''

def inject_startup_check():
    """Prepend PATH fix to tafrigh_gui.py if not already there."""
    gui = ROOT / "tafrigh_gui.py"
    content = gui.read_text(encoding="utf-8")
    marker = "# auto-generated by build.py"
    if marker not in content:
        gui.write_text(STARTUP_CHECK + "\n" + content, encoding="utf-8")
        print("  ✓  injected portable PATH fix into tafrigh_gui.py")
    else:
        print("  ✓  PATH fix already present")

# ─────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Build Tafrigh PRO portable .exe")
    parser.add_argument("--skip-deps",  action="store_true",
                        help="skip pip install step")
    parser.add_argument("--skip-bins",  action="store_true",
                        help="skip downloading ffmpeg/yt-dlp")
    parser.add_argument("--model",      default="small",
                        choices=["tiny","base","small","medium","large"],
                        help="Whisper model to pre-bundle (default: small)")
    parser.add_argument("--no-model",   action="store_true",
                        help="skip pre-downloading Whisper model")
    args = parser.parse_args()

    print("""
  ╔══════════════════════════════════════════════╗
  ║   🎙️  Tafrigh PRO  —  Portable Build         ║
  ╚══════════════════════════════════════════════╝""")

    if not args.skip_deps:
        install_packages()

    if not args.skip_bins:
        download_binaries()

    if not args.no_model:
        download_model(args.model)

    inject_startup_check()
    build_exe()


if __name__ == "__main__":
    main()
