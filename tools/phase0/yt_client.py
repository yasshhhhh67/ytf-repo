"""Build authorised YouTube clients from the encrypted credentials (no secrets printed)."""
import json, os, subprocess
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

def _cred(n):
    cd = os.environ.get('CREDENTIALS_DIRECTORY')
    if cd:
        return open(os.path.join(cd, n)).read()
    return subprocess.run(['systemd-creds', 'decrypt', f'--name={n}', f'/etc/credstore.encrypted/{n}', '-'],
                          capture_output=True, check=True).stdout.decode()

def credentials():
    c = json.loads(_cred('ytf.youtube-client')); c = c.get('installed') or c.get('web')
    t = json.loads(_cred('ytf.youtube-token'))
    return Credentials(None, refresh_token=t['refresh_token'], token_uri=c['token_uri'],
                       client_id=c['client_id'], client_secret=c['client_secret'], scopes=t['scopes'])

def youtube():
    return build('youtube', 'v3', credentials=credentials(), cache_discovery=False)

def analytics():
    return build('youtubeAnalytics', 'v2', credentials=credentials(), cache_discovery=False)
