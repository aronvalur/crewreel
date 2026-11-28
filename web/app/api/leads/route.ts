// Public: the quote page posts here. Never returns other people's data.
import { NextResponse } from "next/server";
import { cleanLead, saveLead } from "@/lib/leads";

export const runtime = "nodejs";

export async function POST(req: Request) {
  let body: Record<string, unknown>;
  try { body = await req.json(); } catch { return NextResponse.json({ error: "Something went wrong. Try again." }, { status: 400 }); }
  const { lead, error, spam } = await cleanLead(body);
  if (spam) return NextResponse.json({ ok: true }, { status: 201 });     // look accepted, store nothing
  if (error || !lead) return NextResponse.json({ error }, { status: 400 });
  await saveLead(lead);
  return NextResponse.json({ ok: true }, { status: 201 });
}
