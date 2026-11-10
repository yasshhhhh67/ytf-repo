"""Scene template catalogue: purpose text for the storyboard prompt + JSON Schemas for parameter validation.
Must stay in sync with engine/templates.js."""

S = lambda n: {'type': 'string', 'minLength': 1, 'maxLength': n}
CUE = {'type': 'string', 'maxLength': 30, 'description': 'one word from the narration this item appears on'}


def obj(props, required, **kw):
    return {'type': 'object', 'properties': props, 'required': required, 'additionalProperties': False, **kw}


TEMPLATES = {
    'title_card': {
        'purpose': 'Video title or chapter opener. Use at the start of each chapter in long videos.',
        'schema': obj({'kicker': S(22), 'title': S(48), 'subtitle': S(70)}, ['title']),
    },
    'kinetic_text': {
        'purpose': 'Big statement / hook / punchline in 1-4 short lines, one emphasised word. Use for hooks and key takeaways.',
        'schema': obj({'lines': {'type': 'array', 'minItems': 1, 'maxItems': 4, 'items': S(26)},
                       'emphasis': S(18)}, ['lines']),
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
                       'label': S(44), 'context': S(70)}, ['value', 'label']),
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
        'purpose': 'Final scene only: closing line and an optional teaser for the next video.',
        'schema': obj({'line': S(48), 'next': S(56)}, ['line']),
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
}


def catalogue_text():
    lines = []
    for name, t in TEMPLATES.items():
        lines.append(f'- {name}: {t["purpose"]}\n  params schema: {t["schema"]}')
    return '\n'.join(lines)


def semantic_errors(name, p):
    """Checks a JSON Schema can't express."""
    errs = []
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
