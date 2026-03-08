#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════╗
║        🎙️  TAFRIGH PRO v2 - Audio Transcriber            ║
║        Whisper + Parallel + Subtitle Embedding           ║
╚══════════════════════════════════════════════════════════╝
"""

import os
import sys
import argparse
import time
import glob
import shutil
import threading
from pathlib import Path
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

# ──────────────────────────────────────────────────────────
# COLORS & STYLING
# ──────────────────────────────────────────────────────────
class Color:
    RESET   = "\033[0m";  BOLD    = "\033[1m";  DIM     = "\033[2m"
    GREEN   = "\033[92m"; YELLOW  = "\033[93m"; BLUE    = "\033[94m"
    CYAN    = "\033[96m"; RED     = "\033[91m"; MAGENTA = "\033[95m"

def banner():
    print(f"""\
{Color.CYAN}{Color.BOLD}
 ████████╗ █████╗ ███████╗██████╗ ██╗ ██████╗ ██╗  ██╗
    ██╔══╝██╔══██╗██╔════╝██╔══██╗██║██╔════╝ ██║  ██║
    ██║   ███████║█████╗  ██████╔╝██║██║  ███╗███████║
    ██║   ██╔══██║██╔══╝  ██╔══██╗██║██║   ██║██╔══██║
    ██║   ██║  ██║██║     ██║  ██║██║╚██████╔╝██║  ██║
    ╚═╝   ╚═╝  ╚═╝╚═╝     ╚═╝  ╚═╝╚═╝ ╚═════╝ ╚═╝  ╚═╝
{Color.RESET}{Color.YELLOW}      🎙️  Tafrigh PRO v2  ·  Whisper + GPU + Parallel  🎙️
{Color.DIM}             engine-agnostic · no limits · offline{Color.RESET}
""")

_print_lock = threading.Lock()

def info(msg):
    with _print_lock: print(f"  {Color.BLUE}i{Color.RESET}  {msg}")
def success(msg):
    with _print_lock: print(f"  {Color.GREEN}v{Color.RESET}  {Color.GREEN}{msg}{Color.RESET}")
def warn(msg):
    with _print_lock: print(f"  {Color.YELLOW}!{Color.RESET}  {Color.YELLOW}{msg}{Color.RESET}")
def error(msg):
    with _print_lock: print(f"  {Color.RED}x{Color.RESET}  {Color.RED}{msg}{Color.RESET}")
def step(n, msg):
    with _print_lock: print(f"\n{Color.MAGENTA}{Color.BOLD}[{n}]{Color.RESET} {Color.BOLD}{msg}{Color.RESET}")

# ──────────────────────────────────────────────────────────
# PROGRESS TRACKER  (thread-safe)
# ──────────────────────────────────────────────────────────
class Progress:
    def __init__(self, total: int, label: str = "", width: int = 38):
        self.total   = total
        self.current = 0
        self.label   = label
        self.width   = width
        self._lock   = threading.Lock()

    def update(self, n: int = 1, label: str = ""):
        with self._lock:
            self.current = min(self.current + n, self.total)
            if label:
                self.label = label
            self._draw()

    def _draw(self):
        filled = int(self.width * self.current / self.total) if self.total else 0
        bar    = "#" * filled + "-" * (self.width - filled)
        pct    = int(100 * self.current / self.total) if self.total else 0
        end    = "\n" if self.current >= self.total else ""
        print(
            f"\r  {Color.CYAN}[{bar}]{Color.RESET} {pct:3d}%  {Color.DIM}{self.label}{Color.RESET}",
            end=end, flush=True
        )

# ──────────────────────────────────────────────────────────
# ENV LOADING
# ──────────────────────────────────────────────────────────
def load_env():
    env_path = Path(".env")
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    os.environ.setdefault(k.strip(), v.strip())

def get_api_key(lang: str) -> Optional[str]:
    mapping = {
        "arabic":  ["WIT_API_KEY_ARABIC",  "WIT_AR"],
        "english": ["WIT_API_KEY_ENGLISH", "WIT_EN"],
        "french":  ["WIT_API_KEY_FRENCH",  "WIT_FR"],
        "darija":  ["WIT_API_KEY_DARIJA",  "WIT_DA"],
    }
    for var in mapping.get(lang.lower(), [f"WIT_API_KEY_{lang.upper()}"]):
        val = os.environ.get(var)
        if val:
            return val
    return None

# ──────────────────────────────────────────────────────────
# ENGINE ABSTRACTION  <-- swap only this section to change backend
# ──────────────────────────────────────────────────────────
class WhisperEngine:
    """
    faster-whisper backend  (2x-4x faster than openai-whisper, less RAM).
    Install: pip install faster-whisper
    GPU:     pip install torch --index-url https://download.pytorch.org/whl/cu118

    Falls back to openai-whisper if faster-whisper not installed.
    """
    LANG_MAP = {
        "arabic": "ar", "english": "en",
        "french": "fr", "darija":  "ar",
    }

    def __init__(self, model_size: str = "medium", device: str = "auto"):
        # detect device
        try:
            import torch
            _device = "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            _device = "cpu"
        if device != "auto":
            _device = device
        self.device = _device

        # prefer faster-whisper, fallback to openai-whisper
        try:
            from faster_whisper import WhisperModel
            compute = "float16" if _device == "cuda" else "int8"
            info(f"faster-whisper  model={model_size}  device={Color.GREEN}{_device}{Color.RESET}  compute={compute}")
            self._model      = WhisperModel(model_size, device=_device, compute_type=compute)
            self._use_faster = True
        except ImportError:
            import whisper
            warn("faster-whisper غير موجود، استعمال openai-whisper  (pip install faster-whisper للسرعة)")
            info(f"openai-whisper  model={model_size}  device={Color.GREEN}{_device}{Color.RESET}")
            self._model      = whisper.load_model(model_size, device=_device)
            self._use_faster = False

    def transcribe(self, wav_path: str, lang: str) -> dict:
        whisper_lang = self.LANG_MAP.get(lang.lower(), lang[:2])

        if self._use_faster:
            # faster-whisper returns a generator of Segment objects
            # vad_filter=True skips silence -> fewer segments -> faster transcription
            segments_gen, _ = self._model.transcribe(
                wav_path, language=whisper_lang, beam_size=3,
                vad_filter=True,
                condition_on_previous_text=False
            )
            segments = []
            full_text = []
            for seg in segments_gen:
                segments.append({"start": seg.start, "end": seg.end, "text": seg.text})
                full_text.append(seg.text.strip())
            return {"text": " ".join(full_text), "segments": segments}
        else:
            # openai-whisper returns a dict directly
            return self._model.transcribe(wav_path, language=whisper_lang, verbose=False)


class WitEngine:
    """
    Cloud Wit.ai transcription (needs API key + internet).
    Fallback engine -- use WhisperEngine for production.
    """
    def __init__(self, api_key: str):
        self.api_key = api_key

    def transcribe(self, wav_path: str, lang: str) -> dict:
        from tafrigh import Config, farrigh
        from tafrigh.config import TranscriberConfig
        config = Config(
            urls_or_paths=[wav_path],
            wit_client_access_tokens=[self.api_key],
            transcriber_config=TranscriberConfig(use_wit=True),
            output_formats=["txt", "srt"],
            output_dir=str(Path(wav_path).parent),
            verbose=False,
        )
        list(farrigh(config))
        txt_file = Path(wav_path).with_suffix(".txt")
        text = txt_file.read_text(encoding="utf-8") if txt_file.exists() else ""
        return {"text": text, "segments": []}  # SRT already written by tafrigh


def build_engine(use_whisper: bool, whisper_model: str,
                 whisper_device: str, lang: str):
    if use_whisper:
        return WhisperEngine(model_size=whisper_model, device=whisper_device)
    api_key = get_api_key(lang)
    if not api_key:
        error(f"مفتاح Wit.ai لـ {lang} غير موجود. استعمل --whisper أو أضفه لـ .env")
        sys.exit(1)
    return WitEngine(api_key)

# ──────────────────────────────────────────────────────────
# OUTPUT FORMATTERS
# ──────────────────────────────────────────────────────────
def segments_to_srt(segments: list, offset: float = 0.0) -> str:
    def fmt(t: float) -> str:
        t  += offset
        ms  = int((t % 1) * 1000)
        t   = int(t)
        h, r = divmod(t, 3600)
        m, s = divmod(r, 60)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    lines = []
    for i, seg in enumerate(segments, 1):
        lines.append(str(i))
        lines.append(f"{fmt(seg['start'])} --> {fmt(seg['end'])}")
        lines.append(seg["text"].strip())
        lines.append("")
    return "\n".join(lines)


def shift_srt(srt_content: str, offset_sec: float) -> str:
    import re

    def shift(match):
        def to_s(h, m, s, ms):
            return int(h)*3600 + int(m)*60 + int(s) + int(ms)/1000
        def from_s(t):
            ms = int((t % 1)*1000); t = int(t)
            h, r = divmod(t, 3600); m, s = divmod(r, 60)
            return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
        s = to_s(*match.group(1,2,3,4)) + offset_sec
        e = to_s(*match.group(5,6,7,8)) + offset_sec
        return f"{from_s(s)} --> {from_s(e)}"

    return re.sub(
        r'(\d+):(\d+):(\d+),(\d+) --> (\d+):(\d+):(\d+),(\d+)',
        shift, srt_content
    )

# ──────────────────────────────────────────────────────────
# AUDIO CONVERSION
# ──────────────────────────────────────────────────────────
def to_wav(input_path: str, output_path: str) -> str:
    import ffmpeg as ff
    info(f"تحويل -> WAV  ({Path(input_path).suffix})")
    (
        ff.input(input_path)
          .output(output_path, ar=16000, ac=1, acodec="pcm_s16le")
          .overwrite_output()
          .run(quiet=True)
    )
    success(f"تم التحويل: {Path(output_path).name}")
    return output_path

# ──────────────────────────────────────────────────────────
# CHUNK SPLITTER
# ──────────────────────────────────────────────────────────
def split_audio(wav_path: str, chunk_minutes: int = 10) -> list:
    from pydub import AudioSegment
    audio    = AudioSegment.from_wav(wav_path)
    duration = len(audio) / 1000
    chunk_ms = chunk_minutes * 60 * 1000

    if duration <= chunk_minutes * 60:
        return [wav_path]

    info(f"المدة: {duration/60:.1f} دقيقة -> تقسيم الى اجزاء من {chunk_minutes} دقيقة")
    base    = Path(wav_path).stem
    out_dir = Path(wav_path).parent / f"{base}_chunks"
    out_dir.mkdir(exist_ok=True)

    chunks = []
    total  = (len(audio) + chunk_ms - 1) // chunk_ms
    prog   = Progress(total, "تقسيم")

    for i, start in enumerate(range(0, len(audio), chunk_ms)):
        chunk_path = str(out_dir / f"{base}_part{i+1:03d}.wav")
        audio[start:start + chunk_ms].export(chunk_path, format="wav")
        chunks.append(chunk_path)
        prog.update(1, f"part {i+1}/{total}")

    success(f"تقسيم OK  ({len(chunks)} جزء)")
    return chunks

# ──────────────────────────────────────────────────────────
# PARALLEL TRANSCRIPTION
# ──────────────────────────────────────────────────────────
def _transcribe_chunk(job):
    """Worker: (index, chunk_path, engine, lang, offset) -> (index, txt, srt_block)"""
    idx, chunk_path, engine, lang, offset = job
    try:
        result = engine.transcribe(chunk_path, lang)
    except Exception as e:
        return idx, "", f"# ERROR chunk {idx}: {e}\n"

    if result.get("segments"):
        srt_block = segments_to_srt(result["segments"], offset=offset)
        txt_block = result.get("text", "").strip()
    else:
        txt_file  = Path(chunk_path).with_suffix(".txt")
        srt_file  = Path(chunk_path).with_suffix(".srt")
        txt_block = txt_file.read_text(encoding="utf-8") if txt_file.exists() else ""
        srt_raw   = srt_file.read_text(encoding="utf-8") if srt_file.exists() else ""
        srt_block = shift_srt(srt_raw, offset)

    return idx, txt_block, srt_block


def transcribe_parallel(chunks: list, engine, lang: str,
                        output_base: str, max_workers: int = 4) -> tuple:
    """Transcribe chunks in parallel, merge in correct order."""
    from pydub import AudioSegment

    offsets, acc = [], 0.0
    for c in chunks:
        offsets.append(acc)
        acc += len(AudioSegment.from_wav(c)) / 1000.0

    jobs    = [(i, c, engine, lang, offsets[i]) for i, c in enumerate(chunks)]
    results = {}
    prog    = Progress(len(chunks), "تفريغ متوازي")

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_transcribe_chunk, j): j[0] for j in jobs}
        for fut in as_completed(futures):
            idx, txt_block, srt_block = fut.result()
            results[idx] = (txt_block, srt_block)
            prog.update(1, f"chunk {idx+1}/{len(chunks)}")

    all_txt = [results[i][0] for i in range(len(chunks))]
    all_srt = [results[i][1] for i in range(len(chunks))]

    txt_path = output_base + ".txt"
    srt_path = output_base + ".srt"
    Path(txt_path).write_text("\n\n".join(all_txt), encoding="utf-8")
    Path(srt_path).write_text("\n\n".join(all_srt), encoding="utf-8")

    return txt_path, srt_path

# ──────────────────────────────────────────────────────────
# SUBTITLE EMBEDDING
# ──────────────────────────────────────────────────────────
def embed_subtitles(video_path: str, srt_path: str, output_path: str) -> str:
    """Burn SRT subtitles into video via ffmpeg subtitles filter."""
    import ffmpeg as ff
    info("تضمين Subtitles في الفيديو...")
    srt_abs = str(Path(srt_path).resolve()).replace("\\", "/").replace(":", "\\:")

    try:
        (
            ff.input(video_path)
              .output(output_path,
                      vf=f"subtitles='{srt_abs}'",
                      acodec="copy")
              .overwrite_output()
              .run(quiet=True)
        )
        success(f"فيديو مع subtitles: {Path(output_path).name}")
        return output_path
    except Exception as e:
        warn(f"فشل تضمين subtitles: {e}")
        warn("تأكد أن ffmpeg مبني مع libass  (sudo apt install libass-dev)")
        return ""

# ──────────────────────────────────────────────────────────
# DEPENDENCY CHECKS
# ──────────────────────────────────────────────────────────
def check_deps(use_whisper: bool):
    step("0", "فحص التبعيات...")
    missing = []

    if use_whisper:
        # faster-whisper preferred, openai-whisper as fallback
        has_faster = False
        try:
            from faster_whisper import WhisperModel
            success("faster-whisper OK")
            has_faster = True
        except ImportError:
            warn("faster-whisper غير موجود (اختياري لكن موصى):  pip install faster-whisper")
        if not has_faster:
            try:
                import whisper; success("openai-whisper OK (fallback)")
            except ImportError:
                missing.append("faster-whisper  # أو: openai-whisper")
        try:
            import torch
            cuda = torch.cuda.is_available()
            success(f"torch OK  (CUDA={'yes - GPU mode' if cuda else 'no - CPU mode'})")
        except ImportError:
            missing.append("torch")
    else:
        try:
            import tafrigh; success("tafrigh OK")
        except ImportError:
            missing.append("tafrigh[wit]")

    for pkg in ["pydub", "ffmpeg"]:
        try:
            __import__(pkg); success(f"{pkg} OK")
        except ImportError:
            missing.append("ffmpeg-python" if pkg == "ffmpeg" else pkg)

    if missing:
        error("المكتبات الناقصة:  pip install " + "  ".join(missing))
        sys.exit(1)

    if not shutil.which("ffmpeg"):
        error("ffmpeg binary غير موجود!  sudo apt install ffmpeg")
        sys.exit(1)
    success("ffmpeg binary OK")

# ──────────────────────────────────────────────────────────
# LANGUAGE DETECTION
# ──────────────────────────────────────────────────────────
def detect_language(filename: str) -> str:
    name = filename.lower()
    if any(k in name for k in ["arab", "ar_", "_ar", "درس", "محاضرة"]): return "arabic"
    if any(k in name for k in ["eng",  "en_", "_en"]):                   return "english"
    if any(k in name for k in ["fr_",  "_fr", "cours", "lecon"]):        return "french"
    return "arabic"

# ──────────────────────────────────────────────────────────
# YOUTUBE DOWNLOAD
# ──────────────────────────────────────────────────────────
def download_youtube(url: str, output_dir: str = ".") -> str:
    if not shutil.which("yt-dlp"):
        error("yt-dlp غير موجود!  pip install yt-dlp")
        sys.exit(1)
    import subprocess
    out_tpl = str(Path(output_dir) / "%(title)s.%(ext)s")
    info("تنزيل من YouTube...")
    r = subprocess.run(
        ["yt-dlp", "-x", "--audio-format", "wav",
         "--audio-quality", "0", "-o", out_tpl, url],
        capture_output=True, text=True
    )
    if r.returncode != 0:
        error("فشل التنزيل:\n" + r.stderr); sys.exit(1)

    files = glob.glob(str(Path(output_dir) / "*.wav")) or \
            glob.glob(str(Path(output_dir) / "*.m4a"))
    if not files:
        error("لم يوجد الملف المنزل"); sys.exit(1)

    newest = max(files, key=os.path.getctime)
    success(f"تم التنزيل: {Path(newest).name}")
    return newest

# ──────────────────────────────────────────────────────────
# SINGLE FILE PIPELINE
# ──────────────────────────────────────────────────────────
VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".webm"}
AUDIO_EXTS = {".mp3", ".m4a", ".ogg", ".flac", ".wav"}


def process_one(input_path: str, lang: str, engine,
                output_dir: str, chunk_minutes: int = 10,
                workers: int = 4, embed: bool = False,
                force: bool = False) -> dict:
    suffix      = Path(input_path).suffix.lower()
    stem        = Path(input_path).stem
    tmp_wav     = Path(output_dir) / f"_tmp_{stem}.wav"
    output_base = str(Path(output_dir) / stem)
    is_video    = suffix in VIDEO_EXTS
    txt_path    = output_base + ".txt"
    srt_path    = output_base + ".srt"

    # SKIP if results already exist (unless --force)
    if not force and Path(txt_path).exists() and Path(srt_path).exists():
        warn(f"موجود مسبقاً، تخطي  ({Path(txt_path).name})  -- استعمل --force لإعادة التفريغ")
        subtitled = output_base + "_subtitled" + suffix
        return {
            "txt":   txt_path,
            "srt":   srt_path,
            "video": subtitled if Path(subtitled).exists() else "",
            "skipped": True,
        }

    # A. Convert to WAV
    if is_video or (suffix in AUDIO_EXTS and suffix != ".wav"):
        label = "استخراج الصوت" if is_video else "تحويل الصوت"
        step("A", f"{label}: {Path(input_path).name}")
        wav = to_wav(input_path, str(tmp_wav))
    else:
        wav = input_path

    # B. Split
    step("B", "فحص المدة وتقسيم اذا لزم...")
    chunks = split_audio(wav, chunk_minutes=chunk_minutes)

    # C. Transcribe
    step("C", f"تفريغ {'متوازي ' if len(chunks) > 1 else ''}({lang})")

    if len(chunks) == 1:
        result = engine.transcribe(chunks[0], lang)
        if result.get("segments"):
            srt_content = segments_to_srt(result["segments"])
            txt_content = result.get("text", "").strip()
        else:
            srt_file    = Path(chunks[0]).with_suffix(".srt")
            txt_file    = Path(chunks[0]).with_suffix(".txt")
            srt_content = srt_file.read_text(encoding="utf-8") if srt_file.exists() else ""
            txt_content = txt_file.read_text(encoding="utf-8") if txt_file.exists() else ""

        Path(txt_path).write_text(txt_content, encoding="utf-8")
        Path(srt_path).write_text(srt_content, encoding="utf-8")
    else:
        txt_path, srt_path = transcribe_parallel(
            chunks, engine, lang, output_base, max_workers=workers
        )

    success(f"TXT -> {Path(txt_path).name}")
    success(f"SRT -> {Path(srt_path).name}")

    # D. Embed subtitles (optional)
    subtitled_video = ""
    if embed and is_video:
        step("D", "تضمين Subtitles في الفيديو...")
        out_vid = output_base + "_subtitled" + suffix
        subtitled_video = embed_subtitles(input_path, srt_path, out_vid)

    # E. Cleanup
    if tmp_wav.exists():
        tmp_wav.unlink()
    if len(chunks) > 1:
        chunk_dir = Path(chunks[0]).parent
        if chunk_dir.exists() and chunk_dir.name.endswith("_chunks"):
            shutil.rmtree(chunk_dir)
            info("تنظيف الملفات المؤقتة OK")

    return {"txt": txt_path, "srt": srt_path, "video": subtitled_video}

# ──────────────────────────────────────────────────────────
# SHARED RUNNER
# ──────────────────────────────────────────────────────────
def _auto_workers() -> int:
    """Scale workers to CPU count — capped at 8 to avoid RAM pressure."""
    import os
    return min(8, os.cpu_count() or 4)


def _run_all(files: list, lang: str, engine, output_dir: str,
             chunk: int = 10, workers: int = None, embed: bool = False,
             force: bool = False):
    if workers is None:
        workers = _auto_workers()
    print(f"\n{Color.CYAN}{'─'*56}{Color.RESET}")
    print(f"  {Color.BOLD}ملفات:{Color.RESET} {Color.GREEN}{len(files)}{Color.RESET}  "
          f"| {Color.BOLD}workers:{Color.RESET} {Color.GREEN}{workers}{Color.RESET}  "
          f"| {Color.BOLD}embed:{Color.RESET} {Color.GREEN}{'yes' if embed else 'no'}{Color.RESET}")
    print(f"{Color.CYAN}{'─'*56}{Color.RESET}\n")

    for i, f in enumerate(files):
        file_lang = lang if lang != "auto" else detect_language(f)
        print(f"\n{Color.YELLOW}{'━'*56}{Color.RESET}")
        print(f"  {Color.BOLD}[{i+1}/{len(files)}] {Path(f).name}  ({file_lang}){Color.RESET}")
        print(f"{Color.YELLOW}{'━'*56}{Color.RESET}")
        t0  = time.time()
        out = process_one(f, file_lang, engine, output_dir,
                          chunk_minutes=chunk, workers=workers, embed=embed,
                          force=force)
        elapsed = time.time() - t0
        mins, secs = divmod(int(elapsed), 60)
        success(f"تم في {mins}m {secs}s")
        if out.get("video"):
            success(f"فيديو مع subtitles -> {Path(out['video']).name}")

    print(f"\n{Color.GREEN}{Color.BOLD}{'='*56}")
    print(f"  OK  انتهى التفريغ!  الملفات في: {output_dir}")
    print(f"{'='*56}{Color.RESET}\n")

# ──────────────────────────────────────────────────────────
# INTERACTIVE MODE
# ──────────────────────────────────────────────────────────
def interactive_mode():
    banner()

    print(f"\n{Color.CYAN}{'─'*56}{Color.RESET}")
    print(f"  {Color.BOLD}اختر المحرك:{Color.RESET}")
    print(f"  {Color.GREEN}1{Color.RESET}  Whisper (local · GPU · بدون limits)  {Color.GREEN}<-- موصى{Color.RESET}")
    print(f"  {Color.GREEN}2{Color.RESET}  Wit.ai  (cloud · يحتاج API key)")
    print(f"{Color.CYAN}{'─'*56}{Color.RESET}")
    ec          = input(f"  > ").strip()
    use_whisper = ec != "2"

    whisper_model = "medium"
    if use_whisper:
        print(f"\n  {Color.BOLD}حجم النموذج:{Color.RESET}  tiny / base / small / medium / large")
        wm            = input(f"  [medium] > ").strip() or "medium"
        whisper_model = wm

    check_deps(use_whisper)
    load_env()

    print(f"\n{Color.CYAN}{'─'*56}{Color.RESET}")
    print(f"  {Color.BOLD}المصدر:{Color.RESET}")
    print(f"  {Color.GREEN}1{Color.RESET}  YouTube    {Color.GREEN}2{Color.RESET}  ملف واحد    {Color.GREEN}3{Color.RESET}  Batch (مجلد)")
    print(f"{Color.CYAN}{'─'*56}{Color.RESET}")
    choice = input(f"  > ").strip()

    print(f"\n  {Color.BOLD}اللغة:{Color.RESET}")
    print(f"  {Color.GREEN}1{Color.RESET} Arabic  {Color.GREEN}2{Color.RESET} English  {Color.GREEN}3{Color.RESET} French  {Color.GREEN}4{Color.RESET} Darija  {Color.GREEN}0{Color.RESET} تلقائي")
    lang_map = {"1":"arabic","2":"english","3":"french","4":"darija","0":"auto"}
    lang     = lang_map.get(input(f"  > ").strip(), "auto")

    embed_flag = input(f"\n  تضمين subtitles في الفيديو؟ [y/N] > ").strip().lower() == "y"
    output_dir = input(f"\n  مجلد الإخراج [./output] > ").strip() or "./output"
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    files = []
    if choice == "1":
        url   = input(f"\n  رابط YouTube > ").strip()
        files = [download_youtube(url, output_dir)]
    elif choice == "2":
        p     = input(f"\n  مسار الملف > ").strip().strip('"')
        if not os.path.exists(p): error(f"غير موجود: {p}"); sys.exit(1)
        files = [p]
    elif choice == "3":
        folder = input(f"\n  مجلد الملفات > ").strip().strip('"')
        for ext in list(VIDEO_EXTS | AUDIO_EXTS):
            files += glob.glob(str(Path(folder) / f"*{ext}"))
        if not files: error("لم توجد ملفات"); sys.exit(1)
        info(f"وجد {len(files)} ملف")

    first_lang = lang if lang != "auto" else detect_language(files[0] if files else "")
    engine     = build_engine(use_whisper, whisper_model, "auto", first_lang)

    _run_all(files, lang, engine, output_dir, embed=embed_flag)

# ──────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────
def build_parser():
    p = argparse.ArgumentParser(
        prog="transcribe",
        description="Tafrigh PRO v2 -- Whisper + Parallel + Subtitle Embedding",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  python transcribe.py --whisper --file lecture.mp4 --lang arabic --embed
  python transcribe.py --whisper --model large --batch ./videos --lang arabic --embed --workers 2
  python transcribe.py --youtube "https://youtu.be/XXXX" --lang english
  python transcribe.py   # interactive mode
        """
    )
    src = p.add_mutually_exclusive_group()
    src.add_argument("--youtube", "-y", metavar="URL",  help="YouTube URL")
    src.add_argument("--file",    "-f", metavar="FILE", help="ملف صوتي أو فيديو")
    src.add_argument("--batch",   "-b", metavar="DIR",  help="مجلد ملفات")

    p.add_argument("--lang",    "-l", default="auto",
                   choices=["arabic","english","french","darija","auto"])
    p.add_argument("--output",  "-o", default="./output", metavar="DIR")
    p.add_argument("--chunk",   "-c", type=int, default=10,
                   help="دقائق كل جزء (افتراضي 10)")
    p.add_argument("--workers", "-w", type=int, default=None,
                   help="عدد threads للمعالجة المتوازية (افتراضي: تلقائي حسب CPU)")
    p.add_argument("--whisper", action="store_true",
                   help="استعمل Whisper (local, GPU, no limits)")
    p.add_argument("--model",   default="medium",
                   choices=["tiny","base","small","medium","large","large-v2","large-v3"],
                   help="حجم نموذج Whisper (افتراضي medium)")
    p.add_argument("--device",  default="auto",
                   choices=["auto","cuda","cpu"])
    p.add_argument("--embed",   action="store_true",
                   help="ضمن subtitles في الفيديو (يخرج *_subtitled.mp4)")
    p.add_argument("--force",   action="store_true",
                   help="أعد التفريغ حتى لو النتائج موجودة مسبقاً")
    return p


def cli_mode(args):
    banner()
    check_deps(args.whisper)
    load_env()
    Path(args.output).mkdir(parents=True, exist_ok=True)

    files = []
    if args.youtube:
        files = [download_youtube(args.youtube, args.output)]
    elif args.file:
        if not os.path.exists(args.file):
            error(f"غير موجود: {args.file}"); sys.exit(1)
        files = [args.file]
    elif args.batch:
        for ext in list(VIDEO_EXTS | AUDIO_EXTS):
            files += glob.glob(str(Path(args.batch) / f"*{ext}"))
        if not files: error("لم توجد ملفات"); sys.exit(1)
        info(f"batch: {len(files)} ملف")

    first_lang = args.lang if args.lang != "auto" else detect_language(files[0] if files else "")
    engine     = build_engine(args.whisper, args.model, args.device, first_lang)

    _run_all(files, args.lang, engine, args.output,
             chunk=args.chunk, workers=args.workers, embed=args.embed,
             force=args.force)


def main():
    parser = build_parser()
    args   = parser.parse_args()
    if not args.youtube and not args.file and not args.batch:
        interactive_mode()
    else:
        cli_mode(args)

if __name__ == "__main__":
    main()
