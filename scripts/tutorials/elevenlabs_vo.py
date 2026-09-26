#!/usr/bin/env python3
"""Generates a tutorial's voice-over lines with ElevenLabs.

    python3 scripts/tutorials/elevenlabs_vo.py videos/<project>/vo-lines.json [--voice <voice_id>] [--only 3,5]

vo-lines.json is a list of [start_seconds, text]. Writes assets/vo/line-NN.wav (silence trimmed so each
line starts on its cue) and reports lines that run into the next one. Needs ELEVENLABS_API_KEY in the
environment (a paid plan is required for commercial use and for custom voices).
"""
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

LINES = Path(sys.argv[1]).resolve()
PROJECT = LINES.parent
VOICE = sys.argv[sys.argv.index("--voice") + 1] if "--voice" in sys.argv else json.loads((Path(__file__).resolve().parents[2] / "marketing/voice/voice.json").read_text())["voice_id"]  # Strokeberry Narrator

def env_local_key():
    """The project's .env.local wins over the shell environment, so a paid key there overrides a free one."""
    env = PROJECT.parents[1] / ".env.local"
    if env.is_file():
        for line in env.read_text().splitlines():
            name, _, value = line.partition("=")
            if name.strip() == "ELEVENLABS_API_KEY" and value.strip():
                return value.strip().strip("'\"")
    return None


KEY = env_local_key() or os.environ["ELEVENLABS_API_KEY"]

lines = json.loads(LINES.read_text())
(PROJECT / "assets/vo").mkdir(parents=True, exist_ok=True)
ONLY = {int(n) for n in sys.argv[sys.argv.index("--only") + 1].split(",")} if "--only" in sys.argv else None  # e.g. --only 3,5
if ONLY is None:
    for old in (PROJECT / "assets/vo").glob("line-*.wav"):
        old.unlink()
for i, (start, text) in enumerate(lines):
    if ONLY is not None and i not in ONLY:
        continue
    body = json.dumps({
        "text": text, "model_id": "eleven_multilingual_v2",
        "previous_text": lines[i - 1][1] if i else "", "next_text": lines[i + 1][1] if i + 1 < len(lines) else "",
        "voice_settings": {"stability": 0.45, "similarity_boost": 0.8, "style": 0.3, "use_speaker_boost": True},
    }).encode()
    req = urllib.request.Request(f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE}?output_format=mp3_44100_128", data=body,
                                 headers={"xi-api-key": KEY, "Content-Type": "application/json"})
    mp3 = PROJECT / f"assets/vo/line-{i:02d}.mp3"
    mp3.write_bytes(urllib.request.urlopen(req, timeout=120).read())
    wav = mp3.with_suffix(".wav")
    trim = "silenceremove=start_periods=1:start_threshold=-45dB"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(mp3), "-af", f"{trim},areverse,{trim},areverse", "-ar", "44100", str(wav)], check=True)
    mp3.unlink()
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(wav)],
                               capture_output=True, text=True).stdout)
    nxt = lines[i + 1][0] if i + 1 < len(lines) else float("inf")
    print(f"{i:02d} {start:5.1f} + {dur:4.2f} = {start + dur:5.1f}   next {nxt:5.1f}  {'OVERLAP' if start + dur > nxt - 0.2 else ''}")
