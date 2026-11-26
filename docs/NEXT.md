# Next (ranked)
1. Real job footage from Aron (one driveway, one house wash) → full renders, judge against the agency bar, tune timings/type. Meanwhile: pull 2–3 more CC clips from Commons (throttled — it rate-limits; try the Dirtblaster wand clip and "Before and after low pressure cleaning.jpg") to keep testing ingest/plate logic on real pixels.
2. Next.js skeleton (app router, TS): `/jobs/new` upload before/after/action → render → result page that shows the reel and the `footage.json` re-shoot hints. No vibe-coded UI.
3. Render queue: Postgres `renders` table + worker (local first, then Render free tier). Fonts are already bundled.
4. VO + word-timed captions: ElevenLabs `with-timestamps` endpoint → caption track (shown only where on-screen text doesn't already say it). Needs key + credit OK.
5. Render speed (≈155 s per 15 s reel): parallel Playwright pages for overlay, skip screenshots when the overlay is unchanged, vectorised compositing.
6. Better hero detection for text placement: detail/edge stability (the tool) + motion (the spray), and apply it to hook and tags, not only the plate.
7. Adaptive legibility: measure luminance behind text per frame; raise scrim only when needed.
8. Square 1:1 re-layout of both templates (layout variant, not crop).
9. Guided camera PWA: ghost overlay of the before photo + shot list per job type + level/light checks (uses the same quality rules as ingest).
10. Text outputs (caption + hashtags, Google Business post, review request) + quote page with tracked links.
