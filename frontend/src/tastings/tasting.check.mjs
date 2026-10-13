// Self-check for tasting.js: node src/tastings/tasting.check.mjs
import assert from "node:assert/strict";
import {
  isDue,
  likingWord,
  PH_BEFORE_TASTING,
  phLine,
  promptReason,
  ratingSummary,
  recommendedTargets,
  TASTING_KEYS,
  tastedWhen,
  tastingPayload,
  tastingReminder,
} from "./tasting.js";

// The 20 keys the API takes (16 aroma series + sour, sweet, umami, alcohol).
assert.equal(TASTING_KEYS.length, 20);
assert.deepEqual(TASTING_KEYS.slice(-4), ["sour", "sweet", "umami", "alcohol"]);
assert.equal(new Set(TASTING_KEYS).size, 20);

// The payload: unrated keys left out, series order, trimmed notes, integers only.
const now = Date.parse("2026-10-13T12:00:00Z");
const ok = tastingPayload(
  { ratings: { sour: 3, fruity: 1, umami: null }, liking: 4, makeAgain: false, notes: "  crisp \n", tastedAt: "" },
  { startedAt: "2026-10-10T08:00:00", now }
);
assert.deepEqual(ok, { body: { ratings: { fruity: 1, sour: 3 }, liking: 4, make_again: false, notes: "crisp" }, errors: [] });
assert.deepEqual(Object.keys(ok.body.ratings), ["fruity", "sour"]);
assert.deepEqual(tastingPayload({ liking: 5 }).body, { ratings: {}, liking: 5 }); // a liking alone is enough
assert.deepEqual(tastingPayload({ ratings: { sour: 0 } }).body, { ratings: { sour: 0 } }); // 0 = not noticed, a rating
assert.ok(!("make_again" in tastingPayload({ liking: 3, makeAgain: null }).body));
assert.ok(!("notes" in tastingPayload({ liking: 3, notes: "   " }).body));
// What the API would refuse is caught first.
assert.deepEqual(tastingPayload({}).errors, ["Rate at least one aroma or taste, or say how much you liked it."]);
assert.deepEqual(tastingPayload({ ratings: { sour: null } }).errors, ["Rate at least one aroma or taste, or say how much you liked it."]);
assert.match(tastingPayload({ ratings: { sour: 4 } }).errors[0], /0 to 3/);
assert.match(tastingPayload({ ratings: { sour: 1.5 } }).errors[0], /0 to 3/);
assert.match(tastingPayload({ ratings: { tangy: 1 } }).errors[0], /Unknown/);
assert.match(tastingPayload({ liking: 6 }).errors[0], /1 to 5/);
assert.match(tastingPayload({ liking: 3, notes: "x".repeat(1001) }).errors[0], /1000/);
assert.equal(tastingPayload({ liking: 3, notes: "x".repeat(1000) }).errors.length, 0);
assert.match(tastingPayload({ liking: 3, notes: "a\u0000b" }).errors[0], /control/);
assert.equal(tastingPayload({ liking: 3, notes: "tab\tand\nlines" }).body.notes, "tab\tand\nlines");
assert.equal(tastingPayload({}).body, null);
// tasted_at: a local datetime → UTC ISO; not before the start, not in the future.
const when = tastingPayload({ liking: 3, tastedAt: "2026-10-12T09:30" }, { startedAt: "2026-10-10T08:00:00Z", now });
assert.equal(when.body.tasted_at, new Date("2026-10-12T09:30").toISOString());
assert.match(tastingPayload({ liking: 3, tastedAt: "2026-10-01T09:30" }, { startedAt: "2026-10-10T08:00:00Z", now }).errors[0], /before the batch started/);
assert.match(tastingPayload({ liking: 3, tastedAt: "2026-10-20T09:30" }, { startedAt: "2026-10-10T08:00:00Z", now }).errors[0], /future/);
assert.match(tastingPayload({ liking: 3, tastedAt: "nonsense" }, { now }).errors[0], /not a date/);

// The pH line stays next to the form on acid-safety types: the reminder's own, else the same line.
const reminder = { action: `Stop-by time: taste the batch and fill in its tasting form. ${PH_BEFORE_TASTING}` };
assert.equal(phLine("lacto_ferment", reminder), PH_BEFORE_TASTING);
assert.equal(phLine("kombucha", null), PH_BEFORE_TASTING);
assert.equal(phLine("miso", null), null);
assert.equal(phLine("miso", { action: "Stop-by time: taste the batch and fill in its tasting form." }), null);
assert.equal(PH_BEFORE_TASTING, "Before tasting: Measure pH. It must reach ≤ 4.6 within 48 h at > 10 °C; if not, discard.");
assert.doesNotMatch(PH_BEFORE_TASTING, /\bsafe\b/i); // never a clearance

// Prompts: a tasting reminder, or a finished batch not tasted yet; never read-only.
assert.equal(promptReason({ readOnly: false, finished: false, tastingsCount: 0, reminder }), "reminder");
assert.equal(promptReason({ readOnly: false, finished: true, tastingsCount: 0, reminder: null }), "finished");
assert.equal(promptReason({ readOnly: false, finished: true, tastingsCount: 2, reminder: null }), null);
assert.equal(promptReason({ readOnly: false, finished: false, tastingsCount: 0, reminder: null }), null);
assert.equal(promptReason({ readOnly: true, finished: true, tastingsCount: 0, reminder }), null);

// GET /reminders lists reminders due in the next 48 h: only a due one prompts (never before stop-by).
const at = Date.parse("2026-10-13T12:00:00Z");
const rem = (id, due, extra = {}) => ({ id, batch_id: "b1", kind: "tasting", completed_at: null, due_at: due, ...extra });
assert.equal(isDue(rem("r", "2026-10-13T11:59:00"), at), true); // zone-less: UTC
assert.equal(isDue(rem("r", "2026-10-13T12:00:00Z"), at), true);
assert.equal(isDue(rem("r", "2026-10-13T18:00:00Z"), at), false); // due in 6 h: not yet
assert.equal(isDue(rem("r", "2026-10-14T13:00:00+02:00"), at), false);
assert.equal(isDue({ due_at: null }, at), false);
assert.equal(isDue(null, at), false);
const future = tastingReminder([rem("f", "2026-10-14T10:00:00Z")], "b1", at);
assert.equal(future.due, null);
assert.equal(future.upcoming.id, "f");
assert.equal(promptReason({ readOnly: false, finished: false, tastingsCount: 0, reminder: future.due }), null); // no prompt before due
const both = tastingReminder(
  [
    rem("other-batch", "2026-10-13T10:00:00Z", { batch_id: "b2" }),
    rem("stage", "2026-10-13T10:00:00Z", { kind: "stage" }),
    rem("closed", "2026-10-13T10:00:00Z", { completed_at: "2026-10-13T11:00:00Z" }),
    rem("due", "2026-10-13T10:00:00Z"),
  ],
  "b1",
  at
);
assert.equal(both.due.id, "due");
assert.equal(both.upcoming, null);
assert.deepEqual(tastingReminder(undefined, "b1", at), { due: null, upcoming: null });

// List text.
assert.equal(ratingSummary({ sour: 3, fruity: 1, umami: 0 }), "fruity: faint · sour: strong · umami: not noticed");
assert.equal(ratingSummary({}), "");
assert.equal(tastedWhen(0.2), "right at the start");
assert.equal(tastedWhen(36), "after 36 h");
assert.equal(tastedWhen(120), "after 5 days");
assert.equal(likingWord(5), "5/5 (loved it)");
assert.equal(likingWord(null), null);

// The batch's targets, from the preview's recommendation_targets (the API keeps them: nothing on
// this device): known keys only, once each, three at most; none when not started from a card.
assert.deepEqual(recommendedTargets(["sour", "fruity"]), ["sour", "fruity"]);
assert.deepEqual(recommendedTargets(["sour", "sour", "x", "umami", "sweet", "alcohol"]), ["sour", "umami", "sweet"]);
assert.deepEqual(recommendedTargets([]), []);
assert.deepEqual(recommendedTargets(null), []); // not started from a card
assert.deepEqual(recommendedTargets(undefined), []);
assert.deepEqual(recommendedTargets("sour"), []);

console.log("tasting.js ok");
