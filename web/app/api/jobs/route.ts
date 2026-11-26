import { NextResponse } from "next/server";
import { promises as fs } from "fs";
import path from "path";
import { jobDir, newId, saveJob, listJobs, type Job } from "@/lib/store";
import { templateById } from "@/lib/templates";

export const runtime = "nodejs";

const VIDEO_EXT = [".mp4", ".mov", ".m4v", ".webm", ".mkv"];
const PHOTO_EXT = [".jpg", ".jpeg", ".png", ".webp", ".heic"];
const MAX_BYTES = 500 * 1024 * 1024;

export async function GET() {
  return NextResponse.json(await listJobs());
}

export async function POST(req: Request) {
  let form: FormData;
  try {
    form = await req.formData();
  } catch {
    return NextResponse.json({ error: "Upload failed. Try again on a stronger connection." }, { status: 400 });
  }
  const tpl = templateById(String(form.get("template") || ""));
  if (!tpl) return NextResponse.json({ error: "Pick a reel style." }, { status: 400 });

  const missing: string[] = [];
  const uploads: { slot: string; file: File; ext: string }[] = [];
  for (const slot of tpl.slots) {
    const f = form.get(slot.name);
    if (!(f instanceof File) || f.size === 0) {
      if (!slot.optional) missing.push(slot.label);
      continue;
    }
    const ext = path.extname(f.name).toLowerCase();
    const allowed = slot.kind === "video" ? VIDEO_EXT : [...VIDEO_EXT, ...PHOTO_EXT];
    if (!allowed.includes(ext)) {
      return NextResponse.json({ error: `${slot.label}: ${slot.kind === "video" ? "needs a video" : "needs a photo or video"} (got ${ext || "unknown"}).` }, { status: 400 });
    }
    if (f.size > MAX_BYTES) {
      return NextResponse.json({ error: `${slot.label}: file is over 500 MB. Trim it to the best 10 seconds.` }, { status: 400 });
    }
    uploads.push({ slot: slot.name, file: f, ext });
  }
  if (missing.length) {
    return NextResponse.json({ error: `Still missing: ${missing.join(", ")}.` }, { status: 400 });
  }

  const params: Record<string, string> = {};
  for (const fld of tpl.fields) {
    const v = String(form.get(fld.name) || "").replace(/\r\n/g, "\n").trim().slice(0, fld.max);
    if (v) params[fld.name] = v;
  }

  const id = newId();
  const dir = path.join(jobDir(id), "in");
  await fs.mkdir(dir, { recursive: true });
  const files: Record<string, string> = {};
  for (const u of uploads) {
    const name = u.slot + u.ext;
    await fs.writeFile(path.join(dir, name), Buffer.from(await u.file.arrayBuffer()));
    files[u.slot] = name;
  }
  const title = String(form.get("title") || "").trim().slice(0, 60) || tpl.title;
  const job: Job = {
    id, createdAt: new Date().toISOString(), template: tpl.id, title, status: "queued", params, files,
  };
  await saveJob(job);
  return NextResponse.json({ id }, { status: 201 });
}
