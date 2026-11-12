"""Automatic schedule: one Short every day at 21:00 IST and one long video on the 7th of each month at 21:00 IST.

The worker loop (ytf worker) keeps the next slots filled: it picks a topic, produces the video (uploaded PRIVATE),
then sends an approval card to Telegram. Nothing becomes public without approval: the bot (ytf bot) handles the
Approve / Reject buttons and schedules approved videos with YouTube's publishAt for their slot.
State lives in data/schedule.json, guarded by a file lock because the worker and the bot both update it."""
import fcntl, json, os, subprocess, sys, time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from rapidfuzz import fuzz

from . import llm
from .common import DATA, PROJECTS, log, read_json, slug, telegram, write_json

IST = timezone(timedelta(hours=5, minutes=30))
SLOT_TIME = (21, 0)                               # 9:00 PM IST
LONG_DAY = 7                                      # long video on the 7th
LEAD = {'short': timedelta(hours=33), 'long': timedelta(days=6)}
RETRIES = 3
STATE = DATA / 'schedule.json'
LOCK = DATA / 'schedule.lock'


# ---------------- state ----------------
@contextmanager
def state():
    """Read-modify-write the schedule under an exclusive lock."""
    LOCK.touch(exist_ok=True)
    with open(LOCK) as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        st = read_json(STATE, None) or {'slots': {}, 'topics': {'short': [], 'long': []}, 'used': [], 'paused': False,
                                         'stats': {'approved_in_a_row': 0}, 'tg_offset': 0}
        yield st
        write_json(STATE, st)


def slot_key(dt):
    return dt.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def ist(dt_key):
    return datetime.strptime(dt_key, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc).astimezone(IST)


def upcoming_slots(now):
    """Slots whose production window is open: Shorts for the next 2 days, the long video for the next 7th."""
    out = []
    today = now.astimezone(IST).date()
    for d in range(0, 3):
        day = today + timedelta(days=d)
        t = datetime(day.year, day.month, day.day, *SLOT_TIME, tzinfo=IST)
        if t > now and t - LEAD['short'] <= now:
            out.append(('short', t))
    for m in range(0, 2):
        y, mo = today.year + (today.month - 1 + m) // 12, (today.month - 1 + m) % 12 + 1
        t = datetime(y, mo, LONG_DAY, *SLOT_TIME, tzinfo=IST)
        if t > now and t - LEAD['long'] <= now:
            out.append(('long', t))
    return sorted(out, key=lambda x: x[1])


# ---------------- topics ----------------
TOPICS_SCHEMA = {'type': 'object', 'additionalProperties': False, 'required': ['topics'],
                 'properties': {'topics': {'type': 'array', 'minItems': 5, 'maxItems': 25, 'items': {
                     'type': 'string', 'minLength': 15, 'maxLength': 140}}}}


def refill_topics(st, fmt, want):
    """Ask the LLM for fresh evergreen topics, dropping near-duplicates of anything used or queued."""
    have = st['topics'][fmt]; used = st['used']
    if len(have) >= want:
        return
    kind = ('45-second YouTube Shorts: ONE surprising, concrete question each, answerable simply'
            if fmt == 'short' else '7-9 minute explainer videos: a bigger "how does X actually work" question each')
    r = llm.complete_json(f'topics_{fmt}', f"""Suggest 20 topic angles for {kind}, for the channel "Future Mechanism"
(AI & technology explained simply for a curious international audience).
Mix: how AI works, chips and computers, the internet and phones, future technology, robots, everyday tech.
Evergreen (still true in 2 years), explainable with an everyday analogy, factual (no news, no health/finance advice,
no claims about specific living people). Write each as a short phrase, e.g. "Why your phone gets warm when gaming".
Already done or planned (do NOT repeat or closely rephrase): {used[-200:] + have}""", TOPICS_SCHEMA)
    for t in r['topics']:
        if all(fuzz.token_set_ratio(t.lower(), x.lower()) < 80 for x in used + have):
            have.append(t)
    log('topics refilled', format=fmt, queued=len(have))


# ---------------- production ----------------
def new_project(fmt, topic):
    pid = datetime.now(IST).strftime('%Y%m%d') + ('-s-' if fmt == 'short' else '-l-') + slug(topic, 32)
    n, base = 2, pid
    while (PROJECTS / pid).exists():
        pid = f'{base}-{n}'; n += 1
    P = PROJECTS / pid
    for d in ('research', 'script', 'audio', 'render', 'qa', 'publish'):
        (P / d).mkdir(parents=True)
    write_json(P / 'project.json', {'id': pid, 'format': fmt, 'topic': topic, 'parent': None, 'auto': True,
                                    'created': datetime.now(timezone.utc).isoformat()})
    write_json(P / 'state.json', {'done': {}, 'failed': None})
    return pid


def produce(pid):
    """Run the whole pipeline in a child process (keeps the worker small; output goes to the journal)."""
    r = subprocess.run([sys.executable, '-m', 'ytf.cli', 'run', pid], cwd='/srv/ytf/app')
    return r.returncode == 0


def approval_card(fmt, pid, slot_k):
    from .common import cred
    import requests, re
    from pathlib import Path
    P = PROJECTS / pid
    meta = read_json(P / 'publish' / 'metadata.json'); up = read_json(P / 'publish' / 'upload.json'); qa = read_json(P / 'qa' / 'report.json')
    when = ist(slot_k).strftime('%a %d %b, 9:00 PM IST')
    text = (f'🎬 New {"Short" if fmt == "short" else "LONG video"} for {when}\n{meta["title"]}\n'
            f'Watch (private): https://youtu.be/{up["video_id"]}\n'
            f'{qa["info"]["duration"]:.0f}s · {qa["info"]["claims"]} sourced claims · clarity {qa["info"].get("clarity")}/10\n'
            + (('⚠️ ' + ' / '.join(x[:160] for x in qa['soft'])) if qa['soft'] else '✅ no QA warnings')
            + '\nNothing goes public unless you approve.')
    chat = re.search(r'allowed_chat_id\s*=\s*(-?\d+)', Path('/etc/ytf/config.toml').read_text()).group(1)
    tok = cred('ytf.telegram-token').strip()
    kb = {'inline_keyboard': [[{'text': '✅ Approve', 'callback_data': f'ok:{pid}'[:64]},
                               {'text': '❌ Reject', 'callback_data': f'no:{pid}'[:64]}]]}
    requests.post(f'https://api.telegram.org/bot{tok}/sendMessage', timeout=20,
                  data={'chat_id': chat, 'text': text[:4000], 'reply_markup': json.dumps(kb), 'disable_web_page_preview': 'true'})


def worker_step():
    now = datetime.now(timezone.utc)
    with state() as st:
        if st['paused']:
            return
        # mark slots that passed without an approved video
        for k, s in st['slots'].items():
            if ist(k) <= now and s['status'] in ('producing', 'ready', 'failed', 'rejected'):
                s['status'] = 'missed'
                telegram(f'⏰ Missed slot {ist(k):%a %d %b 9 PM IST}: no approved {s["format"]} (project {s.get("project")}).')
        todo = None
        for fmt, t in upcoming_slots(now):
            k = slot_key(t); s = st['slots'].get(k)
            if s is None or (s['status'] in ('failed', 'rejected') and s.get('attempts', 0) < RETRIES):
                refill_topics(st, fmt, 6 if fmt == 'short' else 2)
                if not st['topics'][fmt]:
                    continue
                topic = st['topics'][fmt].pop(0); st['used'].append(topic)
                pid = new_project(fmt, topic)
                st['slots'][k] = {'format': fmt, 'project': pid, 'status': 'producing', 'topic': topic,
                                  'attempts': (s or {}).get('attempts', 0) + 1}
                todo = (fmt, k, pid); break
    if not todo:
        return
    fmt, k, pid = todo
    telegram(f'🛠 Producing {fmt} for {ist(k):%a %d %b 9 PM IST}: "{read_json(PROJECTS / pid / "project.json")["topic"]}"')
    ok = produce(pid)
    with state() as st:
        s = st['slots'][k]
        s['status'] = 'ready' if ok else 'failed'
        if ok:
            s['video_id'] = read_json(PROJECTS / pid / 'publish' / 'upload.json')['video_id']
    if ok:
        approval_card(fmt, pid, k)
    else:
        err = (read_json(PROJECTS / pid / 'state.json') or {}).get('failed') or {}
        telegram(f'❌ {fmt} for {ist(k):%d %b} failed at "{err.get("stage")}" (attempt {s["attempts"]}/{RETRIES}); '
                 + ('will retry with a new topic.' if s['attempts'] < RETRIES else 'giving up on this slot.'))


def worker():
    log('worker started')
    while True:
        try:
            worker_step()
        except Exception as e:  # noqa: BLE001 - keep the loop alive; report and continue
            log('worker error', err=str(e)[:500])
            telegram(f'⚠️ worker error: {str(e)[:300]}')
        time.sleep(300)


# ---------------- approvals (used by the bot) ----------------
def schedule_publish(pid):
    """Approve: schedule the private video for its slot (or the next free 9 PM slot if that already passed)."""
    sys.path.insert(0, '/srv/ytf/app/tools/phase0')
    from yt_client import youtube
    now = datetime.now(timezone.utc)
    with state() as st:
        k, s = next(((k, s) for k, s in st['slots'].items() if s.get('project') == pid), (None, None))
        if not s:
            return 'unknown project'
        if s['status'] in ('approved', 'scheduled', 'published'):
            return f'already {s["status"]}'
        when = ist(k)
        if when <= now + timedelta(minutes=15):           # late: next 9 PM that has nothing scheduled
            d = now.astimezone(IST).date()
            while True:
                cand = datetime(d.year, d.month, d.day, *SLOT_TIME, tzinfo=IST)
                if cand > now + timedelta(minutes=15) and not any(
                        x['status'] in ('approved', 'scheduled') and x['format'] == s['format'] and ist(kk) == cand
                        for kk, x in st['slots'].items()):
                    when = cand; break
                d += timedelta(days=1)
        yt = youtube(); vid = s['video_id']
        cur = yt.videos().list(part='status', id=vid).execute()['items'][0]['status']
        body = {k2: v for k2, v in cur.items() if k2 in ('embeddable', 'license', 'publicStatsViewable', 'selfDeclaredMadeForKids', 'containsSyntheticMedia')}
        body.update(privacyStatus='private', publishAt=when.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))
        yt.videos().update(part='status', body={'id': vid, 'status': body}).execute()
        s['status'] = 'scheduled'; s['publish_at'] = slot_key(when)
        st['stats']['approved_in_a_row'] = st['stats'].get('approved_in_a_row', 0) + 1
        return f'scheduled for {when:%a %d %b, %I:%M %p} IST'


def reject(pid):
    with state() as st:
        s = next((s for s in st['slots'].values() if s.get('project') == pid), None)
        if not s:
            return 'unknown project'
        if s['status'] == 'scheduled':
            return 'already scheduled; use /unschedule first'
        s['status'] = 'rejected'; st['stats']['approved_in_a_row'] = 0
        return 'rejected; a replacement will be produced if there is time'


def status_text():
    with state() as st:
        rows = [f'{ist(k):%a %d %b} {s["format"]:5s} {s["status"]:9s} {s.get("topic", "")[:40]}'
                for k, s in sorted(st['slots'].items())[-10:]]
        return ('⏸ PAUSED\n' if st['paused'] else '') + '\n'.join(rows or ['no slots yet']) + \
            f'\nqueue: {len(st["topics"]["short"])} short / {len(st["topics"]["long"])} long topics' + \
            f'\napproved in a row: {st["stats"].get("approved_in_a_row", 0)}'
