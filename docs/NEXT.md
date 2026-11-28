# Next (ranked)
1. Real footage test set: as soon as Aron drops real before/after clips (or films with the new camera), render all
   four templates, tune focus/busy thresholds and the alignment gate on real pixels; check the guided camera on
   a real iPhone (MediaRecorder mp4, tilt permission, ghost alignment).
2. Go online once a bucket exists (NEEDS_ARON): storage adapter (local | R2 via S3 API, presigned PUT from the
   browser), job + lead records in the bucket (or Postgres), web on Render free with CREWREEL_PASSWORD +
   `worker --remote github`. Until then keep everything runnable locally.
3. New-quote alerts to the contractor (email via Resend once a sending domain exists; meanwhile web push or a
   daily digest). A quote request nobody sees is worth nothing.
4. Music: the synth bed is the weakest-sounding part I can't judge by ear. Options: a better arranged synth bed
   (drums, sidechain) measured against reference loudness/spectrum, or a royalty-free library once there's money.
5. Accounts + per-business quote pages (`/q/<slug>`) when the second customer exists (Postgres).
6. Feed version polish: its own poster, check the end card and hooks on real footage in 4:5.
7. Upload robustness: resume after dropped connections (chunked PUT with offsets / multipart to the bucket).
8. Per-job VO with business name/area once a product API key exists ({business} lines).
9. Fifth template: deck/fence (stain/clean), with its own stock VO.
10. Quote page: optional photos from the homeowner, and "What happens next" line set by the contractor.
