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
