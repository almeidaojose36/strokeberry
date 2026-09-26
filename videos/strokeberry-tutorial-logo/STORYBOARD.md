---
format: 1080x1920
duration: 60s
message: "Turn your logo into a hand-drawn video in four taps"
arc: Hook (the result) → Step 1 Upload → Step 2 Drawing style → Step 3 Video settings → Step 4 Preview → Step 5 Export → Result + CTA
audience: small brands, Etsy sellers and creators who want eye-catching content from their logo
mode: autonomous
music: light upbeat playful acoustic pop, plucky guitar and soft claps, friendly tutorial background, around 110 bpm, no vocals
---

## Video direction

- show-it tutorial: every app screen is a real 3x screenshot of the live studio (capture/app/*.png), shown inside one phone frame that stays in the same place for Frames 2–6 so the eye never hunts. No rebuilt UI.
- layout (portrait 1080×1920): step header block at the top (y 200–430: step chip "STEP n / 5" + Bricolage 800 headline + one Figtree hint line); phone (screen 560×1212, 2px ink bezel radius 64, soft hard-offset shadow) centred at x 260–820, y 470–1682. Bottom 238px and right 12% stay clear of Reels/TikTok UI.
- tap language: a coral (#EC2D34) ring + soft fill pulses on the exact control rectangle from capture/app/shots.json when it is "tapped"; the next screenshot crossfades in 0.2s after the tap. Small controls get a punch-in (phone scales ≤1.6 around the target) so text is readable on a phone, then eases back.
- palette: cream ground, ink type, coral taps and the step chip; yellow marker swash under the key word of each headline; teal/leaf only as small chip accents. Full mascot only (never the compact mark above 48px).
- motion: power3 settles; taps are the only spring (back.out). Each frame develops across its full duration (tap → result → next tap); no front-loading.
- negative list: no offer copy, no fake UI, no cursor arrow, no stock imagery.

## Frame 1 — Hook: your logo, drawn

- scene: The finished result plays (the real export) in a tall card while the headline promises "Turn your logo into a drawing video" and a chip says "Step-by-step · 60s"
- voiceover: ""
- duration: 5s
- transition_in: cut
- status: outline
- src: compositions/frames/01-hook.html
- asset_candidates: capture/app/result.mp4 — the real 15s export of the Strokeberry mascot being drawn (plays at 3x, last 5s of colour); ../../frontend/public/brand/strokeberry-mascot@2x.png — full mascot
- sfx: pencil scratch

Scene 1 (0–1.2s): card with result.mp4 (sped 3x) slides up; headline words land.
Scene 2 (1.2–4s): yellow swash under "drawing video"; chip "Step-by-step · 60s" pops.
Scene 3 (4–5s): hold; card shrinks toward the phone position.

## Frame 2 — Step 1: Upload your logo

- scene: Phone shows the studio; tap on Replace; "Preparing your canvas…"; the mascot logo appears in the preview
- voiceover: ""
- duration: 10s
- transition_in: crossfade
- status: outline
- src: compositions/frames/02-upload.html
- asset_candidates: capture/app/01-start.png; capture/app/02-uploading.png; capture/app/03-uploaded.png
- sfx: pop

Scene 1 (0–2s): header "STEP 1 / 5 · Upload your logo", hint "Open the studio and tap Replace (or Choose an image)". Phone with 01-start.
Scene 2 (2–4s): punch-in to the Replace button; tap ring pulses.
Scene 3 (4–6s): crossfade to 02-uploading (spinner). Hint: "PNG, JPG or WebP · up to 15 MB".
Scene 4 (6–10s): crossfade to 03-uploaded; punch-in on the source row "strokeberry-logo.png · 100 drawing strokes"; ease back.

## Frame 3 — Step 2: Pick the drawing style

- scene: Settings → Drawing style; tap Ink; show the pencil and colour toggles on
- voiceover: ""
- duration: 11s
- transition_in: crossfade
- status: outline
- src: compositions/frames/03-style.html
- asset_candidates: capture/app/04-settings.png; capture/app/05-style.png; capture/app/06-toggles.png
- sfx: pop, pop

Scene 1 (0–2s): header "STEP 2 / 5 · Pick Ink for logos", hint "Ink draws bold, confident lines, perfect for logos". Phone with 04-settings.
Scene 2 (2–5s): punch-in on the style cards; tap Ink; crossfade to 05-style.
Scene 3 (5–9s): 06-toggles; ring on "Show drawing pencil" then "Bring in the color"; hint changes to "Keep 'Bring in the color' on to finish in full colour".
Scene 4 (9–11s): ring on Duration 0:15; hint "15 seconds is perfect for Reels".

## Frame 4 — Step 3: Video settings

- scene: Tap Video settings; choose 9:16 Portrait and Full HD 1080p
- voiceover: ""
- duration: 9s
- transition_in: crossfade
- status: outline
- src: compositions/frames/04-video.html
- asset_candidates: capture/app/07-video-tab.png; capture/app/08-video-set.png
- sfx: pop, pop

Scene 1 (0–2s): header "STEP 3 / 5 · Set it up for Reels", 07-video-tab with ring on the tab.
Scene 2 (2–5s): punch-in, tap 9:16 Portrait; crossfade to 08-video-set.
Scene 3 (5–9s): ring on Quality "Full HD · 1080p"; then the summary line "1080p MP4 · 9:16 · 0:15".

## Frame 5 — Step 4: Preview it

- scene: Press play; the live preview draws the logo (4 real preview screenshots in sequence)
- voiceover: ""
- duration: 7s
- transition_in: crossfade
- status: outline
- src: compositions/frames/05-preview.html
- asset_candidates: capture/app/09-preview-1.png … 09-preview-4.png
- sfx: pencil scratch

Scene 1 (0–1.5s): header "STEP 4 / 5 · Preview before you export"; ring on play.
Scene 2 (1.5–7s): the four preview screens step through (sketch → details → colour), punch-in on the preview.

## Frame 6 — Step 5: Export & download

- scene: Tap Export video; "Rendering your video"; "Your video is ready" → tap Download MP4
- voiceover: ""
- duration: 9s
- transition_in: crossfade
- status: outline
- src: compositions/frames/06-export.html
- asset_candidates: capture/app/10-export.png; capture/app/11-exporting.png; capture/app/12-ready.png; capture/app/result.mp4 (plays inside the ready dialog's player)
- sfx: pop, chime

Scene 1 (0–2.5s): header "STEP 5 / 5 · Export & download"; ring on Export video.
Scene 2 (2.5–5s): 11-exporting; hint "Renders on your device, no watermark".
Scene 3 (5–9s): 12-ready with result.mp4 playing in the dialog player; ring on Download MP4.

## Frame 7 — Result + CTA

- scene: The finished video fills the frame, then the full mascot and "Try it at strokeberry.com"
- voiceover: ""
- duration: 9s
- transition_in: crossfade
- status: outline
- src: compositions/frames/07-result.html
- asset_candidates: capture/app/result.mp4; ../../frontend/public/brand/strokeberry-mascot@2x.png
- sfx: chime

Scene 1 (0–5s): "Your logo, drawn to life" over the result video playing in a large card (last colour section).
Scene 2 (5–9s): end card: full mascot, wordmark "strokeberry", "Your images. Drawn to life.", CTA pill "strokeberry.com"; still hold ≥1.5s.
