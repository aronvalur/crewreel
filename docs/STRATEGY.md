# Crewreel — Strategy (working name)
Owner: Aron Valur. Builder: Claude (nightly runs). Aron owns accounts, money, ads.

**One line:** Your crew films the job, and you get back an agency-quality reel that brings in quote requests.

**Who:** exterior-cleaning contractors (pressure washing, soft wash, window cleaning), 1–10 people, international, English first.
**Channel:** Facebook/Instagram software ads only, made with Hyperframes + ElevenLabs.
**Quality bar:** real footage only, no AI-faked visuals; clean designed motion templates; pro voiceover; captions; subtle sound. Looks like a $2k agency edit. No "vibe-coded" UI.

## Product v1
- Guided camera PWA: before-photo ghost overlay; shot list per job type; level/steady/light checks; prompts for the action clip.
- Job types: driveway, house wash, roof, deck, windows.
- Outputs per job: 9:16 reel (15–30 s), square post, caption + hashtags, Google Business post text, review-request text.
- Quote landing page per business with tracked links (?r=<reelId>).

## Pricing (to test)
$49/mo (8 reels) · $99/mo (25 reels + analytics) · 7-day trial.

## Stack
Next.js + Postgres + object storage + render worker (Hyperframes-style HTML compositions → headless Chrome + ffmpeg) on Render (free tiers only), ElevenLabs API voice, Stripe, Resend.

## Roadmap
- Week 1: skeleton + first 2 templates rendering from sample footage.
- Week 2: guided camera + job flow + render worker.
- Week 3: profiles, text outputs, quote page, auth.
- Week 4: Stripe, landing page, first ad creatives.
- v2 auto-posting · v3 local boosted ads.
