// The Ideas page's pure logic: targets, card text and the live-forecast merge.
// No React, no import.meta: `node src/ideas/ideas.check.mjs` runs it.
import { duration } from "../prediction/format.js";
import { FAMILY_GLOSS } from "../prediction/sensory.js";
import { formatC } from "../prediction/temperature.js";

export const MAX_TARGETS = 3;
export const MAX_INGREDIENTS = 20; // the API's limit
export const AROMAS = Object.keys(FAMILY_GLOSS); // the 16 aroma series
export const TASTES = ["sour", "sweet", "umami", "alcohol"];
// Q7: series summed from 2 compounds or fewer. On results, the API's own flag is used.
export const LOW_RESOLUTION = new Set(["phenolic", "vinegary", "fishy"]);
export { FAMILY_GLOSS };

// Add or remove one target; a fourth is refused (the list comes back unchanged).
export function toggleTarget(targets, key, kind) {
  if (targets.some((t) => t.key === key)) return targets.filter((t) => t.key !== key);
  return targets.length >= MAX_TARGETS ? targets : [...targets, { key, kind }];
}

export const targetBody = (targets) => ({
  aromas: targets.filter((t) => t.kind === "aroma").map((t) => t.key),
  tastes: targets.filter((t) => t.kind === "taste").map((t) => t.key),
});

// Flavour spec § 7 wording: "likely noticeable", never "tastes like". No numbers before
// the calibration gate (design § 13.2).
const LEVEL_PHRASE = { High: "likely noticeable", Med: "may be noticeable", Low: "unlikely to be noticeable" };
export const levelPhrase = (target) =>
  target.modelled && target.level ? LEVEL_PHRASE[target.level] : "not modelled for this ferment";

const TIER_TEXT = {
  calibrated: "calibrated evidence",
  reported: "reported in this ferment",
  plausible: "plausible, not reported",
  engine: "from the engine",
};
export const tierText = (tier) => TIER_TEXT[tier] ?? tier;

// A sourdough card times a levain build, not a ferment to taste.
const WINDOW_LABELS = { ferment: ["Taste from", "Peak", "Stop by"], levain: ["Ready from", "Peak", "Use by"] };

export function windowRows(w, levain = false) {
  if (!w) return [];
  const [from, peak, by] = WINDOW_LABELS[levain ? "levain" : "ferment"];
  return [
    { label: from, text: duration(w.taste_from_h) },
    { label: peak, text: duration(w.peak_h) },
    { label: by, text: duration(w.stop_by_h) },
  ];
}

// Aroma levels run at model_c: on a card the nearest precomputed grid temperature, in the live
// forecast the nearest in-range one (Q26). It can differ from the served temperature.
const differs = (t) => Math.abs(t.model_c - t.served_c) > 0.05;

// The line under the window, or null. A source window's own notes (the API's) name the
// documented temperatures, the range the model covers and model_c, so they speak for it.
export function basisText(w, t) {
  if (w.basis === "planner") {
    if (differs(t)) return `Levain peak computed at ${formatC(t.model_c)} (nearest precomputed temperature), from the planner's model`;
    return `Levain peak at ${formatC(t.served_c)}, from the planner's model`;
  }
  if (w.basis === "source") {
    if (w.notes.length) return null;
    return `Timings from the source recipe${differs(t) ? `; aroma levels computed at ${formatC(t.model_c)}` : ""}`;
  }
  // model_c differs here only on a card, never in the live forecast (which runs at the slider's)
  if (differs(t)) return `Model estimate computed at ${formatC(t.model_c)} (nearest precomputed temperature)`;
  return `Model estimate at ${formatC(t.served_c)}`;
}

export const aromaTempText = (t) => (differs(t) ? `Computed at ${formatC(t.model_c)}.` : null);

// [[0, 20], [48, 4]] -> "20 °C from the start, then 4 °C from 2 days"
export const scheduleText = (schedule) =>
  schedule.map(([h, c]) => `${formatC(c)} from ${h === 0 ? "the start" : duration(h)}`).join(", then ");

export function fmtGrams(g) {
  if (g >= 1000) return `${Math.round(g / 10) / 100} kg`;
  return `${Math.round(g * 10) / 10} g`;
}

// The planner's own share-link shape (sourdough/share.js shareUrl): origin + path + hash.
const PLANNER_LINK = /^#\/levain\?p=[A-Za-z0-9_-]+$/;
export const plannerHref = (link, loc) => (PLANNER_LINK.test(link || "") ? `${loc.origin}${loc.pathname}${link}` : null);

// A live forecast (POST /recommendations/forecast) over the card it updates. Its E/U
// numbers are dropped: scores stay Low / Med / High. Q27: the slider moves the first
// stage of a staged recipe only.
export function withForecast(card, fc) {
  const served = fc.temperature.served_c;
  const [first, ...later] = card.recipe.temp_schedule;
  return {
    ...card,
    recipe: {
      ...card.recipe,
      temperature_c: served,
      temp_schedule: first ? [[first[0], served], ...later] : [],
    },
    temperature: fc.temperature,
    window: fc.window,
    level: fc.level,
    targets: fc.targets.map(({ e_peak: _e, u_peak: _u, ...t }) => t),
    safety_lines: fc.safety_lines,
    notes: fc.notes,
  };
}

// FastAPI detail: a string, a {message} object (409 hand-off) or a list of {loc, msg} (422).
export function errorText(status, body) {
  const d = body?.detail;
  if (typeof d === "string") return d;
  if (d && typeof d.message === "string") return d.message;
  if (Array.isArray(d)) {
    return d
      .map((x) => {
        const where = (x.loc || []).slice(1).join(".");
        const msg = String(x.msg).replace(/^Value error, /, "");
        return where ? `${where}: ${msg}` : msg;
      })
      .join("; ");
  }
  return `The server answered ${status}`;
}
