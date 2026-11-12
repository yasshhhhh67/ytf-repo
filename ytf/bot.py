"""Telegram bot (long polling, no open ports). Only the allow-listed chat can use it.
Buttons: ✅ Approve / ❌ Reject on approval cards.
Commands: /status · /pause · /resume · /add <short topic> · /addlong <long topic> · /help"""
import json, re, time
from pathlib import Path

import requests

from . import auto
from .common import cred, log

HELP = ('Commands:\n/status – upcoming slots\n/pause – stop producing new videos\n/resume – continue\n'
        '/add <topic> – put a Short topic at the front of the queue\n/addlong <topic> – same for the long video')


def main():
    tok = cred('ytf.telegram-token').strip(); api = f'https://api.telegram.org/bot{tok}/'
    chat = int(re.search(r'allowed_chat_id\s*=\s*(-?\d+)', Path('/etc/ytf/config.toml').read_text()).group(1))
    send = lambda text, **kw: requests.post(api + 'sendMessage', timeout=20, data={'chat_id': chat, 'text': text[:4000], **kw})
    log('bot started')
    while True:
        try:
            with auto.state() as st:
                offset = st.get('tg_offset', 0)
            r = requests.get(api + 'getUpdates', timeout=70, params={'offset': offset, 'timeout': 50,
                                                                      'allowed_updates': json.dumps(['message', 'callback_query'])}).json()
            for u in r.get('result', []):
                with auto.state() as st:
                    st['tg_offset'] = u['update_id'] + 1
                if 'callback_query' in u:
                    cq = u['callback_query']; msg = cq.get('message', {})
                    if msg.get('chat', {}).get('id') != chat:
                        continue
                    action, _, pid = cq.get('data', '').partition(':')
                    try:
                        res = auto.schedule_publish(pid) if action == 'ok' else auto.reject(pid)
                    except Exception as e:  # noqa: BLE001
                        res = f'error: {str(e)[:200]}'
                    requests.post(api + 'answerCallbackQuery', timeout=20, data={'callback_query_id': cq['id'], 'text': res[:180]})
                    requests.post(api + 'editMessageReplyMarkup', timeout=20,
                                  data={'chat_id': chat, 'message_id': msg['message_id'], 'reply_markup': json.dumps({'inline_keyboard': []})})
                    send(('✅ ' if action == 'ok' and not res.startswith('error') else '📝 ') + res)
                    log('approval', action=action, project=pid, result=res)
                elif 'message' in u:
                    m = u['message']
                    if m.get('chat', {}).get('id') != chat:
                        continue
                    text = (m.get('text') or '').strip()
                    if text.startswith('/status'):
                        send(auto.status_text())
                    elif text.startswith('/pause') or text.startswith('/resume'):
                        with auto.state() as st:
                            st['paused'] = text.startswith('/pause')
                        send('⏸ Paused: no new videos will be produced.' if text.startswith('/pause') else '▶️ Resumed.')
                    elif text.startswith('/addlong ') or text.startswith('/add '):
                        fmt = 'long' if text.startswith('/addlong') else 'short'; topic = text.split(' ', 1)[1].strip()[:140]
                        with auto.state() as st:
                            st['topics'][fmt].insert(0, topic)
                        send(f'➕ Next {fmt} topic: {topic}')
                    else:
                        send(HELP)
        except Exception as e:  # noqa: BLE001 - network hiccups must not kill the bot
            log('bot error', err=str(e)[:300]); time.sleep(10)
