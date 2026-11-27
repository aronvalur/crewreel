# Next (ranked)
1. Real footage test set: as soon as Aron drops any real before/after clips, render all three templates on them,
   tune focus/busy thresholds and the alignment gate on real pixels, add them to the golden set (gitignored).
2. Go online once a bucket exists (NEEDS_ARON): storage adapter (local | R2 via S3 API, presigned PUT from the
   browser), job records in the bucket (or Render free Postgres), web on Render free + `worker --remote github`
   in the same service. Until then, keep everything runnable locally.
3. Driveway pacing: 5 s single action clip is long; consider 4 s action + 1.5 s up-close wipe at P.focus
   (needs a re-timed VO take, ≤400 credits).
4. Judge the VO reels as a viewer: line timing vs cuts, ducking feel, caption size; tune.
5. Per-job VO with business name/area once a product API key exists ({business} lines).
6. Upload robustness: resume after dropped connections (chunked PUT with offsets).
7. Square 1:1 and 4:5 variants (layout, not crop) for FB/IG feed placements.
8. Fourth template: window cleaning (inside/outside glass, squeegee action), with its own stock VO.
9. Guided camera PWA: ghost overlay of the before photo, shot list, level/light checks.
10. Quote page per business with tracked links (?r=<reelId>) + Google Business post / review-request texts.
