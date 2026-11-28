"use client";
// "Alert me on this phone" for new quote requests (Web Push).
import { useEffect, useState } from "react";

const b64 = (s: string) => {
  const p = (s + "=".repeat((4 - s.length % 4) % 4)).replace(/-/g, "+").replace(/_/g, "/");
  return Uint8Array.from(atob(p), c => c.charCodeAt(0));
};

export default function Alerts() {
  const [state, setState] = useState<"loading" | "off" | "on" | "blocked" | "unsupported" | "ios">("loading");
  useEffect(() => {
    (async () => {
      if (!("serviceWorker" in navigator) || !("PushManager" in window)) {
        const ios = /iPhone|iPad/.test(navigator.userAgent) && !(navigator as unknown as { standalone?: boolean }).standalone;
        return setState(ios ? "ios" : "unsupported");
      }
      if (Notification.permission === "denied") return setState("blocked");
      const reg = await navigator.serviceWorker.register("/sw.js");
      setState((await reg.pushManager.getSubscription()) ? "on" : "off");
    })().catch(() => setState("unsupported"));
  }, []);

  async function turnOn() {
    try {
      if ((await Notification.requestPermission()) !== "granted") return setState("blocked");
      const reg = await navigator.serviceWorker.register("/sw.js");
      const { publicKey } = await (await fetch("/api/push")).json();
      const sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: b64(publicKey) });
      const r = await fetch("/api/push", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(sub) });
      setState(r.ok ? "on" : "off");
    } catch { setState("off"); }
  }

  async function turnOff() {
    const reg = await navigator.serviceWorker.getRegistration("/sw.js");
    const sub = await reg?.pushManager.getSubscription();
    if (sub) {
      await fetch("/api/push", { method: "DELETE", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ endpoint: sub.endpoint }) });
      await sub.unsubscribe();
    }
    setState("off");
  }

  if (state === "loading" || state === "unsupported") return null;
  return (
    <div className="card row" style={{ justifyContent: "space-between" }}>
      <div>
        <h2>{state === "on" ? "Alerts are on for this phone" : "Get an alert for every request"}</h2>
        <p className="muted small" style={{ marginTop: 4 }}>
          {state === "ios" ? "On iPhone: Share → Add to Home Screen, open Crewreel from there, then turn alerts on."
            : state === "blocked" ? "Notifications are blocked for this site. Allow them in your browser settings."
            : "Reply first, win the job: call back while they are still looking."}
        </p>
      </div>
      {state === "off" && <button type="button" className="btn sm" onClick={turnOn}>Turn on alerts</button>}
      {state === "on" && <button type="button" className="btn ghost sm" onClick={turnOff}>Turn off</button>}
    </div>
  );
}
