// New-quote alerts on the contractor's phone via Web Push. No accounts or services: VAPID keys are made on
// first use and kept in $CREWREEL_DATA/vapid.json (or come from CREWREEL_VAPID_PUBLIC/PRIVATE), subscriptions
// live in $CREWREEL_DATA/push/. Android Chrome works in the browser; iPhone once the app is on the home screen.
import { promises as fs } from "fs";
import path from "path";
import crypto from "crypto";
import webpush from "web-push";
import { DATA } from "./store";

type Keys = { publicKey: string; privateKey: string };
type Sub = { endpoint: string; keys: { p256dh: string; auth: string } };

let cached: Keys | null = null;
export async function vapidKeys(): Promise<Keys> {
  if (cached) return cached;
  if (process.env.CREWREEL_VAPID_PUBLIC && process.env.CREWREEL_VAPID_PRIVATE)
    return (cached = { publicKey: process.env.CREWREEL_VAPID_PUBLIC, privateKey: process.env.CREWREEL_VAPID_PRIVATE });
  const file = path.join(DATA, "vapid.json");
  try { return (cached = JSON.parse(await fs.readFile(file, "utf8"))); } catch { /* first use */ }
  const k = webpush.generateVAPIDKeys();
  await fs.mkdir(DATA, { recursive: true });
  try { await fs.writeFile(file, JSON.stringify(k), { flag: "wx" }); return (cached = k); }
  catch { return (cached = JSON.parse(await fs.readFile(file, "utf8"))); }      // another process won the race
}

const dir = () => path.join(DATA, "push");
const fileFor = (endpoint: string) => path.join(dir(), crypto.createHash("sha256").update(endpoint).digest("hex").slice(0, 24) + ".json");

export function validSub(s: unknown): s is Sub {
  const x = s as Sub;
  return !!x && typeof x.endpoint === "string" && /^https:\/\//.test(x.endpoint) && x.endpoint.length < 1000 &&
    typeof x.keys?.p256dh === "string" && typeof x.keys?.auth === "string";
}

export async function saveSub(s: Sub) {
  await fs.mkdir(dir(), { recursive: true });
  await fs.writeFile(fileFor(s.endpoint), JSON.stringify({ endpoint: s.endpoint, keys: s.keys }));
}

export async function removeSub(endpoint: string) {
  await fs.rm(fileFor(endpoint), { force: true });
}

async function subs(): Promise<Sub[]> {
  let names: string[] = [];
  try { names = await fs.readdir(dir()); } catch { return []; }
  const out = await Promise.all(names.filter(n => n.endsWith(".json")).map(async n => {
    try { return JSON.parse(await fs.readFile(path.join(dir(), n), "utf8")) as Sub; } catch { return null; }
  }));
  return out.filter(Boolean) as Sub[];
}

// Fire-and-forget from the lead route: never let a push failure lose a quote request.
export async function notifyAll(title: string, body: string, url = "/quotes") {
  const list = await subs();
  if (!list.length) return 0;
  const k = await vapidKeys();
  const subject = `https://${(process.env.CREWREEL_PUBLIC_HOST || "crewreel.app").replace(/^https?:\/\//, "")}`;
  let sent = 0;
  await Promise.all(list.map(async s => {
    try {
      await webpush.sendNotification(s, JSON.stringify({ title, body, url }),
        { vapidDetails: { subject, publicKey: k.publicKey, privateKey: k.privateKey }, TTL: 24 * 3600, urgency: "high" });
      sent++;
    } catch (e) {
      const code = (e as { statusCode?: number }).statusCode;
      if (code === 404 || code === 410) await removeSub(s.endpoint);       // phone unsubscribed / app removed
    }
  }));
  return sent;
}
