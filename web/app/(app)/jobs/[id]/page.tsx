import { notFound } from "next/navigation";
import { getJob, getProfile, saveJob } from "@/lib/store";
import { templateById } from "@/lib/templates";
import { caption } from "@/lib/caption";
import { statusText } from "@/lib/status";
import { revalidatePath } from "next/cache";
import Poll from "./poll";
import CopyButton from "./copy";

export const dynamic = "force-dynamic";

async function retry(form: FormData) {
  "use server";
  const job = await getJob(String(form.get("id")));
  if (job && job.status === "failed") {
    await saveJob({ ...job, status: "queued", error: undefined, stage: undefined });
    revalidatePath(`/jobs/${job.id}`);
  }
}

export default async function JobPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  let job = null;
  try { job = await getJob(id); } catch { /* bad id */ }
  if (!job) notFound();
  const tpl = templateById(job.template);
  const profile = await getProfile();
  const hints = Object.entries(job.hints || {}).flatMap(([slot, hs]) =>
    hs.map(h => ({ slot: tpl?.slots.find(s => s.name === slot)?.label || slot, ...h })));

  if (job.status !== "done") {
    return (
      <div style={{ maxWidth: 560 }} className="stack">
        <h1>{job.title}</h1>
        {job.status === "failed" ? (
          <>
            <p className="error">This reel didn&apos;t render.</p>
            <p className="muted small">{job.error || "Something went wrong on our side."}</p>
            <form action={retry}><input type="hidden" name="id" value={job.id} />
              <button className="btn" type="submit">Try again</button></form>
          </>
        ) : (
          <>
            <p className="muted">{statusText(job)}. Usually two to three minutes. You can leave this page; the reel will be on your Reels page.</p>
            <div className="bar"><i style={{ width: job.status === "queued" ? "4%" : stagePct(job.stage) }} /></div>
            <Poll id={job.id} status={job.status} stage={job.stage || ""} />
          </>
        )}
      </div>
    );
  }

  const text = caption(job, profile);
  return (
    <div className="player">
      <video src={`/api/files/${job.id}/reel.mp4`} poster={`/api/files/${job.id}/poster.jpg`} controls playsInline />
      <div className="stack">
        <div>
          <h1>{job.title}</h1>
          <p className="muted" style={{ marginTop: 6 }}>{tpl?.title} · ready to post</p>
        </div>
        <div className="row">
          <a className="btn" href={`/api/files/${job.id}/reel.mp4?download`}>Download reel</a>
        </div>
        <div className="card stack">
          <div className="row" style={{ justifyContent: "space-between" }}>
            <h2>Caption</h2>
            <CopyButton text={text} />
          </div>
          <p className="copy">{text}</p>
        </div>
        {hints.length > 0 && (
          <div className="stack">
            <h2>For next time</h2>
            {hints.map((h, i) => (
              <div key={i} className="hint"><b>{h.slot}</b>{h.message}</div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function stagePct(stage?: string) {
  const order = ["Preparing footage", "Lining up before and after", "Drawing graphics", "Steadying shots", "Composing frames", "Mixing sound"];
  const i = order.findIndex(s => stage?.startsWith(s));
  return `${Math.round(((i < 0 ? 0 : i) + 1) / (order.length + 1) * 100)}%`;
}
