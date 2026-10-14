// Tastings (design § 11.2): the form's vocabulary, its payload and the list's text. Pure:
// `node src/tastings/tasting.check.mjs` runs it.
import { AROMAS, TASTES } from "../ideas/ideas.js";
import { duration, parseApiDate } from "../prediction/format.js";

export const TASTING_KEYS = [...AROMAS, ...TASTES]; // recommender.run.SERIES: 16 series + 4 tastes
export const RATINGS = [
  [0, "not noticed"],
  [1, "faint"],
  [2, "clear"],
  [3, "strong"],
];
export const LIKINGS = [
  [1, "not for me"],
  [2, "so-so"],
  [3, "fine"],
  [4, "good"],
  [5, "loved it"],
];
export const NOTES_MAX = 1000;
export const FUTURE_SKEW_MS = 10 * 60 * 1000; // routers/tastings.FUTURE_SKEW

// gate.ACID_SAFETY_TYPES, and the stop-by reminder's pH line for them: "Before tasting: " +
// gate.PH_DEADLINE_LINE (routers/recommendations.TASTING_AFTER_PH), verbatim.
export const ACID_SAFETY_TYPES = new Set(["lacto_ferment", "kombucha", "kefir", "cheese", "vinegar"]);
export const PH_BEFORE_TASTING = "Before tasting: Measure pH. It must reach ≤ 4.6 within 48 h at > 10 °C; if not, discard.";

// The pH line to keep next to the form: the tasting reminder's own (from "Before tasting:" on),
// else the same line for an acid-safety type; none for the others.
export function phLine(type, reminder) {
  const at = reminder?.action?.indexOf("Before tasting:") ?? -1;
  if (at >= 0) return reminder.action.slice(at);
  return ACID_SAFETY_TYPES.has(type) ? PH_BEFORE_TASTING : null;
}

const CONTROL = /[\x00-\x08\x0b\x0c\x0e-\x1f]/; // schemas.NoControlChars (tab and line breaks allowed)

// The form's state → POST /batches/{id}/tastings, or what to fix. ratings: {key: 0..3 | null};
// liking: 1..5 | null; makeAgain: true | false | null; tastedAt: a datetime-local value
// ("" = now). The API needs a rating or a liking.
export function tastingPayload({ ratings = {}, liking = null, makeAgain = null, notes = "", tastedAt = "" }, { startedAt = null, now = Date.now() } = {}) {
  const errors = [];
  const rated = {};
  for (const [key, value] of Object.entries(ratings)) {
    if (value == null) continue;
    if (!TASTING_KEYS.includes(key)) errors.push(`Unknown aroma or taste: ${key}.`);
    else if (!Number.isInteger(value) || value < 0 || value > 3) errors.push(`Rate ${key} from 0 to 3.`);
    else rated[key] = value;
  }
  const body = { ratings: Object.fromEntries(TASTING_KEYS.filter((k) => k in rated).map((k) => [k, rated[k]])) };
  if (liking != null) {
    if (Number.isInteger(liking) && liking >= 1 && liking <= 5) body.liking = liking;
    else errors.push("Liking goes from 1 to 5.");
  }
  if (makeAgain === true || makeAgain === false) body.make_again = makeAgain;
  const text = String(notes ?? "").trim();
  if ([...text].length > NOTES_MAX) errors.push(`Notes: at most ${NOTES_MAX} characters.`);
  else if (CONTROL.test(text)) errors.push("Notes: remove the control characters.");
  else if (text) body.notes = text;
  if (tastedAt) {
    const at = new Date(tastedAt); // a datetime-local value: local time
    const start = startedAt ? parseApiDate(startedAt) : null;
    if (Number.isNaN(at.getTime())) errors.push("When: not a date.");
    else if (at.getTime() > now + FUTURE_SKEW_MS) errors.push("When: that is in the future.");
    else if (start && at.getTime() < start.getTime()) errors.push("When: that is before the batch started.");
    else body.tasted_at = at.toISOString();
  }
  if (!Object.keys(body.ratings).length && body.liking == null) errors.push("Rate at least one aroma or taste, or say how much you liked it.");
  return errors.length ? { body: null, errors } : { body, errors };
}

const RATING_WORD = Object.fromEntries(RATINGS);

// "sour: strong · fruity: faint", in the series order.
export const ratingSummary = (ratings) =>
  TASTING_KEYS.filter((k) => ratings?.[k] != null)
    .map((k) => `${k}: ${RATING_WORD[ratings[k]] ?? ratings[k]}`)
    .join(" · ");

export const tastedWhen = (tH) => (tH < 1 ? "right at the start" : `after ${duration(tH)}`);
export const likingWord = (n) => (n == null ? null : `${n}/5 (${Object.fromEntries(LIKINGS)[n] ?? ""})`.replace(" ()", ""));

// Why to prompt for the tasting form: the batch's open tasting reminder (stop-by), or a finished
// batch not tasted yet; never on someone else's batch (an admin's read-only view).
export function promptReason({ readOnly, finished, tastingsCount, reminder }) {
  if (readOnly) return null;
  if (reminder) return "reminder";
  if (finished && tastingsCount === 0) return "finished";
  return null;
}

// A reminder is due once its time has come. GET /reminders also lists those due in the next 48 h:
// a stop-by tasting reminder must not prompt before the stop-by time (nor before the pH deadline).
export function isDue(reminder, now = Date.now()) {
  const at = parseApiDate(reminder?.due_at)?.getTime();
  return Number.isFinite(at) && at <= now;
}

// The batch's open tasting reminder, split: `due` prompts for the form; `upcoming` (not due yet)
// is only mentioned ("Tasting due …").
export function tastingReminder(reminders, batchId, now = Date.now()) {
  const open = (reminders ?? []).filter((r) => r.batch_id === batchId && r.kind === "tasting" && !r.completed_at);
  return { due: open.find((r) => isDue(r, now)) ?? null, upcoming: open.find((r) => !isDue(r, now)) ?? null };
}

// The targets a batch was recommended for (the batch preview's recommendation_targets: its
// recommendation link's keys; null when not started from a card): the ones the form rates first.
export const recommendedTargets = (keys) =>
  Array.isArray(keys) ? [...new Set(keys.filter((k) => TASTING_KEYS.includes(k)))].slice(0, 3) : [];
