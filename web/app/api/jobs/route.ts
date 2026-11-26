// Step 3 of an upload: turn a draft (clips already streamed to disk) into a queued job.
import { NextResponse } from "next/server";
import { promises as fs } from "fs";
import path from "path";
import { getJob, jobDir, saveJob, listJobs } from "@/lib/store";
import { templateById } from "@/lib/templates";
import { PHOTO_EXT, VIDEO_EXT } from "@/lib/upload";

export const runtime = "nodejs";

export async function GET() {
  return NextResponse.json(await listJobs());
}

export async function POST(req: Request) {
  let body: Record<string, unknown>;
  try { body = await req.json(); } catch { return NextResponse.json({ error: "Bad request." }, { status: 400 }); }
  const tpl = templateById(String(body.template || ""));
  if (!tpl) return NextResponse.json({ error: "Pick a reel style." }, { status: 400 });
  let job = null;
  try { job = await getJob(String(body.draft || "")); } catch { /* bad id */ }
  if (!job || job.status !== "draft") return NextResponse.json({ error: "Upload expired. Start again." }, { status: 404 });

  let present: string[] = [];
  try { present = await fs.readdir(path.join(jobDir(job.id), "in")); } catch { /* none yet */ }
  const files: Record<string, string> = {};
  const missing: string[] = [];
  for (const slot of tpl.slots) {
    const f = present.find(n => path.parse(n).name === slot.name && !n.endsWith(".part"));
    if (!f) { if (!slot.optional) missing.push(slot.label); continue; }
    if (slot.kind === "video" && !VIDEO_EXT.includes(path.extname(f))) {
      return NextResponse.json({ error: `${slot.label}: needs a video, not a photo.` }, { status: 400 });
    }
    if (![...VIDEO_EXT, ...PHOTO_EXT].includes(path.extname(f))) continue;
    files[slot.name] = f;
  }
  if (missing.length) return NextResponse.json({ error: `Still missing: ${missing.join(", ")}.` }, { status: 400 });

  const fields = (body.fields || {}) as Record<string, unknown>;
  const params: Record<string, string> = {};
  for (const fld of tpl.fields) {
    const v = String(fields[fld.name] || "").replace(/\r\n/g, "\n").trim().slice(0, fld.max);
    if (v) params[fld.name] = v;
  }
  const title = String(body.title || "").trim().slice(0, 60) || tpl.title;
  await saveJob({ ...job, createdAt: new Date().toISOString(), template: tpl.id, title, status: "queued", params, files });
  return NextResponse.json({ id: job.id }, { status: 201 });
}
