// Streams one clip straight to disk. Never buffers the file in memory, so 4K phone
// clips don't exhaust a small server. The extension comes from ?name=, validated.
import { NextResponse } from "next/server";
import { createWriteStream, promises as fs } from "fs";
import path from "path";
import { getJob, jobDir } from "@/lib/store";
import { TEMPLATES } from "@/lib/templates";
import { MAX_BYTES, PHOTO_EXT, VIDEO_EXT } from "@/lib/upload";
import { COOKIE, authOn, validSession } from "@/lib/session";

export const runtime = "nodejs";

const SLOTS = new Set(TEMPLATES.flatMap(t => t.slots.map(s => s.name)));

export async function PUT(req: Request, { params }: { params: Promise<{ id: string; slot: string }> }) {
  // middleware skips this route (it would buffer the whole clip in memory), so check the sign-in here
  if (authOn() && !(await validSession(req.headers.get("cookie")?.match(new RegExp(`(?:^|; )${COOKIE}=([^;]+)`))?.[1]))) {
    return NextResponse.json({ error: "Sign in again." }, { status: 401 });
  }
  const { id, slot } = await params;
  let job = null;
  try { job = await getJob(id); } catch { /* bad id */ }
  if (!job || job.status !== "draft") return NextResponse.json({ error: "Upload expired. Start again." }, { status: 404 });
  if (!SLOTS.has(slot)) return NextResponse.json({ error: "Unknown shot." }, { status: 400 });
  const ext = path.extname(new URL(req.url).searchParams.get("name") || "").toLowerCase();
  if (![...VIDEO_EXT, ...PHOTO_EXT].includes(ext)) {
    return NextResponse.json({ error: `That file type (${ext || "unknown"}) isn't a photo or video.` }, { status: 400 });
  }
  if (Number(req.headers.get("content-length") || 0) > MAX_BYTES) {
    return NextResponse.json({ error: "File is over 500 MB. Trim it to the best 10 seconds." }, { status: 413 });
  }
  if (!req.body) return NextResponse.json({ error: "Empty upload." }, { status: 400 });

  const dir = path.join(jobDir(id), "in");
  await fs.mkdir(dir, { recursive: true });
  for (const old of await fs.readdir(dir)) if (path.parse(old).name === slot) await fs.rm(path.join(dir, old));
  const target = path.join(dir, slot + ext);
  const tmp = target + ".part";
  const out = createWriteStream(tmp);
  let bytes = 0;
  try {
    const reader = req.body.getReader();
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      bytes += value.byteLength;
      if (bytes > MAX_BYTES) throw new Error("too big");
      if (!out.write(value)) await new Promise<void>(r => out.once("drain", () => r()));
    }
    await new Promise<void>((res, rej) => out.end((e?: Error | null) => (e ? rej(e) : res())));
  } catch (e) {
    out.destroy();
    await fs.rm(tmp, { force: true });
    const big = (e as Error).message === "too big";
    return NextResponse.json({ error: big ? "File is over 500 MB. Trim it to the best 10 seconds." : "Upload interrupted. Try again." },
      { status: big ? 413 : 400 });
  }
  if (bytes === 0) { await fs.rm(tmp, { force: true }); return NextResponse.json({ error: "Empty upload." }, { status: 400 }); }
  await fs.rename(tmp, target);
  return NextResponse.json({ slot, file: slot + ext, bytes });
}
