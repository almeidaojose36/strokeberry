# Strokeberry

A working local image-to-speedpaint application. React + Vite power the studio; Python, OpenCV, Pillow, SQLite, and FFmpeg produce real H.264 MP4 files. No API keys or GPU required.

## Run

Prerequisites: Node.js 20.19+ or 22.12+, Python 3.9+, and FFmpeg with the `libx264` encoder on your PATH.

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
npm install
npm start
```

Open http://127.0.0.1:8001 for the landing page and http://127.0.0.1:8001/studio/ for the app. `npm start` builds the frontend and serves the complete application from FastAPI. If FFmpeg is outside your PATH, set `FFMPEG_PATH` to its executable path.

For development, run these in separate terminals:

```sh
npm run server
```

```sh
npm run dev
```

Open http://127.0.0.1:5173 (landing) or http://127.0.0.1:5173/studio/ (app). Vite proxies API and image requests to port 8001.

## Landing-page gallery

The gallery and scroll-to-draw videos on the landing page are real Strokeberry exports of original illustrations.

```sh
npm run gallery:images   # generate illustrations with KIE (needs KIE_API_KEY in .env.local)
npm run gallery:render   # draw them with the running API into frontend/public/gallery/
```

KIE is used only for these marketing illustrations. User uploads are never sent to KIE or any other AI service.

## What works

- Drag and drop or select PNG, JPEG, and WebP files, up to 15 MB / 20 megapixels.
- EXIF orientation correction, transparent image compositing, and bounded image analysis.
- Canny edges, near-duplicate contour suppression, corner-preserving smoothing, and greedy nearest-endpoint stroke ordering.
- Deterministic pencil/ink pressure variation, slower curves and stroke endpoints, timed pen lifts, an optional graphic pencil with a lifted shadow, and color-segmented reveal.
- Play, pause, restart, scrub, compare the original, and fullscreen preview.
- Landscape, portrait, and square output; 5 seconds–5 minutes; 720p or 1080p at 24 fps.
- Real MP4 exports, bounded single-worker queue, progress polling, downloadable results, and error states.
- Saved projects and export history in SQLite. Browser settings and last-opened project persist locally.
- Responsive layouts, labeled controls, keyboard-operated sliders, and dialogs with Escape and focus handling.
- An original botanical sample, generated locally with Pillow.

## Step-by-step drawing mode

For an image containing several drawing stages, choose **Set up steps** beneath the source image. Bordered panels and borderless grids separated by whitespace are detected automatically, including 3×2 six-stage tutorials. A detected tutorial opens the step editor after upload. Other images start with an editable 2×2 grid.

- Choose the panel layout (for example, 3 columns × 2 rows), or use the detected layout. Drag crop boxes, resize their lower-right corners, or enter crop percentages. Changing layouts resets crops, labels, and timings.
- Change the stage names and order, and set seconds per stage (default: 20 / 30 / 40 / 30 seconds).
- Automatic alignment fits translation and uniform scale to the final panel. Manual offsets and scale adjustments are available for each stage.
- **Prepare drawing steps** creates a separate saved project. Thumbnail buttons preview each completed stage; **Edit steps** creates a revised sequence without altering earlier projects or exports.
- The overall Duration control scales stage timings proportionally. Videos can be up to five minutes long.

The sequence renderer preserves the actual panel marks, shading, and colors. It reveals raster differences along traced paths and progressively replaces obsolete guide marks. Pencil/ink styling and the single-image color toggle are therefore replaced by sequence controls. The moving pencil remains optional. The last 10% of each stage holds the completed drawing before the next stage begins.

Alignment is an approximation, not semantic reconstruction. Strong perspective changes, unrelated panels, sparse guides, and different framing may need manual correction. Paper cleanup can remove very faint marks. Crop review remains important, particularly for captions and panel borders. The editor supports common layouts with two through eight stages. Whitespace detection remains heuristic; use the layout selector when its suggestion is wrong. Existing sequences retain their saved crops until you choose a new layout.

Full normalized uploads are now retained as `original.png` for recropping. Older projects use their existing preview image when a full-resolution original is unavailable; upload the original again for better crops.

## Pipeline and storage

1. `/api/projects` accepts an uploaded image, normalizes it to at most 900 pixels on its longest side, and saves a source PNG.
2. OpenCV extracts and simplifies contours. A nearest-endpoint heuristic orders these into independent strokes. Coordinates, per-segment pressure, and normalized drawing/lift events are saved as `scene.json`. Drawing takes 88% of the outline phase, with 12% allocated to pen travel when multiple strokes exist.
3. Pillow quantizes the image into nine color groups. A grayscale rank map schedules their reveal, with a diagonal sweep within each group.
4. The browser renders a canvas preview. Export uses the same serialized pressure and timing events, including eased pen travel and endpoint pauses, plus the same reveal rank map, rendered with OpenCV.
5. A single background worker streams RGB frames directly to FFmpeg, keeping memory independent of video duration. Only successfully encoded files become downloadable.

`data/studio.sqlite` holds metadata; `data/<project-id>/` holds image, path, and render files. Source images and videos remain local. The UI uses Google Fonts, with local font fallbacks when offline. No user image is sent to an external AI service. Only named source/reveal images and completed job downloads are exposed by the API.

Projects created with the original engine are upgraded automatically when opened or exported. Previous MP4 files remain unchanged; export again to use the improved strokes.

Run one server process: queue coordination is process-local. On restart, unfinished jobs are marked failed with a retry message; completed projects and videos remain available. There is no automatic deletion policy yet. Stop the server before manually removing `data/` to reset the workspace.

## Verification

```sh
npm run build
npm test
```

Tests exercise duplicate suppression, corner preservation, pressure variation, curve pacing, pen lifts, matching browser/encoder pen positions, existing-project upgrades, panel detection, registration, stage continuity, crop validation, staged MP4 encoding, contour extraction, color reveal ranks, flat images, actual FFmpeg encoding/frame count and first-to-last frame change, upload validation, and file access isolation. The encoding test skips when FFmpeg is unavailable.

## Scope and production roadmap

### Editing images and choosing the composition

The image editor's **Clean background** tool removes neutral paper texture, reduces uneven lighting, and removes pale isolated specks. Adjust cleanup strength, apply it to the current canvas, and use Undo/Redo to compare. It preserves dimensions and protects pigment areas, but stronger cleanup can remove faint pencil shading. Cleanup is processed locally and does not create a project until you save the edited image. The resulting flat paper matches the renderer's blank canvas so it does not generate unnecessary background strokes.

Within each panel, structural marks now follow **labels/guides → main subject → environment**, followed by the existing color passes. The subject is estimated from the largest central closed silhouette, with thin attached ground lines removed; compact top-left annotations and long rules are prioritized separately. This geometric heuristic works well for simple tutorial characters, but does not recognize arbitrary lettering or subjects semantically and can misclassify open sketches, off-center subjects, or overlapping scenery.

Step animations finish panels in reading order. Each panel first completes a structural pass for dark lettering, numbers, outlines, their gray antialiased edges, and thin colored marks. Broad paper/dark fills then precede separate pigment passes: blue, yellow, green, red, orange, pink, purple, and gray shading (only colors present are used). Structure detection uses stroke thickness and contrast, not OCR. Similar shades are grouped by hue; every stroke reveals only pixels belonging to its active pass. Preview and MP4 use the same swept brush mask, so neighboring fills stay hidden until their own pass. Saved step projects upgrade on opening; existing MP4 files are unchanged and must be exported again to use the new sequence.

Use **Edit image · eraser & brush** in the studio or step setup to remove marks or paint on the upload. The canvas supports brush size, paper/brush colors, zoom, undo, redo, and reset. Erasing paints with the paper color; it does not reconstruct textured backgrounds. Saving creates a new project and retains the original. Existing step sequences are rebuilt with their saved crops and timing after editing.

In step setup, choose **1 step · keep whole image** to preserve the selected crop as one complete composition. A four-panel tutorial remains four separate drawings in their original positions throughout the video. Choose **2 columns × 2 rows** to combine those panels into one evolving drawing instead. Layout changes reset crops and timing. One-step mode ignores alignment corrections and supports the same 5–300 second video duration.

This is a local MVP, not a hosted multi-user service. It uses contour polylines, not semantic AI sketch generation or Bézier fitting. The pen is a stylized graphic, not a photographic hand. Rendered lines can differ slightly from the browser preview due to rasterization. The 900-pixel analysis image is scaled to the export canvas; 1080p describes the video dimensions, not recovered image detail. Square output is 720×720 / 1080×1080. There is no audio track.

Before a public launch:

1. Add authentication and per-user project/job ownership checks; replace local image endpoints with authorized, expiring object-storage URLs.
2. Move analysis and rendering to a durable queue (Redis/Celery or equivalent), with retries, cancellation, worker heartbeats, and container resource limits. CPU workers cover this pipeline; GPU workers become useful if AI extraction is introduced.
3. Preserve full-resolution originals in object storage, implement retention/deletion, thumbnails, storage quotas, and upload limits at a reverse proxy.
4. Add Stripe Checkout and a verified, idempotent webhook handler. Record credit reservations and refunds transactionally around job lifecycle events.
5. Improve artistic quality with semantic line extraction, higher-quality curve fitting, region-aware fill paths, and properly licensed hand assets anchored to the pen tip.
6. Add monitoring, abuse limits, multi-user isolation tests, deployment configuration, and a documented privacy policy.

API documentation is available at `/docs` while the server is running.

References: [FastAPI uploads](https://fastapi.tiangolo.com/tutorial/request-files/), [OpenCV contour operations](https://docs.opencv.org/4.13.0/d3/dc0/group__imgproc__shape.html).
