"""Script writing in two steps (story outline with verified facts -> narration) plus evidence verification.
Facts are selected and quote-checked in the outline step; the narration may only use those facts."""
import re

from rapidfuzz import fuzz

from . import llm, research
from .common import log, read_json, write_json

WORDS = {'long': (1050, 1400), 'short': (90, 120)}
BANNED = ['in this video', "let's dive", 'dive in', 'buckle up', 'game-changer', 'game changer', 'revolutionary',
          'have you ever wondered', 'in today', 'without further ado', 'mind-blowing', 'unlock the', 'delve']

VOICE_GUIDE = """Channel voice ("Future Mechanism"): a great teacher explaining to a curious 12-year-old with no tech background.
- One idea per sentence. Everyday words. Short spoken sentences (aim for 8-14 words, never more than 22).
- No jargon. If a technical word is truly needed, say what it means in plain words in the same sentence.
- Make it concrete: carry ONE central everyday analogy through the video and come back to it.
- Show cause and effect ("because...", "so..."). Never leave a step out; never be vague or abstract.
- No trivia (people's names, dates, model numbers, odd units) unless it truly helps understanding.
- Honest and precise: a simplification must still be true. No hype, no filler ("in this video", "let's dive in",
  "buckle up", "game-changer", "revolutionary", "mind-blowing", "delve"), no "have you ever wondered".
- Numbers below ten as words ("two cores", "one step"); larger numbers as digits ("1,024 cores").
- Never repeat an earlier sentence word for word, including in the recap: restate ideas in fresh words."""

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
- chapters (5-7): c1 = cold open + roadmap; then AT MOST 4 core ideas, one per chapter, each one explainable to a
  curious 12-year-old with a vivid everyday analogy; one chapter corrects a common misconception; one shows why it
  matters in daily life; the last is a short recap + sign-off. For each: title, goal, beats (the explanation steps),
  analogy, and the fact ids it uses.
- DROP anything that can only be explained with jargon (rounding modes, register names, architecture acronyms,
  instruction-level details, product model numbers). Depth comes from explaining a few ideas really well, not many.
- facts: the 8-16 ESSENTIAL facts the story needs (not trivia), each in plain language, with the source id and a quote
  copied EXACTLY (character for character, 15-400 chars) from that source's text.

{VOICE_GUIDE}

Sources:
{research.pack(P)}""", OUTLINE_SCHEMA, check=_outline_check(sources, 'long'), timeout=900)
    write_json(P / 'script' / 'outline.json', o)
    return o


# ---------------- step 2: narration ----------------
HOOK_RULES = """HOOK (the most important sentence): segment g01 is the hook. It must stop someone scrolling within 2 seconds:
at most {n} words, a surprising true fact, a bold true claim, or a sharp "why" question about something the viewer
already knows. Do not start with "Forget", "Imagine", "Did you know", "Have you ever", "In this", "Today" or "Picture".
Style examples, not to copy: "Your phone does a trillion sums to answer you." / "This chip is dumb. That's its superpower."
"""
HOOK_WORDS = {'short': 9, 'long': 14}
BAD_OPENERS = ('forget', 'imagine', 'did you know', 'have you ever', 'in this', 'today', 'picture', 'welcome')
CLARITY_SCHEMA = {'type': 'object', 'additionalProperties': False, 'required': ['score', 'hook_ok', 'better_hook', 'issues'],
                  'properties': {'score': {'type': 'integer', 'minimum': 1, 'maximum': 10}, 'hook_ok': {'type': 'boolean'},
                                 'better_hook': {'type': 'string', 'maxLength': 90},
                                 'issues': {'type': 'array', 'maxItems': 20, 'items': {
                                     'type': 'object', 'additionalProperties': False, 'required': ['id', 'severity', 'problem', 'fix'],
                                     'properties': {'id': {'type': 'string'}, 'severity': {'enum': ['low', 'high']},
                                                    'problem': {'type': 'string', 'maxLength': 400}, 'fix': {'type': 'string', 'maxLength': 400}}}}}}


def clarity_review(segments, fmt, raw=False, hook=True, context=''):
    """An independent model reads the script as a 12-year-old would. Returns a list of problems (empty = pass)."""
    r = llm.complete_json('clarity_review', f"""You are a curious 12-year-old with no tech background watching this
{'YouTube Short' if fmt == 'short' else 'YouTube video'} narration. Be honest and demanding. {context}
- score: 1-10, how easy it is to follow and understand on first listen (10 = crystal clear).
- hook_ok: after hearing only the first sentence, would you keep watching? (true only if it creates real curiosity)
- better_hook: if hook_ok is false, a stronger first sentence of at most 9 words that is still true; else ""
- each fix must be ONE complete replacement sentence (not advice), simple, true, that still connects smoothly to
  the sentences before and after it and keeps the same analogy
- issues: every sentence that is confusing, uses an unexplained technical word, is vague or abstract, skips a step,
  or could mislead (an oversimplification that becomes false). severity "high" if it would lose or mislead the viewer.
  Give a concrete simpler rewrite as the fix.

Narration (id: text):
{[f"{s['id']}: {s['text']}" for s in segments]}""", CLARITY_SCHEMA, order=('agy_check', 'agy', 'gemini'))
    log('clarity review', score=r['score'], hook_ok=r['hook_ok'], issues=len(r['issues']))
    errs = []
    if r['score'] < 7:
        errs.append(f'a 12-year-old found this hard to follow (clarity {r["score"]}/10, need 7+); simplify')
    if hook and not r['hook_ok']:
        errs.append('the first sentence does not hook the viewer; write a stronger, more surprising hook')
    errs += [f'{i["id"]}: {i["problem"]} -> try: {i["fix"]}' for i in r['issues'] if i['severity'] == 'high']
    return (errs, r) if raw else errs


def polish(segments, fmt, rounds=2, hook=True, context='', min_score=7):
    """Review -> apply the reviewer's concrete rewrites to flagged sentences -> review again. Converges much faster
    than regenerating the whole script. Facts stay tagged; the verify stage re-checks the final wording."""
    segs = [dict(s) for s in segments]
    for rnd in range(rounds):
        errs, r = clarity_review(segs, fmt, raw=True, hook=hook, context=context)
        if not errs:
            return segs, {'rounds': rnd, 'score': r['score']}
        by = {s['id']: s for s in segs}
        if hook and not r['hook_ok'] and r['better_hook'] and segs:
            segs[0]['text'] = r['better_hook'].strip()
        for i in r['issues']:
            if i['id'] in by and i['fix'].strip() and i['severity'] == 'high':
                by[i['id']]['text'] = i['fix'].strip()
        log('polish applied fixes', round=rnd, fixed=len(r['issues']), score=r['score'])
    errs, r = clarity_review(segs, fmt, raw=True, hook=hook, context=context)
    # A critic always finds something: accept a clear, well-hooked script and surface leftovers as warnings.
    if r['score'] < min_score or (hook and not r['hook_ok']):
        raise RuntimeError(f'clarity review still failing after {rounds} polish rounds (score {r["score"]}, hook_ok {r["hook_ok"]}): {errs[:4]}')
    return segs, {'rounds': rounds, 'score': r['score'], 'notes': [f'{i["id"]}: {i["problem"]}'[:200] for i in r['issues'] if i['severity'] == 'high']}


def _script_check(fmt, facts, chapters):
    def check(obj):
        errs = []
        first = obj['segments'][0]['text'] if obj['segments'] else ''
        if len(first.split()) > HOOK_WORDS[fmt]:
            errs.append(f'the hook (g01) has {len(first.split())} words; it must be at most {HOOK_WORDS[fmt]} words')
        if first.lower().startswith(BAD_OPENERS):
            errs.append(f'the hook starts with a weak opener ("{first.split()[0]}"); open with the surprising fact itself')
        lo, hi = WORDS[fmt]; n = word_count(obj)
        if not lo <= n <= hi:
            errs.append(f'total narration is {n} words; it must be between {lo} and {hi}')
        ids = [s['id'] for s in obj['segments']]
        if len(set(ids)) != len(ids): errs.append('segment ids must be unique')
        if fmt == 'short' and not 9 <= len(ids) <= 16:
            errs.append(f'a Short needs 9-16 segments of one sentence each; you gave {len(ids)}')
        for s in obj['segments']:
            if s['chapter'] not in chapters: errs.append(f'{s["id"]}: unknown chapter {s["chapter"]}')
            for f in s['facts']:
                if f not in facts: errs.append(f'{s["id"]}: unknown fact {f}')
            low = s['text'].lower()
            for b in BANNED:
                if b in low: errs.append(f'{s["id"]}: banned phrase "{b}"')
            if len(re.findall(r'\d[\d,.]*', s['text'])) > 2: errs.append(f'{s["id"]}: too many numbers in one segment')
        text = ' '.join(s['text'] for s in obj['segments']); r = readability(text)
        if r['flesch'] < 50 or r['avg'] > 15 or r['max'] > 22:
            sents = sorted((x for x in re.split(r'(?<=[.!?])\s+', text) if x.strip()), key=lambda x: -len(x.split()))
            errs.append(f'too hard to follow (reading ease {r["flesch"]}, need 50+; average sentence {r["avg"]} words, need <=15; '
                        f'longest {r["max"]}, need <=22). Split or simplify these sentences first: ' + ' | '.join(sents[:6]))
        return errs
    return check


def _expand(segments, facts):
    """Turn fact ids into claims with exact source quotes for downstream verification."""
    by = {f['id']: f for f in facts}
    return [{**s, 'claims': [{'text': by[f]['fact'], 'source': by[f]['source'], 'quote': by[f]['quote']} for f in s['facts']]}
            for s in segments]


def _chapter_check(first, target):
    def check(obj):
        errs = []
        segs = obj['segments']; n = sum(len(x['text'].split()) for x in segs)
        if not 0.7 * target <= n <= 1.35 * target:
            errs.append(f'this chapter has {n} words; aim for about {target} (between {int(0.7 * target)} and {int(1.35 * target)})')
        if first and segs:
            w = segs[0]['text']
            if len(w.split()) > HOOK_WORDS['long']:
                errs.append(f'the hook (first sentence) has {len(w.split())} words; at most {HOOK_WORDS["long"]}')
            if w.lower().startswith(BAD_OPENERS):
                errs.append(f'the hook starts with a weak opener ("{w.split()[0]}")')
        for x in segs:
            low = x['text'].lower()
            for b in BANNED:
                if b in low: errs.append(f'{x["id"]}: banned phrase "{b}"')
            if len(re.findall(r'\d[\d,.]*', x['text'])) > 2: errs.append(f'{x["id"]}: too many numbers in one segment')
        r = readability(' '.join(x['text'] for x in segs))
        if r['flesch'] < 50 or r['avg'] > 15 or r['max'] > 22:
            errs.append(f'too hard to follow (reading ease {r["flesch"]}, need 50+; average sentence {r["avg"]} words, need <=15; longest {r["max"]}, need <=22)')
        return errs
    return check


def write_long(proj, P):
    o = outline(proj, P)
    facts = {f['id']: f for f in o['facts']}; n_ch = len(o['chapters']); target = int(1380 / n_ch)   # fact checks trim ~15%
    seg_schema = {'type': 'object', 'additionalProperties': False, 'required': ['segments'],
                  'properties': {'segments': {'type': 'array', 'minItems': 3, 'maxItems': 30, 'items': SEGMENT}}}
    all_segs, notes, scores, prev_tail = [], [], [], ''
    for ci, ch in enumerate(o['chapters']):
        first, last = ci == 0, ci == n_ch - 1
        ch_facts = [facts[f] for f in ch['facts'] if f in facts]
        for attempt in range(2):
            d = llm.complete_json(f'chapter_{ci + 1}', f"""Write chapter {ci + 1} of {n_ch} of a YouTube explainer narration
    (about {target} words). Video title: "{o['title']}". The big idea of the video: {o['big_idea']}

    This chapter: "{ch['title']}"
    Goal: {ch['goal']}
    Beats to cover, in order: {ch['beats']}
    Analogy to use (carry it through the chapter): {ch['analogy']}
    {'Open the whole video with this hook idea: ' + o['hook'] if first else 'The previous chapter ended with: "' + prev_tail + '". Start with one sentence that connects naturally from there.'}
    {HOOK_RULES.format(n=HOOK_WORDS['long']) if first else ''}
    {'End the video with a short recap of the big idea and a one-line sign-off (a natural invitation to follow is fine).' if last else 'End with a sentence that makes the viewer curious about what comes next.'}

    {VOICE_GUIDE}

    Rules: state facts ONLY from this chapter's fact list and tag each segment with the fact ids it uses ("facts": [...]);
    segments without new facts have "facts": []. Never copy wording from quotes. Each segment is one or two short
    sentences; every sentence follows from the one before. Use chapter id "{ch['id']}" and segment ids g01, g02, ...

    Facts for this chapter:
    {[{'id': f['id'], 'fact': f['fact']} for f in ch_facts]}""", seg_schema, check=_chapter_check(first, target), timeout=600, repairs=2)
            segs = [{**x, 'chapter': ch['id'], 'facts': [f for f in x['facts'] if f in facts]} for x in d['segments']]
            try:
                segs, pol = polish(segs, 'long', hook=first, min_score=7 if (first or attempt == 0) else 6,
                                   context=f'This is chapter {ci + 1} of {n_ch} ("{ch["title"]}") of a longer video; judge it as part of that video.')
                break
            except RuntimeError as e:
                log('chapter redraft', chapter=ch['id'], attempt=attempt, err=str(e)[:200])
                if attempt == 1:
                    raise
        scores.append(pol['score']); notes += pol.get('notes', [])
        all_segs += segs; prev_tail = ' '.join(x['text'] for x in segs[-2:])
        log('chapter written', chapter=ch['id'], words=sum(len(x['text'].split()) for x in segs), clarity=pol['score'])
    for i, x in enumerate(all_segs):                 # renumber across chapters
        x['id'] = f'g{i + 1:02d}'
    script = {'title': o['title'], 'chapters': [{'id': c['id'], 'title': c['title']} for c in o['chapters']],
              'facts': o['facts'], 'segments': _expand(all_segs, o['facts']),
              'polish': {'score': min(scores), 'notes': notes[:6]}}
    n = word_count(script)
    if not 1050 <= n <= 1600:
        raise RuntimeError(f'long script is {n} words (want about 1,350)')
    write_json(P / 'script' / 'v1.json', script)
    return {'words': n, 'segments': len(all_segs), 'facts': len(o['facts']), 'clarity_min': min(scores),
            **readability(' '.join(x['text'] for x in script['segments']))}


SHORT_EXAMPLE = """STYLE EXAMPLE (different topic; copy the style and rhythm, never the content):
g01: Your phone is a tiny heater that also makes calls.
g02: Inside it, billions of tiny switches flip on and off every second.
g03: Think of them as light switches in a huge building.
g04: Every flip lets a little electricity rush through.
g05: And rushing electricity always leaves a bit of heat behind.
g06: One flip makes almost no heat at all.
g07: But billions of flips, every single second, add up fast.
g08: That's why games and videos make it hottest: they need the most flips.
g09: So a warm phone isn't broken. It's just busy.
g10: A tiny heater, working hard, that also makes calls.
Why it works: the hook is a surprising twist on something familiar; ONE analogy (light switches) is introduced in
sentence 3 and every later sentence stays inside it; each sentence follows from the one before ("And", "But", "That's
why", "So"); no sentence introduces a new character or idea out of nowhere; the last line echoes the first."""


def write_short(proj, P, parent_P):
    sources = read_json(parent_P / 'research' / 'sources.json'); write_json(P / 'research' / 'sources.json', sources)
    parent = read_json(parent_P / 'script' / 'final.json') or read_json(parent_P / 'script' / 'v1.json')
    facts = {f['id']: f for f in parent['facts']}
    s = llm.complete_json('script_short', f"""Write a YouTube Short (40-50 seconds, 95-115 words) for "Future Mechanism".
Angle: {proj['topic']}
It is a standalone vertical video (not a trailer) derived from the long video "{parent['title']}".

{HOOK_RULES.format(n=9)}

Shape after the hook: introduce ONE everyday analogy (by sentence 3), explain how it works in two to four simple steps
using that analogy, add one twist or common misconception, and end with a payoff line that echoes the hook so the
video loops. Every sentence must follow from the one before; never introduce a new character, object or idea that
the previous sentence didn't set up. Use chapter "c1" for every segment.

{SHORT_EXAMPLE}

{VOICE_GUIDE}

Rules: use only the 2-4 SIMPLEST facts from this verified list (skip anything that needs technical words to explain)
and tag each segment with the fact ids it uses ("facts": [...]); segments without new facts have "facts": [].
Never copy wording from quotes. Each segment is ONE short sentence (10-15 segments in total, ids g01...), because every
segment becomes its own picture on screen.

Facts:
{[{'id': f['id'], 'fact': f['fact']} for f in parent['facts']]}""",
        SCRIPT_SCHEMA, check=_script_check('short', facts, {'c1': 'Short'}), timeout=600, repairs=2)
    segs, pol = polish(s['segments'], 'short')
    script = {'title': proj['topic'], 'chapters': [{'id': 'c1', 'title': 'Short'}], 'facts': parent['facts'],
              'segments': _expand(segs, parent['facts']), 'polish': pol}
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
    issues = {}; seen = []
    for seg in script['segments']:
        errs = []
        for sid, txt in seen:
            if fuzz.ratio(_norm(seg['text']), txt) >= 85:
                errs.append(f'repeats {sid} almost word for word; say it in fresh words'); break
        seen.append((seg['id'], _norm(seg['text'])))
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
Be strict about numbers, superlatives ("first", "fastest", "only"), causal claims, and SCOPE words: "every", "all",
"always", "never", "most" must match the quote's scope exactly (e.g. "central to all applications of linear algebra"
does NOT support "every computer calculation"). One verdict per key.

Items:
{items}""", VERDICT_SCHEMA, order=('agy_check', 'agy', 'gemini'),
        check=lambda o: [] if {x['key'] for x in o['verdicts']} >= keys else ['missing verdicts for some keys'])
    issues = {}
    for x in v['verdicts']:
        if x['verdict'] != 'SUPPORTED' and x['key'] in keys:
            issues.setdefault(x['key'].split('#')[0], []).append(f'{x["verdict"]}: {x["reason"]}')
    return issues


ASSERT_SCHEMA = {'type': 'object', 'additionalProperties': False, 'required': ['flags'], 'properties': {'flags': {
    'type': 'array', 'items': {'type': 'object', 'additionalProperties': False, 'required': ['id', 'claim'],
                               'properties': {'id': {'type': 'string'}, 'claim': {'type': 'string', 'maxLength': 200}}}}}}


def unsupported_assertions(segments):
    """Segments that cite no facts must not make factual claims. Returns {segment id: [problem]}."""
    items = [{'id': s['id'], 'text': s['text']} for s in segments]
    if not items:
        return {}
    v = llm.complete_json('check_uncited', f"""These narration sentences cite NO evidence. Flag every sentence that states a
specific factual claim a viewer could fact-check: numbers or quantities ("hundreds", "nanoseconds", "most"), how a
specific technology works, history, causes and effects, comparisons, or claims about products and companies.
Do NOT flag: hooks and questions, transitions ("let's see how"), analogies clearly framed as analogies ("it's like..."),
sign-offs, or general restatements that make no new specific claim. Return only the flagged ones (or an empty list).

Sentences:
{items}""", ASSERT_SCHEMA, order=('agy_check', 'agy', 'gemini'))
    ids = {i['id'] for i in items}
    return {f['id']: [f'states a fact without evidence ("{f["claim"]}"): tag a supporting fact, or remove/soften it'] for f in v['flags'] if f['id'] in ids}


def verify(proj, P):
    sources = read_json(P / 'research' / 'sources.json'); script = read_json(P / 'script' / 'v1.json')
    facts = script['facts']; report = []; approved = {}            # segment id -> text the LLM approved
    flagged = {}                                                     # segment id -> text that failed last round
    for loop in range(4):
        issues = deterministic_issues(script, sources)
        for sid, txt in flagged.items():                             # an unchanged rewrite can't pass on a lucky re-check
            cur = next((x['text'] for x in script['segments'] if x['id'] == sid), None)
            if cur == txt:
                issues.setdefault(sid, []).append('unchanged after revision; rewrite it so it is supported')
        todo = [s for s in script['segments'] if s['id'] not in issues and s['claims'] and approved.get(s['id']) != s['text']]
        for k, v in llm_issues(todo).items():
            issues.setdefault(k, []).extend(v)
        uncited = [s for s in script['segments'] if s['id'] not in issues and not s['claims'] and approved.get(s['id']) != s['text']]
        for k, v in unsupported_assertions(uncited).items():
            issues.setdefault(k, []).extend(v)
        todo = todo + uncited
        for s in todo:
            if s['id'] not in issues: approved[s['id']] = s['text']
        report.append({'loop': loop, 'issues': issues}); log('verify', loop=loop, segments_with_issues=len(issues))
        flagged = {sid: next(x['text'] for x in script['segments'] if x['id'] == sid) for sid in issues}
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
Each rewritten segment must have the same number of words as the original or fewer.

Failing segments, their problems, and neighbouring text for context:
{[{'id': s['id'], 'chapter': s['chapter'], 'text': s['text'], 'facts': s['facts'], 'problems': issues[s['id']],
   'previous': ctx.get(f"g{int(s['id'][1:]) - 1:02d}", ''), 'next': ctx.get(f"g{int(s['id'][1:]) + 1:02d}", '')} for s in bad]}

Facts (with their evidence quotes):
{facts}""", fix_schema, check=lambda o: [] if {s['id'] for s in o['segments']} == {s['id'] for s in bad} else ['return exactly the failing segment ids'])
        by_id = {s['id']: s for s in _expand(fixed['segments'], facts)}
        script['segments'] = [by_id.get(s['id'], s) for s in script['segments']]
    remaining = report[-1]['issues']
    # Last resort: drop up to 3 still-failing sentences (never the opening hook) if the script stays long enough.
    lo = WORDS[proj['format']][0] * 0.95
    if remaining and len(remaining) <= 3 and 'g01' not in remaining:
        kept = [s for s in script['segments'] if s['id'] not in remaining]
        if sum(len(s['text'].split()) for s in kept) >= lo:
            report.append({'dropped': {k: {'text': next(s['text'] for s in script['segments'] if s['id'] == k), 'problems': v}
                                       for k, v in remaining.items()}})
            log('verify dropped unsupported segments', ids=list(remaining))
            script['segments'] = kept; remaining = {}
    write_json(P / 'script' / 'verify_report.json', report)
    if word_count(script) > WORDS[proj['format']][1] * 1.05:
        raise RuntimeError(f'script grew to {word_count(script)} words during verification (max {WORDS[proj["format"]][1]})')
    if remaining:
        raise RuntimeError(f'verification failed for {len(remaining)} segments: {remaining} (see script/verify_report.json)')
    write_json(P / 'script' / 'final.json', script)
    return {'claims': sum(len(s['claims']) for s in script['segments']), 'loops': len(report), 'words': word_count(script),
            **readability(' '.join(s['text'] for s in script['segments']))}
