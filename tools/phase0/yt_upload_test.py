"""Phase 0 test: private resumable upload + processing poll + custom thumbnail, then delete the test video."""
import json, sys, time
sys.path.insert(0, '/srv/ytf/app/tools/phase0')
from googleapiclient.http import MediaFileUpload
from yt_client import youtube

yt = youtube(); t0 = time.time()
body = {'snippet': {'title': 'ytf pipeline test (private, will be deleted)', 'description': 'Automated Phase 0 test upload.',
                    'tags': ['ytf-phase0-test'], 'categoryId': '28', 'defaultLanguage': 'en'},
        'status': {'privacyStatus': 'private', 'selfDeclaredMadeForKids': False, 'containsSyntheticMedia': False}}
req = yt.videos().insert(part='snippet,status', body=body,
                         media_body=MediaFileUpload('/tmp/ytf_test.mp4', mimetype='video/mp4', resumable=True, chunksize=4 * 1024 * 1024))
resp = None
while resp is None:
    _, resp = req.next_chunk()
vid = resp['id']; out = {'video_id': vid, 'upload_s': round(time.time() - t0, 1), 'privacy': resp['status']['privacyStatus'],
                         'synthetic_flag_echo': resp['status'].get('containsSyntheticMedia')}
for _ in range(40):
    v = yt.videos().list(part='processingDetails,status', id=vid).execute()['items'][0]
    st = v['processingDetails'].get('processingStatus'); out['processing'] = st; out['upload_status'] = v['status']['uploadStatus']
    if st in ('succeeded', 'failed', 'terminated'): break
    time.sleep(15)
try:
    yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload('/tmp/ytf_thumb.jpg', mimetype='image/jpeg')).execute()
    out['thumbnail'] = 'set OK'
except Exception as e:
    out['thumbnail'] = f'FAILED: {str(e)[:200]}'
out['total_s'] = round(time.time() - t0, 1)
yt.videos().delete(id=vid).execute(); out['deleted'] = True
print(json.dumps(out, indent=1))
