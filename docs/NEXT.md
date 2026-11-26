# Next (ranked)
1. Real sample footage from Aron → re-render both templates, judge against the agency bar, tune timings/typography.
2. Per-frame stabilisation of before/after during the reveal (align is computed on frame 0 only; handheld drift of a few px shows at the seam).
3. VO: pick an ElevenLabs voice (needs key), time captions to VO words (burned-in captions for sound-off viewers).
4. Adaptive legibility: measure luminance behind text per frame and raise scrim only when needed.
5. Square 1:1 re-layout of both templates (layout variant, not crop).
6. Next.js skeleton (app router, TS): `/jobs/new` upload before/after/action → render job → result page.
7. Render queue: Postgres `renders` table + worker script (local first, then Render free tier).
8. Guided camera PWA: ghost overlay of before photo + shot list per job type + level/light checks.
9. Text outputs (caption+hashtags, Google Business post, review request) + quote page with tracked links.
