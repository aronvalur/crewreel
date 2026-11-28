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
- Then: uploads now stream per clip straight to disk (draft → PUT per clip → queue); server memory flat during a 300 MB upload; browser flow re-verified.
- Tests: 23 → 31, all green.
- Self-check: chose app skeleton over captions/VO again because VO is blocked on a key and the end-to-end flow is the next biggest gap; kept the store file-based to avoid needing any account.
- Grade: C+ (up from C). A contractor can now go from clips to a postable reel with caption in one flow, locally. Not deployed, no VO, no real customer footage yet.

## 2026-11-26 — run 6 (daytime; Aron: "be independent, make the decisions yourself")
- Recorded the rule in `docs/DECISIONS.md` and updated the nightly task's prompt to follow it. Decided every open item: render host = GitHub Actions; voice = ElevenLabs "Blain – Conversational Ad Voice"; ElevenLabs budget ≤400 chars/run and only while >8,000 remain (protects Aron's daily Short); stock VO per template; mix targets.
- Shipped real voiceover: one take per template (335 credits total, cached in `assets/vo/`), split on its pauses, each line placed at its template time, every word timed from the audio (phrase/pause-aware). Worker uses the stock take automatically.
- Shipped word-timed captions (`_lib/captions.js`) for VO lines no on-screen text carries (driveway: "Same morning.").
- Fixed the mix (found while measuring the first VO render): echo was applied to the whole mix including the voice; levels weren't set relative to the voice; output was −17.5 LUFS. Now voice −18 dBFS, bed ~15 dB under speech with smooth ducking, echo on music/fx only, look-ahead limiter + measured gain → −14.2 LUFS, true peak −1.6 to −1.8.
- Shipped CI (`ci.yml`: web build + full pytest) and `render-samples` (renders both templates with VO on GitHub's free runners, attaches reels + contact sheets).
- Tests: 31 → 34; CI green on GitHub Actions; render-samples produced both VO reels on the free runner in ~7 min.
- Self-check: wanted per-job VO with the business name, but that needs a product API key (account action); stock VO with generic lines gets 90 % of the value for free today.
- Grade: B− (up from C+). Reels now have a real voice, captions and a broadcast-level mix; the app flow works locally; CI renders on free infrastructure. Still not deployed online; no real customer footage.

## 2026-11-27 — run 7 (nightly)
- Self-review (tests + rendered both templates on placeholder footage, read frames). Weakest: (1) house-wash
  hook and result line sat right on the window (the subject); (2) detail close-ups went to hard-coded spots
  with labels ("Windows") that could be wrong on real footage; (3) only two job types, and the online path
  still had no way to render off the web box. Also found: render.py crashed when the output folder was
  missing; reader ffmpeg spammed "Broken pipe".
- Shipped `render/focus.py`: before/after change map picks the close-up points where the clean-up shows most;
  per-band "busy" profile moves hooks/result lines off windows, doors and rooflines (deeper bottom scrim when
  text goes low). House-wash close-up 1 is now an up-close before→after wipe at the strongest change.
  Verified on frames: hook and "Same day. No damage." now sit on plain siding under the window.
- Shipped template 3, **Roof soft wash** (18 s): tilt-down hook, two action clips + method plate, ridge-to-gutter
  rinse wipe with a light band on the edge and BEFORE/AFTER chips handing over, result line synced to the VO,
  up-close wipe, end card. Compositor got vertical masks. Stock VO take (Blain, 210 credits), −14.3 LUFS.
  Roof placeholder footage added. Wired into web picker, worker, render-samples.
- Shipped remote rendering: `worker.py --remote github` ships a job's clips to a temporary pre-release,
  dispatches `render-job.yml`, polls, downloads reel/poster/report and deletes the release + tag. Tested against
  a fake GitHub API (4 tests); the workflow's render path verified for real on GitHub (self-test dispatch,
  roof reel rendered in ~2.5 min, artifact 17 MB).
- Shipped pre-upload footage check on the New reel form (short / sideways / low-res, per-slot minimums).
  Checked in an iPhone-sized browser.
- Shipped golden frames (`scripts/golden.py`, 12 frames) as a visual regression test.
- Tests: 37 → 55, all green locally (incl. the 5 web tests).
- Self-check notes that changed direction: (a) ~45 min: after the focus work I weighed the online beta vs a
  third template; picked the template (reel quality + market) first, then built the render hand-off as a
  finished slice instead of deploying, because (b) Render free's disk is ephemeral and the service sleeps, so
  deploying without a bucket would lose customer uploads — not worth shipping. (c) Commons returned 429 on
  every call; stopped after two tries instead of burning time.
- Grade: B (up from B−). Three job types, close-ups and text placement now driven by the actual footage, and
  rendering can run on free GitHub runners from a web box. Still not online (needs a bucket), still no real
  customer footage.

## 2026-11-28 — run 8 (nightly)
- Self-review: 55 tests green (after fixing a sandbox-only Playwright mismatch, no repo change); rendered all three
  templates on placeholder footage and read frames. Weakest: (1) end card — dead lower half, ghosted blurred
  footage behind the logo, CTA only in the last ~1.5 s, i.e. the conversion frame was the weakest frame;
  (2) driveway sat on one 5 s action clip with nothing happening; (3) no window-cleaning reel although window
  cleaners are a third of the target market — and the reel's CTA link pointed at a page that didn't exist.
- Shipped **end card rebuilt for conversion**: before|after proof card (compositor `box` layers: footage
  cover-cropped into a rounded card on the focus point, soft shadow), logo + name row, big accent CTA button
  readable by 0.8 s with one pulse, URL. Long names shrink then wrap to two lines (tested). Default CTA copy
  "Get a free quote".
- Shipped **driveway re-paced**: 4 s action, then an up-close wipe at the focus point; VO lines re-timed from the
  cached take (0 credits).
- Shipped **template 4, Window cleaning** (16.4 s): spotted-glass hook, scrub + squeegee steps, a crisp wipe
  ridden by a drawn squeegee (rubber blade, channel, wet sheen), up-close squeegee pass, end card. Stock VO
  (Blain, 184 credits; 11,111 left before). Glass placeholder footage. Wired into web, worker, CI, remote.
- Shipped **quote page `/q` + Quotes inbox**: proof strip (tap to watch), service chips, name / phone-or-email /
  address / notes, honeypot; requests stored with the reel that sent them (`?r=<reel>` in captions);
  per-reel tally; nav badge. Captions/end cards default to the built-in page.
- Shipped **guided camera** in the New reel form: viewfinder with shot hint, thirds, level line, upright and
  steady nudges, a length ring that turns green when the slot is covered, before-as-ghost for the after shot;
  clips persist on the phone (IndexedDB) so the after can be filmed hours later. E2E test with a fake camera.
- Shipped **4:5 feed version**: templates take text safe zones from `M.safe(P)`; `--frame feed` crops the
  composite to 1080x1350; opt-in per job; works in local and remote (GitHub) rendering. Test: every visible
  text element stays inside the crop across all four reels.
- Shipped **sign-in** (CREWREEL_PASSWORD, signed cookie; quote page, form post, reels and posters public).
  Upload route checks the cookie itself (middleware would buffer 500 MB bodies — caught by the streaming test).
- Shipped Google Business post + review-request text per job (optional review link), poster download.
- Shipped reveal foley (squeegee swish, roof rinse; meta.sfx), whooshes de-fizzed and 2 dB lower; hooks visible
  on frame 0; byline (logo + business name) under every hook.
- Shipped **new-quote alerts** on the contractor's phone (Web Push; VAPID keys made on first use, no accounts) and
  an installable app (manifest + icon) so iPhones can receive them from the home screen.
- Shipped **template 5, Deck cleaning** (16.4 s): eight board bands wipe clean in a cascade with a wet sheen on each
  edge; rinse foley; stock VO 183 credits (run total 367/400).
- Verified end to end: New reel form (windows, feed on) → worker → reel + 4:5 feed + poster + texts on the job
  page; remote path verified on GitHub (render-job self-test with feed: both files produced).
- render-samples is now manual-only (auto on every push would have cost ~3,000 Actions min/month).
- Tests: 55 → 77, all green locally; CI green.
- Self-check notes that changed direction: (a) after the windows template I picked the quote page over the
  4:5 feed because every reel's CTA pointed at a 404 — the product's promise is quote requests; (b) noticed
  render-samples per push would eat the free minutes meant for customer reels → manual; (c) once the quote
  page collected homeowners' phone numbers, sign-in jumped ahead of the feed version (no going online
  without it); (d) checked the foley by measurement (momentary loudness) since I can't listen.
- Grade: B+ (up from B). The reel's last frame now sells, the job→reel→quote-request loop exists end to end
  with attribution and phone alerts, five job types, feed format, guided filming. Still: no real footage, not online.
