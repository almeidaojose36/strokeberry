#!/usr/bin/env python3
"""Builds a Strokeberry step-by-step tutorial video (HyperFrames project) from captured studio screens.

    python3 scripts/tutorials/build_frames.py videos/<project>/tutorial.json

The spec lists the frames: an intro (the real export in a card), step frames (captured phone screens
with taps, punch-ins and hint lines), and an outro (result + full-mascot end card). Screens and tap
rectangles come from scripts/tutorials/capture-studio.mjs (capture/app/shots.json).
Writes compositions/frames/NN-*.html and index.html; audio comes from audio_meta.json (BGM) and the
spec's sfx list.
"""
import json
import shutil
import subprocess
import sys
from html import escape
from pathlib import Path

SPEC = Path(sys.argv[1]).resolve()
PROJECT = SPEC.parent
ROOT = PROJECT.parents[1]
spec = json.loads(SPEC.read_text())
shots = json.loads((PROJECT / "capture/app/shots.json").read_text())
RECTS = {s["id"]: s["rects"] for s in shots["shots"]}
SPEED = spec.get("result_speed", 3)  # the app's export plays sped up in the intro, export dialog and outro
RESULT = f"assets/result-{SPEED}x.mp4"

# Phone geometry on the 1080x1920 canvas: screen 560 wide, same place in every step frame.
VW, VH = shots["viewport"]["w"], shots["viewport"]["h"]
SX, SY, SW = 260, 470, 560
K = SW / VW
SH = round(VH * K)
C = {"cream": "#FFF8EC", "ink": "#1B1B1B", "coral": "#EC2D34", "button": "#D42630", "teal": "#00BEC8",
     "leaf": "#69B644", "sun": "#FABE3A", "body": "#5B544A"}

FONTS = """
@font-face { font-family: "Bricolage Grotesque"; src: url("assets/fonts/BricolageGrotesque.woff2") format("woff2"); font-weight: 200 800; }
@font-face { font-family: "Figtree"; src: url("assets/fonts/Figtree.woff2") format("woff2"); font-weight: 300 900; }"""
SWASH = ("url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 200 30' "
         "preserveAspectRatio='none'%3E%3Cpath d='M4 13C48 6 120 3 196 8c1 5-1 10-4 13C130 16 70 18 9 26 3 24 2 17 4 13Z' "
         "fill='%23FABE3A'/%3E%3C/svg%3E\")")


def stage_assets():
    (PROJECT / "assets/screens").mkdir(parents=True, exist_ok=True)
    for s in shots["shots"]:
        shutil.copy2(PROJECT / "capture/app" / s["file"], PROJECT / "assets/screens" / s["file"])
    fast = PROJECT / RESULT
    if not fast.exists():
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(PROJECT / "capture/app/result.mp4"), "-an",
                        "-filter:v", f"setpts=PTS/{SPEED}", "-r", "30", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
                        str(fast)], check=True)
    shutil.copy2(ROOT / "frontend/public/brand/strokeberry-mascot@2x.png", PROJECT / "assets/strokeberry-mascot.png")
    sfx = PROJECT / "assets/sfx"
    sfx.mkdir(parents=True, exist_ok=True)
    for f in (ROOT / "videos/strokeberry-launch/assets/sfx").glob("*.mp3"):
        shutil.copy2(f, sfx / f.name)
    fonts = PROJECT / "assets/fonts"
    fonts.mkdir(parents=True, exist_ok=True)
    for f in (ROOT / "videos/strokeberry-launch/assets/fonts").glob("*.woff2"):
        shutil.copy2(f, fonts / f.name)


def headline(text, key):
    """Headline words as inline-block spans, with the yellow marker swash wrapping the key phrase."""
    words = text.split(" ")
    kw = key.split(" ") if key else []
    out, i = [], 0
    while i < len(words):
        if kw and words[i:i + len(kw)] == kw:
            inner = " ".join(f'<span class="w">{escape(w)}</span>' for w in kw)
            out.append(f'<span class="sw">{inner}</span>')
            i += len(kw)
        else:
            out.append(f'<span class="w">{escape(words[i])}</span>')
            i += 1
    return " ".join(out)


def base_css(fid):
    return f"""{FONTS}
    #root-{fid} {{ position: absolute; inset: 0; width: 1080px; height: 1920px; overflow: hidden; font-family: "Figtree", sans-serif; color: {C['ink']}; }}
    .bg-{fid} {{ position: absolute; inset: 0; background:
      radial-gradient(520px 520px at 88% 12%, rgba(236,45,52,.12), transparent 70%),
      radial-gradient(520px 520px at 6% 60%, rgba(250,190,58,.18), transparent 70%),
      radial-gradient(520px 520px at 94% 88%, rgba(0,190,200,.12), transparent 70%), {C['cream']}; }}
    #{fid} .sw {{ padding: 0 .06em; margin: 0 -.04em; background: {SWASH} no-repeat 0 92%/0% 40%; }}"""


def step_frame(i, fr):
    fid = f"f{i}"
    dur = fr["duration"]
    screens = []
    for ev in fr["events"]:
        if ev["do"] == "show" and ev["screen"] not in screens:
            screens.append(ev["screen"])
    imgs = "\n".join(
        f'        <img class="{fid}-scr" id="{fid}-s{n}" src="assets/screens/{s}.png" alt="" />' for n, s in enumerate(screens))
    rings, hints = [], []
    tl = []
    tl.append(f'tl.fromTo("#{fid}-chip", {{ opacity: 0, y: -16 }}, {{ opacity: 1, y: 0, duration: 0.35, ease: "power3.out" }}, 0.05);')
    tl.append(f'tl.fromTo("#{fid}-h .w", {{ opacity: 0, y: 26 }}, {{ opacity: 1, y: 0, duration: 0.45, ease: "power3.out", stagger: 0.06 }}, 0.12);')
    tl.append(f'tl.to("#{fid} .sw", {{ backgroundSize: "100% 40%", duration: 0.5, ease: "power2.inOut" }}, 0.75);')
    tl.append(f'tl.set(".{fid}-scr", {{ opacity: 0 }}, 0);')
    tl.append(f'tl.set(".{fid}-hint", {{ opacity: 0 }}, 0);')
    tl.append(f'tl.set("#{fid}-zoom", {{ scale: 1, x: 0, y: 0, transformOrigin: "0px 0px" }}, 0);')
    tl.append(f'tl.set(".{fid}-ring", {{ opacity: 0, scale: 1, backgroundColor: "rgba(236,45,52,0)" }}, 0);')
    if fr.get("enter"):
        tl.append(f'tl.fromTo("#{fid}-phone", {{ opacity: 0, y: 80 }}, {{ opacity: 1, y: 0, duration: 0.6, ease: "power3.out" }}, 0.1);')
    zoomed = False
    for ev in fr["events"]:
        t = ev["t"]
        if ev["do"] == "show":
            n = screens.index(ev["screen"])
            fade = 0 if t == 0 else 0.25
            if fade:
                tl.append(f'tl.fromTo("#{fid}-s{n}", {{ opacity: 0 }}, {{ opacity: 1, duration: {fade}, ease: "power1.out" }}, {t});')
            else:
                tl.append(f'tl.set("#{fid}-s{n}", {{ opacity: 1 }}, 0);')
            for m in range(len(screens)):
                if m != n:
                    tl.append(f'tl.set("#{fid}-s{m}", {{ opacity: 0 }}, {t + fade});')
        elif ev["do"] in ("tap", "ring"):
            r = RECTS[ev["screen"]][ev["target"]]
            k = len(rings)
            pad = 6
            x, y, w, h = (r["x"] - pad) * K, (r["y"] - pad) * K, (r["w"] + 2 * pad) * K, (max(r["h"], 10) + 2 * pad) * K
            rings.append(f'        <div class="{fid}-ring" id="{fid}-r{k}" style="left:{x:.1f}px;top:{y:.1f}px;width:{w:.1f}px;height:{h:.1f}px"></div>')
            hold = ev.get("hold", 1.4)
            tl.append(f'tl.fromTo("#{fid}-r{k}", {{ opacity: 0, scale: 1.25 }}, {{ opacity: 1, scale: 1, duration: 0.35, ease: "back.out(2.4)", immediateRender: false }}, {t});')
            if ev["do"] == "tap":
                tl.append(f'tl.fromTo("#{fid}-r{k}", {{ backgroundColor: "rgba(236,45,52,0)" }}, {{ backgroundColor: "rgba(236,45,52,.22)", duration: 0.12, yoyo: true, repeat: 1, ease: "power1.inOut", immediateRender: false }}, {t + 0.35});')
            tl.append(f'tl.to("#{fid}-r{k}", {{ opacity: 0, duration: 0.25, ease: "power1.in" }}, {t + hold});')
        elif ev["do"] == "zoom":
            r = RECTS[ev["screen"]][ev["target"]]
            cx, cy = (r["x"] + r["w"] / 2) * K, (r["y"] + r["h"] / 2) * K
            s = ev.get("scale", 1.5)
            # Bring the target to the screen centre, but never reveal past the screen's edges.
            tx = min(0, max(SW - s * SW, SW / 2 - s * cx))
            ty = min(0, max(SH - s * SH, SH / 2 - s * cy))
            tl.append(f'tl.to("#{fid}-zoom", {{ scale: {s}, x: {tx:.1f}, y: {ty:.1f}, duration: 0.7, ease: "power3.inOut" }}, {t});')
            zoomed = True
        elif ev["do"] == "unzoom":
            tl.append(f'tl.to("#{fid}-zoom", {{ scale: 1, x: 0, y: 0, duration: 0.6, ease: "power3.inOut" }}, {t});')
            zoomed = False
        elif ev["do"] == "hint":
            k = len(hints)
            hints.append(f'      <p class="{fid}-hint" id="{fid}-t{k}">{escape(ev["text"])}</p>')
            tl.append(f'tl.fromTo("#{fid}-t{k}", {{ opacity: 0, y: 14 }}, {{ opacity: 1, y: 0, duration: 0.35, ease: "power3.out" }}, {t});')
            if k:
                tl.append(f'tl.to("#{fid}-t{k - 1}", {{ opacity: 0, y: -10, duration: 0.25, ease: "power1.in" }}, {max(0, t - 0.3):g});')
    words = headline(fr["title"], fr.get("key", ""))
    css = base_css(fid) + f"""
    #{fid}-chip {{ position: absolute; left: 80px; top: 196px; height: 58px; padding: 0 26px; border-radius: 9999px; background: {C['coral']}; color: #fff;
      display: flex; align-items: center; font-weight: 800; font-size: 26px; letter-spacing: .12em; border: 2px solid {C['ink']}; }}
    #{fid}-h {{ position: absolute; left: 80px; right: 110px; top: 272px; font-family: "Bricolage Grotesque", sans-serif; font-weight: 800; font-size: 76px; line-height: 1.02; letter-spacing: -.025em; }}
    #{fid}-h .w {{ display: inline-block; }}
    .{fid}-hint {{ position: absolute; left: 80px; right: 110px; top: 360px; margin: 0; font-size: 33px; font-weight: 600; line-height: 1.25; color: {C['body']}; }}
    #{fid}-phone {{ position: absolute; left: {SX - 14}px; top: {SY - 14}px; width: {SW + 28}px; height: {SH + 28}px; border-radius: 76px; background: {C['ink']};
      box-shadow: 14px 14px 0 rgba(27,27,27,.08), 0 40px 80px -30px rgba(27,27,27,.45); }}
    #{fid}-screen {{ position: absolute; left: 14px; top: 14px; width: {SW}px; height: {SH}px; border-radius: 62px; overflow: hidden; background: {C['cream']}; }}
    #{fid}-zoom {{ position: absolute; inset: 0; transform-origin: 50% 50%; }}
    .{fid}-scr {{ position: absolute; left: 0; top: 0; width: {SW}px; height: {SH}px; }}
    .{fid}-ring {{ position: absolute; border: 4px solid {C['coral']}; border-radius: 16px; box-shadow: 0 0 0 6px rgba(236,45,52,.18); opacity: 0; }}"""
    hint_top = fr.get("hint_top", 360)
    css = css.replace(f"top: 360px; margin: 0;", f"top: {hint_top}px; margin: 0;")
    tl.append(f"tl.to({{}}, {{ duration: {dur} }}, 0);")
    body = f"""<template>
  <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
  <style>{css}
  </style>
  <div id="{fid}" data-composition-id="{fr['id']}" data-width="1080" data-height="1920">
    <div id="root-{fid}">
      <div id="{fid}-bg" class="bg-{fid} clip" data-start="0" data-duration="{dur}" data-track-index="0"></div>
      <div id="{fid}-chip">{escape(fr['chip'])}</div>
      <h1 id="{fid}-h">{words}</h1>
{chr(10).join(hints)}
      <div id="{fid}-phone"><div id="{fid}-screen"><div id="{fid}-zoom" data-layout-allow-overflow>
{imgs}
{chr(10).join(rings)}
      </div></div></div>
    </div>
  </div>
  <script>
    (function () {{
      const tl = gsap.timeline({{ paused: true }});
      {chr(10).join('      ' + x for x in tl).strip()}
      window.__timelines = window.__timelines || {{}};
      window.__timelines["{fr['id']}"] = tl;
    }})();
  </script>
</template>
"""
    return body


def intro_frame(i, fr):
    fid = f"f{i}"
    dur = fr["duration"]
    words = headline(fr["title"], fr.get("key", ""))
    card = fr["card"]
    css = base_css(fid) + f"""
    #{fid}-h {{ position: absolute; left: 70px; right: 90px; top: 210px; text-align: center; font-family: "Bricolage Grotesque", sans-serif; font-weight: 800; font-size: 96px; line-height: 1; letter-spacing: -.03em; }}
    #{fid}-h .w {{ display: inline-block; }}
    #{fid}-card {{ position: absolute; left: {card[0] - 12}px; top: {card[1] - 12}px; width: {card[2] + 24}px; height: {card[3] + 24}px; border-radius: 44px; background: #fff; border: 3px solid {C['ink']};
      box-shadow: 14px 14px 0 {C['coral']}, 0 40px 80px -30px rgba(27,27,27,.4); }}
    #{fid}-chip {{ position: absolute; left: 0; right: 0; margin: 0 auto; top: {card[1] + card[3] + 70}px; width: max-content; height: 72px; padding: 0 34px; border-radius: 9999px; background: {C['ink']}; color: #fff;
      display: flex; align-items: center; gap: 14px; font-weight: 700; font-size: 32px; }}
    #{fid}-chip i {{ width: 14px; height: 14px; border-radius: 50%; background: {C['coral']}; }}"""
    tl = [
        f'tl.fromTo("#{fid}-card", {{ opacity: 0, y: 90, scale: .94 }}, {{ opacity: 1, y: 0, scale: 1, duration: 0.6, ease: "power3.out" }}, 0);',
        f'tl.fromTo("#{fid}-h .w", {{ opacity: 0, y: 30 }}, {{ opacity: 1, y: 0, duration: 0.45, ease: "power3.out", stagger: 0.07 }}, 0.2);',
        f'tl.to("#{fid} .sw", {{ backgroundSize: "100% 40%", duration: 0.5, ease: "power2.inOut" }}, 1.0);',
        f'tl.fromTo("#{fid}-chip", {{ opacity: 0, scale: .6 }}, {{ opacity: 1, scale: 1, duration: 0.45, ease: "back.out(2.2)" }}, 1.6);',
        f"tl.to({{}}, {{ duration: {dur} }}, 0);",
    ]
    return f"""<template>
  <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
  <style>{css}
  </style>
  <div id="{fid}" data-composition-id="{fr['id']}" data-width="1080" data-height="1920">
    <div id="root-{fid}">
      <div id="{fid}-bg" class="bg-{fid} clip" data-start="0" data-duration="{dur}" data-track-index="0"></div>
      <h1 id="{fid}-h">{words}</h1>
      <div id="{fid}-card"></div>
      <div id="{fid}-chip"><i></i>{escape(fr['chip'])}</div>
    </div>
  </div>
  <script>
    (function () {{
      const tl = gsap.timeline({{ paused: true }});
      {chr(10).join('      ' + x for x in tl).strip()}
      window.__timelines = window.__timelines || {{}};
      window.__timelines["{fr['id']}"] = tl;
    }})();
  </script>
</template>
"""


def outro_frame(i, fr):
    fid = f"f{i}"
    dur = fr["duration"]
    card = fr["card"]
    end = fr["end_at"]
    words = headline(fr["title"], fr.get("key", ""))
    css = base_css(fid) + f"""
    #{fid}-h {{ position: absolute; left: 70px; right: 90px; top: 210px; text-align: center; font-family: "Bricolage Grotesque", sans-serif; font-weight: 800; font-size: 88px; line-height: 1; letter-spacing: -.03em; }}
    #{fid}-h .w {{ display: inline-block; }}
    #{fid}-card {{ position: absolute; left: {card[0] - 12}px; top: {card[1] - 12}px; width: {card[2] + 24}px; height: {card[3] + 24}px; border-radius: 44px; background: #fff; border: 3px solid {C['ink']};
      box-shadow: 14px 14px 0 {C['coral']}, 0 40px 80px -30px rgba(27,27,27,.4); }}
    #{fid}-end {{ position: absolute; inset: 0; opacity: 0; }}
    #{fid}-mascot {{ position: absolute; left: 290px; top: 360px; width: 500px; height: 517px; }}
    #{fid}-word {{ position: absolute; left: 0; right: 0; top: 930px; text-align: center; font-family: "Bricolage Grotesque", sans-serif; font-weight: 800; font-size: 150px; letter-spacing: -.025em; line-height: 1; }}
    #{fid}-tag {{ position: absolute; left: 0; right: 0; top: 1110px; text-align: center; font-family: "Bricolage Grotesque", sans-serif; font-weight: 700; font-size: 60px; letter-spacing: -.02em; }}
    #{fid}-cta {{ position: absolute; left: 0; right: 0; margin: 0 auto; top: 1250px; width: max-content; padding: 0 56px; height: 130px; border-radius: 9999px; background: {C['button']}; color: #fff;
      border: 3px solid {C['ink']}; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 50px; }}
    #{fid}-note {{ position: absolute; left: 0; right: 0; top: 1412px; text-align: center; font-weight: 600; font-size: 36px; color: {C['body']}; }}"""
    tl = [
        f'tl.fromTo("#{fid}-h .w", {{ opacity: 0, y: 30 }}, {{ opacity: 1, y: 0, duration: 0.45, ease: "power3.out", stagger: 0.07 }}, 0.1);',
        f'tl.to("#{fid} .sw", {{ backgroundSize: "100% 40%", duration: 0.5, ease: "power2.inOut" }}, 0.8);',
        f'tl.fromTo("#{fid}-card", {{ opacity: 0, scale: .94 }}, {{ opacity: 1, scale: 1, duration: 0.5, ease: "power3.out" }}, 0);',
        f'tl.to(["#{fid}-h", "#{fid}-card"], {{ opacity: 0, duration: 0.35, ease: "power1.in" }}, {end - 0.35});',
        f'tl.set("#{fid}-end", {{ opacity: 1 }}, {end});',
        f'tl.fromTo("#{fid}-mascot", {{ opacity: 0, y: 60, scale: .8 }}, {{ opacity: 1, y: 0, scale: 1, duration: 0.6, ease: "back.out(1.8)" }}, {end});',
        f'tl.fromTo("#{fid}-word", {{ opacity: 0, y: 30 }}, {{ opacity: 1, y: 0, duration: 0.45, ease: "power3.out" }}, {end + 0.3});',
        f'tl.fromTo("#{fid}-tag", {{ opacity: 0, y: 20 }}, {{ opacity: 1, y: 0, duration: 0.45, ease: "power3.out" }}, {end + 0.55});',
        f'tl.fromTo("#{fid}-cta", {{ opacity: 0, scale: .7 }}, {{ opacity: 1, scale: 1, duration: 0.5, ease: "back.out(2.2)" }}, {end + 0.85});',
        f'tl.fromTo("#{fid}-note", {{ opacity: 0, y: 16 }}, {{ opacity: 1, y: 0, duration: 0.4, ease: "power3.out" }}, {end + 1.1});',
        f"tl.to({{}}, {{ duration: {dur} }}, 0);",
    ]
    return f"""<template>
  <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
  <style>{css}
  </style>
  <div id="{fid}" data-composition-id="{fr['id']}" data-width="1080" data-height="1920">
    <div id="root-{fid}">
      <div id="{fid}-bg" class="bg-{fid} clip" data-start="0" data-duration="{dur}" data-track-index="0"></div>
      <h1 id="{fid}-h">{words}</h1>
      <div id="{fid}-card"></div>
      <div id="{fid}-end">
        <img id="{fid}-mascot" src="assets/strokeberry-mascot.png" alt="" />
        <div id="{fid}-word">strokeberry</div>
        <div id="{fid}-tag">Your images. Drawn to life.</div>
        <div id="{fid}-cta">{escape(fr.get("cta", "Try it at strokeberry.com"))}</div>
        <div id="{fid}-note">{escape(fr.get("cta_note", ""))}</div>
      </div>
    </div>
  </div>
  <script>
    (function () {{
      const tl = gsap.timeline({{ paused: true }});
      {chr(10).join('      ' + x for x in tl).strip()}
      window.__timelines = window.__timelines || {{}};
      window.__timelines["{fr['id']}"] = tl;
    }})();
  </script>
</template>
"""


def crop_card(fid, n, card):
    """Crop a card image from a captured screen (3x) using a target rectangle; 'square' keeps the centred square."""
    shot = next(x for x in shots["shots"] if x["id"] == card["screen"])
    r = shot["rects"][card.get("target", "canvas")]
    dpr = shots["viewport"]["dpr"]
    x0, y0, w, h = r["x"] * dpr, r["y"] * dpr, r["w"] * dpr, r["h"] * dpr
    if card.get("crop") == "square":
        side = min(w, h)
        x0, y0, w, h = x0 + (w - side) / 2, y0 + (h - side) / 2, side, side
    from PIL import Image
    out = PROJECT / f"assets/crops/{fid}-{n}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    Image.open(PROJECT / "capture/app" / shot["file"]).crop((round(x0), round(y0), round(x0 + w), round(y0 + h))).save(out)
    return out.relative_to(PROJECT)


def compare_frame(i, fr):
    """Side-by-side cards of the real preview under different settings, revealed one after another."""
    fid = f"f{i}"
    dur = fr["duration"]
    cards = fr["cards"]
    n = len(cards)
    gap = 40
    cw = (1080 - 2 * 50 - gap * (n - 1)) // n
    ih = cw if n == 2 else 420
    # Centre the cards in the space between the header (y 470) and the bottom safe line (y 1680).
    top = fr.get("cards_top", round(470 + (1210 - (ih + 200)) / 2))
    words = headline(fr["title"], fr.get("key", ""))
    items, tl = [], []
    for k, c in enumerate(cards):
        src = crop_card(fid, k, c)
        x = 50 + k * (cw + gap)
        items.append(f'''      <div class="{fid}-card" id="{fid}-c{k}" style="left:{x}px;top:{top}px;width:{cw}px">
        <div class="{fid}-img" style="height:{ih}px"><img src="{src}" alt="" /></div>
        <strong>{escape(c["label"])}</strong><small>{escape(c.get("sub", ""))}</small>
      </div>''')
        at = c.get("at", 1.0 + k * 1.2)
        tl.append(f'tl.fromTo("#{fid}-c{k}", {{ opacity: 0, y: 60, scale: .96 }}, {{ opacity: 1, y: 0, scale: 1, duration: 0.5, ease: "back.out(1.6)", immediateRender: false }}, {at});')
    hints = []
    for k, h in enumerate(fr.get("hints", [])):
        hints.append(f'      <p class="{fid}-hint" id="{fid}-t{k}">{escape(h["text"])}</p>')
        tl.append(f'tl.fromTo("#{fid}-t{k}", {{ opacity: 0, y: 14 }}, {{ opacity: 1, y: 0, duration: 0.35, ease: "power3.out", immediateRender: false }}, {h["t"]});')
        if k:
            tl.append(f'tl.to("#{fid}-t{k - 1}", {{ opacity: 0, y: -10, duration: 0.25, ease: "power1.in" }}, {max(0, h["t"] - 0.3):g});')
    head = [
        f'tl.fromTo("#{fid}-chip", {{ opacity: 0, y: -16 }}, {{ opacity: 1, y: 0, duration: 0.35, ease: "power3.out" }}, 0.05);',
        f'tl.fromTo("#{fid}-h .w", {{ opacity: 0, y: 26 }}, {{ opacity: 1, y: 0, duration: 0.45, ease: "power3.out", stagger: 0.06 }}, 0.12);',
        f'tl.to("#{fid} .sw", {{ backgroundSize: "100% 40%", duration: 0.5, ease: "power2.inOut" }}, 0.75);',
    ]
    tl = head + tl + [f"tl.to({{}}, {{ duration: {dur} }}, 0);"]
    css = base_css(fid) + f"""
    #{fid}-chip {{ position: absolute; left: 80px; top: 196px; height: 58px; padding: 0 26px; border-radius: 9999px; background: {C['coral']}; color: #fff;
      display: flex; align-items: center; font-weight: 800; font-size: 26px; letter-spacing: .12em; border: 2px solid {C['ink']}; }}
    #{fid}-h {{ position: absolute; left: 80px; right: 110px; top: 272px; font-family: "Bricolage Grotesque", sans-serif; font-weight: 800; font-size: 76px; line-height: 1.02; letter-spacing: -.025em; }}
    #{fid}-h .w {{ display: inline-block; }}
    .{fid}-hint {{ position: absolute; left: 80px; right: 110px; top: 360px; margin: 0; font-size: 33px; font-weight: 600; line-height: 1.25; color: {C['body']}; }}
    .{fid}-card, .{fid}-hint {{ opacity: 0; }}
    .{fid}-card {{ position: absolute; background: #fff; border: 3px solid {C['ink']}; border-radius: 36px; padding: 18px 18px 24px;
      box-shadow: 10px 10px 0 rgba(27,27,27,.08), 0 30px 60px -30px rgba(27,27,27,.4); }}
    .{fid}-img {{ border-radius: 22px; overflow: hidden; background: #FAF9F6; display: flex; align-items: center; justify-content: center; }}
    .{fid}-img img {{ max-width: 100%; max-height: 100%; display: block; }}
    .{fid}-card strong {{ display: block; margin-top: 20px; font-family: "Bricolage Grotesque", sans-serif; font-weight: 800; font-size: {52 if n == 2 else 44}px; letter-spacing: -.02em; line-height: 1; }}
    .{fid}-card small {{ display: block; margin-top: 10px; font-size: {30 if n == 2 else 26}px; font-weight: 600; line-height: 1.25; color: {C['body']}; }}"""
    return f"""<template>
  <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
  <style>{css}
  </style>
  <div id="{fid}" data-composition-id="{fr['id']}" data-width="1080" data-height="1920">
    <div id="root-{fid}">
      <div id="{fid}-bg" class="bg-{fid} clip" data-start="0" data-duration="{dur}" data-track-index="0"></div>
      <div id="{fid}-chip">{escape(fr['chip'])}</div>
      <h1 id="{fid}-h">{words}</h1>
{chr(10).join(hints)}
{chr(10).join(items)}
    </div>
  </div>
  <script>
    (function () {{
      const tl = gsap.timeline({{ paused: true }});
      {chr(10).join('      ' + x for x in tl).strip()}
      window.__timelines = window.__timelines || {{}};
      window.__timelines["{fr['id']}"] = tl;
    }})();
  </script>
</template>
"""


def build():
    stage_assets()
    out = PROJECT / "compositions/frames"
    out.mkdir(parents=True, exist_ok=True)
    clips, videos, t = [], [], 0.0
    for i, fr in enumerate(spec["frames"], 1):
        kind = fr["kind"]
        html = {"intro": intro_frame, "step": step_frame, "outro": outro_frame, "compare": compare_frame}[kind](i, fr)
        (out / f"{fr['id']}.html").write_text(html)
        clips.append(f'      <div id="el-{fr["id"]}" class="scene" data-composition-id="{fr["id"]}" data-composition-src="compositions/frames/{fr["id"]}.html" '
                     f'data-start="{t:g}" data-duration="{fr["duration"]}" data-track-index="{i - 1}"></div>')
        for v in fr.get("videos", []):
            x, y, w, h = v["rect"]
            if v.get("in_phone"):
                x, y, w, h = SX + x * K, SY + y * K, w * K, h * K
            vid = f'el-{fr["id"]}-v{len(videos)}'
            videos.append((vid, t + v["at"], v["duration"], v.get("media_start", 0), x, y, w, h, v.get("radius", 32)))
        t += fr["duration"]
    total = t
    vtags = "\n".join(
        f'      <video id="{vid}" src="{RESULT}" preload="auto" muted playsinline class="clip" '
        f'style="position:absolute;left:{x:.1f}px;top:{y:.1f}px;width:{w:.1f}px;height:{h:.1f}px;object-fit:cover;border-radius:{r}px" '
        f'data-start="{s:g}" data-duration="{d:g}" data-media-start="{ms:g}" data-track-index="{10 + n}"></video>'
        for n, (vid, s, d, ms, x, y, w, h, r) in enumerate(videos))
    vfades = "\n".join(
        f'        tl.fromTo("#{vid}", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.3, ease: "power1.out" }}, {s:g});\n'
        f'        tl.to("#{vid}", {{ opacity: 0, duration: 0.3, ease: "power1.in" }}, {s + d - 0.3:g});'
        for vid, s, d, *_ in videos)
    meta = json.loads((PROJECT / "audio_meta.json").read_text()) if (PROJECT / "audio_meta.json").exists() else {}
    audio, vo_spans = [], []
    vo_file = PROJECT / spec.get("voiceover", "") if spec.get("voiceover") and "--no-vo" not in sys.argv else None
    if vo_file and vo_file.is_file():
        for n, (at, _text) in enumerate(json.loads(vo_file.read_text())):
            wav = PROJECT / f"assets/vo/line-{n:02d}.wav"
            dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(wav)],
                                       capture_output=True, text=True).stdout)
            vo_spans.append((at, dur))
            audio.append(f'      <audio id="el-vo-{n}" src="assets/vo/line-{n:02d}.wav" data-start="{at:g}" data-duration="{dur:.3f}" data-track-index="{60 + n}" data-volume="1"></audio>')
    if meta.get("bgm"):
        src = PROJECT / meta["bgm"]["path"]
        length = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(src)],
                                      capture_output=True, text=True).stdout)
        if length < total:
            looped = src.with_name(src.stem + "-loop.mp3")
            copies = int(total // (length - 3)) + 1
            inputs = sum([["-i", str(src)] for _ in range(copies)], [])
            filt, last = "", "[0:a]"
            for n in range(1, copies):
                filt += f"{last}[{n}:a]acrossfade=d=3:c1=tri:c2=tri[x{n}];"
                last = f"[x{n}]"
            subprocess.run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", filt.rstrip(";"), "-map", last,
                            "-t", f"{total + 0.5}", "-b:a", "192k", str(looped)], check=True)
            meta["bgm"]["path"] = str(looped.relative_to(PROJECT))
        # Duck the music under the voice: merge lines less than 1.6s apart into one dip, keep points in order.
        spans = []
        for at, dur in sorted(vo_spans):
            if spans and at - spans[-1][1] < 1.6:
                spans[-1][1] = max(spans[-1][1], at + dur)
            else:
                spans.append([at, at + dur])
        pts, last = [{"t": 0, "v": 0}, {"t": 0.4, "v": 1}], 0.4
        for a0, b0 in spans:
            down = max(last + 0.05, a0 - 0.3)
            low_start = max(down + 0.05, a0)
            up = min(total - 3.2, b0 + 0.4)
            if up <= low_start:
                continue
            pts += [{"t": round(down, 2), "v": 1}, {"t": round(low_start, 2), "v": 0.3},
                    {"t": round(max(low_start + 0.05, min(b0, up - 0.05)), 2), "v": 0.3}, {"t": round(up, 2), "v": 1}]
            last = up
        pts += [{"t": total - 3, "v": 1, "curve": -0.3}, {"t": total, "v": 0}]
        auto = json.dumps({"version": 1, "lanes": [{"target": "volume", "points": pts}]})
        audio.append(f"      <audio id=\"el-bgm\" src=\"{meta['bgm']['path']}\" data-automation='{auto}' data-start=\"0\" data-duration=\"{total:g}\" data-track-index=\"30\" data-volume=\"0.8\"></audio>")
    for n, (at, name, vol) in enumerate(spec.get("sfx", [])):
        dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                    str(PROJECT / f"assets/sfx/{name}.mp3")], capture_output=True, text=True).stdout)
        audio.append(f'      <audio id="el-sfx-{n}" src="assets/sfx/{name}.mp3" data-start="{at:g}" data-duration="{dur:.3f}" data-track-index="{31 + n}" data-volume="{vol}"></audio>')
    index = f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=1080, height=1920">
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
    <style>
      * {{ margin: 0; padding: 0; box-sizing: border-box; }}
      html, body {{ width: 1080px; height: 1920px; overflow: hidden; background: #000; }}
      #root {{ position: relative; width: 1080px; height: 1920px; overflow: hidden; background: {C['cream']}; }}
      .scene {{ position: absolute; inset: 0; width: 100%; height: 100%; }}
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="{total:g}" data-width="1080" data-height="1920">
{chr(10).join(clips)}

{vtags}

{chr(10).join(audio)}
    </div>
    <script>
      window.__timelines = window.__timelines || {{}};
      window.__timelines["main"] = gsap.timeline({{ paused: true }});
      (function () {{ var tl = window.__timelines["main"];
{vfades}
        tl.to({{}}, {{ duration: {total:g} }}, 0);
      }})();
    </script>
  </body>
</html>
"""
    (PROJECT / "index.html").write_text(index)
    print(f"Built {len(spec['frames'])} frames, {total:g}s → {PROJECT.relative_to(ROOT)}/index.html")


build()
