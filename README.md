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
Footage folder: `before`, `after`, `action1..3` (.mp4/.mov or .jpg/.png for stills).

## How a template works
`templates/<name>/index.html` is a deterministic HTML composition (no timers, no CSS animation):
- `window.META` — fps, duration, footage `sources`, `cuts` (whoosh), `impacts` (thump), `vo` lines.
- `window.seek(t)` — draws the graphics for time t **and** sets `window.__plan.layers`: which footage goes underneath
  (`src`, clip time `t`, `zoom`/`fx`/`fy` Ken Burns, `mask` + `feather` split, `alpha`, `blur`, `dim`).
- `PARAMS` (business, accent, url, hook, method, vo…) are injected per job.

`render/render.py`: align before/after (`render/align.py`) → overlay PNGs + plan (`render/overlay.js`) →
numpy composite → x264 → audio (`render/audio.py`: synth bed, whooshes, ElevenLabs VO if `ELEVENLABS_API_KEY` +
`ELEVENLABS_VOICE_ID` are set, ducking, loudnorm) → mp4.

Docs: `docs/STRATEGY.md`, `docs/LOG.md`, `docs/NEXT.md`, `docs/NEEDS_ARON.md`.
