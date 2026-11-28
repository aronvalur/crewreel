// Post caption for the finished reel. Plain, local and specific beats hashtag soup.
import type { Job, Profile } from "./store";
import { templateById } from "./templates";
import { quoteLink } from "./leads";

const TAGS: Record<string, string[]> = {
  driveway: ["#pressurewashing", "#drivewaycleaning", "#beforeandafter"],
  "house-wash": ["#softwash", "#housewashing", "#beforeandafter"],
  roof: ["#roofcleaning", "#softwash", "#beforeandafter"],
  windows: ["#windowcleaning", "#cleanwindows", "#beforeandafter"],
};

const flat = (s: string) => s.replace(/\*/g, "").replace(/\s*\n\s*/g, " ").trim();

export function caption(job: Job, p: Profile) {
  // blank fields fall back to the same suggestions the reel itself used
  const field = (name: string) =>
    flat(job.params[name] || templateById(job.template)?.fields.find(f => f.name === name)?.placeholder || "");
  // the link carries ?r=<reel> when it's the Crewreel quote page, so requests are credited to this reel
  const cta = `${p.cta || "Get a free quote"}: ${quoteLink(p.url, job.id)}`;
  const place = p.area ? p.area.split(/\s*(?:&|,|\band\b)\s*/)[0].trim() : "";
  return [
    field("hook"),
    field("method"),
    p.area ? `Serving ${p.area}. ${cta}` : cta,
    "",
    [...(TAGS[job.template] || ["#beforeandafter"]), place ? "#" + place.toLowerCase().replace(/\s+/g, "") : ""]
      .filter(Boolean).join(" "),
  ].join("\n");
}
