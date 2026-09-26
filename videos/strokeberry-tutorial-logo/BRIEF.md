---
workflow: product-launch-video
flow: automation
storyboard: no
message: "Turn your logo into a hand-drawn video in four taps"
destination: tiktok-reels-shorts
aspect: 1080x1920
language: en
audience: small brands, Etsy sellers and creators who want eye-catching content from their logo
length: 60s
angle: step-by-step-tutorial
narration: no
---

## Intent

Tutorial 1 of a 4-part series of ~60s step-by-step marketing tutorials. Show the real Strokeberry
studio as-is (a show-it tutorial, not an invented UI): Step 1 upload the image in the app, Step 2
choose the right settings (Ink style, colour on), Step 3 video settings (9:16 Portrait, 1080p),
Step 4 preview, Step 5 export, then the finished drawn video. The user's words: "include the first
step that shows the image being uploaded on the app, then choosing the right setting etc".
On-screen step captions + music, readable with sound off.

## Assets

- ../../frontend/public/brand/strokeberry-logo@2x.png — the approved Strokeberry logo; the demo image being uploaded and drawn.
- ../../frontend/public/brand/strokeberry-mascot@2x.png — approved full mascot; intro and end card (full mascot everywhere).

## Customizations

- Real screen captures of http://127.0.0.1:8001/studio/ at phone size (390×844 @3x), taken by a scripted browser at each step.
- The app's real exported MP4 of the logo is the result shot.
- Tap highlights on each control that is pressed; step counter chips "Step 1/5".

## Notes

- CTA: strokeberry.com only. No offer copy ("3 videos free", discounts) until billing exists.
- Brand: approved artwork only, never redrawn; full mascot everywhere, compact mark only for tiny spots.
- Series siblings to build after approval: drawing tutorial → video, illustration → speedpaint, settings deep-dive.

## Customizations (added)

- Voice-over variant (renders/video-voiceover.mp4): HeyGen voice "Mira - Upbeat & Lively" (29d09609d8a64c8ca19bb497333ea4c9), lines in vo-lines.json, music ducked to 30% under the voice. Captions-only version stays at renders/video.mp4.
- ../../marketing/demo-brands/little-crumb/little-crumb-logo.png — made-up demo brand (Little Crumb Coffee Co.), transparent PNG; the image uploaded and drawn in the tutorial. Real brands are not used (trademark risk).
