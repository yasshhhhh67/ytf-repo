"""Shared helpers: paths, credentials, JSON I/O, logging, Telegram notifications."""
import hashlib, json, os, re, subprocess, sys, time
from pathlib import Path

import requests

ROOT = Path(os.environ.get('YTF_ROOT', '/srv/ytf'))
APP = ROOT / 'app'
DATA = ROOT / 'data'
PROJECTS = DATA / 'projects'
MODELS = DATA / 'models'
ENGINE = APP / 'engine'
CONFIG = APP / 'config'
UA = 'ytf-research/0.1 (+https://github.com/yasshhhhh67/ytf-repo)'


def log(msg, **kw):
    """Structured log line to stderr (journald). Never pass secrets here."""
    rec = {'ts': time.strftime('%H:%M:%S'), 'msg': msg, **kw}
    print(json.dumps(rec, default=str), file=sys.stderr, flush=True)


def cred(name):
    """Secret from systemd LoadCredentialEncrypted= (preferred) or, as root, systemd-creds decrypt."""
    cd = os.environ.get('CREDENTIALS_DIRECTORY')
    if cd and (Path(cd) / name).exists():
        return (Path(cd) / name).read_text()
    r = subprocess.run(['systemd-creds', 'decrypt', f'--name={name}', f'/etc/credstore.encrypted/{name}', '-'],
                       capture_output=True)
    if r.returncode:
        raise RuntimeError(f'credential {name} unavailable (run via deploy/bin/ytf)')
    return r.stdout.decode()


def read_json(p, default=None):
    p = Path(p)
    return json.loads(p.read_text()) if p.exists() else default


def write_json(p, obj):
    """Atomic write: temp file + rename, so a crash never leaves half-written JSON."""
    p = Path(p); p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + '.tmp')
    tmp.write_text(json.dumps(obj, indent=1, ensure_ascii=False))
    os.replace(tmp, p)


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def slug(text, n=40):
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')[:n].strip('-')


def config(name):
    return json.loads((CONFIG / name).read_text())


def telegram(text):
    """Send a message to the single allow-listed chat. Failures are logged, never raised."""
    try:
        chat = re.search(r'allowed_chat_id\s*=\s*(-?\d+)', Path('/etc/ytf/config.toml').read_text()).group(1)
        tok = cred('ytf.telegram-token').strip()
        r = requests.post(f'https://api.telegram.org/bot{tok}/sendMessage',
                          data={'chat_id': chat, 'text': text[:4000], 'disable_web_page_preview': 'true'}, timeout=20)
        if not r.ok:
            log('telegram failed', status=r.status_code)
    except Exception as e:  # noqa: BLE001 - notifications must never break the pipeline
        log('telegram error', err=type(e).__name__)


def run(cmd, timeout=None, **kw):
    """Run a command, raise with the tail of stderr on failure."""
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, **kw)
    if r.returncode:
        raise RuntimeError(f'{cmd[0]} failed ({r.returncode}): {r.stderr[-1500:]}')
    return r.stdout
