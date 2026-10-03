# Strokeberry — handoff

_Last updated: 26 September 2026 (tutorial series added) · branch `strokeberry-initial` · last commit `9b0e10f` (all work since then is **uncommitted**)_

## 1. What it is

**Strokeberry** turns any image into a hand-drawn speed-drawing video (shape → outline → details → colour) for Reels, TikTok and Shorts.
Tagline: **"Your images. Drawn to life."** Domain target: strokeberry.com (unregistered as of 24 Sep 2026; trademark not searched).

- **Studio app** (`/studio/`): React 19 + Vite frontend, FastAPI + OpenCV + Pillow + SQLite + FFmpeg backend. Runs locally, no GPU or API keys needed.
- **Landing page** (`/`): hero with a live product window, scroll-to-draw section, gallery, features, pricing, FAQ.
- User uploads never go to any AI service. KIE (key in `.env.local`, git-ignored) is used only to generate marketing illustrations.

## 2. Running it

```sh
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
npm install
npm start            # builds frontend, serves everything from FastAPI on :8000
```

Development: `npm run server` + `npm run dev` (http://127.0.0.1:5173).
**Known mismatch:** `vite.config.js` proxies the API to port **8001** while `npm run server` and the README use **8000**. During this work the API was run on 8001 (`.venv/bin/uvicorn backend.app:app --port 8001`). Pick one port and align both.

Tests: `npm test` (pytest, `backend/tests`).

## 3. Brand (final, user-approved)

**Mascot:** ink-outlined strawberry wearing teal headphones and holding a yellow pencil.

**The approved artwork is the master. Never redraw, trace or restyle it in-house.** Files are only cropped, scaled and placed on backgrounds. (A vector redraw was tried and rejected by the owner.)

**Usage rule:**
- **Full-body mascot on everything:** headers, hero, banners, profile pictures, video, docs, merch.
- **Compact mark (head + pencil) only in small places:** favicons, app icon, avatars and badges under ~48 px.

| Token | Hex | Use |
|---|---|---|
| Paper | `#FFF8EC` | Main background |
| Charcoal | `#1B1B1B` | Text, outlines, dark layouts |
| Strawberry | `#EC2D34` | Brand accent, large shapes |
| Strawberry button | `#D42630` | Buttons with white text |
| Strawberry text | `#C81E2A` | Small red text |
| Teal | `#00BEC8` | Headphones, accents |
| Teal deep | `#0096A0` | Teal behind white text |
| Leaf | `#69B644` | Success, leaf |
| Pencil | `#FABE3A` | Highlights, marker swash |
| Blush | `#FD8F90` | Soft accents |

**Type:** Bricolage Grotesque 700–800 (headlines; wordmark is lowercase **strokeberry**, 800, tracking −2%) + Figtree 400–700 (body).
**Voice:** warm, clear, specific. No guaranteed render times, no unsupported AI claims.

### Where the brand files live

| Path | What |
|---|---|
| `marketing/brand-sources/approved/` | **Masters**: `mascot-transparent.png`, `logo-cream.png`, `approval-sheet.webp`, `profile-cream.png`, `banner-dark.png` |
| `marketing/brand-sources/fonts/` | Bricolage Grotesque + Figtree TTFs and licences |
| `frontend/public/brand/` | Exported PNGs used by site/app (mascot, lockups, compact mark, app icons, favicons, og-image) |
| `marketing/social/` | Banner/profile/highlight/og templates (`template.html`, `og.html`, `src/`) and `account-copy.md` (bios + captions) |
| `marketing/brand-kit-v1.1/` + `marketing/Strokeberry-brand-kit-v1.1.zip` | Generated brand kit: logos, app icons, social, tokens, fonts, README, 14-page guidelines PDF + PPTX (git-ignored; rebuild with the command below) |
| `marketing/brand-kit-v1/` | The owner's original v1 kit (kept, git-ignored) |

### Rebuilding all brand assets

```sh
.venv/bin/python scripts/brand/approved_marks.py \
  && .venv/bin/python scripts/brand/export.py \
  && scripts/render-social.sh \
  && .venv/bin/python scripts/brand/build_kit.py
```

- `approved_marks.py`: cuts the compact mark out of the approval sheet (03 app icon), transparent.
- `export.py`: all PNG sizes into `frontend/public/brand/` (dark lockup wordmark set via headless Chrome).
- `render-social.sh`: platform banners, profile pictures, highlight covers, `og-image.png`.
- `build_kit.py`: assembles `brand-kit-v1.1/`, zip, guidelines PDF + PPTX.

Needs Google Chrome at the default macOS path (or set `CHROME`), and `python-pptx` in `.venv`.

**Known limit:** the compact-mark source is only ~312 px (cropped from the approval sheet), so it's soft at 1024 px app-store size. Get the original high-res export of the compact logo/app icon if it exists. For print or embroidery, commission a professional vector trace of the approved art.

## 4. Launch video

`videos/strokeberry-launch/` (HyperFrames 0.8.74): a 20-second vertical 1080×1920 ad for Reels/TikTok/Shorts. The "guess what it is" hook shows the app drawing a sneaker, an owl and a strawberry, then ends on a full-mascot end card with a CTA ("Try it free · strokeberry.com"). Music fades out over 18–20 s.

```sh
cd videos/strokeberry-launch
npm run check
npm run render -- -o renders/video.mp4
```

Hand edits live in `index.html`: SFX timings and the BGM volume automation. Re-running the assemble step overwrites them.

## 4b. Tutorial video series (4 × ~60s, 9:16)

| # | Tutorial | Project | Demo image |
|---|---|---|---|
| 1 | Logo → video (Ink, colour, upload tips, "Set up steps" callout) | `videos/strokeberry-tutorial-logo/` | Little Crumb Coffee Co. — a **made-up** café brand (`marketing/demo-brands/little-crumb/`) |
| 2 | Drawing tutorial sheet → one video ("Set up steps") | `videos/strokeberry-tutorial-steps/` | owl how-to-draw sheet |
| 3 | Illustration → speedpaint (Pencil, drawing pencil, 1:1, View original) | `videos/strokeberry-tutorial-speedpaint/` | cat illustration |
| 4 | Settings deep-dive (side-by-side comparisons of every setting) | `videos/strokeberry-tutorial-settings/` | botanical wreath |

Each renders two versions into `renders/` (git-ignored): `video-voiceover.mp4` (narrated; for the studio empty
state, help centre, welcome emails) and `video.mp4` (captions only; for Reels/TikTok). End cards say
"Create your first video · Open the Studio at strokeberry.com" (no offer copy).

**How they are made** (`scripts/tutorials/`):
1. `capture-flow.mjs <flow.json> <out>` drives the real studio (API on :8001) at phone size (390×844 @3x) through a
   scripted list of actions, saving screenshots, tap-target rectangles (`shots.json`) and the real export (`result.mp4`).
   (`capture-studio.mjs` is the older fixed-flow version used for tutorial 1.)
2. `build_frames.py <tutorial.json> [--no-vo]` builds the HyperFrames frames (intro / step / compare / outro), tap rings,
   punch-ins, SFX, looped BGM with ducking under the voice, and `index.html`.
3. `elevenlabs_vo.py <vo-lines.json> [--only 3,5]` generates narration with the custom **Strokeberry Narrator** voice
   (ElevenLabs, paid Creator plan; key `ELEVENLABS_API_KEY` in `.env.local`; voice id in `marketing/voice/voice.json`).
   `elevenlabs_design_voice.py` created the voice (candidate 3 chosen by the owner; candidate 2 is also in the account).
4. `generate-demo-logo.mjs` made the fictional café logo with KIE. **Never feature real brands' logos** (trademark risk).

Render: `cd videos/<project> && npx hyperframes check && npx hyperframes render --quality high --output renders/video-voiceover.mp4`,
then `build_frames.py … --no-vo` and render `renders/video.mp4` (rebuild without `--no-vo` afterwards).
Check narration by transcribing the render (`npx hyperframes transcribe`).

## 5. Open issues / before launch

1. **Launch gate.** Launch only once everything in §7's checklist is done (Firebase, Lemon Squeezy, hosting, legal review). The landing page shows the Founding member offer only when `STROKEBERRY_FOUNDER_CODE` is set and billing is configured, so nothing is promised before then.
2. **Hosting not done.** Recommended: the owner's Hostinger VPS (FastAPI + FFmpeg need a real server). strokeberry.com is registered on Cloudflare (expires 2027-09-26).
2b. **Tutorial narration:** tutorial 1 (logo) was re-voiced on 2026-09-28 to say "Strokeberry draws it for you". Tutorials 2 and 3 (steps, speedpaint) still say "It renders right on your device" in an on-screen caption (not the narration). Change the caption in `tutorial.json` and re-render before posting. Their app screenshots also show the local-mode footer "Rendered on your device · no watermark".
3. **Don't post the launch video** until the domain is live and the app is hosted.
4. **Port mismatch** 8000 vs 8001 (see §2).
5. **Renderer backlog:** white square around exported images; panel-divider detection on multi-step tutorials.
6. **Uncommitted work:** all the rebrand, brand scripts, marketing and video work, plus earlier edits to `backend/app.py`, `backend/steps.py`, `backend/tests/test_steps.py` and `frontend/src/StepEditor.jsx` that weren't reviewed here. Review `git status` before committing.
7. **Untidy leftovers:** `marketing/marketing/social-kit/` (duplicate of `marketing/social-kit/`), `scripts/build_brand_assets.py` and `scripts/build_social_kit.py` (from another tool, not in the pipeline), plus old zips in `marketing/`.
8. Trademark search for "Strokeberry" not yet done.

## 6. Monetisation direction (from earlier discussion; not final)

Freemium: a few free watermarked 720p exports, then a subscription for 1080p, no watermark and more exports. Launch promo idea: 40% off the first 3 months, but only once checkout supports it. Audiences: creators, teachers, Etsy sellers, small brands.

## 7. Accounts, plans, payments and examples (branch `feature/accounts-plans-gallery`)

Config lives in `.env.local` (see `.env.example`). Each part switches on only when its settings are present.

- **Sign-in:** Firebase Auth (Google and email link). The frontend is in `frontend/src/auth.js` and `SignIn.jsx`; the server verifies ID tokens in `backend/accounts.py`.
  - Without the `VITE_FIREBASE_*` and `FIREBASE_PROJECT_ID` settings, the studio runs as the single local user, as before, and the "on your device" copy stays.
  - Preview the signed-in UI locally: `STROKEBERRY_AUTH=dev STROKEBERRY_DEV_USER=tester npm run server`.
- **Per-user data:** projects and jobs carry `user_id`. Other users' items return 404. `<img>` and `<video>` links are HMAC-signed and valid for 24 hours.
- **Plans** (`accounts.PLANS`):
  - Free: 3 exports per rolling 30 days (changed from 3 lifetime on 2026-09-30), up to 1 minute, 720p, watermark (`backend/watermark.py`, compact mark plus strokeberry.com).
  - Pro: 200 exports per rolling 30 days, 1080p, no watermark.
  - Failed renders don't count, and each user can run at most 2 renders at once. A cancelled Pro subscription lapses by itself at `plan_renews`.
- **Payments:** Lemon Squeezy, the merchant of record (Stripe doesn't support South African payouts). Code is in `backend/billing.py`.
  - Endpoints: `POST /api/billing/checkout`, `GET /api/billing/portal`, `POST /api/billing/webhook` (X-Signature HMAC).
  - Register the webhook at `<STROKEBERRY_APP_URL>/api/billing/webhook` with the `subscription_*` events.
  - Checkout returns to `/studio/?upgraded=1`, and the studio polls until Pro switches on.
- **Examples gallery:** `GET /api/library`, `POST /api/library/{id}/use`; the UI is `frontend/src/Gallery.jsx`.
  - There are 55 examples in 8 categories: the owner's 50 generated images (in `marketing/marketing_gallery-source_/`) plus 5 starter images from `assets/gallery-src/`.
  - After adding or replacing images (named with an ID from `marketing/gallery-prompts.md`), run `.venv/bin/python scripts/gallery/ingest.py`. It also accepts tool-exported names like `fox.png_<timestamp>.jpg` and pads art that touches the edge.
  - Step-by-step examples open the steps editor. Rocket and Flower aren't auto-detected, but the default 2×2 layout matches them.
  - Pizza is cropped at the left edge in the source; regenerate it if you want it complete.
- **How it works guide** (`frontend/src/Guide.jsx`):
  - A 1-minute tutorial plays inline (`frontend/public/guide/tutorial.mp4`, a 540p copy of tutorial 1 with narration).
  - Four step cards use real studio screenshots.
  - Callouts cover Examples and Set up steps, and a "What works best" pair compares a good and a bad image.
  - Rebuild the pictures with `.venv/bin/python scripts/gallery/guide_images.py`.
- **Tests:** `backend/tests/test_accounts.py` and `test_billing.py` (40 tests in the suite in total).

**Contact emails (decided):**
- **hi@strokeberry.com** is the public address. It's in the landing footer.
- **support@strokeberry.com** is for help and billing. It's in the studio Guide and should be the Lemon Squeezy store support email.
- **Mail is hosted on Zoho Mail** (set up 2026-09-28; Cloudflare Email Routing is turned off).
  - `hi@` is the mailbox and the Zoho super-admin.
  - `support@` is an alias of it, with the display name "Strokeberry Support".
- **Cloudflare DNS records:**
  - MX: `mx.zoho.com` (10), `mx2.zoho.com` (20), `mx3.zoho.com` (50).
  - SPF: `v=spf1 include:zohomail.com ~all`.
  - DKIM: `zmail._domainkey`.
  - DMARC: `_dmarc` set to `p=none`, with reports going to hi@.
  - Zoho verification TXT.
  - Zoho has verified MX, SPF and DKIM.
- **Firebase and Lemon Squeezy:** when you add their sending/DNS records, *merge* their SPF include into the single SPF record. Never add a second SPF record.
- **Zoho plan:** the account is on a **Mail Premium trial** that renews 12/10/2026. Choose a plan before then.

**Owner to-dos:**
1. **Firebase project:**
   - Blaze plan with a $5 budget alert. The free Spark plan sends only 5 sign-in emails a day.
   - Enable Google and Email link sign-in.
   - Add strokeberry.com and localhost as authorised domains.
   - Paste the web config into `.env.local`.
2. **Lemon Squeezy store (test mode):**
   - A "Pro" monthly product.
   - Copy the API key, store ID and variant ID, and set a webhook secret.
   - Confirm South African payouts.
3. **Zoho Mail:** choose a plan before the Premium trial ends (12/10/2026).
4. **Gallery images:** generate them into `marketing/gallery-source/`.

## 8. Pricing, guests and the landing page (2026-09-29)

**Decisions (owner):** Free (3 videos every month, up to 1 minute, 720p, watermark) and one paid plan, **Pro: $10/month or $84/year** (30% off, about $7/month). Launch offer: **Founding member, $7/month locked for as long as the subscription stays active, first 100 customers, monthly plan only.**

- **Founding offer, how it works:** a Lemon Squeezy discount code. Create it: 30% off, duration **forever**, max **100 redemptions**, limited to the monthly variant. Set `STROKEBERRY_FOUNDER_CODE` to the code. The server then applies it to monthly checkouts, `GET /api/offer` feeds the landing page banner and the upgrade dialog, and the spots-left counter reads the redemption count from Lemon Squeezy (cached 5 minutes). It disappears by itself when the 100 are used or the code is unset. `billing.founder_offer()`.
- **Yearly plan:** create a second variant ($84/year) and set `LEMONSQUEEZY_PRO_YEARLY_VARIANT_ID`.
- **Guests:** visitors get a Firebase anonymous account and can preview, use examples and create up to 3 projects; exporting, image cleanup and checkout need a real account (401 `Create a free account...`). Signing in with Google or an email link **links** the guest account, so projects carry over (`auth.js`). Firebase console: Authentication -> Sign-in method -> enable **Anonymous**.
  - Guests can be created without limit, so add rate limiting (Cloudflare rules) or Firebase App Check before launch.
- **Landing page** (`frontend/index.html`): removed the scroll-to-draw section and the bento features; order is Hero -> Examples -> How it works -> Who it's for -> Pricing (Free vs Pro, monthly/yearly toggle) -> FAQ. "Get Pro" links to `/studio/?upgrade=1`. Fixed the missing icon sprite. New pages: `/terms/`, `/privacy/`, `/refunds/`.
- **Legal pages are drafts.** Have them reviewed. Decisions in them for the owner to confirm: 14-day refund on the first payment, governing law South Africa, the founding-rate clause, privacy wording about deleting data on request, and no legal entity name or address yet (add one when you have it).

**Launch checklist:** (1) Firebase: Anonymous + Google + Email link, authorised domains strokeberry.com and localhost, Blaze plan with a $5 budget alert, config into `.env.local`; (2) Lemon Squeezy: store, monthly and yearly variants, the founder discount, webhook -> `/api/billing/webhook`, South African payout details, test-mode purchase end to end; (3) host the app on the VPS with HTTPS and set `STROKEBERRY_APP_URL` and `STROKEBERRY_SECRET`; (4) review the legal pages; (5) re-check the tutorials' captions (see 2b); (6) rate-limit guest creation.

## 9. Usability and retention features (2026-09-30)

- **Plan limits (updated 2026-09-30):** Free videos are up to **1 minute**, Pro up to **5 minutes** (`PLANS[...]['max_duration']`, enforced on export, batch and step creation; the slider and steps editor follow the plan). The finished picture is held for ~2 s however long the video (`artistry.phase_bounds`, mirrored in `main.jsx` and `StepCanvas.jsx`).

Built on the same branch. Backend in `backend/app.py` (+ `brand.py`, `mailer.py`, `prune.py`), interface in `frontend/src/` (`ProjectsView`, `ExportsView`, `ExportResult`, `BrandKit`, `Presets`, `Ideas`, `Dialogs`).

- **First run:** the drawing plays by itself the first time (and whenever you upload or pick an example). On phones a fixed **Export** bar stays at the bottom.
- **Projects:** rename, duplicate, delete (also removes that project's videos), search once there are more than 8, and multi-select for batch export.
- **Exports:** thumbnails, Play, Download, Delete, live progress. Deleting a project or export removes its files.
- **"Your video is ready":** Download, Share (on phones, via the system share sheet), one-click re-export as another format or the other style, a watermark upsell for Free, "All 3 formats" for Pro.
- **Ideas this week:** three examples that change every Monday (`GET /api/ideas`), each with a suggested style and format.
- **Saved styles:** Free 1, Pro 20 (`/api/presets`). Guests are asked to create an account.
- **Batch export (Pro):** `POST /api/batch` exports up to 6 projects x 3 formats (max 9 at once). Every video counts toward the 200/month. Free and guests are asked to upgrade or sign in.
- **Brand kit (Pro):** drawing colour and a corner logo applied to every export (`/api/brand`); the live preview uses the colour too. The logo is stored under `data/brand/`. On 9:16 the logo moves to the top. Free users see the screen locked.
- **Emails** (`backend/mailer.py`, off until `SMTP_*` are set, see `.env.example`): a welcome email on first sign-in, then "1 free video left" and "used your 3 free videos this month", each sent at most once a month. Use an **app password** for the Zoho mailbox, not the login password. Firebase's own sign-in emails are separate.
- **Guest cleanup:** `.venv/bin/python -m backend.prune` deletes guest accounts older than 30 days with their files (Firebase auto clean-up removes the accounts on its side). Run it daily from cron on the server.
- **Preview colours:** `frontend/src/drawing.js` and `backend/pipeline.py` both apply the brand colour, so preview and export match.

**Firebase status (2026-09-30):** project `strokeberry-514b7` (owner: the Grupo Angbu Google account). Enabled: Email link, Anonymous (auto clean-up on). Authorised domains: localhost, strokeberry.com, www.strokeberry.com. Web config is in `.env.local`, so the local server now uses guests and real sign-in. **Google sign-in is enabled** (2026-09-30) with public name "Strokeberry" and support email `almeida.jose@grupoangbu.com` (the only project member at the time). To show `support@strokeberry.com` instead: it has a pending Owner invitation (arrived in the Zoho inbox); accept it by creating a Google account with that address, then change the support email under Authentication -> Sign-in method -> Google. To go back to the old single-user local studio, comment out the `VITE_FIREBASE_*` and `FIREBASE_PROJECT_ID` lines in `.env.local` and run `npm run build`.

- **First-run defaults:** new visitors start with the **Sweet cupcake** starter drawn in **Ink** (`defaults` in `frontend/src/main.jsx`, `SAMPLE_*` in `backend/app.py`). Returning users keep the style they saved in their browser. White backgrounds are blended into the paper colour in `prepare_image` (`SCENE_VERSION` 3), so older projects are refreshed when opened.

- **Drawing order** (`artistry.order_strokes`, scene version 4): strokes are drawn like a person builds a picture: major shapes first, then medium details, then thin straight lines and tiny marks, top to bottom inside each group, and each closed stroke starts where the pen already is. Sizes are measured against the drawing, not the canvas, and long *straight* lines (strings, ground lines) count as details. Preview and export share the same stored timeline, so they match. Older projects are re-prepared with the new order the next time they are opened (their exported videos are unchanged). Pen travel between strokes is about 1.3-1.8x higher than the old nearest-neighbour walk; it keeps its fixed 12% share of the timeline, so drawing speed is unaffected. Ideas to go further: a small set of "how-to-draw" style rules (frosting before wrapper, body before neck) would need a learned model.

- **Colour reveal timing** (`prepare_image`, scene version 5): each colour group's share of the reveal is proportional to how visibly it changes the picture (distance from the paper), so the colour arrives steadily across the whole reveal phase. Before, groups had equal slots and the last ones were near-white, so a picture looked finished after about 30% of the reveal (roughly 10 s of dead time on a 1-minute video). Existing projects are refreshed when opened. The landing-page gallery clips were rendered before this change; re-run `scripts/gallery/render_gallery.py` to get the smoother colour in them.

- **Line drawing** (`backend/linework.py`, scene version 6): only the artwork's real black outlines are drawn, each as **one centre line** (no doubled lines); big dark blobs (pupils, soles) are left for the colour phase to paint. It measures the line thickness, splits lines from fills, thins with Zhang-Suen and traces the skeleton (`thin`, `prune_redundant`, `trace`). It is used only when the outlines cover at least 55% of the picture's strong colour boundaries (`MIN_COVERAGE`), otherwise `edge_strokes` traces the colour edges as single lines, and the old contour tracing remains a last resort. `scene['line_method']` records which was used (`outlines`, `edges` or `contours`). Open strokes are drawn from whichever end is nearer the pen. Existing projects are refreshed when opened. Tuning knobs: the darkness cut-off (`gray < 125`), `MIN_COVERAGE`, `MAX_STROKES`. Known limits: thick black outlines that merge into black fills (a panda, some soles) fall back to edge tracing, which can still show two parallel lines around a thick stroke.

- **Drawing completeness and "Improve your lines" (SCENE_VERSION 8).** `linework.outline_fills` outlines every dark shape the centre-line pass leaves uncovered (compact ones as closed outlines, elongated scraps as one centre line), so all hard lines are drawn before any colour. `linework.missing_lines` finds strong colour boundaries with no dark line beside them (fur tufts, tail tips, inner ears) and the scene carries them as `enhance` (`state` null/accepted/rejected, `count`, `lines`). The studio shows a bar under the preview and a side-by-side dialog (`frontend/src/LineSuggestion.jsx`); `POST /api/projects/{id}/enhance {accept}` stores the choice in the project's `enhance.json` and re-prepares the scene. Nothing is added unless the user accepts, and it can be undone.

- **Competitor-driven features (October 2026).** After testing speedpainter.org end to end:
  - **Plans:** Free now exports 1080p (with watermark and a 2.5 s "Made with Strokeberry" end card, `backend/endcard.py`, approved mascot scaled only); Pro adds 4K (`resolution: '4k'`). Settings also gained `ratio` 4:5 and `auto` (follows the image, kept between 9:16 and 16:9), `hand` (`pencil` or a realistic `light`/`medium`/`dark` hand) and `canvas` (`paper`, `blackboard`, `greenboard`: chalk lines, the picture's paper background becomes the board, black outlines are never painted over the chalk).
  - **Video packs** (5/$5, 15/$12 "Most popular", 40/$25 "Best value"): one-time Lemon Squeezy products (`LEMONSQUEEZY_PACK_*_VARIANT_ID`, see `.env.example`), credited by the `order_created` webhook once per order (`pack_orders` table), taken back on `order_refunded`. `users.pack_videos` is the balance; `jobs.paid_with` is `plan`/`pack`/`refunded`. Free members use pack videos first (no watermark/end card, up to 5 min, 1080p); Pro uses packs only after its 200. Failed renders refund the pack video. Deleted exports are now kept as `status='deleted'` so they still count towards the monthly allowance. Create the three products in Lemon Squeezy before launch.
  - **Drawing hand:** cut-out photos in `frontend/public/hands/` (generated with KIE by `scripts/hands/generate.mjs`, cut out with GrabCut and the forearm extended off-frame by `scripts/hands/cutout.py`; `hands.json` holds the tip point and the hand's share of the image). `backend/hands.py` and `frontend/src/frame.js` place the pencil hand on the active line and the brush hand on `scene.paint_path` (48 points along the colour front, computed in `prepare_image`). The colour reveal has a bristle texture baked into `reveal.png` (`brush_texture`). SCENE_VERSION 12.
  - **Website:** hero drop zone (the file is handed to the studio through IndexedDB, `frontend/src/handoff.js`, `?upload=1`), showcase cards with the original image, a use-case label and "Use this style" (`/studio/?example=<library id>&style=&hand=&canvas=`), packs and a Free/Pack/Pro comparison table on the pricing section, FAQ on packs and commercial use, a public gallery page `/examples/` and a blog `/blog/` with four posts, both generated by `scripts/site/build_pages.py` (listed in `vite.config.js`). Terms and refund policy updated for packs and commercial use (still drafts for legal review). Gallery clips re-rendered (9, incl. puppy with a hand and a greenboard fox).
  - **Studio:** export progress shows named steps; the upgrade dialog lists the packs; the sidebar shows the pack balance.

## Production (live since 2 October 2026)

- **Server:** Hostinger VPS `srv1073781.hstgr.cloud` (148.230.79.3, Ubuntu 24.04, São Paulo), shared with the grupoangbu.com portal. **Never touch nginx or the portal** (`/var/www/Netnix-Angbu`, pm2 app `backend`, `portal.grupoangbu.com`). SSH: `ssh -i ~/.ssh/strokeberry_vps root@148.230.79.3`.
- **Strokeberry:** `/opt/strokeberry/app` (code, `.venv`, `.env.local` with the secrets, mode 600), data in `/opt/strokeberry/data`, systemd service `strokeberry` (user `strokeberry`, `127.0.0.1:8100` only).
- **Public access:** Cloudflare Tunnel `strokeberry` (service `cloudflared`, config `/etc/cloudflared/config.yml`) for strokeberry.com and www; Cloudflare handles HTTPS. No ports are opened and nginx is not involved.
- **Deploy:** `npm run build`, then `rsync -az --delete --exclude __pycache__ --exclude backend/tests --relative backend dist frontend/public/library frontend/public/hands root@148.230.79.3:/opt/strokeberry/app/`, then `chown -R strokeberry:strokeberry /opt/strokeberry/app && systemctl restart strokeberry`.
- **Email:** Zoho SMTP (app password "Strokeberry server"). strokeberry.com has SPF, DKIM and DMARC.
- **Analytics:** cookieless funnel counts on our own server (`backend/analytics.py`). Report: `cd /opt/strokeberry/app && sudo -u strokeberry .venv/bin/python -m backend.analytics 30`. Tag links with `?ref=tiktok` etc.
- **Founding-member reservations (since 3 October 2026):** `STROKEBERRY_RESERVATIONS=1` in `.env.local`. While payments are in test mode, "Get Pro" reserves one of the 100 founding places ($7/month) with nothing to pay, and gives 3 watermark-free videos; checkouts and packs are refused. See `backend/reservations.py`.
- **Payments:** Lemon Squeezy store #488057, **test mode**. Test variant ids: Pro monthly 2193555, yearly 2193556, packs 5/15/40 = 2193558/2193562/2193564; discount `FOUNDER` (30% forever, Pro monthly only, 100 uses). Webhook: `https://strokeberry.com/api/billing/webhook`.

### Reminders

- [ ] **DMARC — late October 2026:** once the daily DMARC reports (sent to hi@strokeberry.com) show only Zoho sending as @strokeberry.com, change the `_dmarc` TXT record in Cloudflare from `p=none` to `p=quarantine` (keep `rua=mailto:hi@strokeberry.com`). Lemon Squeezy and Firebase send from their own domains, so they are unaffected.
- [ ] **Webhook secret:** replace the 8-character Lemon Squeezy signing secret with a long random one (32+ characters), in Lemon Squeezy and on the server.
- [ ] **Going live with payments:** finish Lemon Squeezy identity verification, activate the store, copy the products to live mode, then put the live variant ids, a live API key and a live webhook (with its own secret) on the server. Cancel the test subscription. Then end the founding-member reservations: set the live `FOUNDER` discount's redemption limit to at least the number of reservations (`python -m backend.reservations` lists them), remove `STROKEBERRY_RESERVATIONS=1` from `.env.local`, restart, and run `sudo -u strokeberry .venv/bin/python -m backend.reservations notify` to email everyone who reserved.
- [ ] **Lemon Squeezy API key expires ~1 October 2027:** in mid-September 2027 create a new key and put it on the server, or checkout and the billing portal stop working.
- [ ] **Portal logs** rotate daily via `/etc/logrotate.d/pm2-root`; the portal's error log was growing ~18 GB, so its maintainer should look at `/root/backups/portal-logs/backend-error-last5000.log`.
- [ ] Remove the old `jmap.grupoangbu.com` DNS record in Hostinger (the mail server it pointed to was removed on 1 October 2026).
