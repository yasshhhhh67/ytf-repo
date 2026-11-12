"""Upload the master as PRIVATE (never public here), set the thumbnail and captions, then notify for approval.
Idempotent: if this project already has a video id, or YouTube already has a video tagged ytf-<id>, nothing is re-uploaded."""
import sys, time

from googleapiclient.http import MediaFileUpload

from .common import APP, log, read_json, telegram, write_json

sys.path.insert(0, str(APP / 'tools' / 'phase0'))
from yt_client import youtube  # noqa: E402


def _srt(words, path):
    def ts(t):
        h, r = divmod(t, 3600); m, s = divmod(r, 60); return f'{int(h):02d}:{int(m):02d}:{int(s):02d},{int((s % 1) * 1000):03d}'
    lines, cur = [], []
    for w in words:
        cur.append(w)
        if len(cur) >= 10 or w['w'][-1:] in '.?!':
            lines.append(cur); cur = []
    if cur: lines.append(cur)
    path.write_text('\n'.join(f'{i + 1}\n{ts(g[0]["s"])} --> {ts(g[-1]["e"])}\n{" ".join(x["w"] for x in g)}\n' for i, g in enumerate(lines)))


def _existing(yt, pid):
    ch = yt.channels().list(part='contentDetails', mine=True).execute()['items'][0]
    up = ch['contentDetails']['relatedPlaylists']['uploads']
    items = yt.playlistItems().list(part='contentDetails', playlistId=up, maxResults=25).execute().get('items', [])
    ids = [i['contentDetails']['videoId'] for i in items]
    if not ids: return None
    for v in yt.videos().list(part='snippet', id=','.join(ids)).execute().get('items', []):
        if f'ytf-{pid}' in v['snippet'].get('tags', []):
            return v['id']
    return None


def run_stage(proj, P):
    yt = youtube(); meta = read_json(P / 'publish' / 'metadata.json'); state = read_json(P / 'publish' / 'upload.json', {})
    vid = state.get('video_id') or _existing(yt, proj['id'])
    if not vid:
        body = {'snippet': {'title': meta['title'], 'description': meta['description'], 'tags': meta['tags'],
                            'categoryId': '28', 'defaultLanguage': 'en', 'defaultAudioLanguage': 'en'},
                'status': {'privacyStatus': 'private', 'selfDeclaredMadeForKids': False, 'containsSyntheticMedia': False}}
        req = yt.videos().insert(part='snippet,status', body=body, media_body=MediaFileUpload(
            str(P / 'render' / 'master.mp4'), mimetype='video/mp4', resumable=True, chunksize=8 * 1024 * 1024))
        resp = None
        while resp is None:
            _, resp = req.next_chunk()
        vid = resp['id']; state['video_id'] = vid; write_json(P / 'publish' / 'upload.json', state)
        log('uploaded private', video_id=vid)
    for _ in range(80):
        v = yt.videos().list(part='processingDetails,status', id=vid).execute()['items'][0]
        if v['processingDetails'].get('processingStatus') in ('succeeded', 'failed', 'terminated'): break
        time.sleep(15)
    state['processing'] = v['processingDetails'].get('processingStatus')
    if not state.get('thumbnail'):
        yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(str(P / 'render' / 'thumb.jpg'), mimetype='image/jpeg')).execute()
        state['thumbnail'] = True
    if proj['format'] == 'long' and not state.get('captions'):
        srt = P / 'publish' / 'captions.srt'; _srt(read_json(P / 'audio' / 'words.json'), srt)
        yt.captions().insert(part='snippet', body={'snippet': {'videoId': vid, 'language': 'en', 'name': 'English', 'isDraft': False}},
                             media_body=MediaFileUpload(str(srt), mimetype='application/octet-stream')).execute()
        state['captions'] = True
    write_json(P / 'publish' / 'upload.json', state)
    qa = read_json(P / 'qa' / 'report.json')
    if proj.get('auto'):                     # the scheduler sends an approval card with buttons instead
        return {'video_id': vid, 'processing': state['processing']}
    telegram(f'🎬 Ready for review ({proj["format"]}): {meta["title"]}\n'
             f'https://youtu.be/{vid} (private)\n'
             f'Length {qa["info"]["duration"]:.0f}s · {qa["info"]["claims"]} sourced claims · {qa["info"]["lufs"]} LUFS\n'
             + (('⚠️ ' + ' / '.join(qa['soft'])) if qa['soft'] else '✅ no QA warnings')
             + f'\nProject {proj["id"]}. Nothing is public until you approve.')
    return {'video_id': vid, 'processing': state['processing']}
