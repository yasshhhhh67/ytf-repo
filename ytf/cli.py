"""ytf command line.
  ytf new --format long --topic "How a GPU actually does AI math"     -> prints project id
  ytf derive-short <parent_id> --angle "Why AI runs on GPUs, not CPUs" -> prints project id
  ytf run <project_id> [--until STAGE] [--redo STAGE]                 run stages in order, skipping finished ones
  ytf status <project_id>
Stage results are recorded in projects/<id>/state.json; re-running continues where it stopped."""
import argparse, sys, time, traceback

from . import audio, metadata, publish, qa, render, research, script, storyboard, timeline, voice
from .common import PROJECTS, log, read_json, slug, telegram, write_json

STAGES = [
    ('research', lambda pr, P: research.run(pr, P) if not pr.get('parent') else {'reused_from': pr['parent']}),
    ('script', lambda pr, P: script.write_long(pr, P) if pr['format'] == 'long'
               else script.write_short(pr, P, PROJECTS / pr['parent'] if pr.get('parent') else None)),
    ('verify', script.verify),
    ('storyboard', storyboard.run),
    ('voice', voice.synth),
    ('align', voice.align),
    ('timeline', timeline.run),
    ('audio', audio.run_stage),
    ('metadata', metadata.run),
    ('render', render.run_stage),
    ('qa', qa.run_stage),
    ('upload', publish.run_stage),
]
NAMES = [s for s, _ in STAGES]


def _new(fmt, topic, parent=None):
    pid = time.strftime('%Y%m%d') + '-' + ('s-' if fmt == 'short' else 'l-') + slug(topic, 32)
    P = PROJECTS / pid
    if P.exists():
        sys.exit(f'project exists: {pid}')
    for d in ('research', 'script', 'audio', 'render', 'qa', 'publish'):
        (P / d).mkdir(parents=True)
    write_json(P / 'project.json', {'id': pid, 'format': fmt, 'topic': topic, 'parent': parent, 'created': time.strftime('%Y-%m-%dT%H:%M:%S')})
    write_json(P / 'state.json', {'done': {}, 'failed': None})
    print(pid)


def _run(pid, until=None, redo=None):
    P = PROJECTS / pid; proj = read_json(P / 'project.json'); st = read_json(P / 'state.json')
    if redo:
        for n in NAMES[NAMES.index(redo):]:
            st['done'].pop(n, None)
        write_json(P / 'state.json', st)          # persist now so nobody sees stale "done" marks
    for name, fn in STAGES:
        if name in st['done']:
            continue
        t0 = time.time(); log('stage start', project=pid, stage=name)
        try:
            res = fn(proj, P)
        except Exception as e:  # noqa: BLE001
            st['failed'] = {'stage': name, 'error': str(e)[:2000], 'at': time.strftime('%Y-%m-%dT%H:%M:%S')}
            write_json(P / 'state.json', st)
            log('stage failed', project=pid, stage=name, err=str(e)[:500]); traceback.print_exc()
            telegram(f'❌ {pid}: stage "{name}" failed\n{str(e)[:600]}')
            sys.exit(1)
        st['done'][name] = {'secs': round(time.time() - t0, 1), 'result': res}; st['failed'] = None
        write_json(P / 'state.json', st)
        log('stage done', project=pid, stage=name, secs=round(time.time() - t0, 1), result=res)
        if name == until:
            break


def main():
    ap = argparse.ArgumentParser(prog='ytf'); sub = ap.add_subparsers(dest='cmd', required=True)
    a = sub.add_parser('new'); a.add_argument('--format', choices=['long', 'short'], required=True); a.add_argument('--topic', required=True)
    a = sub.add_parser('derive-short'); a.add_argument('parent'); a.add_argument('--angle', required=True)
    a = sub.add_parser('run'); a.add_argument('project'); a.add_argument('--until', choices=NAMES); a.add_argument('--redo', choices=NAMES)
    a = sub.add_parser('status'); a.add_argument('project')
    sub.add_parser('worker'); sub.add_parser('bot'); sub.add_parser('schedule'); sub.add_parser('cleanup')
    x = ap.parse_args()
    if x.cmd == 'new':
        _new(x.format, x.topic)
    elif x.cmd == 'derive-short':
        # Shorts use only the parent's outline facts (each quote already checked against its source)
        if not (PROJECTS / x.parent / 'script' / 'final.json').exists() and not (PROJECTS / x.parent / 'script' / 'v1.json').exists():
            sys.exit('parent needs a written script (with its fact list) first')
        _new('short', x.angle, parent=x.parent)
    elif x.cmd == 'run':
        _run(x.project, x.until, x.redo)
    elif x.cmd == 'worker':
        from . import auto; auto.worker()
    elif x.cmd == 'bot':
        from . import bot; bot.main()
    elif x.cmd == 'cleanup':
        from . import auto; print(f'freed {auto.cleanup()} MB')
    elif x.cmd == 'schedule':
        from . import auto; print(auto.status_text())
    elif x.cmd == 'status':
        st = read_json(PROJECTS / x.project / 'state.json')
        for n in NAMES:
            d = st['done'].get(n)
            print(f'{n:11s} {"done " + str(d["secs"]) + "s" if d else ("FAILED" if st.get("failed", {}) and st["failed"]["stage"] == n else "-")}')
        if st.get('failed'):
            print('error:', st['failed']['error'][:800])


if __name__ == '__main__':
    main()
