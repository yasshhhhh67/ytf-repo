"""One-time YouTube OAuth consent (Desktop/loopback flow). Listens on 127.0.0.1:8765, reached via an SSH tunnel
from the user's computer. Stores the refresh token ONLY as a systemd-creds encrypted credential. Run as root."""
import json, subprocess, sys
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ['https://www.googleapis.com/auth/youtube.upload',
          'https://www.googleapis.com/auth/youtube',
          'https://www.googleapis.com/auth/youtube.force-ssl',
          'https://www.googleapis.com/auth/yt-analytics.readonly']
client = json.loads(subprocess.run(['systemd-creds', 'decrypt', '--name=ytf.youtube-client',
                                    '/etc/credstore.encrypted/ytf.youtube-client', '-'], capture_output=True, check=True).stdout)
flow = InstalledAppFlow.from_client_config(client, SCOPES)
creds = flow.run_local_server(host='localhost', bind_addr='127.0.0.1', port=8765, open_browser=False,
                              authorization_prompt_message='AUTH_URL {url}', success_message='Done. You can close this tab.',
                              access_type='offline', prompt='consent')
if not creds.refresh_token:
    print('ERROR: no refresh token returned'); sys.exit(1)
blob = json.dumps({'refresh_token': creds.refresh_token, 'scopes': list(creds.scopes or SCOPES)}).encode()
subprocess.run(['systemd-creds', 'encrypt', '--name=ytf.youtube-token', '-', '/etc/credstore.encrypted/ytf.youtube-token'],
               input=blob, check=True, capture_output=True)
print('TOKEN_SAVED scopes=' + ','.join(s.rsplit('/', 1)[-1] for s in (creds.scopes or SCOPES)))
