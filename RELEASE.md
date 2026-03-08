# 🚀 RELEASE.md — First Push Checklist

## قبل git push

- [ ] `.env` مش موجود في الـ commit  (موجود في .gitignore)
- [ ] `output/` فارغ أو ما موجودش
- [ ] `dist/` و `build/` محذوفين
- [ ] `README.md` محدّث

## الأوامر

```bash
git init
git add .
git commit -m "Initial release: Tafrigh PRO v1.0 — CLI + GUI + portable build"
git branch -M main
git remote add origin https://github.com/USERNAME/tafrigh-pro.git
git push -u origin main
```

## GitHub Release

بعد الـ push مباشرة:

1. GitHub → **Releases** → **Create a new release**
2. Tag: `v1.0.0`
3. Title: `Tafrigh PRO v1.0 — Whisper + GPU + Portable`
4. Description:

```
### What's new in v1.0
- faster-whisper engine (2-4x faster, less RAM)
- VAD filter — skips silence, fewer hallucinations
- Parallel chunk processing
- GUI (Tkinter dark theme)
- Portable Windows .exe via PyInstaller
- YouTube download + batch processing
- Subtitle embedding in video
```

5. Attach: `dist/TafrighPRO.zip` (اضغط المجلد وارفعه)

## GitHub Topics (للـ SEO)

أضف هذه الـ topics في صفحة الـ repo:

```
whisper  transcription  arabic  speech-to-text
subtitles  faster-whisper  python  cli  gui
batch-processing  gpu  ffmpeg  youtube-dl
```

الناس اللي تبحث عن whisper أو transcription tools غادي تلقى المشروع.
