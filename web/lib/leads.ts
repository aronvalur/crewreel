// Quote requests from the public quote page (/q). One JSON file per request under $CREWREEL_DATA/leads/.
// `ref` is the reel the visitor came from (?r=<jobId> in the link the reel's caption carries),
// so the contractor can see which reels bring in work.
import { promises as fs } from "fs";
import path from "path";
import crypto from "crypto";
import { DATA, getJob } from "./store";

export const SERVICES = ["Driveway or patio", "House wash", "Roof", "Windows", "Deck or fence", "Something else"] as const;

export type Lead = {
  id: string;
  createdAt: string;
  name: string;
  contact: string;       // phone or email, as typed
  address: string;
  services: string[];
  message: string;
  ref?: string;          // job id of the reel that sent them
  seen?: boolean;
};

const dir = () => path.join(DATA, "leads");
const ID = /^[0-9]{8}-[0-9a-f]{8}$/;

export type LeadInput = { name?: unknown; contact?: unknown; address?: unknown; services?: unknown; message?: unknown; ref?: unknown; website?: unknown };

// Validate + clean a submission. Returns the lead fields or a plain-English error for the visitor.
export async function cleanLead(b: LeadInput): Promise<{ lead?: Omit<Lead, "id" | "createdAt">; error?: string; spam?: boolean }> {
  if (String(b.website || "")) return { spam: true };                    // honeypot: humans never see it
  const s = (v: unknown, max: number) => String(v ?? "").replace(/\s+/g, " ").trim().slice(0, max);
  const name = s(b.name, 60), contact = s(b.contact, 80), address = s(b.address, 120);
  const message = String(b.message ?? "").replace(/\r\n/g, "\n").trim().slice(0, 800);
  const services = (Array.isArray(b.services) ? b.services : []).map(String).filter(x => (SERVICES as readonly string[]).includes(x));
  if (!name) return { error: "Add your name." };
  const digits = contact.replace(/\D/g, "");
  if (!(/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(contact) || digits.length >= 7)) return { error: "Add a phone number or email so we can send your quote." };
  let ref: string | undefined = s(b.ref, 40) || undefined;
  if (ref) { try { if (!(await getJob(ref))) ref = undefined; } catch { ref = undefined; } }
  return { lead: { name, contact, address, services, message, ref } };
}

export async function saveLead(l: Omit<Lead, "id" | "createdAt">): Promise<Lead> {
  const now = new Date();
  const lead: Lead = { id: `${now.toISOString().slice(0, 10).replace(/-/g, "")}-${crypto.randomBytes(4).toString("hex")}`,
    createdAt: now.toISOString(), ...l };
  await fs.mkdir(dir(), { recursive: true });
  const file = path.join(dir(), `${lead.id}.json`), tmp = `${file}.${process.pid}.tmp`;
  await fs.writeFile(tmp, JSON.stringify(lead, null, 1));
  await fs.rename(tmp, file);
  return lead;
}

export async function listLeads(): Promise<Lead[]> {
  let names: string[] = [];
  try { names = await fs.readdir(dir()); } catch { return []; }
  const out = await Promise.all(names.filter(n => ID.test(n.replace(/\.json$/, "")) && n.endsWith(".json")).map(async n => {
    try { return JSON.parse(await fs.readFile(path.join(dir(), n), "utf8")) as Lead; } catch { return null; }
  }));
  return (out.filter(Boolean) as Lead[]).sort((a, b) => b.createdAt.localeCompare(a.createdAt));
}

export async function countNewLeads() {
  return (await listLeads()).filter(l => !l.seen).length;
}

export async function markSeen(ids: string[]) {
  for (const id of ids) {
    if (!ID.test(id)) continue;
    const file = path.join(dir(), `${id}.json`);
    try {
      const l = JSON.parse(await fs.readFile(file, "utf8")) as Lead;
      if (l.seen) continue;
      await fs.writeFile(`${file}.tmp`, JSON.stringify({ ...l, seen: true }, null, 1));
      await fs.rename(`${file}.tmp`, file);
    } catch { /* gone */ }
  }
}

// The link a reel's caption and end card point to. The contractor's own quote link wins;
// otherwise their Crewreel quote page. Tracked with ?r=<jobId> when it's ours.
export const PUBLIC_HOST = (process.env.CREWREEL_PUBLIC_HOST || "crewreel.app").replace(/^https?:\/\//, "").replace(/\/$/, "");
export function quoteLink(profileUrl: string, jobId?: string) {
  if (profileUrl) return profileUrl;
  return `${PUBLIC_HOST}/q${jobId ? `?r=${jobId}` : ""}`;
}
