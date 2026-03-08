# 🎙️ Tafrigh PRO

> **Audio & Video Transcription Tool** — Arabic, English, French, Darija
> CLI + GUI · Whisper · GPU · Batch · YouTube · Portable .exe

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=flat-square)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)

---

## شنو هو Tafrigh PRO؟

أداة تفرّغ الصوت من فيديوهات الدروس والمحاضرات وتخرج لك:

- **TXT** — النص الكامل
- **SRT** — Subtitles جاهزة للفيديو
- **MP4 مع subtitles مدمجة** — اختياري

تدعم فيديوهات طويلة (+2 ساعة)، batch processing، وتخدم بدون internet بعد التثبيت.

---

## المميزات

| الميزة | التفاصيل |
|--------|----------|
| 🧠 Whisper | faster-whisper · GPU/CPU · offline |
| ⚡ سريع | parallel chunks · vad_filter · beam_size=3 |
| 📁 Batch | مجلد كامل دفعة واحدة |
| ▶ YouTube | تنزيل وتفريغ مباشرة برابط |
| 🎬 Embed | subtitles مدمجة في الفيديو |
| 🖥️ GUI | واجهة رسومية dark theme |
| ⌨️ CLI | كامل مع جميع الخيارات |
| 💾 Portable | .exe بدون تثبيت Python |
| ⏭️ Skip | يتخطى الملفات المفرّغة مسبقاً |

---

## متطلبات التثبيت

### Python

```
Python 3.10 أو 3.11
```

### المكتبات

```bash
pip install faster-whisper ffmpeg-python pydub yt-dlp
```

> **GPU — اختياري لكن موصى (أسرع 8×):**
> ```bash
> pip install torch --index-url https://download.pytorch.org/whl/cu118
> ```

### ffmpeg

| النظام | الأمر |
|--------|-------|
| Windows | `winget install ffmpeg` أو [ffmpeg.org](https://ffmpeg.org/download.html) |
| Linux | `sudo apt install ffmpeg` |
| macOS | `brew install ffmpeg` |

---

## طرق الاستعمال

### 1️⃣ GUI (الأسهل)

```bash
python tafrigh_gui.py
```

افتح البرنامج، اختر الملف، اضغط **START** ☕

---

### 2️⃣ CLI

```bash
# ملف واحد
python transcribe.py --whisper --file lecture.mp4 --lang arabic

# YouTube
python transcribe.py --whisper --youtube "https://youtu.be/XXXX" --lang arabic

# Batch — مجلد كامل
python transcribe.py --whisper --batch ./videos/ --lang arabic --output ./results

# مع تضمين subtitles في الفيديو
python transcribe.py --whisper --file lecture.mp4 --lang arabic --embed

# وضع تفاعلي — بدون arguments
python transcribe.py
```

### جميع خيارات CLI

```
--whisper           استعمل Whisper  (موصى)
--model   SIZE      tiny | base | small | medium | large  (افتراضي: small)
--device  DEVICE    auto | cuda | cpu
--lang    LANG      arabic | english | french | darija | auto
--output  DIR       مجلد الإخراج  (افتراضي: ./output)
--chunk   N         دقائق كل جزء  (افتراضي: 10)
--workers N         عدد threads  (افتراضي: تلقائي)
--embed             ضمّن subtitles في الفيديو
--force             أعد التفريغ حتى لو النتائج موجودة
```

---

## الملفات الصادرة

```
output/
├── lecture.txt              ← النص الكامل
├── lecture.srt              ← Subtitles
└── lecture_subtitled.mp4   ← فيديو مع subtitles  (مع --embed)
```

---

## Portable .exe — Windows

```bash
# بناء كامل — أمر واحد
python build.py

# خيارات
python build.py --model medium      # نموذج أكبر
python build.py --skip-bins         # لو ffmpeg/yt-dlp عندك
```

النتيجة:

```
dist/TafrighPRO/
└── TafrighPRO.exe   ← شارك هذا المجلد كاملاً
```

المستخدم ما يحتاجش Python ولا أي تثبيت — فقط كليك مزدوج.

---

## اختيار النموذج

| النموذج | السرعة | الدقة | مناسب لـ |
|---------|--------|-------|----------|
| `tiny`   | ⚡⚡⚡⚡ | متوسط     | اختبار سريع |
| `base`   | ⚡⚡⚡  | جيد        | محادثات بسيطة |
| `small`  | ⚡⚡   | جيد جداً   | **دروس ومحاضرات ← موصى** |
| `medium` | ⚡    | ممتاز      | لهجات ولغة معقدة |
| `large`  | 🐌   | الأفضل     | جودة عالية / بدون GPU |

> نصيحة: `small` على GPU أسرع من `medium` على CPU مع جودة قريبة.

---

## هيكل المشروع

```
tafrigh-pro/
├── transcribe.py      ← Engine الرئيسي — CLI + pipeline كامل
├── tafrigh_gui.py     ← GUI wrapper — Tkinter
├── tafrigh.spec       ← PyInstaller config
├── build.py           ← Build script للـ portable .exe
├── .env.example       ← نموذج ملف مفاتيح Wit.ai
└── README.md
```

### Architecture

```
INPUT (file / folder / youtube)
    ↓
ffmpeg → WAV 16kHz mono
    ↓
split audio (chunks × N دقائق)
    ↓
parallel transcription  ←  faster-whisper + VAD + GPU
    ↓
ordered merge
    ↓
TXT + SRT
    ↓
embed subtitles (optional)  ←  ffmpeg
    ↓
cleanup temp files
```

### engine-agnostic design

الـ pipeline كاملاً مستقل عن الـ engine. لتبديل الـ backend:

```python
# أضف class جديد بنفس interface
class MyEngine:
    def transcribe(self, wav_path: str, lang: str) -> dict:
        # segments: [{start, end, text}]
        ...
```

والباقي ما يتبدلش.

---

## Wit.ai — بديل cloud

إذا ما أردتيش تثبت Whisper:

1. سجّل في [wit.ai](https://wit.ai)
2. صايب App لكل لغة وخذ Server Access Token
3. صايب `.env`:

```env
WIT_API_KEY_ARABIC=xxxx
WIT_API_KEY_ENGLISH=xxxx
```

4. شغّل بدون `--whisper`:

```bash
python transcribe.py --file lecture.mp4 --lang arabic
```

> ⚠️ Wit.ai عنده limits وما يخدمش offline — Whisper موصى للاستعمال الجدي.

---

## Troubleshooting

**`ffmpeg not found`**
```bash
winget install ffmpeg          # Windows
sudo apt install ffmpeg        # Linux
brew install ffmpeg            # macOS
```

**`CUDA out of memory`**
```bash
python transcribe.py --whisper --model small --device cpu --file ...
```

**السكريبت بطيء**
```bash
# استعمل small بدل medium، أو أضف GPU
python transcribe.py --whisper --model small ...
```

**ملفات مؤقتة بقات بعد خطأ**
```bash
rm -rf output/*_chunks/
rm output/_tmp_*.wav
```

**GUI ما فتحتش على Linux**
```bash
sudo apt install python3-tk
```

---

## المساهمة

Pull requests مرحب بها.
للأخطاء والاقتراحات: افتح Issue.

---

## الترخيص

MIT License — استعملو، طوّرو، وزّعو بحرية.
