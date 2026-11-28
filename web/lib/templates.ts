// Reel templates the contractor can pick, with the shots each one needs.
// Slot names match the footage names the renderer expects (render/render.py).

export type Slot = {
  name: string;
  label: string;
  hint: string;          // what to film, in crew language
  kind: "video" | "photo-or-video";
  optional?: boolean;
  min?: number;          // seconds of video this slot needs (shorter clips play in slow motion)
};

export type Field = { name: string; label: string; placeholder: string; max: number; hint?: string };

export type Template = {
  id: "driveway" | "house-wash" | "roof" | "windows" | "deck";
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
      { name: "before", min: 3, label: "Before", kind: "photo-or-video",
        hint: "Stand at the end of the drive, phone upright, chest height. Hold still for 5 seconds." },
      { name: "action1", min: 5, label: "Cleaning", kind: "video",
        hint: "Film the surface cleaner or wand mid-pass for 5–8 seconds. Get the clean line in shot." },
      { name: "after", min: 3, label: "After", kind: "photo-or-video",
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
      { name: "before", min: 2.5, label: "Before", kind: "photo-or-video",
        hint: "Whole wall in frame, phone upright. Hold still for 5 seconds." },
      { name: "action1", min: 2.2, label: "Step 1", kind: "video", hint: "Applying the soft wash, 3–5 seconds." },
      { name: "action2", min: 2.2, label: "Step 2", kind: "video", hint: "Rinsing, 3–5 seconds." },
      { name: "action3", min: 2.2, label: "Step 3", kind: "video", hint: "Detail work: windows, trim or gutters, 3–5 seconds." },
      { name: "after", min: 3.5, label: "After", kind: "photo-or-video",
        hint: "Same spot as the before shot. Hold still for 5 seconds." },
    ],
    fields: [
      { name: "hook", label: "Opening line", placeholder: "Green siding?\n*One* visit.", max: 40,
        hint: "Wrap one word in *stars* to colour it." },
      { name: "method", label: "How you cleaned it", placeholder: "Low-pressure soft wash. Safe on siding, tough on algae.", max: 70 },
      { name: "result", label: "Result line", placeholder: "Same day.\nNo damage.", max: 30 },
    ],
  },
  {
    id: "roof",
    title: "Roof soft wash",
    length: "18 s",
    blurb: "The streaked roof, the soft wash, then a ridge-to-gutter rinse reveal and a close-up.",
    slots: [
      { name: "before", min: 3, label: "Before", kind: "photo-or-video",
        hint: "From the street or a ladder, phone upright, ridge to gutter in frame. Hold still for 5 seconds." },
      { name: "action1", min: 2.7, label: "Applying", kind: "video", hint: "Spraying the soft wash on the roof, 3–5 seconds." },
      { name: "action2", min: 2.7, label: "Rinsing", kind: "video", hint: "Rinsing down the slope, 3–5 seconds." },
      { name: "after", min: 3.5, label: "After", kind: "photo-or-video",
        hint: "Same spot as the before shot, ideally once it has dried. Hold still for 5 seconds." },
    ],
    fields: [
      { name: "hook", label: "Opening line", placeholder: "Black streaks?\nThat's *algae.*", max: 40,
        hint: "Wrap one word in *stars* to colour it." },
      { name: "method", label: "How you cleaned it", placeholder: "Soft wash, not pressure. Kills the algae, spares the shingles.", max: 70 },
      { name: "result", label: "Result line", placeholder: "Ridge to gutter.\nStreak-free.", max: 32 },
    ],
  },
  {
    id: "windows",
    title: "Window cleaning",
    length: "16 s",
    blurb: "The spotted glass, scrub and squeegee, then a squeegee-pull reveal and a close-up.",
    slots: [
      { name: "before", min: 3, label: "Before", kind: "photo-or-video",
        hint: "Straight at the window, phone upright, whole pane in frame. Hold still for 5 seconds." },
      { name: "action1", min: 2.5, label: "Scrubbing", kind: "video", hint: "Scrubbing the glass with the applicator, 3–5 seconds." },
      { name: "action2", min: 2.5, label: "Squeegee", kind: "video", hint: "One clean squeegee pull across the glass, 3–5 seconds." },
      { name: "after", min: 3.5, label: "After", kind: "photo-or-video",
        hint: "Same spot as the before shot, once the glass is dry. Hold still for 5 seconds." },
    ],
    fields: [
      { name: "hook", label: "Opening line", placeholder: "Can't see out?\n*Now* you can.", max: 40,
        hint: "Wrap one word in *stars* to colour it." },
      { name: "method", label: "How you cleaned it", placeholder: "Pure water, scrub, squeegee. Frames and sills detailed.", max: 70 },
      { name: "result", label: "Result line", placeholder: "Crystal clear.\nInside and out.", max: 32 },
    ],
  },
  {
    id: "deck",
    title: "Deck cleaning",
    length: "16 s",
    blurb: "The grey deck, wash and brighten, then a board-by-board reveal and a close-up.",
    slots: [
      { name: "before", min: 3, label: "Before", kind: "photo-or-video",
        hint: "From the steps or a corner, phone upright, boards running across the frame. Hold still for 5 seconds." },
      { name: "action1", min: 2.5, label: "Washing", kind: "video", hint: "The wand or surface cleaner going along a board, 3–5 seconds." },
      { name: "action2", min: 2.5, label: "Brightening", kind: "video", hint: "Brightener going on, or the rinse showing the wood colour, 3–5 seconds." },
      { name: "after", min: 3.5, label: "After", kind: "photo-or-video",
        hint: "Same spot as the before shot, once the wood has dried a bit. Hold still for 5 seconds." },
    ],
    fields: [
      { name: "hook", label: "Opening line", placeholder: "Grey deck?\nIt's *not* old.", max: 40,
        hint: "Wrap one word in *stars* to colour it." },
      { name: "method", label: "How you cleaned it", placeholder: "Low-pressure wash, board by board, then a wood brightener.", max: 70 },
      { name: "result", label: "Result line", placeholder: "Back to\nthe real colour.", max: 32 },
    ],
  },
];

export const templateById = (id: string) => TEMPLATES.find(t => t.id === id);
