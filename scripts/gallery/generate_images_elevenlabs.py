"""Generate gallery source art with ElevenLabs' image API (POST /v1/flows/image).

    .venv/bin/python scripts/gallery/generate_images_elevenlabs.py <model_id> <key> [key ...]

Uses the SPORTS prompts from generate-hero-art.mjs (plus overrides below) and writes assets/sports-src-gpt/<key>-<model>.png.
ELEVENLABS_API_KEY is read from .env.local. No extra packages.
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STYLE = ("Clean vector-style illustration with bold, smooth black outlines and flat solid colors. Pure white background, "
         "subject centered with generous margins. No shading gradients, no texture, no letters, no logos, no brand names, no watermark, no border, no signature.")
PROMPTS = {
    'sprinter': "Illustration of an invented African American female sprinter running at full speed on a track, leaning forward, side view. A detailed, well-drawn face in profile with a focused expression, dark brown skin, hair tied back, correct human anatomy with exactly two arms and two legs and both feet in running spikes. She wears a plain United States-flag kit: a white crop top with red and blue stripes across the chest and blue shorts with white stars, in the colours of the American flag. No logo, no number, no text.",
    'dunk': "Illustration of an invented African American basketball player in mid-air making a one-handed dunk, shown with correct human anatomy: exactly two arms and exactly two legs, both legs clearly visible and both feet in sneakers. A detailed, well-drawn face with two eyes, nose and mouth, dark brown skin, short hair. He wears a plain Spain-flag kit: a red basketball jersey and shorts with yellow trim, in the colours of the Spanish flag. A hoop and backboard at the top. No logo, no number, no text.",
}


def key():
    for line in (ROOT / '.env.local').read_text().splitlines():
        m = re.match(r'\s*ELEVENLABS_API_KEY\s*=\s*(.*)', line)
        if m:
            return m.group(1).strip().strip('"\'')
    return os.environ['ELEVENLABS_API_KEY']


def call(method, url, headers, body=None):
    request = urllib.request.Request(url, method=method, headers=headers, data=json.dumps(body).encode() if body else None)
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as error:
        raise SystemExit(f'{error.code} {error.read().decode()[:400]}')


def main():
    model, names = sys.argv[1], sys.argv[2:]
    headers = {'xi-api-key': key(), 'Content-Type': 'application/json'}
    out = ROOT / 'assets' / 'sports-src-gpt'
    out.mkdir(exist_ok=True)
    for name in names:
        body = {'model_id': model, 'prompt': f'{PROMPTS[name]} {STYLE}', 'aspect_ratio': '1:1'}
        started = call('POST', 'https://api.elevenlabs.io/v1/flows/image', headers, body)
        print(name, started)
        for _ in range(90):
            time.sleep(3)
            g = call('GET', f"https://api.elevenlabs.io/v1/flows/image/{started['id']}", headers)
            if g.get('content_url') or g.get('status') in ('failed', 'error'):
                break
        print(name, {k: v for k, v in g.items() if k != 'content_url'})
        if g.get('content_url'):
            (out / f'{name}-{model}.png').write_bytes(urllib.request.urlopen(g['content_url'], timeout=120).read())


main()
