// Self-check for sensory.js (no test runner in this frontend): node src/prediction/sensory.check.mjs
import assert from "node:assert/strict";
import { fmtValue, timesThreshold, unitSuffix } from "./format.js";
import {
  cellText, changeText, indexAt, jarSummary, lensOf, mixHex, phaseColor, phaseRuns, phaseSpans,
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
console.log("sensory.check: ok");
