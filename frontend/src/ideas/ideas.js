// The Ideas page's pure logic: targets, card text and the live-forecast merge.
// No React, no import.meta: `node src/ideas/ideas.check.mjs` runs it.
import { duration, parseApiDate } from "../prediction/format.js";
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
// numbers are dropped: scores stay Low / Med / High, and a calibrated card's numbers
// (p_peak) belong to the card as served, so they go too, with calibrated_on and the
// "calibrated on n batches" label (levels never sit next to a "calibrated" tag). Q27: the
// slider moves the first stage of a staged recipe only. A screened card's live forecast
// confirms it (design § 8.5).
export function withForecast(card, fc) {
  const served = fc.temperature.served_c;
  const [first, ...later] = card.recipe.temp_schedule;
  const merged = {
    ...withoutCalibration(card),
    recipe: {
      ...card.recipe,
      temperature_c: served,
      temp_schedule: first ? [[first[0], served], ...later] : [],
    },
    temperature: fc.temperature,
    window: fc.window,
    level: fc.level,
    targets: fc.targets.map(({ e_peak: _e, u_peak: _u, p_peak: _pp, ...t }) => t),
    safety_lines: fc.safety_lines,
    notes: fc.notes,
  };
  return card.screened || card.confirmed ? confirmedBy(merged, fc) : merged;
}

// ── Experimental, Community and calibration (B12) ───────────────────────

export const MODES = [
  { value: "proven", label: "Proven", hint: "curated, cited recipes kept inside their documented ranges" },
  {
    value: "experimental",
    label: "Experimental",
    hint: "up to 3 changes to a recipe, to one of your batches or to a community recipe; model-guided and untested",
  },
  { value: "both", label: "Both", hint: "Proven and Experimental ideas side by side" },
];
export const MAX_USDA = 5; // the API's limit
export const SCREENED = "screened";
export const AROMA_UNKNOWN = "aroma effect unknown";

const one = (x) => {
  const r = Math.round(x * 10) / 10;
  return Number.isInteger(r) ? String(r) : r.toFixed(1);
};

// A mass share of the whole batch (0.0078) as the chip shows it ("0.8 %").
export function shareText(share) {
  if (!Number.isFinite(share) || share <= 0) return null;
  return share * 100 < 0.1 ? "< 0.1 %" : `${one(share * 100)} %`;
}

// An Experimental card's operator chip (design § 11.1) as text: "+ Fresh ginger 0.8 %",
// "swap Napa cabbage → Cucumber", "24 → 27 °C", "+ USDA: Persimmons, raw — aroma effect unknown".
export function chipText(chip) {
  switch (chip.op) {
    case "add":
      return [`+ ${chip.ingredient}`, shareText(chip.share)].filter(Boolean).join(" ");
    case "swap":
      return `swap ${chip.replaces} → ${chip.ingredient}`;
    case "temperature":
      return chip.from_c != null ? `${one(chip.from_c)} → ${one(chip.to_c)} °C` : `→ ${one(chip.to_c)} °C`;
    case "usda": {
      const what =
        chip.fdc_id != null
          ? `+ USDA: ${chip.ingredient ?? `food ${chip.fdc_id}`}`
          : [`+ ${chip.ingredient}`, shareText(chip.share)].filter(Boolean).join(" ");
      return `${what} — ${chip.label || AROMA_UNKNOWN}`;
    }
    default:
      return chip.key ?? String(chip.op);
  }
}

// Temperature variants have no slider (slider null): the variant is the temperature change.
export const isTemperatureVariant = (card) => (card.operators ?? []).some((op) => op.op === "temperature");

// What the forecast and Start batch need to recompute a card on the server: a library recipe
// (recipe_key), a variant of it, of your batch (own-batch cards have recipe_key null: their
// parent's batch_id) or of a community recipe, or a community card itself. Chips go back as is.
export function cardSource(card) {
  if (card.section === "community" && card.community) return { community_recipe_id: card.community.id };
  const ops = card.operators?.length ? { operators: card.operators } : {};
  const p = card.parent;
  if (p?.kind === "own_batch") return { parent_batch_id: p.batch_id, ...ops };
  if (p?.kind === "community") return { community_recipe_id: p.community_recipe_id, ...ops };
  return { recipe_key: card.recipe_key, ...ops };
}

// A screened card after its live forecast: no longer screened; interaction_detected as the
// forecast says (null without targets).
export function confirmedBy(card, fc) {
  return {
    ...card,
    screened: false,
    confirmed: true,
    interaction_detected: fc.interaction_detected ?? null,
    trust: { ...card.trust, labels: card.trust.labels.filter((l) => l !== SCREENED) },
  };
}

// Numbers only once the calibration gate passed (design § 13.2): the API then adds calibrated_on
// and each modelled target's p_peak. Nothing else (a forecast's e_peak or u_peak) is ever shown.
export const calibratedOn = (card) =>
  Number.isInteger(card?.calibrated_on) && card.calibrated_on > 0 ? card.calibrated_on : null;

// service.CALIBRATED_LABEL ("calibrated on {n} batches"), the trust label calibrated cards carry.
export const CALIBRATED_LABEL = /^calibrated on \d+ batch(es)?$/;

// The card without its calibrated numbers: no p_peak, no calibrated_on, no "calibrated on n
// batches" label. trust is kept as is when it has no such label.
export function withoutCalibration(card) {
  const { p_peak: _p, calibrated_on: _n, ...rest } = card;
  const labels = card.trust?.labels ?? [];
  if (!labels.some((l) => CALIBRATED_LABEL.test(l))) return rest;
  return { ...rest, trust: { ...card.trust, labels: labels.filter((l) => !CALIBRATED_LABEL.test(l)) } };
}

export function pText(target, card) {
  if (calibratedOn(card) == null || !target.modelled) return null;
  const p = target.p_peak;
  return Number.isFinite(p) && p >= 0 && p <= 1 ? `${Math.round(p * 100)} %` : null;
}

export function calibratedText(card) {
  const n = calibratedOn(card);
  return n == null ? null : `calibrated on ${n} batch${n === 1 ? "" : "es"}`;
}

const NOTICE_AT_PEAK = "chance of being noticeable at the peak";

// A target's line on a card. Once calibrated (design § 13.2) the number replaces Low / Med / High:
// the level comes from E and the number from P, so showing both could contradict each other.
export function targetLine(target, card) {
  const number = pText(target, card);
  if (number) return { number, level: null, text: NOTICE_AT_PEAK };
  return { number: null, level: target.modelled ? target.level : null, text: levelPhrase(target) };
}

// The legend under a card's targets.
export function levelsLegend(card) {
  const scope = "A model estimate of compounds above their detection threshold, not of how it will taste to you.";
  const levels = "Low / Med / High: how likely each target is to be noticeable at the peak.";
  const numbered = (card.targets ?? []).filter((t) => pText(t, card) != null).length;
  if (!numbered) return `${levels} ${scope}`;
  const c = calibratedText(card);
  const numbers = `${c[0].toUpperCase()}${c.slice(1)}: numbers are the model's chance of being noticed at the peak.`;
  const rest = numbered < card.targets.length ? " Low / Med / High where there is no number." : "";
  return `${numbers}${rest} ${scope}`;
}

// The calibration gate's status line (GET /recommendations/calibration, design § 13.2), counts
// and decision only: no score is ever shown. report: the public report; null: none yet (404).
export const GATE_BATCHES = 30; // recommender.calibration.MIN_BATCHES
export const DISPLAY_FOR_MS = 14 * 24 * 3600 * 1000; // calibration.DISPLAY_FOR: a pass this old is off
const TOO_FEW = `fewer than ${GATE_BATCHES} tasted batches`; // calibration.TOO_FEW
export function calibrationText(report, now = Date.now()) {
  const levels = "scores show as Low / Med / High";
  if (!report) return `Not calibrated yet: ${levels}.`;
  const n = Number.isInteger(report.n_batches) ? report.n_batches : 0;
  const batches = `${n} tasted batch${n === 1 ? "" : "es"}`;
  if (report.passed) {
    const at = parseApiDate(report.computed_at)?.getTime();
    if (Number.isFinite(at) && now - at > DISPLAY_FOR_MS) return `Not calibrated: the last check (on ${batches}) is out of date; ${levels}.`;
    return `Calibrated on ${batches}: scores show as numbers.`;
  }
  const why = report.reason && report.reason !== TOO_FEW ? ` (${report.reason})` : "";
  if (n < GATE_BATCHES) return `Not calibrated yet: ${n} of ${GATE_BATCHES} tasted batches${why}; ${levels}.`;
  return `Not calibrated: ${batches}${why}; ${levels}.`;
}

export const madeText = (n) => `made ${Number.isFinite(n) ? n : 0}×`;
export const likingText = (x) => (Number.isFinite(x) ? `liked ${one(x)} / 5 on average` : null);

// Experimental cards grouped by their parent, in the order they come (ranked).
export function parentKey(card) {
  const p = card.parent;
  if (!p) return card.recipe_key ?? card.id;
  return p.recipe_key ?? p.batch_id ?? p.community_recipe_id ?? p.label;
}

export function groupByParent(cards) {
  const groups = new Map();
  for (const c of cards) {
    const key = parentKey(c);
    if (!groups.has(key)) groups.set(key, { key, label: c.parent?.label ?? c.name, cards: [] });
    groups.get(key).cards.push(c);
  }
  return [...groups.values()];
}

// Search deeper's confirmed cards over the Experimental section of the same search: one with the
// id of a screened card replaces it in place; one already shown (not screened) is not repeated;
// the others are grouped by parent.
export function mergeDeep(sectionCards, results) {
  const byId = new Map(results.map((c) => [c.id, c]));
  const shown = new Set(sectionCards.map((c) => c.id));
  return {
    cards: sectionCards.map((c) => (c.screened && byId.has(c.id) ? byId.get(c.id) : c)),
    groups: groupByParent(results.filter((c) => !shown.has(c.id))),
  };
}

const sorted = (xs) => [...(xs ?? [])].map(String).sort();
const searchKey = (q) =>
  JSON.stringify([
    sorted(q.ingredients),
    sorted(q.aromas),
    sorted(q.tastes),
    q.temperature_c ?? null,
    q.batch_g ?? 1000,
    sorted(q.usda_fdc_ids),
    q.parent_batch_id ?? null, // a deep search has no parent: results with one are never its own
    q.community_recipe_id ?? null,
  ]);

// Two requests that search deeper the same way (the mode does not change a deep search).
export const sameSearch = (a, b) => Boolean(a && b) && searchKey(a) === searchKey(b);

// "Cabbage, Fresh ginger · aiming for sour, fruity · at 21 °C": a deep search's request.
export function searchSummary(q) {
  if (!q) return "";
  const aims = [...(q.aromas ?? []), ...(q.tastes ?? [])];
  return [
    (q.ingredients ?? []).join(", "),
    aims.length ? `aiming for ${aims.join(", ")}` : "",
    q.usda_fdc_ids?.length ? `${q.usda_fdc_ids.length} USDA food${q.usda_fdc_ids.length === 1 ? "" : "s"}` : "",
    q.temperature_c != null ? `at ${formatC(q.temperature_c)}` : "",
  ]
    .filter(Boolean)
    .join(" · ");
}

// Your finished batches (GET /batches) that can be an Experimental parent (Q16): not sourdough
// (the planner varies those), newest first.
export function finishedParents(batches) {
  const at = (iso) => parseApiDate(iso)?.getTime() ?? 0;
  return batches
    .filter((b) => b.outcome !== "in_progress" && b.ended_at && b.culture_type !== "sourdough")
    .sort((x, y) => at(y.ended_at) - at(x.ended_at) || (x.id < y.id ? -1 : 1));
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
