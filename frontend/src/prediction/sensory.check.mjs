// Self-check for sensory.js (no test runner in this frontend): node src/prediction/sensory.check.mjs
import assert from "node:assert/strict";
import { fmtValue, timesThreshold, unitSuffix } from "./format.js";
import {
  aromaBin, aromaChance, aromaImpression, aromaRows, aromaTimeline, cellText, concOnly, FAMILY_GLOSS,
  impressionText, smellWord, withSmell, changeText, indexAt, jarSummary, lensOf, mixHex,
  paletteSeries, paletteSources, phaseColor, phaseRuns, phaseSpans, stripColumns, topCompounds,
} from "./sensory.js";

const tp = {
  vocabulary: ["sweet", "balanced", "tart"],
  t_h: [0, 24, 48, 72],
  prob: { sweet: [1, 0.55, 0.1, 0], balanced: [0, 0.45, 0.7, 0.2], tart: [0, 0, 0.2, 0.8] },
};
const runs = phaseRuns(tp);
assert.deepEqual(runs.map((r) => r.name), ["sweet", "sweet", "balanced", "tart"]);
assert.equal(runs[1].k2, 1);
assert.deepEqual(
  phaseSpans(runs).map((s) => [s.name, s.start_h, s.end_h]),
  [["sweet", 0, 48], ["balanced", 48, 72], ["tart", 72, 72]],
);
assert.equal(indexAt([0, 24, 48], 30), 1);
assert.equal(indexAt([0, 24, 48], -5), 0);
assert.equal(phaseColor(0, 2), "#184f95");
assert.equal(phaseColor(1, 2), "#b7d3f6");
assert.equal(mixHex("#000000", "#ffffff", 0.5), "#808080");

assert.deepEqual(cellText({ p05: 3.1, p50: 4.12, p95: 5.0, lower_bound: false }, "g"), { value: "4.1", range: "3.1–5.0" });
assert.deepEqual(cellText({ p05: 30, p50: 31.4, p95: 33, lower_bound: true }, "kcal"), { value: "≥ 31", range: "30–33" });
assert.deepEqual(cellText(null, "g"), { value: "–", range: null });
assert.equal(changeText({ p50: 4.8 }, { p50: 2.4 }), "−50 %");
assert.equal(changeText({ p50: 0 }, { p50: 2.4 }), null);

assert.equal(timesThreshold(2.4), "×251");
assert.equal(timesThreshold(0.2), "×1.6");
assert.equal(timesThreshold(-1), "×0.10");
assert.equal(fmtValue(2.4, "× threshold", 3), "×251");
assert.equal(unitSuffix("× threshold"), "");

assert.equal(lensOf({}), "process");
const sensory = {
  now_h: 30, end_h: 72, taste_phases: tp,
  noticeable: { now: { sour: 0.9, sweet: 0.6, umami: 0.01, alcohol: 0.2 }, end: { sour: 1, sweet: 0.3 } },
  nutrition_label: [{ key: "sugars", now: { p50: 4.1 }, end: { p50: 1 } }],
};
const now = jarSummary(sensory, "now");
assert.equal(now.phase.name, "sweet");
assert.deepEqual(now.tastes, ["sour", "sweet"]);
assert.equal(now.sugars.p50, 4.1);
assert.equal(jarSummary(sensory, "end").phase.name, "tart");

// aroma palette and strip
assert.deepEqual([-0.5, 0.2, 1.5, 2.5, 4].map(aromaBin), [0, 1, 2, 3, 4]);
assert.equal(aromaChance(0.1), "unlikely");
assert.equal(aromaChance(0.9), "likely");
assert.deepEqual(aromaRows(undefined, []), []);
assert.deepEqual(paletteSeries(undefined, []), []);
assert.deepEqual(paletteSources(undefined), []);
const route = (kind, name, via) => ({ kind, name, via });
const aromaSensory = {
  aroma_series: [
    { key: "green", label: "Green", compounds: ["hexanal"], noticeable: [0.9, 0.2], peak_noticeable: 0.9, peak_t_h: 0 },
    { key: "fruity", label: "Fruity", compounds: ["ethyl_butanoate", "ethyl_lactate"], noticeable: [0, 0.95], peak_noticeable: 0.95, peak_t_h: 24 },
  ],
  compounds: [
    { key: "hexanal", name: "hexanal", descriptor: "green, grassy", series: ["green"], peak_noticeable: 0.9, routes: [route("ingredient", "Cabbage", "carried in")] },
    { key: "ethyl_butanoate", name: "ethyl butanoate", descriptor: "fruity, pineapple-like", series: ["fruity"], peak_noticeable: 0.95, routes: [route("organism", "Leuconostoc mesenteroides", "ester synthesis")] },
    { key: "ethyl_lactate", name: "ethyl lactate", descriptor: "fruity", series: ["fruity"], peak_noticeable: 0.1, routes: [route("chemistry", "acid + ethanol", "esterification"), route("ingredient", "Cabbage", "carried in")] },
  ],
};
const band = (key, label, p50) => ({ key, label, unit: "× threshold", group: "aroma", t_h: [0, 24], p05: p50, p50, p95: p50 });
const aromaBands = [
  band("aroma:green", "Green", [0.5, -0.5]), band("aroma:fruity", "Fruity", [-3, 1.4]),
  band("odor:ethyl_butanoate", "ethyl butanoate", [-3, 1.3]), band("odor:ethyl_lactate", "ethyl lactate", [-3, 0.2]),
];
const pal = paletteSeries(aromaSensory, aromaBands);
assert.deepEqual(pal.map((r) => r.key), ["fruity", "green"]);
assert.equal(pal[0].strength, 2);
assert.equal(pal[0].chance, "likely");
assert.deepEqual(pal[0].origins, ["Cabbage", "Leuconostoc mesenteroides", "chemistry"]);
const src = paletteSources(aromaSensory);
assert.deepEqual(src.map((g) => g.kind), ["ingredient", "organism", "chemistry"]);
assert.deepEqual(src[0].series.map((s) => s.key), ["green", "fruity"]);
assert.deepEqual(stripColumns(Array(161).fill(0), 41).slice(0, 2), [0, 4]);
assert.equal(stripColumns(Array(161).fill(0), 41).length, 41);
assert.equal(stripColumns(Array(161).fill(0), 41).at(-1), 160);
assert.deepEqual(topCompounds(aromaRows(aromaSensory, aromaBands)[0], aromaBands, 1), ["ethyl butanoate", "ethyl lactate"]);
// smell interpretation
assert.equal(smellWord({ descriptor: "green, grassy" }, "green"), "grassy");
assert.equal(smellWord({ descriptor: "fruity, pineapple-like" }, "fruity"), "pineapple-like");
assert.equal(smellWord({ descriptor: "fruity" }, "fruity"), null);
assert.equal(smellWord({ descriptor: "cabbage-like" }, "sulfurous"), "cabbage-like");
assert.equal(withSmell("dimethyl trisulfide", "cabbage-like"), "dimethyl trisulfide · cabbage-like");
assert.equal(withSmell("x", ""), "x");
assert.equal(Object.keys(FAMILY_GLOSS).length, 16);
const now0 = aromaImpression(aromaSensory, aromaBands, 0);
assert.deepEqual(now0.leads.map((f) => [f.key, f.word]), [["green", "grassy"]]);
assert.equal(impressionText(now0), "mostly green (grassy)");
const now1 = aromaImpression(aromaSensory, aromaBands, 1);
assert.deepEqual(now1.leads.map((f) => f.key), ["fruity"]);
assert.deepEqual(now1.extras.map((f) => f.key), ["green"]);
assert.equal(impressionText(now1), "mostly fruity (pineapple-like), with green (grassy) notes");
assert.equal(
  impressionText({ leads: [{ label: "Sulfurous", word: "cabbage-like" }, { label: "Green", word: "grassy" }],
    extras: [{ label: "Fruity", word: null }, { label: "Pungent", word: "mustard-like" }] }),
  "mostly sulfurous (cabbage-like) and green (grassy), with fruity and pungent (mustard-like) notes",
);
assert.equal(impressionText({ leads: [], extras: [{ label: "Fruity", word: null }] }), "faint fruity notes");
assert.equal(impressionText({ leads: [], extras: [] }), null);
assert.equal(aromaImpression(undefined, [], 0), null);
assert.deepEqual(
  aromaTimeline(aromaSensory, aromaBands).map((s) => [s.label, s.start_h, s.end_h]),
  [["green", 0, 24], ["fruity", 24, 24]],
);
assert.deepEqual(aromaTimeline(undefined, []), []);
// a family's word comes from its own compounds, never from another family's "-like"
assert.equal(smellWord({ descriptor: "solvent-like" }, "fruity"), null);
const withEster = {
  ...aromaSensory,
  compounds: [...aromaSensory.compounds,
    { key: "ethyl_acetate", name: "ethyl acetate", descriptor: "solvent-like", series: ["solvent", "fruity"], routes: [] }],
  aroma_series: aromaSensory.aroma_series.map((r) => (r.key === "fruity" ? { ...r, compounds: [...r.compounds, "ethyl_acetate"] } : r)),
};
const esterBands = [...aromaBands, band("odor:ethyl_acetate", "ethyl acetate", [-3, 2.5])];
assert.equal(aromaImpression(withEster, esterBands, 1).leads[0].word, "pineapple-like");
const sweaty = {
  ...aromaSensory,
  compounds: [...aromaSensory.compounds.filter((c) => c.key !== "ethyl_butanoate"),
    { key: "ethyl_butanoate", name: "ethyl butanoate", descriptor: "fruity", series: ["fruity"], routes: [] },
    { key: "methylbutanoic_2", name: "2-methylbutanoic acid", descriptor: "fruity, sweaty", series: ["cheesy", "fruity"], routes: [] }],
  aroma_series: aromaSensory.aroma_series.map((r) => (r.key === "fruity" ? { ...r, compounds: [...r.compounds, "methylbutanoic_2"] } : r)),
};
assert.equal(aromaImpression(sweaty, aromaBands, 1).leads[0].word, null); // not "sweaty" from a cheesy compound
// spans shorter than 2 % of the window merge into the next one
const flicker = {
  aroma_series: [
    { key: "green", label: "Green", compounds: [], noticeable: [0.9, 0.2, 0.2], peak_noticeable: 0.9, peak_t_h: 0 },
    { key: "fruity", label: "Fruity", compounds: [], noticeable: [0.1, 0.9, 0.9], peak_noticeable: 0.9, peak_t_h: 1 },
  ],
  compounds: [],
};
const flickerBands = [
  { key: "aroma:green", t_h: [0, 1, 100], p50: [0.5, -1, -1] }, { key: "aroma:fruity", t_h: [0, 1, 100], p50: [-1, 1, 1] },
];
assert.deepEqual(aromaTimeline(flicker, flickerBands).map((s) => [s.label, s.start_h, s.end_h]), [["fruity", 0, 100]]);
assert.deepEqual(concOnly(undefined), []);
assert.deepEqual(
  concOnly({ compounds: [{ key: "a", name: "allyl cyanide", threshold: null }, { key: "b", name: "hexanal", threshold: { p50: 2.4 } }] }),
  ["allyl cyanide"],
);
console.log("sensory.check: ok");
