import Link from "next/link";
import { countNewLeads } from "@/lib/leads";

export const dynamic = "force-dynamic";

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const fresh = await countNewLeads();
  return (
    <>
      <header className="top">
        <div className="wrap">
          <Link href="/" className="brand">Crewreel</Link>
          <Link href="/" className="nav">Reels</Link>
          <Link href="/quotes" className="nav">Quotes{fresh > 0 && <span className="badge">{fresh}</span>}</Link>
          <Link href="/settings" className="nav">Business</Link>
          <Link href="/jobs/new" className="btn sm">New reel</Link>
        </div>
      </header>
      <main className="wrap">{children}</main>
    </>
  );
}
