"""LLM adapter. Providers in order: Antigravity CLI (subscription, headless) -> Gemini API free tier.
Every call returns a JSON object validated against a JSON Schema; invalid output gets one repair attempt per provider.
A circuit breaker disables a provider for the rest of the run after an auth/quota failure."""
import json, re, subprocess, time

import jsonschema
import requests

from .common import DATA, cred, log

PREAMBLE = ('You are one step in an automated video-production pipeline. Do not use any tools, do not read or write '
            'files, do not run commands, do not browse. Reply with ONE JSON object only: no markdown fences, no prose.\n\n')
AGY_MAX_BYTES = 120_000          # Linux limits a single argv string to 128 KiB
GEMINI_MODELS = ['gemini-flash-latest', 'gemini-flash-lite-latest']   # fall back to Lite when Flash is overloaded
_broken = set()


class LLMError(RuntimeError):
    pass


def _extract_json(text):
    t = text.strip()
    t = re.sub(r'^```(?:json)?\s*|\s*```$', '', t)
    a, b = t.find('{'), t.rfind('}')
    if a < 0 or b < a:
        raise ValueError('no JSON object in response')
    return json.loads(t[a:b + 1])


CHECK_MODEL = 'Claude Sonnet 4.6 (Thinking)'      # independent checker; offered on this plan until 18 Nov 2026


def _agy(prompt, timeout, model='', name='agy'):
    if len(prompt.encode()) > AGY_MAX_BYTES:
        raise LLMError('prompt too large for agy')
    r = subprocess.run(['sudo', '-n', '-H', '-u', 'ytf-llm', '/usr/local/libexec/ytf-agy'] + ([model] if model else []),
                       input=prompt, capture_output=True, text=True, timeout=timeout)
    if r.returncode:
        err = (r.stderr or r.stdout)[-400:]
        if re.search(r'auth|sign.?in|login|quota|limit|429|permission|not recognized|not allowed|not available', err, re.I):
            _broken.add(name)
        raise LLMError(f'{name} exit {r.returncode}: {err}')
    out = json.loads(r.stdout)
    if out.get('status') != 'SUCCESS':
        raise LLMError(f'agy status {out.get("status")}')
    return out['response']


def _gemini(prompt, timeout):
    key = cred('ytf.gemini-key').strip()
    for model, wait in ((GEMINI_MODELS[0], 30), (GEMINI_MODELS[0], 60), (GEMINI_MODELS[1], 30), (GEMINI_MODELS[1], None)):
        r = requests.post(f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',
                          headers={'x-goog-api-key': key, 'Content-Type': 'application/json'}, timeout=timeout,
                          json={'contents': [{'parts': [{'text': prompt}]}],
                                'generationConfig': {'responseMimeType': 'application/json', 'temperature': 0.6}})
        if r.status_code not in (500, 503) or wait is None:
            break
        time.sleep(wait)
    if r.status_code in (401, 403, 429):
        _broken.add('gemini')
    if not r.ok:
        raise LLMError(f'gemini http {r.status_code}: {r.text[:300]}')
    d = r.json()
    try:
        return d['candidates'][0]['content']['parts'][0]['text']
    except (KeyError, IndexError):
        raise LLMError(f'gemini empty response: {str(d)[:300]}')


PROVIDERS = {'agy': _agy, 'agy_check': lambda p, t: _agy(p, t, CHECK_MODEL, 'agy_check'), 'gemini': _gemini}


def _ledger(**rec):
    with open(DATA / 'llm_ledger.jsonl', 'a') as f:
        f.write(json.dumps({'ts': time.strftime('%Y-%m-%dT%H:%M:%S'), **rec}) + '\n')


def complete_json(task, prompt, schema, order=('agy', 'gemini'), timeout=600, check=None, repairs=1):
    """Return a dict valid against `schema` (and optional extra `check(obj) -> list[str] errors`)."""
    full = PREAMBLE + prompt + '\n\nThe JSON must match this JSON Schema:\n' + json.dumps(schema)
    errors_seen = []
    for prov in order:
        if prov in _broken:
            continue
        p = full
        for attempt in range(1 + repairs):
            t0 = time.time()
            try:
                raw = PROVIDERS[prov](p, timeout)
                obj = _extract_json(raw)
                errs = [f'{"/".join(map(str, e.absolute_path))}: {e.message}'[:300]
                        for e in jsonschema.Draft202012Validator(schema).iter_errors(obj)]
                if not errs and check:
                    errs = check(obj)
                _ledger(task=task, provider=prov, attempt=attempt, ok=not errs, secs=round(time.time() - t0, 1), chars=len(p))
                if not errs:
                    log('llm ok', task=task, provider=prov, secs=round(time.time() - t0, 1))
                    return obj
                errors_seen.append(f'{prov}: {errs[:5]}')
                log('llm invalid output', task=task, provider=prov, errors=errs[:5])
                p = (full + '\n\nYour previous answer was rejected for these reasons:\n- ' + '\n- '.join(errs[:15]) +
                     '\nReturn the complete corrected JSON object.')
            except (LLMError, ValueError, json.JSONDecodeError, subprocess.TimeoutExpired, requests.RequestException) as e:
                _ledger(task=task, provider=prov, attempt=attempt, ok=False, secs=round(time.time() - t0, 1), err=str(e)[:200])
                errors_seen.append(f'{prov}: {str(e)[:200]}')
                log('llm call failed', task=task, provider=prov, err=str(e)[:200])
                if prov in _broken:
                    break
    raise LLMError(f'{task}: all providers failed: {errors_seen[-4:]}')
