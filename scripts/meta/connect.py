"""Turn a short-lived Graph API Explorer token into a permanent Page token for the dashboard.

    .venv/bin/python scripts/meta/connect.py

Reads META_APP_ID, META_APP_SECRET and META_USER_TOKEN from .env.local, swaps the user token for a long-lived one, asks
for the Strokeberry Page's own token (which never expires) and the linked Instagram account, then writes META_PAGE_ID,
META_PAGE_TOKEN and META_IG_ID to .env.local and, with --server, to the server's .env.local. Nothing secret is printed.
"""
import json
import re
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENV = ROOT / '.env.local'
GRAPH = 'https://graph.facebook.com/v26.0'
PAGE_ID = '1290136847527332'
SSH = ['ssh', '-i', str(Path.home() / '.ssh' / 'strokeberry_vps'), 'root@148.230.79.3']


def env():
    values = {}
    for line in ENV.read_text().splitlines():
        match = re.match(r'\s*([A-Z0-9_]+)\s*=\s*(.*?)\s*$', line)
        if match:
            values[match.group(1)] = match.group(2).strip('"\'')
    return values


def get(path, **params):
    with urllib.request.urlopen(f'{GRAPH}/{path}?' + urllib.parse.urlencode(params), timeout=30) as response:
        return json.loads(response.read())


def set_line(text, key, value):
    line = f'{key}={value}'
    if re.search(rf'^{key}=.*$', text, re.M):
        return re.sub(rf'^{key}=.*$', lambda _: line, text, flags=re.M)
    return text.rstrip('\n') + f'\n{line}\n'


def main():
    cfg = env()
    long_lived = get('oauth/access_token', grant_type='fb_exchange_token', client_id=cfg['META_APP_ID'],
                     client_secret=cfg['META_APP_SECRET'], fb_exchange_token=cfg['META_USER_TOKEN'])['access_token']
    page = get(PAGE_ID, fields='name,access_token,instagram_business_account', access_token=long_lived)
    result = {'META_PAGE_ID': PAGE_ID, 'META_PAGE_TOKEN': page['access_token'],
              'META_IG_ID': page['instagram_business_account']['id']}
    text = ENV.read_text()
    for key, value in result.items():
        text = set_line(text, key, value)
    ENV.write_text(text)
    if '--server' in sys.argv:
        script = '; '.join(f"grep -q '^{k}=' /opt/strokeberry/app/.env.local && sed -i 's|^{k}=.*|{k}={v}|' /opt/strokeberry/app/.env.local "
                           f"|| echo '{k}={v}' >> /opt/strokeberry/app/.env.local" for k, v in result.items())
        subprocess.run(SSH + [script], check=True)
    debug = get('debug_token', input_token=result['META_PAGE_TOKEN'], access_token=f"{cfg['META_APP_ID']}|{cfg['META_APP_SECRET']}")['data']
    print(f"Page: {page['name']}, Instagram id: {result['META_IG_ID']}, token never expires: {debug.get('expires_at') == 0}, "
          f"valid: {debug.get('is_valid')}, scopes: {', '.join(debug.get('scopes', []))}")


main()
