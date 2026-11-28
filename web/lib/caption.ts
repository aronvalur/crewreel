// Post caption for the finished reel. Plain, local and specific beats hashtag soup.
import type { Job, Profile } from "./store";
import { templateById } from "./templates";
import { quoteLink } from "./leads";

const TAGS: Record<string, string[]> = {
  driveway: ["#pressurewashing", "#drivewaycleaning", "#beforeandafter"],
  "house-wash": ["#softwash", "#housewashing", "#beforeandafter"],
  roof: ["#roofcleaning", "#softwash", "#beforeandafter"],
  windows: ["#windowcleaning", "#cleanwindows", "#beforeandafter"],
  deck: ["#deckcleaning", "#deckrestoration", "#beforeandafter"],
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

// What the job was, in a customer's words (for texts to the customer and the Google post).
const JOB_NOUN: Record<string, string> = { driveway: "driveway", "house-wash": "house", roof: "roof", windows: "windows", deck: "deck" };
const JOB_PLURAL: Record<string, string> = { driveway: "driveways", "house-wash": "houses", roof: "roofs", windows: "windows", deck: "decks" };

// Google Business Profile "update" post: no hashtags (they do nothing there), the result first, one link.
export function gbpPost(job: Job, p: Profile) {
  const field = (name: string) =>
    flat(job.params[name] || templateById(job.template)?.fields.find(f => f.name === name)?.placeholder || "");
  const lines = [field("result") || field("hook"), field("method")].filter(Boolean);
  const where = p.area ? ` across ${p.area}` : "";
  return `${lines.join(" ")}\n\nWe clean ${JOB_PLURAL[job.template] || "homes"}${where}. ` +
    `${p.cta || "Get a free quote"}: ${quoteLink(p.url, job.id)}`;
}

// Text the crew sends the customer the same day, while they're happy. Only when there's a review link.
export function reviewText(job: Job, p: Profile) {
  if (!p.reviewUrl) return "";
  const what = JOB_NOUN[job.template] || "place";
  const plural = what.endsWith("s");
  return `Hi, thanks for having ${p.business || "us"} clean your ${what} today. If you're happy with how ${plural ? "they" : "it"} turned out, ` +
    `a quick Google review would help us a lot: ${p.reviewUrl}`;
}
