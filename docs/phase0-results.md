# Phase 0 benchmark results — controller VM (E2.1.Micro, AMD EPYC 7551), 2026-11-10

| Test | Result |
|---|---|
| CPU, 1 worker sustained 60 s | 333 bogo-ops/s, 26% steal |
| CPU, 2 workers sustained 180 s | 295 bogo-ops/s total, 74.5% steal -> effectively ONE usable thread |
| RAM free at idle | ~540-600 MB (ledger site: nginx+mariadb+php ~56 MB) |
| Kokoro int8, 45 s narration, 1 thread | 263 s (RTF 5.8), peak 631 MB |
| Kokoro fp32 | 348 s (RTF 7.7), peak 629 MB -> use int8 |
| Piper ljspeech-medium (PD voice) | 21 s (RTF 0.52), peak 352 MB |
| faster-whisper base.en int8, 1 thread | 38 s for 45 s audio (RTF 0.84), peak 383 MB, 111/111 words |
| Chromium Canvas2D capture + x264 veryfast 1080x1920 | 2.81 fps (10.7x realtime), chrome ~470 MB + ffmpeg 211 MB |
| Same 1920x1080 veryfast | 2.86 fps (10.5x realtime) |
| Same 1920x1080 medium | 1.61 fps (18.7x realtime), ffmpeg 381 MB -> use veryfast |

Projected per video (micro only): Short 45 s = TTS 4.4 min + align 0.7 min + render 8 min ~ 13 min.
Long 8.5 min = TTS ~50 min + align ~7 min + render ~90 min ~ 2.5 h.
Launch cadence (3 Shorts + 1 long / week) ~ 3.2 CPU-hours/week -> feasible on the micro alone.
