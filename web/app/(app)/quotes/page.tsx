import Link from "next/link";
import { listLeads, markSeen, quoteLink } from "@/lib/leads";
import { getProfile, listJobs } from "@/lib/store";

export const dynamic = "force-dynamic";

const when = (iso: string) => new Date(iso).toLocaleString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

export default async function Quotes() {
  const [leads, jobs, profile] = await Promise.all([listLeads(), listJobs(), getProfile()]);
  const title = new Map(jobs.map(j => [j.id, j.title]));
  // which reels bring in work: requests per reel, best first
  const perReel = [...leads.reduce((m, l) => l.ref ? m.set(l.ref, (m.get(l.ref) || 0) + 1) : m, new Map<string, number>())]
    .sort((a, b) => b[1] - a[1]);
  const fresh = new Set(leads.filter(l => !l.seen).map(l => l.id));
  await markSeen([...fresh]);                       // opening the inbox marks them read (badge clears next load)
  return (
    <div className="stack" style={{ maxWidth: 680 }}>
      <div>
        <h1>Quote requests</h1>
        <p className="muted" style={{ marginTop: 6 }}>
          From your quote page{profile.url ? "" : <> (<span className="copy">{quoteLink("")}</span>)</>}. Each reel&apos;s caption links here, so you can see which reels bring in work.
        </p>
      </div>
      {perReel.length > 0 && (
        <div className="card">
          <h2>Reels that brought requests</h2>
          <div className="stack" style={{ marginTop: 12 }}>
            {perReel.map(([id, n]) => (
              <div key={id} className="row" style={{ justifyContent: "space-between" }}>
                <Link href={`/jobs/${id}`}>{title.get(id) || "A deleted reel"}</Link>
                <b>{n}</b>
              </div>
            ))}
          </div>
        </div>
      )}
      {leads.length === 0 ? (
        <div className="card" style={{ textAlign: "center", padding: "40px 20px" }}>
          <h2>No requests yet</h2>
          <p className="muted" style={{ marginTop: 6 }}>Post a reel with its caption. The link in it brings people to your quote page.</p>
        </div>
      ) : leads.map(l => (
        <div key={l.id} className={`card lead${fresh.has(l.id) ? " new" : ""}`}>
          <h2>{l.name}</h2>
          <span className="when">{when(l.createdAt)}</span>
          <p style={{ gridColumn: "1 / -1" }}>
            <a href={/@/.test(l.contact) ? `mailto:${l.contact}` : `tel:${l.contact.replace(/[^\d+]/g, "")}`}>{l.contact}</a>
            {l.address && <span className="muted"> · {l.address}</span>}
          </p>
          {l.services.length > 0 && <div className="tags" style={{ gridColumn: "1 / -1" }}>{l.services.map(s => <span key={s}>{s}</span>)}</div>}
          {l.message && <p className="copy" style={{ gridColumn: "1 / -1", marginTop: 6 }}>{l.message}</p>}
          {l.ref && <p className="from">From the reel “{title.get(l.ref) || "a deleted reel"}”</p>}
        </div>
      ))}
    </div>
  );
}
