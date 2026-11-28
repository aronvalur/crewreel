// Public quote page: where the reel's link lands. Proof first (recent before/after frames), then a
// short form a homeowner can finish on a phone in under a minute.
import type { Metadata } from "next";
import { getProfile, listJobs } from "@/lib/store";
import { SERVICES } from "@/lib/leads";
import QuoteForm from "./form";
import Work from "./work";

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const p = await getProfile();
  const name = p.business || "Free quote";
  return { title: `${name} · Free quote`, description: p.area ? `Exterior cleaning in ${p.area}. Ask for a free quote.` : "Ask for a free quote." };
}

export default async function QuotePage({ searchParams }: { searchParams: Promise<{ r?: string }> }) {
  const { r } = await searchParams;
  const [p, jobs] = await Promise.all([getProfile(), listJobs()]);
  const done = jobs.filter(j => j.status === "done");
  const ref = done.find(j => j.id === r);
  const work = (ref ? [ref, ...done.filter(j => j !== ref)] : done).slice(0, 6);
  const initial = (p.business || "?").trim()[0]?.toUpperCase() || "?";
  return (
    <main className="q" style={{ ["--accent" as string]: p.accent }}>
      <header className="q-id">
        <div className="q-logo">{initial}</div>
        <div>
          <h1 className="q-biz">{p.business || "Your business"}</h1>
          {p.area && <p className="muted small">Exterior cleaning · {p.area}</p>}
        </div>
      </header>

      <section>
        <h2 className="q-title">{p.cta || "Get a free quote"}</h2>
        <p className="muted" style={{ marginTop: 6 }}>Tell us what needs cleaning and where. We&apos;ll come back to you with a price.</p>
      </section>

      {work.length > 0 && (
        <section aria-label="Recent work">
          <p className="q-k">Recent work</p>
          <Work items={work.map(j => ({ id: j.id, title: j.title }))} />
        </section>
      )}

      <QuoteForm services={[...SERVICES]} refId={ref?.id || ""} business={p.business} />
    </main>
  );
}
