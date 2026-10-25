// Self-check for ideas.js (no test runner in this frontend): node src/ideas/ideas.check.mjs
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  aromaShareText,
  aromaTempText,
  AROMAS,
  basisText,
  CALIBRATED_LABEL,
  calibratedOn,
  calibratedText,
  calibrationText,
  cardSource,
  chipText,
  errorText,
  finishedParents,
  fmtGrams,
  groupByParent,
  isTemperatureVariant,
  levelPhrase,
  levelsLegend,
  likingText,
  LOW_RESOLUTION,
  madeText,
  mergeDeep,
  MODES,
  plannerHref,
  pText,
  sameSearch,
  scheduleText,
  searchSummary,
  shareText,
  TASTES,
  targetBody,
  targetLine,
  tierText,
  toggleTarget,
  windowRows,
  withForecast,
  withoutCalibration,
} from "./ideas.js";

// The vocabulary: 16 aroma series + 4 tastes; low resolution only on known aroma series.
assert.equal(AROMAS.length, 16);
assert.deepEqual(TASTES, ["sour", "sweet", "umami", "alcohol"]);
for (const k of LOW_RESOLUTION) assert.ok(AROMAS.includes(k), k);
assert.deepEqual([...LOW_RESOLUTION].sort(), ["fishy", "phenolic", "vinegary"]);

// At most 3 targets: a fourth is refused, removing one frees a slot; order is kept.
let t = [];
for (const [k, kind] of [["fruity", "aroma"], ["sour", "taste"], ["vinegary", "aroma"], ["umami", "taste"]]) t = toggleTarget(t, k, kind);
assert.deepEqual(t.map((x) => x.key), ["fruity", "sour", "vinegary"]);
t = toggleTarget(t, "sour", "taste");
assert.deepEqual(t.map((x) => x.key), ["fruity", "vinegary"]);
assert.deepEqual(targetBody(toggleTarget(t, "umami", "taste")), { aromas: ["fruity", "vinegary"], tastes: ["umami"] });

// Wording (flavour spec § 7): never a number, never "tastes like".
const phrases = ["High", "Med", "Low"].map((level) => levelPhrase({ level, modelled: true }));
assert.deepEqual(phrases, ["likely to stand out", "may stand out", "unlikely to stand out"]);
assert.equal(levelPhrase({ level: null, modelled: false }), "not modelled for this ferment");
for (const p of phrases) assert.doesNotMatch(p, /\d|tastes? like|smells? like/);
assert.equal(tierText("reported"), "reported in this ferment");
assert.equal(tierText("new_tier"), "new_tier");

// Window in hours below 2 days, days above; the basis says where it comes from.
assert.deepEqual(windowRows({ taste_from_h: 24, peak_h: 60, stop_by_h: 588 }).map((r) => r.text), ["24 h", "2.5 days", "25 days"]);
assert.deepEqual(windowRows({ taste_from_h: 9, peak_h: 12, stop_by_h: 15 }).map((r) => r.label), ["Taste from", "Peak", "Stop by"]);
assert.deepEqual(windowRows({ taste_from_h: 9, peak_h: 12, stop_by_h: 15 }, true).map((r) => r.label), ["Ready from", "Peak", "Use by"]);
assert.deepEqual(windowRows(null), []);
const at21 = { served_c: 21, model_c: 21 };
assert.equal(basisText({ basis: "model", notes: [] }, at21), "Model estimate at 21 °C");
assert.match(basisText({ basis: "planner", notes: [] }, { served_c: 26.5, model_c: 26.5 }), /planner/);
assert.equal(aromaTempText(at21), null);

// Q26 source-only card: served 30 °C (the source's), model_c 28 °C. The API's window note
// speaks for the basis; the fallback never says the model "does not cover" anything.
const kombucha = { served_c: 30, model_c: 28 };
const apiNote = "timings from the source at 27–33 °C (the model covers 20–28 °C); aroma levels are computed at 28 °C";
assert.equal(basisText({ basis: "source", notes: [apiNote] }, kombucha), null);
const fallback = basisText({ basis: "source", notes: [] }, kombucha);
assert.equal(fallback, "Timings from the source recipe; aroma levels computed at 28 °C");
assert.equal(basisText({ basis: "source", notes: [] }, at21), "Timings from the source recipe");
for (const s of [fallback, basisText({ basis: "source", notes: [] }, at21)]) assert.doesNotMatch(s, /does not cover/);
assert.equal(aromaTempText(kombucha), "Computed at 28 °C.");
assert.equal(aromaTempText({ served_c: 21.1, model_c: 21.1000001 }), null); // API rounding, not a difference

// A card's grid statistics: sauerkraut served 23.9 °C, computed at the 22.5 °C grid temperature.
const kraut = { served_c: 23.9, model_c: 22.5 };
assert.equal(basisText({ basis: "model", notes: [] }, kraut), "Model estimate computed at 22.5 °C (nearest precomputed temperature)");
assert.equal(aromaTempText(kraut), "Computed at 22.5 °C.");
for (const s of [basisText({ basis: "model", notes: [] }, kraut), aromaTempText(kraut), aromaTempText(kombucha)]) {
  assert.doesNotMatch(s, /23\.9|model covers/);
}

// A sourdough card: served 22 °C, levain timings from the 24 °C grid temperature.
const levain = { served_c: 22, model_c: 24 };
const levainLine = basisText({ basis: "planner", notes: ["levain peak from the planner's model (P10 to P90)"] }, levain);
assert.equal(levainLine, "Levain peak computed at 24 °C (nearest precomputed temperature), from the planner's model");
assert.doesNotMatch(levainLine, /22 °C/);

assert.equal(scheduleText([[0, 20], [48, 4]]), "20 °C from the start, then 4 °C from 2 days");
assert.equal(fmtGrams(17.25), "17.3 g");
assert.equal(fmtGrams(1500), "1.5 kg");

// Planner hand-off: the planner's share-link shape on this deployment, nothing else.
const loc = { origin: "https://x.github.io", pathname: "/FermentTrack/", search: "?batch=1" };
assert.equal(plannerHref("#/levain?p=eyJ2IjoxfQ", loc), "https://x.github.io/FermentTrack/#/levain?p=eyJ2IjoxfQ");
for (const bad of [null, "", "#/levain", "javascript:alert(1)", "https://evil/#/levain?p=a", "#/levain?p=a&x=<b>"]) {
  assert.equal(plannerHref(bad, loc), null, bad);
}

// A live forecast replaces the card's window, levels, safety and notes; numbers are dropped.
const card = {
  recipe_key: "napa_kimchi_room_temp",
  recipe: { batch_g: 1000, temperature_c: 20, temp_schedule: [[0, 20], [48, 4]], ingredients: [] },
  temperature: { served_c: 20, slider: { min_c: 16, max_c: 24 } },
  window: { taste_from_h: 24, peak_h: 30, stop_by_h: 36, basis: "model", notes: [] },
  level: "Low",
  targets: [{ key: "sour", kind: "taste", level: "Low", modelled: true, low_resolution: false, top_compound: null }],
  safety_lines: ["old"],
  notes: [],
  trust: { labels: ["Model-guided idea"] },
};
const fc = {
  temperature: { served_c: 23, slider: { min_c: 16, max_c: 24 } },
  window: { taste_from_h: 20, peak_h: 26, stop_by_h: 34, basis: "model", notes: ["n"] },
  level: "High",
  e_peak: 0.81,
  u_peak: 0.9,
  targets: [{ key: "sour", kind: "taste", level: "High", modelled: true, low_resolution: false, top_compound: null, e_peak: 0.81, u_peak: 0.9 }],
  safety_lines: ["Measure pH."],
  notes: ["live"],
};
const merged = withForecast(card, fc);
assert.equal(merged.level, "High");
assert.equal(merged.window.peak_h, 26);
assert.deepEqual(merged.safety_lines, ["Measure pH."]);
assert.deepEqual(merged.recipe.temp_schedule, [[0, 23], [48, 4]]); // Q27: first stage only
assert.equal(merged.recipe.temperature_c, 23);
assert.equal(merged.trust, card.trust);
assert.ok(!("e_peak" in merged) && !("u_peak" in merged));
assert.ok(merged.targets.every((x) => !("e_peak" in x) && !("u_peak" in x)));
assert.ok(!JSON.stringify(merged).includes("0.81"));
assert.deepEqual(withForecast({ ...card, recipe: { ...card.recipe, temp_schedule: [] } }, fc).recipe.temp_schedule, []);

// FastAPI errors: string, the 409 hand-off object, and 422 lists.
assert.equal(errorText(404, { detail: "Recipe not found" }), "Recipe not found");
assert.equal(
  errorText(409, { detail: { message: "Sourdough starts in the levain planner.", handoff: "planner", planner_link: "#/levain?p=a" } }),
  "Sourdough starts in the levain planner."
);
assert.equal(
  errorText(422, { detail: [{ loc: ["body", "aromas"], msg: "Value error, at most 3 target aromas and tastes in total" }] }),
  "aromas: at most 3 target aromas and tastes in total"
);
assert.equal(errorText(500, {}), "The server answered 500");

// ── B12: Experimental, Community, calibration ──
assert.deepEqual(MODES.map((m) => m.value), ["proven", "experimental", "both"]);

// Operator chips (design § 11.1).
const chip = (x) => ({ key: "k", ingredient: null, replaces: null, share: null, from_c: null, to_c: null, fdc_id: null, label: null, ...x });
assert.equal(chipText(chip({ op: "add", ingredient: "Fresh ginger", share: 0.0078 })), "+ Fresh ginger 0.8 %");
assert.equal(chipText(chip({ op: "add", ingredient: "Fresh ginger", share: 0.02 })), "+ Fresh ginger 2 %");
assert.equal(chipText(chip({ op: "add", ingredient: "Chili flakes", share: 0.0004 })), "+ Chili flakes < 0.1 %");
assert.equal(chipText(chip({ op: "add", ingredient: "Garlic" })), "+ Garlic");
assert.equal(chipText(chip({ op: "swap", ingredient: "Cucumber", replaces: "Cabbage" })), "swap Cabbage → Cucumber");
assert.equal(chipText(chip({ op: "temperature", from_c: 24, to_c: 27 })), "24 → 27 °C");
assert.equal(chipText(chip({ op: "temperature", from_c: 20.25, to_c: 22.5 })), "20.3 → 22.5 °C");
assert.equal(chipText(chip({ op: "temperature", to_c: 18 })), "→ 18 °C");
assert.equal(
  chipText(chip({ op: "usda", ingredient: "Persimmons, japanese, raw", share: 0.05, fdc_id: 169941, label: "aroma effect unknown" })),
  "+ USDA: Persimmons, japanese, raw — aroma effect unknown"
);
assert.equal(chipText(chip({ op: "usda", fdc_id: 1 })), "+ USDA: food 1 — aroma effect unknown");
assert.equal(chipText(chip({ op: "usda", ingredient: "Carrot", share: 0.05 })), "+ Carrot 5 % — aroma effect unknown");
assert.equal(shareText(null), null);
assert.equal(shareText(0), null);

// Where a card comes from, for its forecast and Start batch.
const lib = { section: "proven", recipe_key: "sauerkraut", operators: [], parent: null };
const ops = [chip({ op: "add", ingredient: "Fresh ginger", share: 0.0078 })];
assert.deepEqual(cardSource(lib), { recipe_key: "sauerkraut" });
assert.deepEqual(
  cardSource({ section: "experimental", recipe_key: "sauerkraut", operators: ops, parent: { kind: "library", recipe_key: "sauerkraut", batch_id: null } }),
  { recipe_key: "sauerkraut", operators: ops }
);
assert.deepEqual(
  cardSource({ section: "experimental", recipe_key: null, operators: ops, parent: { kind: "own_batch", recipe_key: null, batch_id: "b-1" } }),
  { parent_batch_id: "b-1", operators: ops }
);
assert.deepEqual(
  cardSource({ section: "experimental", recipe_key: null, operators: ops, parent: { kind: "community", recipe_key: null, batch_id: null, community_recipe_id: "c-1" } }),
  { community_recipe_id: "c-1", operators: ops }
);
assert.deepEqual(cardSource({ section: "community", recipe_key: null, operators: [], parent: null, community: { id: "c-2" } }), { community_recipe_id: "c-2" });
assert.ok(isTemperatureVariant({ operators: [chip({ op: "temperature", to_c: 27 })] }));
assert.ok(!isTemperatureVariant({ operators: ops }));
assert.ok(!isTemperatureVariant({}));

// A screened card's live forecast confirms it: no "screened" left; interaction as the API says.
const screened = {
  ...card,
  section: "experimental",
  screened: true,
  interaction_detected: null,
  trust: { labels: ["Model-guided idea", "screened"] },
  p_peak: 0.7,
  calibrated_on: 31,
};
const confirmedCard = withForecast(screened, { ...fc, interaction_detected: true });
assert.equal(confirmedCard.screened, false);
assert.equal(confirmedCard.confirmed, true);
assert.equal(confirmedCard.interaction_detected, true);
assert.deepEqual(confirmedCard.trust.labels, ["Model-guided idea"]);
assert.ok(!("p_peak" in confirmedCard)); // the numbers belong to the card as served
assert.equal(withForecast(screened, { ...fc, interaction_detected: null }).interaction_detected, null);
// ...and a confirmed card stays confirmed through later slider forecasts.
assert.equal(withForecast(confirmedCard, { ...fc, interaction_detected: false }).confirmed, true);
assert.equal(withForecast(card, fc).confirmed, undefined); // a Proven card is never "confirmed"

// A slider move or a confirmation drops the calibrated numbers, and their trust label with them:
// levels never sit next to "calibrated on n batches".
const calibrated = {
  ...card,
  calibrated_on: 34,
  p_peak: 0.66,
  targets: [{ ...card.targets[0], p_peak: 0.66 }],
  trust: { labels: ["Model-guided idea", "calibrated on 34 batches"] },
};
const moved = withForecast(calibrated, fc);
assert.deepEqual(moved.trust.labels, ["Model-guided idea"]);
assert.ok(!("calibrated_on" in moved) && !("p_peak" in moved));
assert.ok(moved.targets.every((x) => !("p_peak" in x)));
assert.equal(calibratedText(moved), null);
assert.deepEqual(targetLine(moved.targets[0], moved), { number: null, level: "High", text: "likely to stand out" });
assert.doesNotMatch(levelsLegend(moved), /calibrated/i);
assert.deepEqual(calibrated.trust.labels, ["Model-guided idea", "calibrated on 34 batches"]); // as served: unchanged
const confirmedCalibrated = withForecast(
  { ...calibrated, section: "experimental", screened: true, trust: { labels: ["Model-guided idea", "screened", "calibrated on 34 batches"] } },
  { ...fc, interaction_detected: false }
);
assert.deepEqual(confirmedCalibrated.trust.labels, ["Model-guided idea"]);
assert.ok(!("calibrated_on" in confirmedCalibrated) && !("p_peak" in confirmedCalibrated));
assert.ok(CALIBRATED_LABEL.test("calibrated on 1 batch") && CALIBRATED_LABEL.test("calibrated on 34 batches"));
assert.ok(!CALIBRATED_LABEL.test("Calibrated on 34 tasted batches: scores show as numbers."));
assert.deepEqual(withoutCalibration({ trust: { labels: ["x"] }, calibrated_on: 3, p_peak: 0.5 }), { trust: { labels: ["x"] } });

// Start batch keeps nothing on this device: the batch preview gives the tasting form its targets.
const ideaCard = readFileSync(new URL("./IdeaCard.jsx", import.meta.url), "utf8");
assert.doesNotMatch(ideaCard, /localStorage|tasting-targets|rememberTargets/);

// Numbers only when calibrated (design § 13.2); a forecast's E/U never.
const tgt = { key: "sour", modelled: true, level: "High", p_peak: 0.72 };
assert.equal(pText(tgt, { calibrated_on: 34 }), "72 %");
assert.equal(pText(tgt, {}), null);
assert.equal(pText(tgt, { calibrated_on: null }), null);
assert.equal(pText(tgt, { calibrated_on: 0 }), null);
assert.equal(pText({ ...tgt, modelled: false }, { calibrated_on: 34 }), null);
assert.equal(pText({ ...tgt, p_peak: undefined }, { calibrated_on: 34 }), null);
assert.equal(pText({ ...tgt, p_peak: 1.4 }, { calibrated_on: 34 }), null);
assert.equal(pText({ key: "sour", modelled: true, e_peak: 0.8, u_peak: 0.9 }, { calibrated_on: 34 }), null);
assert.equal(calibratedOn({ calibrated_on: 34 }), 34);
assert.equal(calibratedOn({ calibrated_on: "34" }), null);
assert.equal(calibratedText({ calibrated_on: 34 }), "calibrated on 34 batches");
assert.equal(calibratedText({}), null);

// Once calibrated, the number replaces Low / Med / High (E gives the level, P the number: both
// could contradict, e.g. "High · 41 %").
const calCard = {
  calibrated_on: 34,
  targets: [
    { key: "fruity", modelled: true, level: "High", p_peak: 0.72 },
    { key: "sour", modelled: true, level: "High", p_peak: 0.41 },
  ],
};
const numbered = targetLine(calCard.targets[1], calCard);
assert.deepEqual(numbered, { number: "41 %", level: null, text: "chance of being noticeable at the peak" });
assert.doesNotMatch(`${numbered.number} ${numbered.text}`, /High|Med|Low|likely|tastes? like/);
assert.deepEqual(targetLine({ key: "sour", modelled: true, level: "High" }, {}), { number: null, level: "High", text: "likely to stand out" });
assert.deepEqual(targetLine({ key: "sour", modelled: true, level: "Low", p_peak: 0.41 }, {}), { number: null, level: "Low", text: "unlikely to stand out" }); // not calibrated: no number
assert.deepEqual(targetLine({ key: "umami", modelled: false, level: null }, calCard), { number: null, level: null, text: "not modelled for this ferment" });
assert.equal(
  levelsLegend(calCard),
  "Calibrated on 34 batches: numbers are the model's chance of being noticed at the peak. A model estimate of compounds above their detection threshold, not of how it will taste to you."
);
assert.doesNotMatch(levelsLegend(calCard), /Low \/ Med \/ High/);
const mixed = { ...calCard, targets: [...calCard.targets, { key: "umami", modelled: false, level: null }] };
assert.match(levelsLegend(mixed), /^Calibrated on 34 batches: numbers .* Low \/ Med \/ High where there is no number\. /);
assert.equal(
  levelsLegend({ targets: [{ key: "sour", modelled: true, level: "High" }] }),
  "Low / Med / High: how likely each target is to stand out at the peak. A model estimate of compounds above their detection threshold, not of how it will taste to you."
);

// The calibration gate's status line: counts and decision only, never a score (nulls never 0).
const nowMs = Date.parse("2026-10-13T12:00:00Z");
const report = (x) => ({
  computed_at: "2026-10-13T06:00:00+00:00",
  n_tastings: 4,
  n_observations: 9,
  n_batches: 3,
  brier_model: null,
  brier_baseline: null,
  diff: null,
  ci_low: null,
  ci_high: null,
  auc: null,
  auc_low: null,
  passed: false,
  reason: "fewer than 30 tasted batches",
  bins: [{ lo: 0, hi: 0.2, n: 2, mean_p: null, observed: null }],
  ...x,
});
assert.equal(calibrationText(null, nowMs), "Not calibrated yet: scores show as Low / Med / High."); // 404
assert.equal(calibrationText(report(), nowMs), "Not calibrated yet: 3 of 30 tasted batches; scores show as Low / Med / High.");
assert.equal(calibrationText(report({ n_batches: 1 }), nowMs), "Not calibrated yet: 1 of 30 tasted batches; scores show as Low / Med / High.");
assert.equal(calibrationText(report({ n_batches: 0, reason: null }), nowMs), "Not calibrated yet: 0 of 30 tasted batches; scores show as Low / Med / High.");
const notBetter = "the model does not beat the baseline (the 90 % CI's upper bound is not below 0)";
assert.equal(
  calibrationText(report({ n_batches: 34, reason: notBetter, brier_model: 0.21, diff: 0.01 }), nowMs),
  `Not calibrated: 34 tasted batches (${notBetter}); scores show as Low / Med / High.`
);
assert.equal(calibrationText(report({ n_batches: 34, passed: true, reason: null }), nowMs), "Calibrated on 34 tasted batches: scores show as numbers.");
assert.equal(
  calibrationText(report({ n_batches: 34, passed: true, reason: null, computed_at: "2026-09-20T06:00:00" }), nowMs),
  "Not calibrated: the last check (on 34 tasted batches) is out of date; scores show as Low / Med / High."
);
for (const r of [null, report(), report({ n_batches: 34, reason: notBetter, brier_model: 0.21, diff: 0.01, auc: 0.6 })]) {
  assert.doesNotMatch(calibrationText(r, nowMs), /0\.\d|\bNaN\b|undefined|null|Brier|AUC/);
}

// Community cards.
assert.equal(madeText(3), "made 3×");
assert.equal(madeText(0), "made 0×");
assert.equal(likingText(4.25), "liked 4.3 / 5 on average");
assert.equal(likingText(null), null);

// Search deeper: replace a screened card with the same id, never repeat one, group by parent.
const v = (id, parentKey, screenedFlag = false) => ({
  id,
  screened: screenedFlag,
  name: parentKey,
  recipe_key: parentKey,
  parent: { kind: "library", recipe_key: parentKey, batch_id: null, community_recipe_id: null, label: `Recipe ${parentKey}` },
});
const section = [v("a", "kraut", true), v("b", "kimchi"), v("c", "kraut")];
const results = [{ ...v("a", "kraut"), confirmed: true }, v("b", "kimchi"), v("d", "kimchi"), v("e", "kraut"), v("f", "kimchi")];
const merged2 = mergeDeep(section, results);
assert.deepEqual(merged2.cards.map((x) => [x.id, x.screened]), [["a", false], ["b", false], ["c", false]]);
assert.equal(merged2.cards[0], results[0]);
assert.deepEqual(merged2.groups.map((g) => [g.label, g.cards.map((x) => x.id)]), [["Recipe kimchi", ["d", "f"]], ["Recipe kraut", ["e"]]]);
assert.deepEqual(mergeDeep([], results).groups.map((g) => g.cards.length), [2, 3]); // kraut first: ranked order
const own = { id: "o", name: "Kraut, your batch #2", parent: { kind: "own_batch", recipe_key: null, batch_id: "b1", label: "your batch #2" } };
assert.deepEqual(groupByParent([own]).map((g) => [g.key, g.label]), [["b1", "your batch #2"]]);

// The same deep search (mode aside, order aside).
const q1 = { ingredients: ["Cabbage", "Carrot"], aromas: ["fruity"], tastes: ["sour"], mode: "proven", temperature_c: null, batch_g: 1000, usda_fdc_ids: [] };
assert.ok(sameSearch(q1, { ...q1, mode: "both", ingredients: ["Carrot", "Cabbage"] }));
assert.ok(sameSearch(q1, { ...q1, usda_fdc_ids: undefined }));
assert.ok(!sameSearch(q1, { ...q1, temperature_c: 21 }));
assert.ok(!sameSearch(q1, { ...q1, aromas: [] }));
assert.ok(!sameSearch(q1, null));
assert.ok(!sameSearch(q1, { ...q1, mode: "experimental", parent_batch_id: "b1" })); // results with a parent
assert.ok(!sameSearch(q1, { ...q1, mode: "experimental", community_recipe_id: "c1" }));
assert.equal(searchSummary({ ...q1, temperature_c: 21, usda_fdc_ids: [1] }), "Cabbage, Carrot · aiming for fruity, sour · 1 USDA food · at 21 °C");
assert.equal(searchSummary({ aromas: ["fruity"] }), "aiming for fruity");

// Your finished batches as parents: not sourdough, not running, newest first.
const batches = [
  { id: "1", outcome: "success", ended_at: "2026-10-01T10:00:00", culture_type: "lacto_ferment" },
  { id: "2", outcome: "in_progress", ended_at: null, culture_type: "lacto_ferment" },
  { id: "3", outcome: "success", ended_at: "2026-10-05T10:00:00Z", culture_type: "kombucha" },
  { id: "4", outcome: "success", ended_at: "2026-10-06T10:00:00Z", culture_type: "sourdough" },
  { id: "5", outcome: "failure", ended_at: "2026-09-01T10:00:00Z", culture_type: "miso" },
];
assert.deepEqual(finishedParents(batches).map((b) => b.id), ["3", "1", "5"]);

console.log("ideas.js ok");

// v2 § 3.1: the share of the aroma, in words only (no digits before calibration).
assert.equal(aromaShareText({ key: "sulfurous", modelled: true, share: "dominant" }), "dominates the aroma");
assert.equal(aromaShareText({ key: "sulfurous", modelled: true, share: "large" }), "a large part of the aroma");
assert.equal(aromaShareText({ key: "floral", modelled: true, share: "smaller" }), "a smaller part of the aroma");
assert.equal(aromaShareText({ key: "mushroom", modelled: true, share: "trace" }), "only a trace in the aroma");
assert.equal(aromaShareText({ key: "sour", modelled: true, share: null }), null); // a taste
assert.equal(aromaShareText({ key: "x", modelled: true, share: 0.3 }), null); // never a raw number
assert.equal(aromaShareText({ key: "fishy", modelled: false, share: null }), null);
assert.equal(aromaShareText({ key: "fishy", modelled: true, share: "large", noticeable: false }), null);
for (const x of ["trace", "smaller", "large", "dominant"]) assert.doesNotMatch(aromaShareText({ modelled: true, share: x }), /\d/);

// v2 § 3.3: a composed card sends back only its ingredients.
assert.deepEqual(
  cardSource({ section: "experimental", recipe_key: "composed:brine:Carrot+Garlic", operators: [],
    parent: { kind: "composed", composed: { bases: ["Carrot"], aromatics: ["Garlic"] } } }),
  { composed: { bases: ["Carrot"], aromatics: ["Garlic"] } }
);
