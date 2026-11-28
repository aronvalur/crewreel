import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { COOKIE, newSession, passwordOk } from "@/lib/session";

export const dynamic = "force-dynamic";

const safeNext = (n: string) => (n.startsWith("/") && !n.startsWith("//") ? n : "/");

async function signIn(form: FormData) {
  "use server";
  const next = safeNext(String(form.get("next") || "/"));
  if (!passwordOk(String(form.get("password") || ""))) {
    await new Promise(r => setTimeout(r, 700));               // slows guessing
    redirect(`/login?bad=1&next=${encodeURIComponent(next)}`);
  }
  const s = await newSession();
  (await cookies()).set(COOKIE, s.value, { httpOnly: true, sameSite: "lax", secure: process.env.NODE_ENV === "production" && !process.env.CREWREEL_INSECURE_COOKIE, maxAge: s.maxAge, path: "/" });
  redirect(next);
}

export default async function Login({ searchParams }: { searchParams: Promise<{ next?: string; bad?: string }> }) {
  const { next = "/", bad } = await searchParams;
  return (
    <main className="q" style={{ maxWidth: 400, paddingTop: 80 }}>
      <form action={signIn} className="stack">
        <h1>Crewreel</h1>
        <label className="field"><span>Password</span>
          <input type="password" name="password" autoComplete="current-password" autoFocus required />
        </label>
        <input type="hidden" name="next" value={safeNext(next)} />
        {bad && <p className="error" role="alert">That password didn&apos;t work.</p>}
        <button className="btn" type="submit">Sign in</button>
      </form>
    </main>
  );
}
