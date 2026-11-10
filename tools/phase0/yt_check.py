import json, sys
sys.path.insert(0, '/srv/ytf/app/tools/phase0')
from yt_client import youtube
ch = youtube().channels().list(part='snippet,status,statistics,contentDetails', mine=True).execute()['items'][0]
print(json.dumps({'channel_id': ch['id'], 'title': ch['snippet']['title'], 'custom_url': ch['snippet'].get('customUrl'),
  'long_uploads': ch['status'].get('longUploadsStatus'), 'made_for_kids': ch['status'].get('madeForKids'),
  'privacy': ch['status'].get('privacyStatus'), 'videos': ch['statistics'].get('videoCount'),
  'subscribers': ch['statistics'].get('subscriberCount'), 'uploads_playlist': ch['contentDetails']['relatedPlaylists']['uploads']}, indent=1))
