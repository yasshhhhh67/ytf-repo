"""Research: plan sources with the LLM, fetch only allow-listed domains, snapshot text as evidence."""
import time
from urllib.parse import quote, urlparse

import requests
import trafilatura

from . import llm
from .common import UA, config, log, read_json, sha256_bytes, write_json

PLAN_SCHEMA = {
    'type': 'object', 'additionalProperties': False,
    'required': ['angle', 'takeaway', 'wikipedia_titles', 'urls', 'questions'],
    'properties': {
        'angle': {'type': 'string', 'maxLength': 300},
        'takeaway': {'type': 'string', 'maxLength': 300},
        'wikipedia_titles': {'type': 'array', 'minItems': 2, 'maxItems': 6, 'items': {'type': 'string', 'maxLength': 100}},
        'urls': {'type': 'array', 'maxItems': 10, 'items': {'type': 'string', 'maxLength': 300}},
        'questions': {'type': 'array', 'minItems': 3, 'maxItems': 8, 'items': {'type': 'string', 'maxLength': 200}},
    },
}
MAX_CHARS = 14000


def tier(url):
    host = (urlparse(url).hostname or '').lower()
    doms = config('sources.json')['domains']
    best = None
    for d, t in doms.items():
        if host == d or host.endswith('.' + d):
            best = t if best is None else min(best, t)
    return best


def fetch_wikipedia(title):
    r = requests.get('https://en.wikipedia.org/w/api.php', headers={'User-Agent': UA}, timeout=30, params={
        'action': 'query', 'prop': 'extracts|info', 'explaintext': 1, 'redirects': 1, 'inprop': 'url',
        'titles': title, 'format': 'json', 'formatversion': 2})
    r.raise_for_status()
    pages = r.json()['query']['pages']
    if not pages or pages[0].get('missing'):
        return None
    p = pages[0]
    return {'url': p.get('fullurl') or f'https://en.wikipedia.org/wiki/{quote(title)}', 'title': p['title'],
            'publisher': 'Wikipedia', 'text': p.get('extract', '')}


def fetch_url(url):
    r = requests.get(url, headers={'User-Agent': UA}, timeout=30, allow_redirects=True, stream=True)
    if tier(r.url) is None:                                    # redirected off the allowlist
        raise ValueError(f'redirect left allowlist: {r.url}')
    r.raise_for_status()
    body = r.raw.read(3_000_000, decode_content=True)
    if 'html' not in r.headers.get('content-type', ''):
        raise ValueError(f'not html: {r.headers.get("content-type")}')
    text = trafilatura.extract(body.decode(r.encoding or 'utf-8', 'replace'), include_comments=False, include_tables=True) or ''
    meta = trafilatura.extract_metadata(body.decode(r.encoding or 'utf-8', 'replace'))
    return {'url': r.url, 'title': (meta.title if meta and meta.title else url), 'publisher': urlparse(r.url).hostname, 'text': text}


def run(proj, P):
    topic, fmt = proj['topic'], proj['format']
    plan = llm.complete_json('research_plan', f"""Plan research for an educational YouTube {'7-10 minute video' if fmt == 'long' else 'Short'}
for the channel "Future Mechanism" (AI & technology explained for a curious international audience).
Topic: {topic}

Return:
- angle: the specific explanatory angle that makes this video useful and original (not a generic overview)
- takeaway: the one thing a viewer should understand at the end
- wikipedia_titles: exact English Wikipedia article titles that cover the core concepts
- urls: up to 10 specific pages you are confident exist, ONLY from these domains (official docs, papers, universities,
  manufacturers, quality tech press): {', '.join(config('sources.json')['domains'])}
- questions: the key questions the script must answer""", PLAN_SCHEMA)
    write_json(P / 'research' / 'plan.json', plan)

    sources = []
    def add(src, kind):
        if not src or len(src['text']) < 800:
            return
        key = src['url'].split('#')[0].rstrip('/').lower()
        if any(s['url'].split('#')[0].rstrip('/').lower() == key or s['sha256'] == sha256_bytes(src['text'][:MAX_CHARS].encode()) for s in sources):
            log('duplicate source skipped', url=src['url']); return
        t = tier(src['url']) or 3
        n = len(sources) + 1
        text = src['text'][:MAX_CHARS]
        rec = {'id': f'S{n}', 'url': src['url'], 'title': src['title'][:200], 'publisher': src['publisher'],
               'tier': t, 'kind': kind, 'retrieved_at': time.strftime('%Y-%m-%d'), 'sha256': sha256_bytes(text.encode()), 'text': text}
        sources.append(rec)
        log('source ok', id=rec['id'], url=src['url'], chars=len(text), tier=t)

    for title in plan['wikipedia_titles']:
        try:
            add(fetch_wikipedia(title), 'wikipedia')
        except Exception as e:  # noqa: BLE001
            log('wikipedia fetch failed', title=title, err=str(e)[:150])
    for url in plan['urls']:
        if tier(url) is None:
            log('url rejected (not allow-listed)', url=url); continue
        try:
            add(fetch_url(url), 'web')
        except Exception as e:  # noqa: BLE001
            log('url fetch failed', url=url, err=str(e)[:150])
        time.sleep(1)

    if len(sources) < 3:
        raise RuntimeError(f'research: only {len(sources)} usable sources')
    write_json(P / 'research' / 'sources.json', sources)
    return {'sources': len(sources), 'tier1': sum(s['tier'] == 1 for s in sources)}


def pack(P, budget=48000):
    """Source texts for prompts, trimmed to a total character budget (tier 1 sources get more room)."""
    sources = read_json(P / 'research' / 'sources.json')
    weights = {1: 1.5, 2: 1.2, 3: 1.0}
    total_w = sum(weights[s['tier']] for s in sources)
    out = []
    for s in sources:
        n = int(budget * weights[s['tier']] / total_w)
        out.append(f'[{s["id"]}] {s["title"]} ({s["publisher"]}, tier {s["tier"]})\n{s["text"][:n]}')
    return '\n\n'.join(out)
