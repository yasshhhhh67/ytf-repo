"""Narration (Kokoro-82M int8, single thread) and word timing (faster-whisper, script spelling preserved)."""
import gc, json, re
from difflib import SequenceMatcher
from math import gcd

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

from .common import MODELS, config, log, read_json, write_json

SR = 24000
VOICE = {'long': ('am_michael', 1.0), 'short': ('am_michael', 1.08)}
GAP = {'segment': 0.30, 'chapter': 0.70, 'lead': 0.35, 'outro': 1.0}


def tts_text(text):
    """Apply the pronunciation lexicon (whole words, case-sensitive) for the synthesiser only."""
    lex = {k: v for k, v in config('lexicon.json').items() if not k.startswith('_')}
    for k in sorted(lex, key=len, reverse=True):
        text = re.sub(r'(?<![\w-])' + re.escape(k) + r'(?![\w-])', lex[k], text)
    return text


def _trim(x, thr=0.006):
    idx = np.where(np.abs(x) > thr)[0]
    if not len(idx):
        return x
    return x[max(0, idx[0] - int(0.01 * SR)): min(len(x), idx[-1] + int(0.04 * SR))]


def synth(proj, P):
    import onnxruntime as ort
    from kokoro_onnx import Kokoro
    script = read_json(P / 'script' / 'final.json'); voice, speed = VOICE[proj['format']]
    so = ort.SessionOptions(); so.intra_op_num_threads = 1; so.inter_op_num_threads = 1
    k = Kokoro.from_session(ort.InferenceSession(str(MODELS / 'kokoro' / 'kokoro-v1.0.int8.onnx'), so, providers=['CPUExecutionProvider']),
                            str(MODELS / 'kokoro' / 'voices-v1.0.bin'))
    (P / 'audio' / 'seg').mkdir(parents=True, exist_ok=True)
    lead = 0.1 if proj['format'] == 'short' else GAP['lead']
    parts = [np.zeros(int(lead * SR), np.float32)]; t = lead; segs = []; prev_ch = None
    for i, s in enumerate(script['segments']):
        if prev_ch and s['chapter'] != prev_ch:
            extra = np.zeros(int((GAP['chapter'] - GAP['segment']) * SR), np.float32); parts.append(extra); t += len(extra) / SR
        prev_ch = s['chapter']
        cache = P / 'audio' / 'seg' / f'{s["id"]}.wav'
        if cache.exists() and read_json(cache.with_suffix('.json'), {}).get('text') == s['text']:
            x, _ = sf.read(cache, dtype='float32')
        else:
            x, _ = k.create(tts_text(s['text']), voice=voice, speed=speed, lang='en-us')
            x = _trim(np.asarray(x, np.float32)); sf.write(cache, x, SR); write_json(cache.with_suffix('.json'), {'text': s['text']})
        segs.append({'id': s['id'], 'chapter': s['chapter'], 'text': s['text'], 'start': round(t, 3), 'end': round(t + len(x) / SR, 3)})
        parts += [x, np.zeros(int(GAP['segment'] * SR), np.float32)]; t += len(x) / SR + GAP['segment']
        log('tts', seg=s['id'], n=f'{i + 1}/{len(script["segments"])}', secs=round(len(x) / SR, 2))
    parts.append(np.zeros(int(GAP['outro'] * SR), np.float32))
    y = np.concatenate(parts); y = 0.9 * y / (np.abs(y).max() + 1e-9)
    sf.write(P / 'audio' / 'narration.wav', y, SR)
    write_json(P / 'audio' / 'segments.json', {'duration': round(len(y) / SR, 3), 'voice': voice, 'speed': speed, 'segments': segs})
    del k; gc.collect()
    return {'duration': round(len(y) / SR, 1)}


def _words(text):
    return re.findall(r"[A-Za-z0-9][A-Za-z0-9'%$.,\-]*", text)


def _n(w):
    return re.sub(r'[^a-z0-9]', '', w.lower())


def align(proj, P):
    from faster_whisper import WhisperModel
    m = WhisperModel('base.en', device='cpu', compute_type='int8', cpu_threads=1, download_root=str(MODELS / 'whisper'))
    meta = read_json(P / 'audio' / 'segments.json')
    out, qa = [], []
    for s in meta['segments']:
        x, sr = sf.read(P / 'audio' / 'seg' / f'{s["id"]}.wav', dtype='float32')
        g = gcd(16000, sr); x16 = resample_poly(x, 16000 // g, sr // g).astype(np.float32)
        res, _ = m.transcribe(x16, language='en', word_timestamps=True, beam_size=1, condition_on_previous_text=False)
        heard = [(w.word.strip(), w.start, w.end) for r in res for w in (r.words or [])]
        script_words = _words(s['text'])
        a, b = [_n(w) for w in script_words], [_n(h[0]) for h in heard]
        sm = SequenceMatcher(None, a, b, autojunk=False)
        times = [None] * len(a)
        for blk in sm.get_matching_blocks():
            for j in range(blk.size):
                times[blk.a + j] = heard[blk.b + j][1:]
        # fill gaps by interpolating between known neighbours, proportional to word length
        dur = s['end'] - s['start']; known = [(i, t) for i, t in enumerate(times) if t]
        for i in range(len(times)):
            if times[i] is None:
                prev = max([k for k in known if k[0] < i], default=(-1, (0.0, 0.0)), key=lambda k: k[0])
                nxt = min([k for k in known if k[0] > i], default=(len(times), (dur, dur)), key=lambda k: k[0])
                span_words = script_words[prev[0] + 1:nxt[0]]; total = sum(len(w) for w in span_words) or 1
                t0, t1 = prev[1][1], nxt[1][0]; off = sum(len(w) for w in script_words[prev[0] + 1:i])
                times[i] = (t0 + (t1 - t0) * off / total, t0 + (t1 - t0) * (off + len(script_words[i])) / total)
        for w, (ws, we) in zip(script_words, times):
            out.append({'w': w, 'seg': s['id'], 's': round(s['start'] + ws, 3), 'e': round(s['start'] + we, 3)})
        wer = 1 - SequenceMatcher(None, a, b, autojunk=False).ratio()
        qa.append({'seg': s['id'], 'wer': round(wer, 3), 'heard': ' '.join(h[0] for h in heard)[:300]})
    write_json(P / 'audio' / 'words.json', out)
    write_json(P / 'qa' / 'pronunciation.json', qa)
    bad = [q for q in qa if q['wer'] > 0.2]
    return {'words': len(out), 'segments_wer_over_0.2': len(bad), 'worst': sorted(qa, key=lambda q: -q['wer'])[:3]}
