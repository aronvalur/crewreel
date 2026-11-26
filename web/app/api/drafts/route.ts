// Step 1 of an upload: reserve a job folder. Clips are then streamed one by one
// (PUT /api/drafts/<id>/<slot>) and the job is queued with POST /api/jobs.
import { NextResponse } from "next/server";
import { newId, saveJob } from "@/lib/store";

export const runtime = "nodejs";

export async function POST() {
  const id = newId();
  await saveJob({ id, createdAt: new Date().toISOString(), template: "", title: "", status: "draft", params: {}, files: {} });
  return NextResponse.json({ id }, { status: 201 });
}
