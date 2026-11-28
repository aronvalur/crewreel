import { redirect } from "next/navigation";
import { getProfile, saveProfile } from "@/lib/store";
import { quoteLink } from "@/lib/leads";

export const dynamic = "force-dynamic";

async function save(form: FormData) {
  "use server";
  const s = (k: string, max: number) => String(form.get(k) || "").trim().slice(0, max);
  const accent = s("accent", 7);
  await saveProfile({
    business: s("business", 40),
    area: s("area", 40),
    url: s("url", 60).replace(/^https?:\/\//, ""),
    accent: /^#[0-9a-fA-F]{6}$/.test(accent) ? accent : "#7FD1FF",
    cta: s("cta", 32) || "Get a free quote",
    reviewUrl: s("reviewUrl", 200).replace(/^(?!https?:\/\/)(?=.)/, "https://"),
  });
  redirect("/");
}

export default async function Settings() {
  const p = await getProfile();
  return (
    <form action={save} className="stack" style={{ maxWidth: 560 }}>
      <div>
        <h1>Your business</h1>
        <p className="muted" style={{ marginTop: 6 }}>This goes on the end card of every reel.</p>
      </div>
      <label className="field"><span>Business name</span>
        <input type="text" name="business" defaultValue={p.business} placeholder="Valur Exterior Cleaning" required maxLength={40} />
      </label>
      <label className="field"><span>Area you cover</span>
        <input type="text" name="area" defaultValue={p.area} placeholder="Reykjavík & Kópavogur" maxLength={40} />
      </label>
      <label className="field"><span>Quote link</span>
        <input type="text" name="url" defaultValue={p.url} placeholder="valurcleaning.com/quote" maxLength={60} />
        <small>Leave blank to use your Crewreel quote page ({quoteLink("")}): requests land under Quotes and show which reel sent them.</small>
      </label>
      <label className="field"><span>Call to action</span>
        <input type="text" name="cta" defaultValue={p.cta} maxLength={32} />
      </label>
      <label className="field"><span>Google review link</span>
        <input type="text" name="reviewUrl" defaultValue={p.reviewUrl} placeholder="g.page/r/..." maxLength={200} />
        <small>Optional. In Google Business Profile: Ask for reviews → copy link. We put it in a ready-made thank-you text for each job.</small>
      </label>
      <label className="field"><span>Brand colour</span>
        <input type="color" name="accent" defaultValue={p.accent} />
        <small>Used for the logo tile and one highlighted word.</small>
      </label>
      <div><button className="btn" type="submit">Save</button></div>
    </form>
  );
}
