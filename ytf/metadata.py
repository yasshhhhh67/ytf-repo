"""Title, description (summary, chapters, sources, attributions), tags and thumbnail text."""
from . import llm
from .common import read_json, write_json
from .templates import GRAPHICS

META_SCHEMA = {'type': 'object', 'additionalProperties': False,
               'required': ['title', 'summary', 'tags', 'thumbnail_text', 'thumbnail_tag', 'thumbnail_graphic'],
               'properties': {'title': {'type': 'string', 'minLength': 10, 'maxLength': 70},
                              'summary': {'type': 'string', 'minLength': 40, 'maxLength': 500},
                              'tags': {'type': 'array', 'minItems': 3, 'maxItems': 10, 'items': {'type': 'string', 'maxLength': 30}},
                              'thumbnail_text': {'type': 'string', 'minLength': 3, 'maxLength': 28},
                              'thumbnail_tag': {'type': 'string', 'maxLength': 12},
                              'thumbnail_graphic': {'enum': GRAPHICS}}}


def _ts(t):
    t = int(t); return f'{t // 60}:{t % 60:02d}'


def run(proj, P):
    script = read_json(P / 'script' / 'final.json'); tl = read_json(P / 'render' / 'timeline.json')
    sources = read_json(P / 'research' / 'sources.json')
    narration = ' '.join(s['text'] for s in script['segments'])
    m = llm.complete_json('metadata', f"""Write YouTube metadata for this {'Short' if proj['format'] == 'short' else 'video'} on the
channel "Future Mechanism" (AI & technology explained).
- title: accurate and specific, curiosity without clickbait, no ALL CAPS words, no emojis, ideally under 60 characters
- summary: 2-3 plain sentences saying what the viewer will understand (no hashtags, no links)
- tags: 5-10 search phrases
- thumbnail_text: 2-4 punchy words for the thumbnail (must be true to the content)
- thumbnail_tag: one short label like "Explained"
- thumbnail_graphic: the illustration key (from this list) that best shows the video's idea: {', '.join(GRAPHICS)}

Narration:
{narration}""", META_SCHEMA)
    used = sorted({c['source'] for s in script['segments'] for c in s['claims']}, key=lambda x: int(x[1:]))
    src = {s['id']: s for s in sources}
    lines = [m['summary'], '']
    if tl['chapters'] and len(tl['chapters']) >= 3:
        lines += ['Chapters:'] + [f'{_ts(c["t"])} {c["title"]}' for c in tl['chapters']] + ['']
    if used:
        lines += ['Sources:'] + [f'[{i + 1}] {src[s]["title"]} ({src[s]["publisher"]}) {src[s]["url"]}' for i, s in enumerate(used)] + ['']
    lines += ['Narration uses a synthetic voice. Animations made in code; illustrations: Microsoft Fluent Emoji (MIT License).']
    if proj['format'] == 'short':
        lines += ['', '#Shorts #AI #Technology']
    desc = '\n'.join(lines)
    out = {**m, 'description': desc[:4900], 'tags': m['tags'] + [f'ytf-{proj["id"]}']}
    write_json(P / 'publish' / 'metadata.json', out)
    return {'title': m['title'], 'thumbnail_text': m['thumbnail_text'], 'sources_cited': len(used)}
