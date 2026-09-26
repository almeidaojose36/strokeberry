---
format: 1080x1920
duration: 20s
message: "Turn any image into a hand-drawn video in one click"
arc: Hook (guess 1) → Guess 2 + value claim → Speed round reveals the mascot → The ad draws itself (CTA)
audience: social creators, art teachers, Etsy sellers and small brands scrolling vertical feeds
mode: autonomous
music: upbeat playful bouncy pop, bright plucks and claps, satisfying, around 120 bpm, no vocals
---

## Video direction

- palette system (frame.md): ground = cream; all type = ink; primary accent = coral (#EC2D34, berry) for countdown rings, answer-pill fills and the CTA; yellow (#FABE3A, sun) only as the marker-highlight swash under key words; sky/violet (teal) and lime (leaf) as small chip accents. Drawing canvases are the product's own paper (#FAF9F6) inside a white pill-card with the frame.md 2px ink outline and soft hard-offset shadow.
- type: display ramp (Bricolage Grotesque 800) for the question/header lines; body ramp (Figtree) for the value line and chips; the answer pill uses pill-text.
- motion grammar + reveal model: smooth long-tail settles (power3) for everything except the answer pills, which spring-pop (the one sanctioned playful overshoot — this is a game). Nothing is narrated, so reveals are paced to the MUSIC and the drawing itself: the canvas is live from t=0 (the drawing IS the hook), each text piece arrives on the next bar, and every color reveal is the beat's payoff. No lazy breathing; holds stay still (subtle jitter at most).
- rhythm: frames 1–3 escalate (each round shorter, faster playback, quicker text); frame 4 slows down for the hand-drawn ending and ends on a still, readable CTA hold (~1.1s).
- layout: portrait 1080×1920. All content in the top ~83% and away from the right edge (~12%), clear of TikTok/Reels buttons and captions. The drawing canvas is the dominant element (≥40% of frame) in every guess frame, same position frame to frame so the eye never hunts.
- negative list: no stock imagery, no third-party characters, no bokeh/"AI" gradients, no cursor or browser chrome; no slideshow (front-load then freeze) and no screensaver (everything floating independently).


## Frame 1 — Guess #1

- scene: A sneaker draws itself line by line while bold type asks "Guess what it is 👀"; a countdown ring ticks, then the colors pop in
- voiceover: ""
- duration: 5.5s
- poster: 3s
- transition_in: cut
- status: animated
- src: compositions/frames/01-guess-one.html
- type: hook
- persuasion: Curiosity gap (an unanswered question the viewer must stay to resolve)
- beat: curiosity + intrigue
- blueprint: kinetic-type-beats
- asset_candidates: assets/sneaker.mp4 — real Strokeberry ink export: sneaker drawn line by line, then colors sweep in; assets/sneaker.jpg — finished colored sneaker
- sfx: pencil scratch, pop
- focal: assets/sneaker.mp4
- roles: sneaker.mp4 = cutout (the live canvas, played at 2.2× so the 10s export resolves in ~4.5s) · sneaker.jpg = supporting (poster)

Adapt kinetic-type-beats: keep the bold statement slam as the signature; add the live drawing canvas as the stage and a countdown ring as the timer.
Scene 1 (0.0–0.5s): the canvas card already sits centered in the middle band (~70% width), its drawing live from frame one; "Guess what it is 👀" slams in above it word by word (kinetic beat-slam), display ramp, centered upper third.
Scene 2 (0.5–2.9s): the sneaker keeps drawing; a coral countdown ring on a small pill at the card's top-left edge sweeps and ticks 3 → 2 → 1 (bars/progress ring fill), one tick per beat. Nothing else enters.
Scene 3 (2.9–3.6s): the colors sweep into the drawing (the export itself); on that beat an answer pill "A sneaker! 👟" spring-pops just below the card, coral fill, pop sfx.
Scene 4 (3.6–5.5s): hold the read — card, question and answer still; subtle jitter at most.

narrativeRole: Stop the scroll in the first half-second with a live drawing and a question; the answer arrives only at the end of the beat.
keyMessage: Something is being drawn in front of you — stay to find out what.

## Frame 2 — Guess #2 (the value claim)

- scene: Round 2, harder: the owl builds from guide circles; a line under the canvas states the value — one image, one click, no drawing skills
- voiceover: ""
- duration: 4.8s
- poster: 3s
- transition_in: cut
- status: animated
- src: compositions/frames/02-guess-two.html
- type: product_intro
- persuasion: Show-don't-tell proof (real output plays while the claim is stated)
- beat: curiosity + aspiration
- blueprint: kinetic-type-beats
- asset_candidates: assets/owl.mp4 — real Strokeberry tutorial-mode export: owl from guide circles to outlines to details to color; assets/owl.jpg — finished owl
- sfx: pop
- focal: assets/owl.mp4
- roles: owl.mp4 = cutout (live canvas at 3.5×, 16s export → ~4.6s) · owl.jpg = supporting

Adapt kinetic-type-beats: keep the in-place header swap as the signature ("Round 2 · harder 👀" replaces frame 1's question); the value line builds per chunk under the canvas.
Scene 1 (0.0–0.6s): card in the same centered position; the owl's guide circles are already sketching; header hard-cuts in: "Round 2 · harder 👀".
Scene 2 (0.6–2.9s): the owl moves through outlines and details; under the card the value line assembles chunk by chunk on the beat — "1 image in." · "1 click." · "No drawing skills." (per-word staggered reveal, body ramp, the last chunk with a yellow marker highlight sweep).
Scene 3 (3.1–3.7s): the owl colors in; the answer pill "An owl! 🦉" spring-pops over the card's lower edge, pop sfx.
Scene 4 (3.7–4.8s): hold still.

narrativeRole: Land the value claim by the second beat while the game continues: every drawing here came from a single uploaded image.
keyMessage: One image in, a hand-drawn video out — no drawing skills needed.

## Frame 3 — Speed round (the reveal is us)

- scene: "Speed round ⚡" — a strawberry builds at speed; when it colors in, it is the Strokeberry mascot, and the type answers "It's us 🍓"
- voiceover: ""
- duration: 4.2s
- poster: 3.4s
- transition_in: cut
- status: animated
- src: compositions/frames/03-speed-round.html
- type: key_feature
- persuasion: Pattern escalation into a brand reveal (each round faster; the final answer is the brand)
- beat: excitement → delight
- blueprint: kinetic-type-beats
- asset_candidates: assets/strawberry.mp4 — real Strokeberry tutorial-mode export: the strawberry mascot built in four stages then colored; assets/strawberry.jpg — finished mascot
- sfx: whoosh, pop
- handoff_out: element strawberry canvas — centered x 540 y 722, scale 1, opacity 1, holding still at the cut
- focal: assets/strawberry.mp4
- roles: strawberry.mp4 = cutout (live canvas at 4.2×, 16s export → ~3.8s) · strawberry.jpg = supporting

Adapt kinetic-type-beats: keep the beat-slam header; add four stage chips as an in-place token cycle so the speed is felt.
Scene 1 (0.0–0.4s): "Speed round ⚡" slams in (header, display ramp), the card in the same centered position, drawing already racing.
Scene 2 (0.4–2.8s): below the card four small chips — Shape · Outline · Details · Color — light up one after another in step with the drawing's stages (in-place token cycle; teal/leaf accents), whoosh sfx at the start.
Scene 3 (2.85–3.5s): the mascot colors in; the answer "It's us 🍓" spring-pops as a coral pill and a yellow marker highlight sweeps under "us", pop sfx.
Scene 4 (3.5–4.2s): hold; the card rests at the handoff position (centered, x 540 y 722, scale 1).

narrativeRole: Escalate the game, then turn the last answer into the brand: the mascot the viewer just watched being drawn IS Strokeberry.
keyMessage: This is Strokeberry — the drawing app that made everything you just watched.

## Frame 4 — The ad draws itself

- scene: On cream paper the Strokeberry logo draws in stroke by stroke, the wordmark writes itself, the promise line and a "Try it free · strokeberry.com" pill draw in, then everything snaps into brand color
- voiceover: ""
- duration: 5.5s
- poster: 4.6s
- transition_in: zoom-through
- status: animated
- src: compositions/frames/04-ad-draws-itself.html
- type: cta
- persuasion: Risk reversal (free to try) + the medium is the message (the CTA is drawn like the product draws)
- beat: delight → urgency-to-act
- blueprint: logo-assemble-lockup
- asset_candidates: assets/strokeberry-icon.svg — Strokeberry mascot/logo, flat vector
- sfx: pencil scratch, chime
- handoff_in: element strawberry mascot — enters centered x 540 y 722 as the logo outline, scale 1, opacity 1, then settles upward into the lockup
- focal: assets/strokeberry-icon.svg
- roles: strokeberry-icon.svg = cutout (hero mark; drawn as outlines first, then filled)

Adapt logo-assemble-lockup: keep the signature "an outline draws on, then resolves into the lockup"; extend it so every element of the end card is drawn the way Strokeberry draws.
Scene 1 (0.0–1.6s): cream paper; the mascot's outlines self-draw stroke by stroke in ink at center-upper (SVG self-draw), pencil scratch sfx. Layout: centered, mascot ~40% width.
Scene 2 (1.6–2.2s): the mascot's fills snap in (berry body, leaf crown, teal headphones, sun clips) and the lowercase wordmark "strokeberry" writes on beside/below it (display ramp 800), lockup settles on a smooth ease.
Scene 3 (2.2–3.4s): the promise line "Turn any image into a hand‑drawn video." reveals word by word below the lockup; a yellow marker swash draws under "hand‑drawn".
Scene 4 (3.4–4.4s): the CTA pill draws its ink outline, then fills berry with white text "Try it free · strokeberry.com", a small press-release spring, chime sfx.
Scene 5 (4.4–5.5s): final still hold on the full end card, fully readable; no exit motion.

narrativeRole: Close by doing what the product does — the brand and the ask are hand-drawn in real time — then give the one action: try it free.
keyMessage: Try Strokeberry free at strokeberry.com.
