# Crewreel (working name)

Your crew films the job, and you get back an agency-quality reel that brings in quote requests.

## Render a reel locally
Needs: Python 3.11+ (numpy, opencv-python, pillow, pytest), Node 20+ with `playwright` (Chromium), ffmpeg.

```sh
python scripts/gen_placeholder.py pavers footage/driveway     # test footage only, never for customers
python render/render.py templates/driveway footage/driveway out/driveway.mp4
python scripts/gen_placeholder.py siding footage/house
python render/render.py templates/house-wash footage/house out/house.mp4 --params my-business.json
pytest -q                     # unit + template tests (+ a 2 s end-to-end render)
```
Footage folder: `before`, `after`, `action1..3` (.mp4/.mov/.webm/.mkv or .jpg/.png/.webp for stills), any orientation,
HDR or SDR. Next to the reel the renderer writes `<out>.footage.json`: what ingest did per clip plus plain-English
re-shoot hints for the crew (low res, too dark, washed out, sideways, too short).

## Run the app (job → reel)
```sh
cd web && npm install && npx next build && npx next start      # http://localhost:3000
python worker/worker.py                                          # second terminal: renders queued jobs
```
Contractor flow: Business (name, area, quote link, colour) → New reel (pick style, add clips with shot guidance,
optional words; upload shows progress) → job page polls while rendering → reel, poster, ready-to-paste caption,
and "For next time" re-shoot tips. Jobs live in `data/` (`CREWREEL_DATA`): plain folders + JSON, written atomically,
claimed by the worker with an O_EXCL lock. Swap for Postgres + a bucket when it goes online.

## How a template works
`templates/<name>/index.html` is a deterministic HTML composition (no timers, no CSS animation):
- `window.META` — fps, duration, footage `sources`, `cuts` (whoosh), `impacts` (thump), `vo` lines.
- `window.seek(t)` — draws the graphics for time t **and** sets `window.__plan.layers`: which footage goes underneath
  (`src`, clip time `t`, `zoom`/`fx`/`fy` Ken Burns, `mask` + `feather` split, `alpha`, `blur`, `dim`).
- `PARAMS` (business, accent, url, hook, method, vo…) are injected per job; the renderer adds `aligned` and
  `activity` (per-clip motion profile; `M.quietZone` uses it to keep text off the action).
- Fonts are bundled in `templates/_lib/fonts` (Inter Display, OFL) so every machine sets identical type.

`render/render.py`: ingest every upload (`render/ingest.py`: HDR→SDR tonemap, rotation, EXIF, letterbox removal,
landscape → action-following 9:16 crop, activity profile so text avoids the subject, quality hints) →
align before/after (`render/align.py`) → overlay PNGs + plan (`render/overlay.js`) → tripod-lock before/after
(`render/stabilize.py`) →
numpy composite (short clips play in blended slow motion, down to 0.5x) → x264 → audio (`render/audio.py`: synth bed, whooshes, ElevenLabs VO if `ELEVENLABS_API_KEY` +
`ELEVENLABS_VOICE_ID` are set, ducking, loudnorm) → mp4.

Docs: `docs/STRATEGY.md`, `docs/LOG.md`, `docs/NEXT.md`, `docs/NEEDS_ARON.md`.
