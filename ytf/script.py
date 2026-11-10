"""Script writing in two steps (story outline with verified facts -> narration) plus evidence verification.
Facts are selected and quote-checked in the outline step; the narration may only use those facts."""
import re

from rapidfuzz import fuzz

from . import llm, research
from .common import log, read_json, write_json

WORDS = {'long': (1050, 1400), 'short': (95, 135)}
BANNED = ['in this video', "let's dive", 'dive in', 'buckle up', 'game-changer', 'game changer', 'revolutionary',
          'have you ever wondered', 'in today', 'without further ado', 'mind-blowing', 'unlock the', 'delve']

VOICE_GUIDE = """Channel voice ("Future Mechanism"): a brilliant teacher explaining to a smart, curious 15-year-old.
- Start from what the viewer can picture; introduce each technical term only when needed and explain it in plain words
  the moment it appears. Prefer concrete images and everyday analogies over jargon.
- No trivia (people's names, dates, product model numbers, units like "mebibyte") unless it truly helps understanding.
- Short spoken sentences (aim for 10-16 words, never more than 28). Contractions are fine. At most one number per sentence.
- Honest and precise, no hype, no filler phrases ("in this video", "let's dive in", "buckle up", "game-changer",
  "revolutionary", "mind-blowing", "delve"), no rhetorical "have you ever wondered".
- Write numbers as digits ("3 nanometers")."""

FACT = {'type': 'object', 'additionalProperties': False, 'required': ['id', 'fact', 'source', 'quote'],
        'properties': {'id': {'type': 'string', 'pattern': '^F[0-9]{1,2}$'}, 'fact': {'type': 'string', 'maxLength': 220},
                       'source': {'type': 'string', 'pattern': '^S[0-9]+$'}, 'quote': {'type': 'string', 'minLength': 15, 'maxLength': 400}}}
OUTLINE_SCHEMA = {'type': 'object', 'additionalProperties': False, 'required': ['title', 'hook', 'big_idea', 'chapters', 'facts'],
                  'properties': {'title': {'type': 'string', 'maxLength': 80}, 'hook': {'type': 'string', 'maxLength': 300},
                                 'big_idea': {'type': 'string', 'maxLength': 300},
                                 'chapters': {'type': 'array', 'minItems': 1, 'maxItems': 8, 'items': {
                                     'type': 'object', 'additionalProperties': False, 'required': ['id', 'title', 'goal', 'beats', 'analogy', 'facts'],
                                     'properties': {'id': {'type': 'string', 'pattern': '^c[0-9]$'}, 'title': {'type': 'string', 'maxLength': 40},
                                                    'goal': {'type': 'string', 'maxLength': 200},
                                                    'beats': {'type': 'array', 'minItems': 1, 'maxItems': 8, 'items': {'type': 'string', 'maxLength': 200}},
                                                    'analogy': {'type': 'string', 'maxLength': 250},
                                                    'facts': {'type': 'array', 'items': {'type': 'string'}}}}},
                                 'facts': {'type': 'array', 'minItems': 4, 'maxItems': 24, 'items': FACT}}}
SEGMENT = {'type': 'object', 'additionalProperties': False, 'required': ['id', 'chapter', 'text', 'facts'],
           'properties': {'id': {'type': 'string', 'pattern': '^g[0-9]{2,3}$'}, 'chapter': {'type': 'string', 'pattern': '^c[0-9]$'},
                          'text': {'type': 'string', 'minLength': 3, 'maxLength': 300},
                          'facts': {'type': 'array', 'maxItems': 3, 'items': {'type': 'string', 'pattern': '^F[0-9]{1,2}$'}}}}
SCRIPT_SCHEMA = {'type': 'object', 'additionalProperties': False, 'required': ['segments'],
                 'properties': {'segments': {'type': 'array', 'minItems': 5, 'maxItems': 140, 'items': SEGMENT}}}


# ---------------- text checks ----------------
def _norm(t):
    t = t.replace('’', "'").replace('‘', "'").replace('“', '"').replace('”', '"').replace('–', '-').replace('—', '-')
    return re.sub(r'\s+', ' ', t).strip().lower()


def _syll(w):
    w = re.sub(r'[^a-z]', '', w.lower())
    if not w: return 0
    n = len(re.findall(r'[aeiouy]+', w)) - (1 if w.endswith('e') and not w.endswith('le') else 0)
    return max(1, n)


def readability(text):
    sents = [s for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]
    words = re.findall(r"[A-Za-z0-9'-]+", text)
    if not sents or not words: return {'flesch': 100, 'avg': 0, 'max': 0}
    syl = sum(_syll(w) for w in words)
    lens = [len(s.split()) for s in sents]
    return {'flesch': round(206.835 - 1.015 * len(words) / len(sents) - 84.6 * syl / len(words), 1),
            'avg': round(sum(lens) / len(lens), 1), 'max': max(lens)}


def word_count(script):
    return sum(len(s['text'].split()) for s in script['segments'])


def _quote_ok(quote, src_text):
    return fuzz.partial_ratio(_norm(quote), _norm(src_text)) >= 90


# ---------------- step 1: outline ----------------
def _outline_check(sources, fmt):
    by = {s['id']: s['text'] for s in sources}
    def check(o):
        errs = []
        fids = {f['id'] for f in o['facts']}
        for f in o['facts']:
            if f['source'] not in by:
                errs.append(f'{f["id"]}: unknown source {f["source"]}')
            elif not _quote_ok(f['quote'], by[f['source']]):
                errs.append(f'{f["id"]}: quote is not an exact copy of text in {f["source"]}: "{f["quote"][:90]}"')
        for c in o['chapters']:
            for x in c['facts']:
                if x not in fids: errs.append(f'{c["id"]}: unknown fact {x}')
        if fmt == 'long' and not 5 <= len(o['chapters']) <= 8:
            errs.append('long videos need 5-8 chapters')
        return errs
    return check


def outline(proj, P):
    sources = read_json(P / 'research' / 'sources.json'); plan = read_json(P / 'research' / 'plan.json')
    o = llm.complete_json('outline', f"""Plan the story of a 7-10 minute YouTube explainer for the channel "Future Mechanism".
Topic: {proj['topic']}
Angle: {plan['angle']}
Viewer takeaway: {plan['takeaway']}
Questions to answer: {plan['questions']}

Return:
- title: the working title
- hook: the opening 1-2 sentences: a concrete, surprising image or fact that makes people stay (true, from the facts)
- big_idea: the single insight the whole video builds to
- chapters (5-8): c1 = cold open + roadmap; middle chapters build understanding step by step (one idea each, with a
  vivid everyday analogy); one chapter corrects a common misconception; one shows why it matters in daily life; the last
  is a short recap + sign-off. For each: title, goal, beats (the explanation steps), analogy, and the fact ids it uses.
- facts: the 10-20 ESSENTIAL facts the story needs (not trivia), each in plain language, with the source id and a quote
  copied EXACTLY (character for character, 15-400 chars) from that source's text.

{VOICE_GUIDE}

Sources:
{research.pack(P)}""", OUTLINE_SCHEMA, check=_outline_check(sources, 'long'), timeout=900)
    write_json(P / 'script' / 'outline.json', o)
    return o


# ---------------- step 2: narration ----------------
def _script_check(fmt, facts, chapters):
    def check(obj):
        errs = []
        lo, hi = WORDS[fmt]; n = word_count(obj)
        if not lo <= n <= hi:
            errs.append(f'total narration is {n} words; it must be between {lo} and {hi}')
        ids = [s['id'] for s in obj['segments']]
        if len(set(ids)) != len(ids): errs.append('segment ids must be unique')
        for s in obj['segments']:
            if s['chapter'] not in chapters: errs.append(f'{s["id"]}: unknown chapter {s["chapter"]}')
            for f in s['facts']:
                if f not in facts: errs.append(f'{s["id"]}: unknown fact {f}')
            low = s['text'].lower()
            for b in BANNED:
                if b in low: errs.append(f'{s["id"]}: banned phrase "{b}"')
            if len(re.findall(r'\d[\d,.]*', s['text'])) > 2: errs.append(f'{s["id"]}: too many numbers in one segment')
        text = ' '.join(s['text'] for s in obj['segments']); r = readability(text)
        if r['flesch'] < 45 or r['avg'] > 17 or r['max'] > 28:
            sents = sorted((x for x in re.split(r'(?<=[.!?])\s+', text) if x.strip()), key=lambda x: -len(x.split()))
            errs.append(f'too hard to follow (reading ease {r["flesch"]}, need 45+; average sentence {r["avg"]} words, need <=17; '
                        f'longest {r["max"]}, need <=28). Split or simplify these sentences first: ' + ' | '.join(sents[:6]))
        return errs
    return check


def _expand(segments, facts):
    """Turn fact ids into claims with exact source quotes for downstream verification."""
    by = {f['id']: f for f in facts}
    return [{**s, 'claims': [{'text': by[f]['fact'], 'source': by[f]['source'], 'quote': by[f]['quote']} for f in s['facts']]}
            for s in segments]


def write_long(proj, P):
    o = outline(proj, P)
    facts = {f['id']: f for f in o['facts']}; chapters = {c['id']: c['title'] for c in o['chapters']}
    s = llm.complete_json('script_long', f"""Write the narration for this YouTube explainer from the story outline below
(about 1,200 words total, 7-9 minutes spoken).

{VOICE_GUIDE}

Rules:
- Follow the outline's chapters and beats. Open with the hook. Use each chapter's analogy.
- State facts ONLY from the fact list; tag each segment with the ids of the facts it relies on ("facts": ["F3"]).
  Explanations, analogies and transitions that add no new factual claim have "facts": [].
- Never copy wording from quotes; say it in your own words.
- A segment is 1-2 spoken sentences. Segment ids g01, g02, ... in order; chapter ids as in the outline.
- The last segment is a one-line sign-off (a natural invitation to follow is fine, no begging).

Outline:
{ {k: v for k, v in o.items() if k != 'facts'} }

Facts:
{[{'id': f['id'], 'fact': f['fact']} for f in o['facts']]}""",
        SCRIPT_SCHEMA, check=_script_check('long', facts, chapters), timeout=900, repairs=2)
    script = {'title': o['title'], 'chapters': [{'id': c['id'], 'title': c['title']} for c in o['chapters']],
              'facts': o['facts'], 'segments': _expand(s['segments'], o['facts'])}
    write_json(P / 'script' / 'v1.json', script)
    return {'words': word_count(script), 'segments': len(script['segments']), 'facts': len(o['facts']),
            **readability(' '.join(x['text'] for x in script['segments']))}


def write_short(proj, P, parent_P):
    sources = read_json(parent_P / 'research' / 'sources.json'); write_json(P / 'research' / 'sources.json', sources)
    parent = read_json(parent_P / 'script' / 'final.json')
    facts = {f['id']: f for f in parent['facts']}
    s = llm.complete_json('script_short', f"""Write a YouTube Short (40-55 seconds, 105-130 words) for "Future Mechanism".
Angle: {proj['topic']}
It is a standalone vertical video (not a trailer) derived from the long video "{parent['title']}".

Shape: the very first sentence is the hook (a surprising, concrete image or fact). Then explain the mechanism simply with
one analogy, add one twist or misconception, and end with a line that loops back to the opening.
Use chapter "c1" for every segment.

{VOICE_GUIDE}

Rules: state facts ONLY from this verified list and tag each segment with the fact ids it uses ("facts": [...]);
segments without new facts have "facts": []. Never copy wording from quotes. Segments are 1-2 short sentences, ids g01...

Facts:
{[{'id': f['id'], 'fact': f['fact']} for f in parent['facts']]}""",
        SCRIPT_SCHEMA, check=_script_check('short', facts, {'c1': 'Short'}), timeout=600, repairs=2)
    script = {'title': proj['topic'], 'chapters': [{'id': 'c1', 'title': 'Short'}], 'facts': parent['facts'],
              'segments': _expand(s['segments'], parent['facts'])}
    write_json(P / 'script' / 'v1.json', script)
    return {'words': word_count(script), 'segments': len(script['segments']), **readability(' '.join(x['text'] for x in script['segments']))}


# ---------------- verification ----------------
VERDICT_SCHEMA = {'type': 'object', 'additionalProperties': False, 'required': ['verdicts'], 'properties': {'verdicts': {
    'type': 'array', 'items': {'type': 'object', 'additionalProperties': False, 'required': ['key', 'verdict', 'reason'],
                               'properties': {'key': {'type': 'string'}, 'verdict': {'enum': ['SUPPORTED', 'PARTIAL', 'UNSUPPORTED']},
                                              'reason': {'type': 'string', 'maxLength': 300}}}}}}
NUM = re.compile(r'(?<![\w.])\d[\d,]*(?:\.\d+)?')


def _ngrams(text, n=8):
    w = re.findall(r"[a-z0-9']+", text.lower())
    return {' '.join(w[i:i + n]) for i in range(len(w) - n + 1)}


def deterministic_issues(script, sources):
    src = {s['id']: s['text'] for s in sources}
    src_grams = set().union(*(_ngrams(s['text']) for s in sources))
    issues = {}
    for seg in script['segments']:
        errs = []
        for c in seg['claims']:
            if not _quote_ok(c['quote'], src.get(c['source'], '')):
                errs.append(f'quote not found in {c["source"]}: "{c["quote"][:80]}"')
        evidence = ' '.join(_norm(c['quote']) + ' ' + _norm(c['text']) for c in seg['claims']).replace(',', '')
        for n in NUM.findall(seg['text']):
            v = n.replace(',', '').rstrip('.')
            if v and float(v) > 10 and v not in evidence:
                errs.append(f'the number {n} is not supported by this segment\'s facts')
        copied = sorted(_ngrams(seg['text']) & src_grams)
        if copied:
            errs.append(f'copies source wording ("{copied[0]}"); rewrite that part in different words')
        if errs:
            issues[seg['id']] = errs
    return issues


def llm_issues(segments):
    items = [{'key': f'{seg["id"]}#{i}', 'segment_text': seg['text'], 'quote': c['quote']}
             for seg in segments for i, c in enumerate(seg['claims'])]
    if not items:
        return {}
    keys = {i['key'] for i in items}
    v = llm.complete_json('verify_claims', f"""You are a strict fact-checker. For each item decide whether the QUOTE supports what
SEGMENT_TEXT asserts. SUPPORTED = everything factual in the segment text that relates to this quote is backed by it
(simplified wording and analogies are fine if they don't change the meaning); PARTIAL = exaggerated, wrong number,
missing an important qualifier, or adds a factual claim the quote doesn't make; UNSUPPORTED = contradicts or unrelated.
Be strict about numbers, superlatives ("first", "fastest", "only") and causal claims. One verdict per key.

Items:
{items}""", VERDICT_SCHEMA, order=('gemini', 'agy'),
        check=lambda o: [] if {x['key'] for x in o['verdicts']} >= keys else ['missing verdicts for some keys'])
    issues = {}
    for x in v['verdicts']:
        if x['verdict'] != 'SUPPORTED' and x['key'] in keys:
            issues.setdefault(x['key'].split('#')[0], []).append(f'{x["verdict"]}: {x["reason"]}')
    return issues


def verify(proj, P):
    sources = read_json(P / 'research' / 'sources.json'); script = read_json(P / 'script' / 'v1.json')
    facts = script['facts']; report = []; approved = {}            # segment id -> text the LLM approved
    for loop in range(4):
        issues = deterministic_issues(script, sources)
        todo = [s for s in script['segments'] if s['id'] not in issues and s['claims'] and approved.get(s['id']) != s['text']]
        for k, v in llm_issues(todo).items():
            issues.setdefault(k, []).extend(v)
        for s in todo:
            if s['id'] not in issues: approved[s['id']] = s['text']
        report.append({'loop': loop, 'issues': issues}); log('verify', loop=loop, segments_with_issues=len(issues))
        if not issues or loop == 3:
            break
        bad = [s for s in script['segments'] if s['id'] in issues]
        ctx = {s['id']: s['text'] for s in script['segments']}
        fix_schema = {'type': 'object', 'additionalProperties': False, 'required': ['segments'],
                      'properties': {'segments': {'type': 'array', 'items': SEGMENT}}}
        fixed = llm.complete_json('revise_segments', f"""These narration segments failed fact-checking. Rewrite ONLY these segments.
Keep the same ids and chapters, keep them flowing with their neighbours, and keep the channel voice:
{VOICE_GUIDE}
State only what the listed facts support (soften or drop anything else). Use your own words; never reuse wording from quotes.

Failing segments, their problems, and neighbouring text for context:
{[{'id': s['id'], 'chapter': s['chapter'], 'text': s['text'], 'facts': s['facts'], 'problems': issues[s['id']],
   'previous': ctx.get(f"g{int(s['id'][1:]) - 1:02d}", ''), 'next': ctx.get(f"g{int(s['id'][1:]) + 1:02d}", '')} for s in bad]}

Facts (with their evidence quotes):
{facts}""", fix_schema, check=lambda o: [] if {s['id'] for s in o['segments']} == {s['id'] for s in bad} else ['return exactly the failing segment ids'])
        by_id = {s['id']: s for s in _expand(fixed['segments'], facts)}
        script['segments'] = [by_id.get(s['id'], s) for s in script['segments']]
    write_json(P / 'script' / 'verify_report.json', report)
    remaining = report[-1]['issues']
    if remaining:
        raise RuntimeError(f'verification failed for {len(remaining)} segments: {remaining} (see script/verify_report.json)')
    write_json(P / 'script' / 'final.json', script)
    return {'claims': sum(len(s['claims']) for s in script['segments']), 'loops': len(report), 'words': word_count(script),
            **readability(' '.join(s['text'] for s in script['segments']))}
