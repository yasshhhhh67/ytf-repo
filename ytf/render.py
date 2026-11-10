"""Render: layout check, chunked frame capture (resumable), concat, mux with the mix, thumbnail, contact sheet."""
import json, os, subprocess

from .common import ENGINE, log, read_json, run, sha256_file, write_json

NODE = ['node', str(ENGINE / 'render.mjs')]
CHUNK_S = 60


def _node(args, timeout):
    r = subprocess.run(NODE + args, capture_output=True, text=True, timeout=timeout, cwd=ENGINE)
    if r.returncode:
        raise RuntimeError(f'render.mjs {args[1]} failed: {(r.stderr or r.stdout)[-1500:]}')
    return r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ''


def check(P):
    out = json.loads(_node([str(P / 'render'), 'check', '0.5'], 3600))
    write_json(P / 'qa' / 'layout.json', out)
    return out


def run_stage(proj, P):
    job = P / 'render'; tl = read_json(job / 'timeline.json'); meta = read_json(P / 'publish' / 'metadata.json')
    lay = check(P)
    if lay['reports'] or lay['pageErrors']:
        raise RuntimeError(f'layout check failed: {lay["reports"][:5]} {lay["pageErrors"][:3]}')
    fps = tl['fps']; total = int(round(tl['duration'] * fps))
    # chunk boundaries on scene starts, roughly CHUNK_S apart
    bounds = [0]
    for s in tl['scenes'][1:]:
        f = int(round(s['start'] * fps))
        if f - bounds[-1] >= CHUNK_S * fps:
            bounds.append(f)
    bounds.append(total)
    th = sha256_file(job / 'timeline.json')
    man = read_json(job / 'chunks.json', {})
    if man.get('timeline') != th:
        for f in (job / 'chunks').glob('*.mp4') if (job / 'chunks').exists() else []:
            f.unlink()
        man = {'timeline': th, 'done': {}}
    (job / 'chunks').mkdir(exist_ok=True)
    for i, (a, b) in enumerate(zip(bounds, bounds[1:])):
        name = f'c{i:02d}.mp4'
        if man['done'].get(name) == [a, b] and (job / 'chunks' / name).exists():
            continue
        res = json.loads(_node([str(job), 'video', str(job / 'chunks' / name), str(a), str(b)], 6 * 3600))
        man['done'][name] = [a, b]; write_json(job / 'chunks.json', man)
        log('chunk rendered', chunk=name, frames=res['frames'], reused=res['reused'], secs=res['seconds'], of=len(bounds) - 1)
    lst = job / 'chunks' / 'list.txt'
    lst.write_text(''.join(f"file '{job / 'chunks' / f'c{i:02d}.mp4'}'\n" for i in range(len(bounds) - 1)))
    run(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', str(lst), '-c', 'copy', str(job / 'video.mp4')])
    run(['ffmpeg', '-v', 'error', '-y', '-i', str(job / 'video.mp4'), '-i', str(P / 'audio' / 'mix.wav'), '-map', '0:v', '-map', '1:a',
         '-c:v', 'copy', '-c:a', 'aac', '-b:a', '320k', '-ar', '48000', '-movflags', '+faststart', '-shortest', str(job / 'master.mp4')])
    # thumbnail + contact sheet
    W, H = (1280, 720) if proj['format'] == 'long' else (1080, 1920)
    write_json(job / 'thumb.json', {'width': W, 'height': H, 'accent': tl['accent'],
                                    'params': {'text': meta['thumbnail_text'], 'tag': meta.get('thumbnail_tag', '')}})
    _node([str(job), 'thumb', str(job / 'thumb.jpg')], 600)
    _node([str(job), 'sheet', str(P / 'qa' / 'contact.jpg'), '2' if proj['format'] == 'short' else '6', '8' if proj['format'] == 'short' else '6'], 3600)
    os.remove(job / 'video.mp4')
    size = (job / 'master.mp4').stat().st_size
    return {'chunks': len(bounds) - 1, 'master_mb': round(size / 1048576, 1)}
