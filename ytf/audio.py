"""Soundtrack: procedural music bed + soft scene-change whooshes (no third-party audio), ducked under the narration,
then two-pass loudness normalisation to -14 LUFS / -1.5 dBTP. Written in blocks to stay within ~100 MB RAM."""
import json, re

import numpy as np
import soundfile as sf
from scipy import signal

from .common import log, read_json, run

SR = 48000
# chord progressions as semitone offsets from the root (minor/major colours); one is picked per video
PROGRESSIONS = [[[0, 3, 7], [-4, 0, 3], [-9, -5, 0], [-2, 2, 5]],      # i - VI - III - VII
                [[0, 4, 7], [-3, 0, 4], [-7, -3, 0], [-5, -1, 2]],      # I - vi - IV - V
                [[0, 3, 7], [-2, 2, 5], [-4, 0, 3], [-5, -1, 2]],       # i - VII - VI - V
                [[0, 4, 7], [-5, -1, 2], [-3, 0, 4], [-7, -3, 0]]]      # I - V - vi - IV
ROOTS = [110.0, 116.54, 123.47, 130.81, 146.83]                        # A2, A#2, B2, C3, D3


def _bed_block(t0, n, seed, chord_len):
    rng = np.random.default_rng(seed); prog = PROGRESSIONS[rng.integers(len(PROGRESSIONS))]; root = ROOTS[rng.integers(len(ROOTS))]
    t = t0 + np.arange(n) / SR; out = np.zeros((n, 2), np.float32)
    ci = (t // chord_len).astype(int); pos = t - ci * chord_len
    env = np.minimum(1, pos / 1.2) * np.minimum(1, (chord_len - pos) / 1.0) * 0.85 + 0.15
    for k in range(len(prog)):
        mask = (ci % len(prog)) == k
        if not mask.any():
            continue
        tm = t[mask]; e = env[mask]
        for v, semi in enumerate(prog[k]):
            f = root * 2 ** (semi / 12) * 2
            for side, det in ((0, -0.6), (1, 0.6)):
                ph = 2 * np.pi * (f + det) * tm
                out[mask, side] += (np.sin(ph) + 0.25 * np.sin(2 * ph) + 0.08 * np.sin(3 * ph)) * e * 0.06
        bass = root * 2 ** (prog[k][0] / 12) / 2
        out[mask, :] += (np.sin(2 * np.pi * bass * tm) * e * 0.08)[:, None]
    lfo = 0.85 + 0.15 * np.sin(2 * np.pi * 0.05 * t)
    return out * lfo[:, None]


def _whoosh(n, seed):
    rng = np.random.default_rng(seed); x = rng.standard_normal(n).astype(np.float32)
    f = np.linspace(400, 3500, n); y = np.zeros(n, np.float32); blk = 512
    for i in range(0, n, blk):                              # crude moving band-pass sweep
        b, a = signal.butter(2, [max(80, f[i] * 0.6) / (SR / 2), min(SR / 2 - 100, f[i] * 1.4) / (SR / 2)], 'band')
        y[i:i + blk] = signal.lfilter(b, a, x[i:i + blk])
    env = np.sin(np.linspace(0, np.pi, n)) ** 2
    return (y * env / (np.abs(y).max() + 1e-9) * 0.12).astype(np.float32)


def run_stage(proj, P):
    tl = read_json(P / 'render' / 'timeline.json'); dur = tl['duration']; seed = sum(map(ord, proj['id']))
    n_total = int(dur * SR) + SR // 2; chord_len = 4.0 if proj['format'] == 'short' else 6.0
    cues = [s['start'] for s in tl['scenes'][1:]]
    wn = int(0.45 * SR); wh = _whoosh(wn, seed)
    bed_path = P / 'audio' / 'bed.wav'
    with sf.SoundFile(bed_path, 'w', SR, 2, 'PCM_16') as f:
        blk = SR * 10
        for i0 in range(0, n_total, blk):
            n = min(blk, n_total - i0); buf = _bed_block(i0 / SR, n, seed, chord_len)
            fade = np.minimum(1, np.minimum((i0 + np.arange(n)) / (2 * SR), (n_total - i0 - np.arange(n)) / (2 * SR)))
            buf *= fade[:, None]
            for c in cues:                                  # whoosh peaks right at the cut
                a = int((c - 0.3) * SR) - i0
                lo, hi = max(0, a), min(n, a + wn)
                if lo < hi:
                    buf[lo:hi, :] += wh[lo - a:hi - a, None] * 0.6
            f.write(np.clip(buf, -1, 1))
    raw = P / 'audio' / 'mix_raw.wav'
    graph = ('[0:a]aresample=48000,highpass=f=70,acompressor=threshold=0.12:ratio=3:attack=8:release=120:makeup=1.5,'
             'asplit=2[v][sc];[1:a][sc]sidechaincompress=threshold=0.02:ratio=10:attack=25:release=450[m];'
             '[v][m]amix=inputs=2:duration=longest:normalize=0[out]')
    run(['ffmpeg', '-v', 'error', '-y', '-i', str(P / 'audio' / 'narration.wav'), '-i', str(bed_path), '-filter_complex', graph,
         '-map', '[out]', '-ac', '2', '-ar', str(SR), '-c:a', 'pcm_s16le', str(raw)])
    meas = _loudnorm_measure(raw)
    ln = (f'loudnorm=I=-14:TP=-1.5:LRA=11:measured_I={meas["input_i"]}:measured_TP={meas["input_tp"]}:measured_LRA={meas["input_lra"]}:'
          f'measured_thresh={meas["input_thresh"]}:offset={meas["target_offset"]}:linear=true')
    run(['ffmpeg', '-v', 'error', '-y', '-i', str(raw), '-af', ln + ',aresample=48000', '-ar', str(SR), '-c:a', 'pcm_s16le', str(P / 'audio' / 'mix.wav')])
    raw.unlink(); bed_path.unlink()
    log('audio mixed', input_lufs=meas['input_i'])
    return {'input_lufs': float(meas['input_i'])}


def _loudnorm_measure(path):
    import subprocess
    r = subprocess.run(['ffmpeg', '-hide_banner', '-i', str(path), '-af', 'loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json', '-f', 'null', '-'],
                       capture_output=True, text=True)
    m = re.search(r'\{[^{}]*"input_i"[^{}]*\}', r.stderr, re.S)
    if not m:
        raise RuntimeError('loudnorm measurement failed: ' + r.stderr[-500:])
    return json.loads(m.group(0))
