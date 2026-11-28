# Crewreel (working name)

Your crew films the job, and you get back an agency-quality reel that brings in quote requests.

## Render a reel locally
Needs: Python 3.11+ (numpy, opencv-python, pillow, pytest), Node 20+ with `playwright` (Chromium), ffmpeg.

```sh
python scripts/gen_placeholder.py pavers footage/driveway     # test footage only, never for customers
python render/render.py templates/driveway footage/driveway out/driveway.mp4
python scripts/gen_placeholder.py siding footage/house
python render/render.py templates/house-wash footage/house out/house.mp4 --params my-business.json
python scripts/gen_placeholder.py roof footage/roof
python render/render.py templates/roof footage/roof out/roof.mp4 --vo-take assets/vo/roof_blain.mp3
python scripts/gen_placeholder.py glass footage/windows
python render/render.py templates/windows footage/windows out/windows.mp4 --vo-take assets/vo/windows_blain.mp3
python render/render.py templates/windows footage/windows out/windows-feed.mp4 --frame feed   # 4:5 feed post
pytest -q                     # unit + template tests (+ a 2 s end-to-end render)
```
Footage folder: `before`, `after`, `action1..3` (.mp4/.mov/.webm/.mkv or .jpg/.png/.webp for stills), any orientation,
HDR or SDR. Next to the reel the renderer writes `<out>.footage.json`: what ingest did per clip plus plain-English
re-shoot hints for the crew (low res, too dark, washed out, sideways, too short).

## Run the app (job → reel)
```sh
cd web && npm install && npx next build && npx next start      # http://localhost:3000
python worker/worker.py                                          # second terminal: renders queued jobs
GITHUB_REPO=aronvalur/crewreel GITHUB_TOKEN=... python worker/worker.py --remote github   # or: ship jobs to GitHub Actions
```
Remote mode (`worker/remote.py` + `.github/workflows/render-job.yml`): clips go up as assets of a temporary
pre-release `job-<id>`, the workflow renders and puts the reel back, the worker downloads it and deletes the
release. Token needs Contents + Actions write on this repo. Self-test without a token: dispatch `render-job`
with `selftest: true` (placeholder footage, reel as an artifact).
Contractor flow: Business (name, area, quote link, colour, Google review link) → New reel (pick style; film each
shot with the guided camera — level, upright check, length timer, the before as a ghost for the after — or pick
clips; clips stay on the phone until sent; optional 4:5 feed version) → job page polls while rendering → reel,
feed version, poster, caption, Google Business post, review-request text, "For next time" re-shoot tips.
Homeowners land on the public quote page `/q` (the reel's link, `?r=<reel>` in captions) → requests show under
Quotes with the reel that brought them. Set `CREWREEL_PASSWORD` to require sign-in for everything except `/q`,
the quote form post and reel posters (unset = open, for local use). `CREWREEL_PUBLIC_HOST` = the host shown on
end cards and in links. Jobs live in `data/` (`CREWREEL_DATA`): plain folders + JSON, written atomically,
claimed by the worker with an O_EXCL lock. Swap for Postgres + a bucket when it goes online.

## How a template works
`templates/<name>/index.html` is a deterministic HTML composition (no timers, no CSS animation):
- `window.META` — fps, duration, footage `sources`, `cuts` (whoosh), `impacts` (thump), `vo` lines, `sfx` (reveal foley: squeegee, rinse).
- `window.seek(t)` — draws the graphics for time t **and** sets `window.__plan.layers`: which footage goes underneath
  (`src`, clip time `t`, `zoom`/`fx`/`fy` Ken Burns, `mask` (horizontal) / `vmask` (vertical) + `feather` split, `alpha`, `blur`, `dim`).
- `PARAMS` (business, accent, url, hook, method, vo, frame…) are injected per job; text positions come from
  `M.safe(P)` (reel UI zones or the 4:5 feed band), so one template serves both outputs; the renderer adds `aligned` and
  `activity` (per-clip motion profile; `M.quietZone` uses it to keep text off the action).
- Fonts are bundled in `templates/_lib/fonts` (Inter Display, OFL) so every machine sets identical type.

`render/render.py`: ingest every upload (`render/ingest.py`: HDR→SDR tonemap, rotation, EXIF, letterbox removal,
landscape → action-following 9:16 crop, activity profile so text avoids the subject, quality hints) →
align before/after (`render/align.py`) → focus + calm bands (`render/focus.py`: close-ups aim where the clean-up
shows most, hooks avoid the subject) → overlay PNGs + plan (`render/overlay.js`) → tripod-lock before/after
(`render/stabilize.py`) →
numpy composite (short clips play in blended slow motion, down to 0.5x) → x264 → audio (`render/audio.py`: synth bed, whooshes, ElevenLabs VO if `ELEVENLABS_API_KEY` +
`ELEVENLABS_VOICE_ID` are set, ducking, loudnorm) → mp4.

Docs: `docs/STRATEGY.md`, `docs/LOG.md`, `docs/NEXT.md`, `docs/NEEDS_ARON.md`.
