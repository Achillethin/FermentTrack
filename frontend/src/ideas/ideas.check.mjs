// Self-check for ideas.js (no test runner in this frontend): node src/ideas/ideas.check.mjs
import assert from "node:assert/strict";
import {
  aromaTempText,
  AROMAS,
  basisText,
  errorText,
  fmtGrams,
  levelPhrase,
  LOW_RESOLUTION,
  plannerHref,
  scheduleText,
  TASTES,
  targetBody,
  tierText,
  toggleTarget,
  windowRows,
  withForecast,
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
assert.deepEqual(phrases, ["likely noticeable", "may be noticeable", "unlikely to be noticeable"]);
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

console.log("ideas.js ok");
