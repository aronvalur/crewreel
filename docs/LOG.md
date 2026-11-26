# Log

## 2026-11-25 — run 1 (repo not attached; work kept in claude.ai project doc `claude/crewreel-run-handoff.md`)
- Shipped (locally, not pushed): Template 1 "Driveway Before/After" 15 s 9:16; deterministic HTML overlay (`seek(t)`), Playwright frame renderer, numpy compositor, ffmpeg sound bed + whooshes, loudnorm −16 LUFS. Safe zones (top 300 / bottom 520 px). Tags hide under the divider.
- Better: pipeline proven end to end (render ≈ 90 s per 15 s reel on CPU).
- Grade: D+ (no real footage, no VO, no app).

## 2026-11-25 — run 2 (manual fire; repo created but still not attached to the task → push 403)
- Prepared repo contents locally: these four docs + pipeline code. Saved docs to project under `claude/crewreel-repo/` so the first attached run can commit them verbatim.
- Grade: D+ (unchanged; blocked on repo access).

## 2026-11-26 — run 3 (push still 403: repo not in the task's authorized set; full repo mirrored to project `claude/crewreel-repo/`)
- Shipped: plan-driven render engine. Templates now declare per frame which footage layers sit under the graphics (`window.__plan`: src, clip time, Ken Burns zoom/focus, split mask with feather, alpha, blur, dim) — the compositor is generic, new templates need no Python.
- Shipped: before/after **auto-align** (`render/align.py`): ORB+RANSAC, rotation×translation grid search on low-pass luminance, pyramid ECC refine, confidence gate → fallback to crossfade. "Meet halfway" warp halves the crop zoom (1.17 → 1.085). Verified on placeholder footage shot 8 % off and 1.5° rotated: paver joints line up across the divider.
- Shipped: Template 2 "House Wash Transformation" (20 s: hook pull-out, 3 numbered action steps + method plate, soft light-sweep reveal with 220 px feathered edge, 2 detail push-ins with labels, end card).
- Shared template lib (`templates/_lib`: motion easing, word-rise with blur, end card over blurred/dimmed after frame, centred logo/CTA/URL pill). Stronger scrims + text shadow for legibility on light siding.
- Audio: synthesized I–V–vi–IV pad + soft arpeggio + felt pulse at 100 bpm, filtered-noise whooshes on every cut, low thump on the reveal, ElevenLabs VO hook (env vars) with ducking, loudnorm. Template VO lines written.
- Tests: 7 pytest (alignment recovery/rejection, halfway transform math, audio length, plan determinism for both templates, 2 s end-to-end render). All green.
- Render time: 15 s reel ≈ 100 s, 20 s reel ≈ 135–155 s on CPU.
- Grade: C− (up from D+): two templates render with aligned reveals and a real end card; still no real footage, no VO voice chosen, no app.

## 2026-11-26 — run 4 (first run with push access; repo bootstrapped from the project mirror)
- Bootstrapped aronvalur/crewreel from `claude/crewreel-repo/` in the project; all 7 existing tests green, pushed to main.
- Self-review (rendered both templates, read frames): (1) nothing handled real phone footage — HDR, rotation, EXIF, landscape and letterboxed clips would come out grey, sideways or blindly centre-cropped; (2) before/after seam drifted during the reveal (align on frame 0 only); (3) no VO/captions (blocked on key).
- Pulled a real CC BY clip from Wikimedia Commons (rotary nozzle on red pavers, 720p letterboxed with burned-in "Slow 40x" text) for internal testing only (gitignored, never in customer reels).
- Shipped `render/ingest.py`: HDR (HLG/PQ) → SDR tonemap, rotation flag, EXIF photos, letterbox/pillarbox removal (flat-and-black test so deep shadows are never cropped), landscape → 9:16 crop that follows the action as a calm, speed-limited pan. On the Commons clip: bars and burned-in text gone, crop follows the spray.
- Shipped subject-aware text: the real clip showed the method plate sitting on the nozzle (the hero). Ingest now records a per-clip vertical activity profile; templates pick the plate zone from motion + centre-subject prior (plate high by default on action shots, low only when action is up top), and the plate exits after reading time so the action breathes.
- Shipped footage quality gate (crew-friendly re-shoot hints → `<out>.footage.json`) and blended slow-motion fill for clips shorter than their slot (no more frozen last frames).
- Shipped `render/stabilize.py`: each before/after take locked to its own frame 0, composed with the alignment, one shared crop zoom. Measured handheld drift 29–30 px → <1 px; paver joints run straight across the divider for the whole reveal.
- Bundled Inter Display (OFL) so type is identical on any render machine; plate re-measured after fonts load.
- Tests: 7 → 23, all green. Render: 15 s reel ≈ 155 s on CPU (ingest + stabilise added ~40 s).
- Self-check notes that changed direction: (a) ~40 min: planned captions first, but the templates are text-driven, so captions add little until VO exists; real-footage robustness was the bigger unknown → switched. (b) first plate-avoidance version used motion only and still covered the nozzle (tool is static relative to camera, spray mist dominates motion) → added centre prior and flipped the default zone. (c) first seam test used phase correlation across dirty/clean pavers and aliased on the repeating grid → measured each take against itself instead, and made placeholder takes wobble independently (they shared one wobble, which hid the bug).
- Grade: C (up from C−). The pipeline now survives real phone footage and the reveal holds registration; still no customer footage, no VO voice, no app.

## 2026-11-26 — run 5 (daytime, started by Aron: "keep going, not only at night")
- Shipped render speed-up: overlay frames whose DOM is unchanged reuse the previous PNG (220/450 on driveway), CDP fast capture, compositor decodes each overlay once and blends only rows with graphics. 15 s reel 159 s → 91 s on 2 cores, PSNR 64 dB vs old path.
- Shipped the core job → reel flow: `web/` (Next 15) with Business profile, New reel (style, footage slots with crew shot guidance + previews, optional words, upload progress), job page (polls, then reel + download + ready-to-paste caption + "For next time" re-shoot tips), reels grid with mid-reveal posters. `worker/worker.py` claims queued jobs and renders them. File-based job store so it runs with zero accounts.
- Verified end to end in an iPhone-sized browser with the real Commons clip: setup → upload 3 clips → reel in 115 s, tips shown ("low resolution", "filmed sideways").
- Fixed from looking at the screens: poster grabbed while the divider was still far left (now split at 50 %); caption read awkwardly and dropped the method line when blank; one giant card per row on phones (now 2 columns); video streaming threw an uncaught "Controller is already closed" on aborted range requests (custom stream with cancel).
- Found: Render's free tier (0.1 CPU, 512 MB) cannot run the render worker (Chromium + 1080×1920 float frames; a reel would take 30+ min if it fit at all). Added to NEEDS_ARON as a decision.
- Tests: 23 → 30, all green.
- Self-check: chose app skeleton over captions/VO again because VO is blocked on a key and the end-to-end flow is the next biggest gap; kept the store file-based to avoid needing any account.
- Grade: C+ (up from C). A contractor can now go from clips to a postable reel with caption in one flow, locally. Not deployed, no VO, no real customer footage yet.
