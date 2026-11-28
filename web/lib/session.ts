// Contractor sign-in: one password per deployment (CREWREEL_PASSWORD), a signed cookie, no accounts yet.
// Without CREWREEL_PASSWORD the app is open (local use, tests). Edge-safe: Web Crypto only.
export const COOKIE = "cr_session";
const DAYS = 60;

const enc = new TextEncoder();
const secret = () => process.env.CREWREEL_SECRET || process.env.CREWREEL_PASSWORD || "";
export const authOn = () => !!process.env.CREWREEL_PASSWORD;

async function sign(msg: string) {
  const key = await crypto.subtle.importKey("raw", enc.encode(secret()), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const sig = new Uint8Array(await crypto.subtle.sign("HMAC", key, enc.encode(msg)));
  return Array.from(sig, b => b.toString(16).padStart(2, "0")).join("");
}

export async function newSession() {
  const exp = String(Date.now() + DAYS * 864e5);
  return { value: `${exp}.${await sign(exp)}`, maxAge: DAYS * 86400 };
}

export async function validSession(value?: string) {
  if (!value) return false;
  const [exp, sig] = value.split(".");
  if (!exp || !sig || !(Number(exp) > Date.now())) return false;
  const good = await sign(exp);
  if (good.length !== sig.length) return false;
  let diff = 0;                                         // constant-time compare
  for (let i = 0; i < good.length; i++) diff |= good.charCodeAt(i) ^ sig.charCodeAt(i);
  return diff === 0;
}

export function passwordOk(given: string) {
  const want = process.env.CREWREEL_PASSWORD || "";
  if (!want || given.length !== want.length) return false;
  let diff = 0;
  for (let i = 0; i < want.length; i++) diff |= want.charCodeAt(i) ^ given.charCodeAt(i);
  return diff === 0;
}

// What homeowners may reach without signing in: the quote page, its form post, finished reels + posters
// (they're the proof on the quote page; ids are unguessable and the reels are made to be posted publicly).
export function isPublic(path: string, method: string) {
  return path === "/q" || path === "/login" ||
    (path === "/api/leads" && method === "POST") ||
    /^\/api\/files\/[a-z0-9-]{6,40}\/(poster\.jpg|reel\.mp4)$/.test(path) ||
    path.startsWith("/_next/") || path.startsWith("/fonts/") || path === "/favicon.ico";
}
