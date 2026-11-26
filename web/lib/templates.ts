// Reel templates the contractor can pick, with the shots each one needs.
// Slot names match the footage names the renderer expects (render/render.py).

export type Slot = {
  name: string;
  label: string;
  hint: string;          // what to film, in crew language
  kind: "video" | "photo-or-video";
  optional?: boolean;
};

export type Field = { name: string; label: string; placeholder: string; max: number; hint?: string };

export type Template = {
  id: "driveway" | "house-wash";
  title: string;
  length: string;
  blurb: string;
  slots: Slot[];
  fields: Field[];
};

export const TEMPLATES: Template[] = [
  {
    id: "driveway",
    title: "Driveway before / after",
    length: "15 s",
    blurb: "Hook over the dirty drive, the surface cleaner at work, then a split-screen reveal.",
    slots: [
      { name: "before", label: "Before", kind: "photo-or-video",
        hint: "Stand at the end of the drive, phone upright, chest height. Hold still for 5 seconds." },
      { name: "action1", label: "Cleaning", kind: "video",
        hint: "Film the surface cleaner or wand mid-pass for 5–8 seconds. Get the clean line in shot." },
      { name: "after", label: "After", kind: "photo-or-video",
        hint: "Same spot as the before shot. Line it up, hold still for 5 seconds." },
    ],
    fields: [
      { name: "hook", label: "Opening line", placeholder: "8 years of grime.\n*Gone* in one morning.", max: 60,
        hint: "Wrap one word in *stars* to colour it." },
      { name: "method", label: "How you cleaned it", placeholder: "Surface clean + soft rinse. No harsh chemicals.", max: 70 },
    ],
  },
  {
    id: "house-wash",
    title: "House wash transformation",
    length: "20 s",
    blurb: "Three numbered steps, a light-sweep reveal and two close-up details.",
    slots: [
      { name: "before", label: "Before", kind: "photo-or-video",
        hint: "Whole wall in frame, phone upright. Hold still for 5 seconds." },
      { name: "action1", label: "Step 1", kind: "video", hint: "Applying the soft wash, 3–5 seconds." },
      { name: "action2", label: "Step 2", kind: "video", hint: "Rinsing, 3–5 seconds." },
      { name: "action3", label: "Step 3", kind: "video", hint: "Detail work: windows, trim or gutters, 3–5 seconds." },
      { name: "after", label: "After", kind: "photo-or-video",
        hint: "Same spot as the before shot. Hold still for 5 seconds." },
    ],
    fields: [
      { name: "hook", label: "Opening line", placeholder: "Green siding?\n*One* visit.", max: 40,
        hint: "Wrap one word in *stars* to colour it." },
      { name: "method", label: "How you cleaned it", placeholder: "Low-pressure soft wash. Safe on siding, tough on algae.", max: 70 },
      { name: "result", label: "Result line", placeholder: "Same day.\nNo damage.", max: 30 },
    ],
  },
];

export const templateById = (id: string) => TEMPLATES.find(t => t.id === id);
