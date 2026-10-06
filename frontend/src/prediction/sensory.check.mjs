// Self-check for sensory.js (no test runner in this frontend): node src/prediction/sensory.check.mjs
import assert from "node:assert/strict";
import { fmtValue, timesThreshold, unitSuffix } from "./format.js";
import {
  aromaBin, aromaChance, aromaRows, cellText, concOnly, changeText, indexAt, jarSummary, lensOf, mixHex,
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
    { key: "hexanal", name: "hexanal", series: ["green"], peak_noticeable: 0.9, routes: [route("ingredient", "Cabbage", "carried in")] },
    { key: "ethyl_butanoate", name: "ethyl butanoate", series: ["fruity"], peak_noticeable: 0.95, routes: [route("organism", "Leuconostoc mesenteroides", "ester synthesis")] },
    { key: "ethyl_lactate", name: "ethyl lactate", series: ["fruity"], peak_noticeable: 0.1, routes: [route("chemistry", "acid + ethanol", "esterification"), route("ingredient", "Cabbage", "carried in")] },
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
assert.deepEqual(concOnly(undefined), []);
assert.deepEqual(
  concOnly({ compounds: [{ key: "a", name: "allyl cyanide", threshold: null }, { key: "b", name: "hexanal", threshold: { p50: 2.4 } }] }),
  ["allyl cyanide"],
);
console.log("sensory.check: ok");
