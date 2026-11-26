import type { Job } from "./store";

export function statusText(j: Job) {
  if (j.status === "queued") return "Waiting to render";
  if (j.status === "rendering") return j.stage || "Rendering";
  if (j.status === "failed") return "Render failed";
  const n = Object.values(j.hints || {}).flat().length;
  return n ? `Ready · ${n} tip${n > 1 ? "s" : ""} for next time` : "Ready";
}
