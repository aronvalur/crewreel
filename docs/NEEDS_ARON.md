# Needs Aron
1. 3–5 real before/after photos + 3–5 s vertical action clips from one driveway job and one house wash (before and after from roughly the same spot). Upload to the project or Drive.
2. **Decision: where renders run.** Render's free tier (0.1 CPU / 512 MB) can't render reels. Options: (a) GitHub Actions as the render runner, free for a private repo up to 2,000 min/month ≈ 700+ reels/month at ~2.5 min each, fine for beta (my recommendation); (b) a paid Render worker (from ~$7/mo starter, faster with $25 standard); (c) your Mac while testing. Web app itself can stay on Render free.
3. ElevenLabs: an API key for the product (env `ELEVENLABS_API_KEY`) and a voice pick (`ELEVENLABS_VOICE_ID`) — or tell me to pick a calm, confident English voice. Also say whether build runs may spend ElevenLabs credits on test VO (and a cap, e.g. 2,000 characters/run). None used so far.
4. Build schedule: you asked for builds during the day too. I couldn't change the scheduled task from here (permission blocked). In Claude → Scheduled tasks → "Crewreel nightly build", set it to run e.g. 04:13, 10:13, 16:13, 22:13. Also: an older "Crewreel daily build" task (00:39) still fires every night with an outdated prompt and would collide with the nightly one; consider turning it off.
5. Later: Stripe account, domain, R2/S3 bucket, Meta ad account.
6. Approve anything public (ads, posts, emails).
