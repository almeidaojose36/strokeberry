"""Generate Strokeberry's original background-music library with the ElevenLabs Music API.

    .venv/bin/python scripts/social/generate_music.py [key ...]

Styles follow what is trending on Reels and TikTok (researched October 2026), described by genre only: never an artist
or song name. Each track fits a ~15 s drawing clip: lighter while the lines are drawn, lifting around second 8-9 when
the colour paints in, resolving for the end card. Writes marketing/music/<key>.mp3. ELEVENLABS_API_KEY from .env.local.
Eleven Music is cleared for commercial use on paid plans (social media and ads included).
"""
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'marketing' / 'music'
SHAPE = ('Instrumental only, no vocals. 20 seconds. Starts light and sparse for the first 8 seconds, then lifts with fuller '
         'drums and melody around second 8 or 9, and resolves cleanly in the last 3 seconds. Catchy hook in the first 2 seconds.')
TRACKS = {
    'autumn-acoustic-1': 'Cosy autumn acoustic instrumental: warm fingerpicked acoustic guitar, soft brushed percussion, light glockenspiel, relaxed and happy, 95 bpm.',
    'autumn-acoustic-2': 'Warm seasonal acoustic folk-pop instrumental: strummed and plucked guitars, gentle hand claps, cello pad, cheerful and cosy, 100 bpm.',
    'soul-lounge-1': 'Smooth soul lounge groove: Rhodes electric piano, warm round bass, laid-back drums with soft snare, mellow and stylish, 88 bpm.',
    'soul-lounge-2': 'Modern neo-soul instrumental groove: muted guitar licks, Rhodes chords, deep bass, crisp relaxed drums, confident and smooth, 92 bpm.',
    'funk-bounce-1': 'Bouncy Brazilian funk-style beat: punchy tamborzao drum pattern, playful synth stabs, deep 808 bass, high energy and fun, 130 bpm, clean and family friendly.',
    'funk-bounce-2': 'Energetic dance funk beat for reveals: snappy percussion, bright plucked synth hook, bouncing bass, exciting and upbeat, 128 bpm.',
    'dreamy-indie-1': 'Dreamy indie-pop instrumental: shimmering clean electric guitars with chorus, soft drums, warm synth pad, nostalgic and hopeful, 105 bpm.',
    'dreamy-indie-2': 'Bright bedroom-pop instrumental: jangly guitar melody, soft drum machine, airy synths, sweet and nostalgic, 110 bpm.',
    'playful-spooky-1': 'Playful spooky Halloween instrumental: plucked pizzicato strings, celesta, light swing rhythm, mischievous and fun not scary, 120 bpm.',
    'playful-curious-1': 'Playful curious instrumental for a guessing game: pizzicato strings, marimba, soft claps, ticking percussion, cheerful suspense, 115 bpm.',
    'future-bass-1': 'Melodic future bass for an art time-lapse: airy chords, gentle build, uplifting drop with bright supersaw chords when the colour appears, 140 bpm half-time feel.',
    'soft-piano-1': 'Soft inspiring piano instrumental for a lesson: gentle piano melody, light strings, subtle soft beat, calm and encouraging, 90 bpm.',
}


def key():
    for line in (ROOT / '.env.local').read_text().splitlines():
        if line.startswith('ELEVENLABS_API_KEY='):
            return line.split('=', 1)[1].strip().strip('"').strip("'")
    sys.exit('ELEVENLABS_API_KEY missing from .env.local')


def generate(name, prompt, api_key):
    body = json.dumps({'prompt': f'{prompt} {SHAPE}', 'music_length_ms': 20000}).encode()
    request = urllib.request.Request('https://api.elevenlabs.io/v1/music', data=body, method='POST',
                                     headers={'xi-api-key': api_key, 'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=300) as response:
        (OUT / f'{name}.mp3').write_bytes(response.read())


if __name__ == '__main__':
    OUT.mkdir(parents=True, exist_ok=True)
    api_key = key()
    for name, prompt in TRACKS.items():
        if sys.argv[1:] and name not in sys.argv[1:]:
            continue
        try:
            generate(name, prompt, api_key)
            print(f'{name}: {(OUT / f"{name}.mp3").stat().st_size // 1024} KB', flush=True)
        except Exception as error:  # noqa: BLE001
            print(f'{name}: FAILED {error}', flush=True)
