import Link from "next/link";
import { listJobs, getProfile, type Job } from "@/lib/store";
import { templateById } from "@/lib/templates";
import { statusText } from "@/lib/status";

export const dynamic = "force-dynamic";

export default async function Home() {
  const [jobs, profile] = await Promise.all([listJobs(), getProfile()]);
  return (
    <>
      <div className="head">
        <div>
          <h1>Your reels</h1>
          <p className="muted" style={{ marginTop: 6 }}>Film the job, upload the clips, get back a reel ready to post.</p>
        </div>
      </div>

      {!profile.business && (
        <div className="card row" style={{ justifyContent: "space-between", marginBottom: 24 }}>
          <div>
            <h2>Add your business first</h2>
            <p className="muted small" style={{ marginTop: 4 }}>Your name, area and quote link go on the last frame of every reel.</p>
          </div>
          <Link href="/settings" className="btn ghost sm">Set up business</Link>
        </div>
      )}

      {jobs.length === 0 ? (
        <div className="card" style={{ textAlign: "center", padding: "48px 20px" }}>
          <h2>No reels yet</h2>
          <p className="muted" style={{ margin: "6px 0 20px" }}>Your next job is your first reel. It takes three clips.</p>
          <Link href="/jobs/new" className="btn">Make a reel</Link>
        </div>
      ) : (
        <div className="grid">
          {jobs.map(j => (
            <Link key={j.id} href={`/jobs/${j.id}`} className="reel">
              {j.status === "done" ? (
                <div className="thumb"><img src={`/api/files/${j.id}/poster.jpg`} alt="" /></div>
              ) : (
                <div className="thumb empty">{statusText(j)}</div>
              )}
              <div className="meta">
                <h3>{j.title}</h3>
                <p className="muted small">
                  {templateById(j.template)?.title} · {new Date(j.createdAt).toLocaleDateString("en-GB", { day: "numeric", month: "short" })}
                </p>
                {j.status === "done" && <p className="muted small">{statusText(j)}</p>}
              </div>
            </Link>
          ))}
        </div>
      )}
    </>
  );
}
