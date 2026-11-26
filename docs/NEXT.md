# Next (ranked)
1. Real job footage from Aron (one driveway, one house wash) → full renders through the app, judge against the agency bar, tune timings/type.
2. Deploy decision (see NEEDS_ARON #2). If GitHub Actions: workflow that renders a job from a bucket/artifact; if a paid Render worker: Dockerfile (ffmpeg + Chromium + Python) + render.yaml. Prepare the Dockerfile either way.
3. VO + word-timed captions: ElevenLabs `with-timestamps` → caption track only where on-screen text doesn't already say it. Needs key + credit OK.
4. Upload robustness: resumable/direct-to-bucket uploads for 4K phone clips (route handler buffers whole files in memory today), client-side checks (duration, orientation) before upload using the same rules as ingest.
5. Better hero detection for text placement (detail/edge stability + motion) and apply to hook + tags.
6. Square 1:1 and 4:5 variants (layout, not crop) offered on the job page.
7. Postgres job store behind the same interface (`web/lib/store.ts` + worker) once deployed.
8. Guided camera PWA: ghost overlay of the before photo, shot list per job type, level/light checks.
9. Quote page per business with tracked links (?r=<reelId>) + Google Business post and review-request texts.
10. More templates: roof soft wash, deck/patio, window cleaning.
