"""Phase 0 benchmark B0: TTS + alignment speed and peak memory on this host.
Usage: python bench_tts.py <engine> <out_dir>   engine = kokoro-int8 | kokoro-fp32 | piper | whisper
Each engine runs in its own process so peak RSS is measured per engine."""
import json, resource, sys, time, wave
from pathlib import Path

M = Path('/srv/ytf/data/models')
TEXT = ("What actually happens inside a chip when an AI answers your question? "
        "Every word you type becomes a list of numbers, called a vector. "
        "Those numbers flow through billions of tiny multiplications, done by thousands of cores working at the same time. "
        "That is why GPUs, not ordinary processors, power modern AI. "
        "A CPU is like a few brilliant professors solving problems one by one, "
        "while a GPU is like a stadium full of students, each doing one simple sum. "
        "For AI, the stadium wins. And the newest chips, built on three nanometer transistors, "
        "pack more than a hundred billion of them onto a piece of silicon smaller than a postage stamp.")


def peak_mb():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


def wav_seconds(p):
    with wave.open(str(p)) as w:
        return w.getnframes() / w.getframerate()


def main():
    engine, out = sys.argv[1], Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
    t0 = time.time(); res = {'engine': engine}
    if engine.startswith('kokoro'):
        import numpy as np, onnxruntime as ort, soundfile as sf
        from kokoro_onnx import Kokoro
        so = ort.SessionOptions(); so.intra_op_num_threads = 1; so.inter_op_num_threads = 1
        model = M / 'kokoro' / ('kokoro-v1.0.int8.onnx' if engine == 'kokoro-int8' else 'kokoro-v1.0.onnx')
        sess = ort.InferenceSession(str(model), so, providers=['CPUExecutionProvider'])
        k = Kokoro.from_session(sess, str(M / 'kokoro' / 'voices-v1.0.bin'))
        res['load_s'] = round(time.time() - t0, 2); t1 = time.time()
        audio, sr = k.create(TEXT, voice='am_michael', speed=1.0, lang='en-us')
        p = out / f'{engine}.wav'; sf.write(p, audio, sr)
    elif engine == 'piper':
        from piper import PiperVoice
        v = PiperVoice.load(str(M / 'piper' / 'en_US-ljspeech-medium.onnx'))
        res['load_s'] = round(time.time() - t0, 2); t1 = time.time()
        p = out / 'piper.wav'
        with wave.open(str(p), 'wb') as w:
            v.synthesize_wav(TEXT, w)
    elif engine == 'whisper':
        from faster_whisper import WhisperModel
        m = WhisperModel('base.en', device='cpu', compute_type='int8', cpu_threads=1, download_root=str(M / 'whisper'))
        res['load_s'] = round(time.time() - t0, 2); t1 = time.time()
        import numpy as np, soundfile as sf
        from math import gcd
        from scipy.signal import resample_poly
        p = out / 'kokoro-int8.wav'
        x, sr = sf.read(str(p), dtype='float32')        # decode ourselves: avoids PyAV version issues
        if x.ndim > 1: x = x.mean(axis=1)
        g = gcd(16000, sr); x = resample_poly(x, 16000 // g, sr // g).astype(np.float32)
        segs, _ = m.transcribe(x, word_timestamps=True, language='en', beam_size=1)
        words = [w for s in segs for w in s.words]
        res['words'] = len(words); res['text'] = ' '.join(w.word.strip() for w in words)[:160]
    gen = time.time() - t1; dur = wav_seconds(p)
    res.update(gen_s=round(gen, 2), audio_s=round(dur, 2), rtf=round(gen / dur, 3), peak_rss_mb=round(peak_mb()))
    print(json.dumps(res))


if __name__ == '__main__':
    main()
