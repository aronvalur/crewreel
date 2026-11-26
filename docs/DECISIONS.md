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
