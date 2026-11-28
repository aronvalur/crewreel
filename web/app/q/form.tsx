"use client";
import { useState } from "react";

export default function QuoteForm({ services, refId, business }: { services: string[]; refId: string; business: string }) {
  const [state, setState] = useState<"idle" | "sending" | "sent">("idle");
  const [error, setError] = useState("");
  const [picked, setPicked] = useState<string[]>([]);

  if (state === "sent") {
    return (
      <div className="card q-done" role="status">
        <h2>Thanks, we&apos;ve got it.</h2>
        <p className="muted" style={{ marginTop: 6 }}>{business || "We"} will get back to you with a price soon.</p>
      </div>
    );
  }

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setState("sending"); setError("");
    try {
      const res = await fetch("/api/leads", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...Object.fromEntries(f.entries()), services: picked, ref: refId }),
      });
      if (res.ok) { setState("sent"); return; }
      setError((await res.json().catch(() => ({}))).error || "Something went wrong. Try again.");
    } catch {
      setError("No connection. Check your signal and try again.");
    }
    setState("idle");
  }

  return (
    <form className="stack" onSubmit={submit} noValidate>
      <fieldset className="q-services">
        <legend>What needs cleaning?</legend>
        <div className="q-chips">
          {services.map(s => (
            <label key={s} className="q-chip">
              <input type="checkbox" checked={picked.includes(s)}
                onChange={e => setPicked(p => e.target.checked ? [...p, s] : p.filter(x => x !== s))} />
              <span>{s}</span>
            </label>
          ))}
        </div>
      </fieldset>
      <label className="field"><span>Your name</span>
        <input type="text" name="name" autoComplete="name" required maxLength={60} />
      </label>
      <label className="field"><span>Phone or email</span>
        <input type="text" name="contact" autoComplete="tel" required maxLength={80} />
      </label>
      <label className="field"><span>Address or postcode</span>
        <input type="text" name="address" autoComplete="street-address" maxLength={120} />
      </label>
      <label className="field"><span>Anything we should know?</span>
        <textarea name="message" maxLength={800} placeholder="Size of the driveway, how long since it was last cleaned…" />
      </label>
      <input type="text" name="website" tabIndex={-1} autoComplete="off" className="q-hp" aria-hidden="true" />
      {error && <p className="error" role="alert">{error}</p>}
      <button className="btn q-send" type="submit" disabled={state === "sending"}>
        {state === "sending" ? "Sending…" : "Send quote request"}
      </button>
      <p className="muted small">Your details only go to {business || "us"}. No spam.</p>
    </form>
  );
}
