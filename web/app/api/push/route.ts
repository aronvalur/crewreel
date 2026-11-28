// Contractor's phone subscribes to new-quote alerts (behind sign-in via middleware).
import { NextResponse } from "next/server";
import { removeSub, saveSub, validSub, vapidKeys } from "@/lib/push";

export const runtime = "nodejs";

export async function GET() {
  return NextResponse.json({ publicKey: (await vapidKeys()).publicKey });
}

export async function POST(req: Request) {
  const body = await req.json().catch(() => null);
  if (!validSub(body)) return NextResponse.json({ error: "Bad subscription." }, { status: 400 });
  await saveSub(body);
  return NextResponse.json({ ok: true }, { status: 201 });
}

export async function DELETE(req: Request) {
  const body = await req.json().catch(() => null);
  if (body?.endpoint) await removeSub(String(body.endpoint));
  return NextResponse.json({ ok: true });
}
