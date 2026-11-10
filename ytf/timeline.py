"""Timeline: absolute scene times from the narration, cue-word reveal times, Shorts captions, chapters."""
import re

from .common import read_json, write_json

ACCENTS = ['#3d6bff', '#7c5cff', '#0ea5e9', '#14b8a6']
STOP = set('the a an and or of to in on at for is are was were be it its this that with as by from but so if then than you your we our they their can will just how what why'.split())
LIST_KEYS = {'process_flow': 'steps', 'bar_chart': 'bars', 'kinetic_text': 'lines'}


def _n(w):
    return re.sub(r'[^a-z0-9]', '', w.lower())


def _captions(words):
    groups, cur = [], []
    for i, w in enumerate(words):
        gap = (w['s'] - words[i - 1]['e']) if i else 0
        text_len = len(' '.join(x['w'] for x in cur + [w]))
        if cur and (len(cur) >= 3 or gap > 0.35 or text_len > 18 or re.search(r'[.,;:?!]$', cur[-1]['w'])):
            groups.append(cur); cur = []
        cur.append(w)
    if cur:
        groups.append(cur)
    out = []
    for i, g in enumerate(groups):
        txt = ' '.join(re.sub(r'[.,;:!]+$', '', x['w']) for x in g)
        content = [x['w'] for x in g if _n(x['w']) not in STOP and len(_n(x['w'])) > 2]
        hi = max(content, key=lambda w: len(_n(w)), default='')
        hi = re.sub(r'[.,;:!?]+$', '', hi)
        end = groups[i + 1][0]['s'] if i + 1 < len(groups) and groups[i + 1][0]['s'] - g[-1]['e'] < 0.6 else g[-1]['e'] + 0.25
        out.append({'s': round(g[0]['s'] - 0.04, 3), 'e': round(end - 0.02, 3), 'text': txt, 'hi': hi})
    return out


def run(proj, P):
    fmt = proj['format']; W, H = (1080, 1920) if fmt == 'short' else (1920, 1080)
    board = read_json(P / 'storyboard.json'); meta = read_json(P / 'audio' / 'segments.json')
    words = read_json(P / 'audio' / 'words.json'); script = read_json(P / 'script' / 'final.json')
    segt = {s['id']: s for s in meta['segments']}; dur = meta['duration']
    scenes = []
    for i, sc in enumerate(board['scenes']):
        start = 0.0 if i == 0 else max(0.0, segt[sc['segments'][0]]['start'] - 0.12)
        scenes.append({'id': f's{i + 1:02d}', 'template': sc['template'], 'params': sc['params'], 'segments': sc['segments'], 'start': round(start, 3)})
    for i, s in enumerate(scenes):
        s['end'] = scenes[i + 1]['start'] if i + 1 < len(scenes) else dur
        # reveal cues: explicit "cue" words, or for kinetic_text the first word of each line
        key = LIST_KEYS.get(s['template'])
        if key:
            sw = [w for w in words if w['seg'] in s['segments']]; cues = {}; after = s['start']
            for j, item in enumerate(s['params'].get(key, [])):
                cue = item.get('cue') if isinstance(item, dict) else (item.split()[0] if item.split() else None)
                if not cue:
                    continue
                hit = next((w for w in sw if w['s'] >= after - 0.05 and _n(w['w']) == _n(cue)), None)
                if hit:
                    cues[j] = round(max(0.15, hit['s'] - s['start'] - 0.1), 3); after = hit['s']
            if cues:
                s['cues'] = cues
    chapters = []
    if fmt == 'long':
        titles = {c['id']: c['title'] for c in script['chapters']}; seen = set()
        for s in scenes:
            ch = segt[s['segments'][0]]['chapter']
            if ch not in seen:
                seen.add(ch); chapters.append({'t': 0.0 if not chapters else s['start'], 'title': titles.get(ch, ch)})
    tl = {'format': fmt, 'width': W, 'height': H, 'fps': 30, 'duration': dur,
          'accent': ACCENTS[sum(map(ord, proj['id'])) % len(ACCENTS)], 'scenes': scenes,
          'captions': _captions(words) if fmt == 'short' else [], 'chapters': chapters}
    write_json(P / 'render' / 'timeline.json', tl)
    lens = [s['end'] - s['start'] for s in scenes]
    return {'scenes': len(scenes), 'duration': dur, 'shortest_scene': round(min(lens), 2), 'longest_scene': round(max(lens), 2)}
