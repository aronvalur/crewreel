import { NextResponse, type NextRequest } from "next/server";
import { COOKIE, authOn, isPublic, validSession } from "@/lib/session";

export async function middleware(req: NextRequest) {
  if (!authOn() || isPublic(req.nextUrl.pathname, req.method)) return NextResponse.next();
  if (await validSession(req.cookies.get(COOKIE)?.value)) return NextResponse.next();
  if (req.nextUrl.pathname.startsWith("/api/")) return NextResponse.json({ error: "Sign in again." }, { status: 401 });
  const url = req.nextUrl.clone();
  url.pathname = "/login";
  url.search = `?next=${encodeURIComponent(req.nextUrl.pathname + req.nextUrl.search)}`;
  return NextResponse.redirect(url);
}

// Clip uploads (PUT /api/drafts/<id>/<slot>) are excluded: middleware would buffer the body (10 MB cap).
// That route checks the session itself.
export const config = { matcher: ["/((?!_next/static|_next/image|api/drafts/[^/]+/[^/]+$).*)"] };
