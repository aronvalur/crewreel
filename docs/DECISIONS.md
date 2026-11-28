# Decisions

Aron's standing instruction (2026-11-26): "be independent". The builder makes every product, design,
technical and prioritisation decision and records it here. Only things that physically need Aron go to
NEEDS_ARON.md: creating accounts, paying, payment details, publishing anything public, messaging anyone.
Every run reads this file and follows it. Reverse a decision only with a written reason below.

## Standing
- **Schedule:** Aron doesn't care when; the goal is a few hours of building every day. The nightly
  task ("Crewreel nightly build", 01:13 Reykjavík) runs ~3 h. A second, older task ("Crewreel daily build",
  00:39) also fires; harmless as long as every run does `git pull --rebase` before pushing.
- **Render host: GitHub Actions** (free for a private repo, 2,000 min/month ≈ 700+ reels/month at ~2.5 min).
  Render's free tier (0.1 CPU / 512 MB) can't render. The web app can live on Render free once there is
  durable storage. Revisit when paying customers exist (then a paid worker is cheap relative to revenue).
- **Voice: "Blain – Conversational Ad Voice"** (ElevenLabs voice_id `jHprmvvyQreWpRuutdmV`, model `eleven_v4`).
  Calm, confident, made for Reels, not salesy — matches "contractor's trusted friend", not "infomercial".
  Templates' VO lines are written for this read (short, plain, one idea per line).
- **ElevenLabs credit budget:** the account is shared with Aron's daily Short (≈1,500 chars/day, uses voice
  "Michael C. Vincent" — never touch that). Crewreel may spend **at most 400 characters per run, only while
  more than 8,000 characters remain** in the billing period, always `generations_count: 1`, never retry a
  generation. Check `account_get_usage` first. Cache every take in `assets/vo/` so it is never paid twice.
- **Test footage:** placeholder generator + CC-licensed clips from Wikimedia Commons, for internal testing
  only, never in customer reels or ads (gitignored). Attribution kept in LOG.
- **Job store:** file-based (`data/`, atomic JSON) until deployed; then Postgres behind the same interface.
- **Uploads:** streamed per clip to disk (no buffering); direct-to-bucket once a bucket exists.
- **Captions:** shown only for VO lines that on-screen text doesn't already say (templates are text-led;
  doubling text clutters the frame). Word timing from the VO audio itself.
- **Stock VO per template:** template VO lines are generic (no business name), so one cached take per
  template (`assets/vo/<template>_blain.mp3`) serves every customer for free. The worker uses it
  automatically. Per-job custom VO (business name, area) waits for a product API key.
- **Mix targets:** voice −18 dBFS RMS, music bed −26 dBFS alone and ducked a further 8 dB under the voice
  (≈15 dB below speech), echo on music/fx only (never on the voice), output −14 LUFS, true peak < −1.5 dBTP.

## Run 7 (2026-11-27)
- **Close-ups aim at the clean-up, not at fixed coordinates.** `render/focus.py` compares the aligned
  before/after first frames (Lab, exposure-shift tolerant) and passes `P.focus` (up to 2 points) to templates.
  Labels on close-ups are generic ("Up close") because we can't know what object is there.
- **Text avoids the subject on still-ish shots.** `P.busy[before|after]` (edges + texture + distinct objects
  per band); hooks and result lines drop to the lower zone (with a deeper bottom scrim) when the top band is
  clearly busier. For hooks the after frame counts too when aligned (structure reads better without grime).
- **Third template = Roof soft wash**, not window cleaning: roofs are the most dramatic before/after and the
  highest-ticket job these contractors sell. Its reveal is a top-to-bottom rinse wipe (vmask), the way a roof
  is actually rinsed. Stock VO take cost 210 credits (budget ≤400/run kept; account showed 11,814 left before it).
- **Remote render hand-off = GitHub pre-release as a mailbox** (`worker/remote.py`, `render-job.yml`): the
  web box uploads clips, dispatches the workflow, polls, downloads the reel and deletes the release + tag.
  Outbound HTTPS only. A bucket replaces the release later; the dispatch stays.
- **Going online needs durable storage.** Render free's disk is ephemeral and the service sleeps after 15 min,
  so uploads and job records would vanish. Not worth deploying without a bucket; the bucket (Cloudflare R2,
  needs an account + card) is the one true blocker → NEEDS_ARON.
- **Wikimedia Commons rate-limits this sandbox (HTTP 429)** on both API and uploads. Don't spend run time on
  it; placeholder footage per surface (pavers, siding, roof) covers tests, real clips come from Aron.
- **Pre-upload footage check** in the web form uses the renderer's rules (min seconds per slot, sideways, low
  res) and warns, never blocks.

## Run 8 (2026-11-28)
- **End card = proof + one action.** Before|after proof card (footage drawn by the compositor in a rounded box at
  the focus point), logo + name row, a full-width accent CTA button readable by 0.8 s. Default CTA copy is an
  action: "Get a free quote". Background after-frame blurred hard (no ghosting of windows/doors).
- **Driveway** = 2.8 s hook, 4 s action, 3.6 s split, 1.6 s up-close wipe, 3 s end card. VO re-timed, no new take.
- **Fourth template = Window cleaning** (third trade in the one-liner). Signature reveal: a squeegee pulled across
  the glass (crisp edge, drawn blade). Stock VO take 184 credits (budget kept: ≤400/run, 11,111 left before).
- **render-samples runs on manual dispatch only.** Every run dispatches it once at the end. Free Actions minutes
  (2,000/month) are for customer reels.
- **Built-in quote page** (`/q`) is the default destination of every reel (end card shows `<host>/q`, captions
  carry `?r=<reel>`). A contractor's own quote URL still wins if set. Leads are files in `data/leads/` until
  Postgres. Unknown `?r` ids are dropped. Honeypot, no captcha (friction kills conversions).
- **Sign-in before going online:** one password per deployment (`CREWREEL_PASSWORD`, HMAC-signed cookie, 60 days).
  Public: `/q`, `POST /api/leads`, finished reels and posters (they're made to be posted; ids unguessable).
  Real accounts come with multi-tenancy.
- **Guided camera in the browser**, not a native app: MediaRecorder, no audio (the reel replaces it), clips kept in
  IndexedDB for 3 days so before/after can be filmed hours apart; the before frame is the ghost for the after.
- **4:5 feed version = layout via safe zones, then crop** (band y 285..1635 of the 9:16 canvas). One template serves
  both; opt-in per job because it doubles render minutes.
- **Foley:** synthesised reveal sounds (squeegee, rinse) via `meta.sfx`, kept ~6–10 dB under the voice;
  FX peak −14 dBFS; whooshes band-limited to ≤4.5 kHz.
- **Byline under every hook** (logo + business name): most viewers never reach the end card.
- **No ElevenLabs music** for the bed: it would blow the 400-credit/run budget. Synth bed stays for now (NEXT #4).
