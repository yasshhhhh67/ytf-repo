"""Scene template catalogue: purpose text for the storyboard prompt + JSON Schemas for parameter validation.
Must stay in sync with engine/templates.js."""

import json, re
from pathlib import Path

S = lambda n: {'type': 'string', 'minLength': 1, 'maxLength': n}
CUE = {'type': 'string', 'maxLength': 30, 'description': 'one word from the narration this item appears on'}
GRAPHIC = {'type': 'string', 'pattern': '^[a-z0-9-]{2,40}$', 'description': 'a key from the GRAPHICS list'}
MOTION = {'enum': ['none', 'float', 'pulse', 'wiggle', 'spin', 'bob', 'headShake']}
# Graphics preset: Microsoft Fluent Emoji (MIT). Keys = slug of the curated names in tools/assets/fluent_catalog.json.
_CAT = Path(__file__).resolve().parent.parent / 'tools' / 'assets' / 'fluent_catalog.json'
_DARK = json.loads((_CAT.parent / 'fluent_dark.json').read_text())['dark']     # measured by engine/tools/measure_fluent.mjs
TOO_DARK = {k for k, luma in _DARK.items() if luma < 0.22}                       # invisible on the navy background
GRAPHICS = sorted({re.sub(r'[^a-z0-9]+', '-', n.lower()).strip('-') for n in json.loads(_CAT.read_text())} - TOO_DARK)


def obj(props, required, **kw):
    return {'type': 'object', 'properties': props, 'required': required, 'additionalProperties': False, **kw}


# ---------- cartoon world (engine/world.js): one illustrated world that stays on screen across world_shot scenes ----------
PROP_KINDS = ['tower', 'car', 'phone', 'house', 'building', 'tree', 'server', 'laptop', 'router', 'satellite',
              'person', 'cloud', 'chip', 'robot', 'tunnel', 'lamp']                     # must match engine/world.js
ACTIONS = ['show', 'hide', 'move', 'attach', 'link', 'unlink', 'range', 'range_off', 'badge', 'highlight',
           'activate', 'deactivate', 'pulse', 'label']
ICONS = ['bars0', 'bars1', 'bars2', 'bars3', 'bars4', 'check', 'cross', 'question', 'warn', 'clock', 'bolt']
PID = {'type': 'string', 'pattern': '^[a-z][a-z0-9_]{0,11}$'}
TONE = {'enum': ['yellow', 'red', 'teal', 'dark']}
WORLD = obj({
    'setting': {'enum': ['road', 'city', 'indoor']},
    'props': {'type': 'array', 'minItems': 1, 'maxItems': 14, 'items': obj({
        'id': PID, 'kind': {'enum': PROP_KINDS}, 'graphic': GRAPHIC,
        'x': {'type': 'number', 'minimum': -1000, 'maximum': 6000}, 'y': {'type': 'number', 'minimum': 0, 'maximum': 1200},
        'scale': {'type': 'number', 'minimum': 0.5, 'maximum': 2}, 'label': S(14), 'hidden': {'type': 'boolean'}, 'on': PID},
        ['id', 'x'])},
}, ['setting', 'props'])
WORLD_HELP = f"""WORLD (cartoon look; use it for most of a Short). Define ONE "world" for the whole storyboard: a side-on cartoon
scene on a ground line. "setting": road (road, trees, hills), city (road + skyline) or indoor (floor + wall).
"props": the things in it, each {{"id", "kind" (one of {PROP_KINDS}) OR "graphic" (a GRAPHICS key, for anything the
kinds don't cover), "x" (world position, ground units), optional "y" (height above ground, for flying things),
"scale", "label" (1-2 words shown above it), "hidden" (true = appears later via a "show" action), "on" (id of a prop
it rides on, e.g. a phone "on" a car shows in a bubble above the car)}}. Sizes at scale 1: tower 150 wide x 560 tall,
building 210x440, server 150x290, house 230x215, tree 130x215, car 230x125, person 80x185, laptop 190x120,
router 170x100, chip 170x170, robot 160x210, tunnel 480x300, satellite and cloud float high up. The screen shows about
1000 units across, so things that should be on screen TOGETHER must be within ~800 units of each other; spread the
story left to right (0 to ~3000) and let the camera travel. Keep 3-8 props.
Then each world_shot scene is one camera shot of that world. The world and everything that happened stays from shot
to shot (even if other templates cut in between), so build the explanation up step by step."""


TEMPLATES = {
    'title_card': {
        'purpose': 'Video title or chapter opener. Use at the start of each chapter in long videos.',
        'schema': obj({'kicker': S(22), 'title': S(48), 'subtitle': S(70), 'graphic': GRAPHIC}, ['title']),
    },
    'kinetic_text': {
        'purpose': 'Big statement / hook / punchline in 1-4 short lines, one emphasised word, optional illustration above. Use for hooks and key takeaways.',
        'schema': obj({'lines': {'type': 'array', 'minItems': 1, 'maxItems': 4, 'items': S(26)},
                       'emphasis': S(18), 'graphic': GRAPHIC}, ['lines']),
    },
    'labeled_diagram': {
        'purpose': 'How parts connect: 2-7 labelled boxes with arrows (data flow, system architecture, cause->effect).',
        'schema': obj({'title': S(44),
                       'nodes': {'type': 'array', 'minItems': 2, 'maxItems': 7, 'items': obj(
                           {'id': {'type': 'string', 'pattern': '^[a-z0-9_]{1,12}$'}, 'label': S(22),
                            'highlight': {'type': 'boolean'}}, ['id', 'label'])},
                       'edges': {'type': 'array', 'maxItems': 10, 'items': obj(
                           {'from': S(12), 'to': S(12), 'label': S(14)}, ['from', 'to'])}}, ['nodes', 'edges']),
    },
    'process_flow': {
        'purpose': 'An ordered sequence of 2-5 steps (how something happens step by step).',
        'schema': obj({'title': S(44),
                       'steps': {'type': 'array', 'minItems': 2, 'maxItems': 5, 'items': obj(
                           {'label': S(26), 'detail': S(48), 'cue': CUE}, ['label'])}}, ['steps']),
    },
    'comparison_split': {
        'purpose': 'Contrast two things (A vs B) with 1-3 points each and an optional one-line verdict.',
        'schema': obj({'title': S(44),
                       'left': obj({'heading': S(18), 'points': {'type': 'array', 'minItems': 1, 'maxItems': 3, 'items': S(32)}}, ['heading', 'points']),
                       'right': obj({'heading': S(18), 'points': {'type': 'array', 'minItems': 1, 'maxItems': 3, 'items': S(32)}}, ['heading', 'points']),
                       'verdict': S(40)}, ['left', 'right']),
    },
    'big_number': {
        'purpose': 'One striking number that is stated in the narration, counted up on screen.',
        'schema': obj({'value': {'type': 'number'}, 'prefix': S(3), 'suffix': S(12), 'decimals': {'type': 'integer', 'minimum': 0, 'maximum': 2},
                       'label': S(44), 'context': S(70), 'graphic': GRAPHIC}, ['value', 'label']),
    },
    'bar_chart': {
        'purpose': 'Compare 2-6 quantities. Every value MUST appear in the narration or its cited evidence.',
        'schema': obj({'title': S(48), 'unit': S(10),
                       'bars': {'type': 'array', 'minItems': 2, 'maxItems': 6, 'items': obj(
                           {'label': S(16), 'value': {'type': 'number', 'minimum': 0}, 'highlight': {'type': 'boolean'}, 'cue': CUE},
                           ['label', 'value'])},
                       'source': S(60)}, ['title', 'bars']),
    },
    'recap_list': {
        'purpose': 'Checklist summary of 2-5 takeaways.',
        'schema': obj({'title': S(30), 'items': {'type': 'array', 'minItems': 2, 'maxItems': 5, 'items': S(42)}}, ['title', 'items']),
    },
    'end_card': {
        'purpose': 'Final scene only: the closing payoff line (no teasers for other videos).',
        'schema': obj({'line': S(48), 'graphic': GRAPHIC}, ['line']),
    },
    'parallel_grid': {
        'purpose': 'Sequential vs parallel processing: few big cores working one-by-one vs many small cores at once.',
        'schema': obj({'title': S(44), 'left_label': S(26), 'left_cores': {'type': 'integer', 'minimum': 1, 'maximum': 16},
                       'right_label': S(26), 'right_cores': {'type': 'integer', 'minimum': 32, 'maximum': 1024},
                       'tasks': {'type': 'integer', 'minimum': 32, 'maximum': 1024}, 'task_label': S(10)},
                      ['left_label', 'left_cores', 'right_label', 'right_cores']),
    },
    'matrix_multiply': {
        'purpose': 'Animated matrix multiplication (row x column = one output cell). Small integer matrices (2-3 rows/cols).',
        'schema': obj({'title': S(44),
                       'a': {'type': 'array', 'minItems': 2, 'maxItems': 3, 'items': {'type': 'array', 'minItems': 2, 'maxItems': 3, 'items': {'type': 'integer', 'minimum': 0, 'maximum': 9}}},
                       'b': {'type': 'array', 'minItems': 2, 'maxItems': 3, 'items': {'type': 'array', 'minItems': 2, 'maxItems': 3, 'items': {'type': 'integer', 'minimum': 0, 'maximum': 9}}},
                       'caption': S(60)}, ['a', 'b']),
    },
    'hero_graphic': {
        'purpose': 'ONE big illustration of the thing being discussed (or the analogy), with 0-3 short callout labels. Great for introducing an object or analogy.',
        'schema': obj({'title': S(40), 'graphic': GRAPHIC, 'callouts': {'type': 'array', 'maxItems': 3, 'items': S(22)},
                       'caption': S(60), 'motion': MOTION}, ['graphic']),
    },
    'versus_graphics': {
        'purpose': 'Two illustrations side by side (A vs B) with labels; optional winner. Best for analogies and contrasts (one genius vs a crowd).',
        'schema': obj({'title': S(40),
                       'left': obj({'graphic': GRAPHIC, 'label': S(22), 'sub': S(40), 'motion': MOTION}, ['graphic', 'label']),
                       'right': obj({'graphic': GRAPHIC, 'label': S(22), 'sub': S(40), 'motion': MOTION}, ['graphic', 'label']),
                       'winner': {'enum': ['left', 'right', 'none']}}, ['left', 'right']),
    },
    'crowd': {
        'purpose': 'Many small copies of one illustration working at once (e.g. 64 cooks, 100 workers), optionally next to one big contrasting illustration. Shows "many simple things in parallel".',
        'schema': obj({'title': S(40), 'graphic': GRAPHIC, 'count': {'type': 'integer', 'minimum': 4, 'maximum': 120}, 'label': S(40),
                       'contrast': obj({'graphic': GRAPHIC, 'label': S(30)}, ['graphic', 'label'])}, ['graphic', 'count', 'label']),
    },
    'graphic_steps': {
        'purpose': '2-4 steps, each shown as an illustration with a short label, connected by arrows.',
        'schema': obj({'title': S(40), 'steps': {'type': 'array', 'minItems': 2, 'maxItems': 4, 'items': obj(
            {'graphic': GRAPHIC, 'label': S(30), 'cue': CUE}, ['graphic', 'label'])}}, ['steps']),
    },
    'world_shot': {
        'purpose': ('One camera shot of the cartoon WORLD (see WORLD below): optional big 2-line "title" (hook-style, '
                    '1 "highlight" word shown in yellow), optional "chapter" badge {n, title, sub} that stays until the next '
                    'chapter, optional "callout" pill {text, tone, cue}, "focus" = prop ids the camera frames, and 0-6 '
                    '"actions" played in order (each may have a "cue" word): show/hide target; move target to (prop id or x) '
                    '- cars drive, people walk; attach target to (prop id); link target to (prop id) with style '
                    'signal/data/weak/wire = dotted line with travelling dots; unlink target [to]; range target [r] = dashed '
                    'coverage circle, range_off; badge target with text and/or icon (' + ', '.join(ICONS) + ') and tone, '
                    'badge with neither clears it; highlight target (yellow glow, one at a time; "none" clears); '
                    'activate/deactivate target (tower/router broadcast, screen on); pulse target; label target text.'),
        'schema': obj({'title': S(40), 'highlight': S(16),
                       'chapter': obj({'n': {'type': 'integer', 'minimum': 1, 'maximum': 9}, 'title': S(18), 'sub': S(34)}, ['n', 'title']),
                       'callout': obj({'text': S(28), 'tone': TONE, 'cue': CUE}, ['text']),
                       'focus': {'type': 'array', 'minItems': 1, 'maxItems': 6, 'items': PID},
                       'zoom': {'type': 'number', 'minimum': 0.5, 'maximum': 2.2},
                       'actions': {'type': 'array', 'maxItems': 6, 'items': obj({
                           'do': {'enum': ACTIONS}, 'target': {'type': 'string', 'pattern': '^([a-z][a-z0-9_]{0,11}|none)$'},
                           'to': {'anyOf': [PID, {'type': 'number', 'minimum': -1000, 'maximum': 6000}]},
                           'style': {'enum': ['signal', 'data', 'weak', 'wire']}, 'r': {'type': 'number', 'minimum': 150, 'maximum': 900},
                           'text': S(16), 'icon': {'enum': ICONS}, 'tone': TONE, 'cue': CUE}, ['do', 'target'])}}, []),
    },
    'graphic_flow': {
        'purpose': 'Something travelling between 2-4 illustrated places/things (data from phone to server, power from plug to chip); optional moving packet illustration.',
        'schema': obj({'title': S(40), 'nodes': {'type': 'array', 'minItems': 2, 'maxItems': 4, 'items': obj(
            {'graphic': GRAPHIC, 'label': S(24)}, ['graphic', 'label'])}, 'packet': GRAPHIC}, ['nodes']),
    },
}


def catalogue_text():
    lines = []
    for name, t in TEMPLATES.items():
        lines.append(f'- {name}: {t["purpose"]}\n  params schema: {json.dumps(t["schema"], separators=(",", ":"))}')
    lines.append('\n' + WORLD_HELP)
    lines.append('\nGRAPHICS (illustration keys for every "graphic"/"packet" field; use ONLY these exact keys):\n' + ', '.join(GRAPHICS))
    return '\n'.join(lines)


def _graphic_values(o, out):
    if isinstance(o, dict):
        for k, v in o.items():
            if k in ('graphic', 'packet') and isinstance(v, str): out.append(v)
            else: _graphic_values(v, out)
    elif isinstance(o, list):
        for v in o: _graphic_values(v, out)
    return out


NEEDS = {'move': 'to', 'attach': 'to', 'link': 'to'}


def world_errors(world):
    """Checks on the storyboard's world definition."""
    errs = []
    ids = [p['id'] for p in world['props']]
    if len(set(ids)) != len(ids):
        errs.append('world: duplicate prop ids')
    for p in world['props']:
        if ('kind' in p) == ('graphic' in p):
            errs.append(f'world: prop {p["id"]} needs exactly one of "kind" or "graphic"')
        if 'graphic' in p and p['graphic'] not in GRAPHICS:
            errs.append(f'world: prop {p["id"]} has unknown graphic "{p["graphic"]}"')
        if p.get('on') and (p['on'] not in ids or p['on'] == p['id']):
            errs.append(f'world: prop {p["id"]} is "on" unknown prop "{p["on"]}"')
    return errs


def shot_errors(p, world):
    """Checks on one world_shot against the world (prop ids exist, actions have what they need)."""
    if world is None:
        return ['world_shot used but the storyboard has no "world"']
    ids = {q['id'] for q in world['props']}; errs = []
    for f in p.get('focus', []):
        if f not in ids: errs.append(f'world_shot: focus "{f}" is not a prop id {sorted(ids)}')
    for a in p.get('actions', []):
        if a['target'] != 'none' and a['target'] not in ids:
            errs.append(f'world_shot: {a["do"]} target "{a["target"]}" is not a prop id {sorted(ids)}')
        if a['target'] == 'none' and a['do'] != 'highlight':
            errs.append(f'world_shot: target "none" only works with highlight')
        if a['do'] in NEEDS and 'to' not in a:
            errs.append(f'world_shot: {a["do"]} needs "to"')
        if isinstance(a.get('to'), str) and a['to'] not in ids:
            errs.append(f'world_shot: {a["do"]} to "{a["to"]}" is not a prop id')
        if a['do'] in ('attach', 'link') and not isinstance(a.get('to'), str):
            errs.append(f'world_shot: {a["do"]} "to" must be a prop id')
    if not (p.get('title') or p.get('callout') or p.get('chapter') or p.get('actions')):
        errs.append('world_shot: give it a title, chapter, callout or at least one action (something must happen)')
    if p.get('highlight') and p.get('title') and p['highlight'].lower() not in p['title'].lower().split():
        errs.append('world_shot: "highlight" must be one word of the title')
    return errs


def semantic_errors(name, p):
    """Checks a JSON Schema can't express."""
    errs = [f'{name}: unknown graphic "{g}" (use a key from the GRAPHICS list)' for g in _graphic_values(p, []) if g not in GRAPHICS]
    if name == 'labeled_diagram':
        ids = {n['id'] for n in p['nodes']}
        if len(ids) != len(p['nodes']):
            errs.append('labeled_diagram: duplicate node ids')
        for e in p['edges']:
            if e['from'] not in ids or e['to'] not in ids:
                errs.append(f'labeled_diagram: edge {e["from"]}->{e["to"]} refers to unknown node')
    if name == 'matrix_multiply':
        a, b = p['a'], p['b']
        if len({len(r) for r in a}) != 1 or len({len(r) for r in b}) != 1:
            errs.append('matrix_multiply: rows must have equal length')
        elif len(a[0]) != len(b):
            errs.append('matrix_multiply: columns of a must equal rows of b')
    return errs
