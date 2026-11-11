"""Automated QA on the finished master. Hard failures block upload; soft warnings go on the approval card."""
import json, re, subprocess

from .common import read_json, write_json

LIMITS = {'short': (20.0, 59.5), 'long': (420.0, 630.0)}


def _ff(args):
    return subprocess.run(['ffmpeg', '-hide_banner', '-nostats'] + args, capture_output=True, text=True).stderr


def run_stage(proj, P):
    m = P / 'render' / 'master.mp4'; fmt = proj['format']
    hard, soft, info = [], [], {}
    pr = json.loads(subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(m)], capture_output=True, text=True).stdout)
    v = next(s for s in pr['streams'] if s['codec_type'] == 'video'); a = next((s for s in pr['streams'] if s['codec_type'] == 'audio'), None)
    dur = float(pr['format']['duration']); info.update(duration=round(dur, 2), size_mb=round(int(pr['format']['size']) / 1048576, 1))
    want = (1080, 1920) if fmt == 'short' else (1920, 1080)
    if (v['width'], v['height']) != want: hard.append(f'resolution {v["width"]}x{v["height"]} != {want}')
    if v['codec_name'] != 'h264' or v['pix_fmt'] != 'yuv420p': hard.append(f'video codec {v["codec_name"]}/{v["pix_fmt"]}')
    if v['r_frame_rate'] != '30/1': hard.append(f'frame rate {v["r_frame_rate"]}')
    if not a or a['codec_name'] != 'aac' or a['sample_rate'] != '48000': hard.append('audio must be AAC 48 kHz')
    lo, hi = LIMITS[fmt]
    if not lo <= dur <= hi: hard.append(f'duration {dur:.1f}s outside {lo}-{hi}s')
    # black frames
    blacks = re.findall(r'black_start:([\d.]+) black_end:([\d.]+) black_duration:([\d.]+)', _ff(['-i', str(m), '-vf', 'blackdetect=d=0.3:pix_th=0.06', '-an', '-f', 'null', '-']))
    if blacks: hard.append(f'black segments: {blacks[:3]}')
    # silence inside narration
    tl = read_json(P / 'render' / 'timeline.json'); speech_end = tl['duration'] - 1.2
    sil = [(float(s), float(e)) for s, e in re.findall(r'silence_start: ([\d.]+)[\s\S]*?silence_end: ([\d.]+)', _ff(['-i', str(m), '-af', 'silencedetect=n=-45dB:d=1.2', '-vn', '-f', 'null', '-']))]
    sil = [x for x in sil if x[0] > 0.5 and x[1] < speech_end]
    if sil: hard.append(f'silences inside narration: {sil[:3]}')
    # loudness
    lo_txt = _ff(['-i', str(m), '-af', 'ebur128=peak=true', '-vn', '-f', 'null', '-'])
    I = float(re.findall(r'I:\s+(-?[\d.]+) LUFS', lo_txt)[-1]); TP = float(re.findall(r'Peak:\s+(-?[\d.]+) dBFS', lo_txt)[-1])
    info.update(lufs=I, true_peak=TP)
    if not -15.0 <= I <= -13.0: hard.append(f'loudness {I} LUFS (want -14 +/-1)')
    if TP > -1.0: hard.append(f'true peak {TP} dBTP > -1.0')
    # layout, claims, pronunciation, captions
    lay = read_json(P / 'qa' / 'layout.json', {'reports': [], 'pageErrors': []})
    if lay['reports'] or lay['pageErrors']: hard.append(f'layout problems: {lay["reports"][:3]}')
    script = read_json(P / 'script' / 'final.json'); vr = read_json(P / 'script' / 'verify_report.json')
    last = next((r for r in reversed(vr or []) if 'issues' in r), {'issues': {}})
    dropped = next((r['dropped'] for r in (vr or []) if 'dropped' in r), {})
    if last['issues'] and not dropped: hard.append('unverified claims remain')
    if dropped: soft.append(f'{len(dropped)} sentence(s) removed because they could not be verified: {list(dropped)}')
    info['claims'] = sum(len(s['claims']) for s in script['segments'])
    pol = script.get('polish') or {}
    info['clarity'] = pol.get('score')
    if pol.get('notes'): soft.append(f'clarity reviewer notes ({len(pol["notes"])}): ' + ' | '.join(pol['notes'][:2]))
    pron = read_json(P / 'qa' / 'pronunciation.json', [])
    badp = [q for q in pron if q['wer'] > 0.2]
    if badp: soft.append(f'{len(badp)} segment(s) may be mispronounced: ' + '; '.join(f'{q["seg"]} heard "{q["heard"][:60]}"' for q in badp[:3]))
    if fmt == 'short':
        caps = tl['captions']
        if not caps: hard.append('short has no captions')
        overlap = [c for c, d in zip(caps, caps[1:]) if c['e'] > d['s'] + 0.01]
        if overlap: soft.append(f'{len(overlap)} caption overlaps')
    report = {'pass': not hard, 'hard': hard, 'soft': soft, 'info': info}
    write_json(P / 'qa' / 'report.json', report)
    if hard:
        raise RuntimeError('QA failed: ' + ' | '.join(hard))
    return report
