"""Change a video's privacy status, keeping every other status field.
Usage: yt_privacy.py <video_id> <private|unlisted|public>"""
import json, sys

sys.path.insert(0, '/srv/ytf/app/tools/phase0')
from yt_client import youtube  # noqa: E402

vid, priv = sys.argv[1], sys.argv[2]
assert priv in ('private', 'unlisted', 'public')
yt = youtube()
cur = yt.videos().list(part='status,snippet', id=vid).execute()['items'][0]
st = {k: v for k, v in cur['status'].items()
      if k in ('embeddable', 'license', 'publicStatsViewable', 'selfDeclaredMadeForKids', 'containsSyntheticMedia')}
st['privacyStatus'] = priv
res = yt.videos().update(part='status', body={'id': vid, 'status': st}).execute()
print(json.dumps({'video': vid, 'title': cur['snippet']['title'], 'before': cur['status']['privacyStatus'],
                  'after': res['status']['privacyStatus'], 'link': f'https://youtu.be/{vid}'}))
