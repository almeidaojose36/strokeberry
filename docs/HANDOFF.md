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

1. **Offer copy.** Accounts, the Free plan (3 videos, 720p, watermark) and Pro are now built (§7), but billing only goes live once the Lemon Squeezy store is set up. Until then keep "Upgrade" copy off public pages.
2. **Hosting not done.** Recommended: the owner's Hostinger VPS (FastAPI + FFmpeg need a real server). strokeberry.com is registered on Cloudflare (expires 2027-09-26).
2b. **Tutorial narration** says the video "renders right on your device", which stops being true once hosted. Re-record that line before posting.
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
  - Free: 3 lifetime exports, 720p, watermark (`backend/watermark.py`, compact mark plus strokeberry.com).
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
