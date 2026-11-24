"""Storyboard: map script segments to scene templates with validated parameters (LLM output is data, never code)."""
import json, re
from collections import Counter

import jsonschema

from . import llm
from .common import read_json, write_json
from .templates import TEMPLATES, WORLD, catalogue_text, semantic_errors, shot_errors, world_errors

SCENE = {'type': 'object', 'additionalProperties': False, 'required': ['segments', 'template', 'params'],
         'properties': {'segments': {'type': 'array', 'minItems': 1, 'maxItems': 4, 'items': {'type': 'string'}},
                        'template': {'enum': list(TEMPLATES)}, 'params': {'type': 'object'}}}
BOARD_SCHEMA = {'type': 'object', 'additionalProperties': False, 'required': ['scenes'],
                'properties': {'world': WORLD, 'scenes': {'type': 'array', 'minItems': 1, 'items': SCENE}}}
NOT_DATA = ('a', 'b', 'left_cores', 'right_cores', 'tasks', 'decimals', 'to', 'r', 'zoom', 'n', 'x', 'y', 'scale')  # layout numbers, not facts


def _numbers(params):
    out = []
    def walk(x, key=''):
        if isinstance(x, dict):
            for k, v in x.items():
                if k not in NOT_DATA:
                    walk(v, k)
        elif isinstance(x, list):
            for v in x: walk(v, key)
        elif isinstance(x, (int, float)) and not isinstance(x, bool):
            out.append(x)
        elif isinstance(x, str):
            out.extend(float(n.replace(',', '')) for n in re.findall(r'\d[\d,]*(?:\.\d+)?', x))
    walk(params)
    return out


def _num_in(v, text):
    t = text.replace(',', '')
    cands = {f'{v:g}', str(int(v)) if float(v).is_integer() else f'{v}'}
    return any(re.search(r'(?<![\d.])' + re.escape(c) + r'(?![\d])', t) for c in cands)


def make_check(segs, fmt, final_scene_required):
    order = [s['id'] for s in segs]
    by_id = {s['id']: s for s in segs}
    def check(obj):
        errs = []
        flat = [g for sc in obj['scenes'] for g in sc['segments']]
        collapsed = [g for i, g in enumerate(flat) if i == 0 or g != flat[i - 1]]
        if collapsed != order:
            errs.append(f'scenes must cover these segment ids in order (a segment may continue into the next scene); expected {order}; got {flat}')
        if any(flat.count(g) > 3 for g in order):
            errs.append('a segment may be split across at most 3 scenes')
        world = obj.get('world')
        if world:
            errs += world_errors(world)
        for i, sc in enumerate(obj['scenes']):
            t = sc['template']
            bad = [f'scene {i + 1} ({t}) params {"/".join(map(str, e.absolute_path))}: {e.message[:160]}'
                   for e in jsonschema.Draft202012Validator(TEMPLATES[t]['schema']).iter_errors(sc['params'])]
            if bad:                                  # schema errors first; the semantic checks assume a valid shape
                errs += bad; continue
            errs += [f'scene {i + 1}: {m}' for m in semantic_errors(t, sc['params'])]
            if t == 'world_shot':
                errs += [f'scene {i + 1}: {m}' for m in shot_errors(sc['params'], world)]
            text = ' '.join(by_id[g]['text'] + ' ' + ' '.join(c['quote'] for c in by_id[g]['claims']) for g in sc['segments'] if g in by_id)
            for v in _numbers(sc['params']):
                if v > 10 and not _num_in(v, text):
                    errs.append(f'scene {i + 1} ({t}): number {v:g} does not appear in its narration or evidence; do not invent data')
            if t == 'end_card' and i != len(obj['scenes']) - 1:
                errs.append('end_card may only be the last scene')
        if final_scene_required and obj['scenes'] and obj['scenes'][-1]['template'] != 'end_card':
            errs.append('the last scene must be end_card')
        if fmt == 'short':
            need = max(8, round(len(order) * 0.75))
            if len(obj['scenes']) < need:
                errs.append(f'a Short needs at least {need} scenes (a new picture every 3-5 seconds); you gave {len(obj["scenes"])}')
            if any(len(sc['segments']) > 2 for sc in obj['scenes']):
                errs.append('in a Short each scene may cover at most 2 segments')
        if fmt == 'long' and any(len(sc['segments']) > 2 for sc in obj['scenes']):
            errs.append('in a long video each scene may cover at most 2 segments (a new picture every few sentences)')
        with_g = sum(1 for sc in obj['scenes'] if '"graphic"' in json.dumps(sc['params']) or sc['template'] in ('crowd', 'graphic_flow', 'world_shot'))
        shots = sum(1 for sc in obj['scenes'] if sc['template'] == 'world_shot')
        if fmt == 'short' and shots < 0.5 * len(obj['scenes']):
            errs.append(f'only {shots} of {len(obj["scenes"])} scenes are world_shot; a Short is told in ONE cartoon world, so at least half must be world_shot (cut to other templates only for a number, a comparison or the end)')
        plain = len(obj['scenes']) - with_g
        if fmt == 'short' and plain > 2:
            errs.append(f'{plain} scenes have no illustration; a Short may have at most 2 (use hero_graphic, versus_graphics, crowd, graphic_steps, graphic_flow, or add a "graphic")')
        if fmt == 'long' and len(obj['scenes']) >= 4 and with_g < 0.4 * len(obj['scenes']):
            errs.append(f'only {with_g} of {len(obj["scenes"])} scenes show an illustration; at least 40% must')
        cnt = Counter(sc['template'] for sc in obj['scenes'])
        if fmt == 'long' and len(obj['scenes']) >= 8:
            for t, n in cnt.items():
                if t != 'world_shot' and n / len(obj['scenes']) > 0.4:
                    errs.append(f'template {t} is used for {n} of {len(obj["scenes"])} scenes; vary the visuals (max 40%)')
        for a, b, c in zip(obj['scenes'], obj['scenes'][1:], obj['scenes'][2:]):
            if a['template'] == b['template'] == c['template'] != 'world_shot':
                errs.append(f'three {a["template"]} scenes in a row; vary the visuals'); break
        return errs
    return check


def run(proj, P):
    script = read_json(P / 'script' / 'final.json'); fmt = proj['format']
    chapters = {c['id']: c['title'] for c in script['chapters']}
    groups = [script['segments']] if fmt == 'short' else [
        [s for s in script['segments'] if s['chapter'] == cid] for cid in chapters]
    groups = [g for g in groups if g]
    scenes, worlds = [], []
    for gi, segs in enumerate(groups):
        last = gi == len(groups) - 1
        aspect = 'vertical 9:16 phone Short' if fmt == 'short' else 'horizontal 16:9 video'
        pace = ('a new picture every 3-5 seconds, at least 8 scenes; one scene per segment, and you may split a segment with two visual ideas across 2 consecutive scenes (list its id in both)' if fmt == 'short'
                else 'one scene per 1-2 segments (a new picture every 5-10 seconds)')
        chapter_rule = ('' if fmt == 'short' else
                        f'This is chapter "{chapters[segs[0]["chapter"]]}". ' +
                        ('Start with title_card for the video title (kicker "Explained").' if gi == 0 else 'Start with a title_card naming this chapter (kicker "Part ' + str(gi) + '").'))
        board = llm.complete_json(f'storyboard_{gi + 1}', f"""Create the storyboard for part of a {aspect} explainer.
{chapter_rule}
Pacing: {pace}. Pick the template that best EXPLAINS each idea visually (diagrams, flows, comparisons, numbers),
not decoration.
LOOK: a flat cartoon explainer. {'Tell this Short inside ONE cartoon world: define "world" with the few things the story is about (placed left to right in story order), then show it as a run of world_shot scenes. Each shot moves the camera (focus) and makes something happen (a car drives, a link appears, a badge changes) right when the narration says it, using "cue" words. Use chapter badges (n 1, 2, 3) for the main beats, a short callout pill for the key idea of a shot, and a big title only on the hook shot. At least half the scenes must be world_shot; cut away only for a striking number (big_number), a comparison, or the end_card.' if fmt == 'short' else 'Where the chapter explains how something physically works (signals, devices, data moving between places), define a "world" for this chapter and show it with world_shot scenes; use the other templates for structure, numbers and comparisons.'} Make the video's central analogy visible on screen with ILLUSTRATIONS (hero_graphic, versus_graphics,
crowd, graphic_steps, graphic_flow, or a "graphic" on kinetic_text/title_card/big_number/end_card). Shorts: at most 2
scenes without an illustration. Long videos: at least 40% of scenes with an illustration. Use plain diagrams/charts
only where the exact structure or numbers matter. On-screen words must be as simple as the narration
(no jargon the narration didn't explain). Prefer topic-specific visuals: matrix_multiply for matrix math, parallel_grid for parallel vs sequential
work, labeled_diagram for how components connect. On-screen text must be short, accurate and match what is said;
never put a number on screen that isn't in the narration or its evidence. Use "cue" words (copied from the narration)
so items appear when they are spoken. {'Shorts: the first scene shows the hook instantly: a world_shot with the hook as its "title" (2-5 words, one highlight word), or kinetic_text in 1-3 big lines (2-4 words each).' if fmt == 'short' else ''}
{'The last scene must be end_card.' if last else 'Do not use end_card.'}

Templates:
{catalogue_text()}

Segments to cover, in order (ids, narration, evidence):
{[{'id': s['id'], 'text': s['text'], 'evidence': [c['quote'] for c in s['claims']]} for s in segs]}""",
            BOARD_SCHEMA, check=make_check(segs, fmt, last), timeout=600)
        if board.get('world'):                       # each storyboard call (the Short, or one chapter) has its own world
            worlds.append(board['world'])
            for sc in board['scenes']:
                if sc['template'] == 'world_shot':
                    sc['world'] = len(worlds) - 1
        scenes += board['scenes']
    write_json(P / 'storyboard.json', {'scenes': scenes, 'worlds': worlds})
    return {'scenes': len(scenes), 'templates': dict(Counter(s['template'] for s in scenes))}
