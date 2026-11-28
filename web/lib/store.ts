// File-based job store. One folder per job under $CREWREEL_DATA/jobs/<id>/:
//   job.json      the job record (status is advanced by worker/worker.py)
//   in/<slot>.*   uploaded footage
//   reel.mp4      finished reel, poster.jpg, footage.json (re-shoot hints)
// Deliberately boring so it runs anywhere with zero accounts; swap for Postgres + a bucket later.
import { promises as fs } from "fs";
import path from "path";
import crypto from "crypto";

export const DATA = path.resolve(process.env.CREWREEL_DATA || path.join(process.cwd(), "..", "data"));

export type JobStatus = "draft" | "queued" | "rendering" | "done" | "failed";
export type Hint = { code: string; message: string };

export type Job = {
  id: string;
  createdAt: string;
  template: string;
  title: string;
  status: JobStatus;
  stage?: string;                     // human progress line while rendering
  params: Record<string, string>;
  files: Record<string, string>;      // slot -> filename in in/
  error?: string;
  startedAt?: string;
  finishedAt?: string;
  hints?: Record<string, Hint[]>;     // slot -> re-shoot hints from ingest
};

export type Profile = {
  business: string;
  area: string;
  url: string;
  accent: string;
  cta: string;
  reviewUrl?: string;                 // their Google review link (g.page/r/... or search.google.com/local/writereview?...)
};

export const DEFAULT_PROFILE: Profile = {
  business: "", area: "", url: "", accent: "#7FD1FF", cta: "Get a free quote",
};

const jobsDir = () => path.join(DATA, "jobs");
export const jobDir = (id: string) => path.join(jobsDir(), safeId(id));

export function safeId(id: string) {
  if (!/^[a-z0-9-]{6,40}$/.test(id)) throw new Error("bad id");
  return id;
}

export function newId() {
  const d = new Date().toISOString().slice(0, 10).replace(/-/g, "");
  return `${d}-${crypto.randomBytes(4).toString("hex")}`;
}

async function writeJson(file: string, data: unknown) {
  const tmp = `${file}.${process.pid}.tmp`;
  await fs.writeFile(tmp, JSON.stringify(data, null, 1));
  await fs.rename(tmp, file);                 // atomic: the worker never reads half a file
}

export async function saveJob(job: Job) {
  await fs.mkdir(jobDir(job.id), { recursive: true });
  await writeJson(path.join(jobDir(job.id), "job.json"), job);
}

export async function getJob(id: string): Promise<Job | null> {
  try {
    return JSON.parse(await fs.readFile(path.join(jobDir(id), "job.json"), "utf8"));
  } catch {
    return null;
  }
}

export async function listJobs(): Promise<Job[]> {
  let ids: string[] = [];
  try { ids = await fs.readdir(jobsDir()); } catch { return []; }
  const jobs = await Promise.all(ids.filter(i => /^[a-z0-9-]{6,40}$/.test(i)).map(getJob));
  return (jobs.filter(j => j && j.status !== "draft") as Job[]).sort((a, b) => b.createdAt.localeCompare(a.createdAt));
}

export async function getProfile(): Promise<Profile> {
  try {
    return { ...DEFAULT_PROFILE, ...JSON.parse(await fs.readFile(path.join(DATA, "profile.json"), "utf8")) };
  } catch {
    return DEFAULT_PROFILE;
  }
}

export async function saveProfile(p: Profile) {
  await fs.mkdir(DATA, { recursive: true });
  await writeJson(path.join(DATA, "profile.json"), p);
}
