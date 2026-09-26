#!/usr/bin/env python3
"""Designs the Strokeberry narrator voice with ElevenLabs Voice Design (needs a paid plan).

    python3 scripts/tutorials/elevenlabs_design_voice.py preview          # 3 candidates → marketing/voice/previews/
    python3 scripts/tutorials/elevenlabs_design_voice.py save <1|2|3>     # save a candidate to the account

The key comes from .env.local (ELEVENLABS_API_KEY), falling back to the environment.
Saved voice ids are recorded in marketing/voice/voice.json.
"""
import base64
import json
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "marketing/voice"
DESCRIPTION = (
    "A warm, upbeat young woman in her late twenties with a clear, neutral American English accent. "
    "Friendly and encouraging, like a creative YouTuber showing a fun app to a friend. A smile in the voice, "
    "natural conversational pace, crisp studio-quality recording, no background noise.")
SAMPLE = (
    "Here's how to turn your logo into a hand-drawn video, step by step. Step one: open the Strokeberry studio and "
    "tap Replace. Pick your logo. Clean line art or a transparent PNG works best. Step two: choose Ink. It draws bold, "
    "clean lines, perfect for logos. And that's it. Open the studio and create your first video.")


def key():
    env = ROOT / ".env.local"
    if env.is_file():
        for line in env.read_text().splitlines():
            name, _, value = line.partition("=")
            if name.strip() == "ELEVENLABS_API_KEY" and value.strip():
                return value.strip().strip("'\"")
    return os.environ["ELEVENLABS_API_KEY"]


def post(path, body):
    req = urllib.request.Request(f"https://api.elevenlabs.io{path}", data=json.dumps(body).encode(),
                                 headers={"xi-api-key": key(), "Content-Type": "application/json"})
    try:
        return json.load(urllib.request.urlopen(req, timeout=240))
    except urllib.error.HTTPError as e:
        raise SystemExit(f"{e.code} {e.read()[:400]!r}")


if sys.argv[1] == "preview":
    (OUT / "previews").mkdir(parents=True, exist_ok=True)
    d = post("/v1/text-to-voice/design", {"voice_description": DESCRIPTION, "text": SAMPLE, "model_id": "eleven_multilingual_ttv_v2"})
    meta = []
    for i, p in enumerate(d["previews"], 1):
        f = OUT / f"previews/candidate-{i}.mp3"
        f.write_bytes(base64.b64decode(p["audio_base_64"]))
        meta.append({"candidate": i, "file": str(f.relative_to(ROOT)), "generated_voice_id": p["generated_voice_id"]})
    (OUT / "previews/previews.json").write_text(json.dumps({"description": DESCRIPTION, "previews": meta}, indent=1))
    print(json.dumps(meta, indent=1))
elif sys.argv[1] == "save":
    n = int(sys.argv[2])
    previews = json.loads((OUT / "previews/previews.json").read_text())
    gen = previews["previews"][n - 1]["generated_voice_id"]
    d = post("/v1/text-to-voice", {"voice_name": "Strokeberry Narrator", "voice_description": DESCRIPTION, "generated_voice_id": gen})
    (OUT / "voice.json").write_text(json.dumps({"name": "Strokeberry Narrator", "voice_id": d["voice_id"], "from_candidate": n,
                                                "description": DESCRIPTION}, indent=1))
    print("saved voice", d["voice_id"])
