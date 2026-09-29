// Self-check for plan.js (no test runner in this frontend): node src/sourdough/plan.check.mjs
import assert from "node:assert/strict";
import { closestRow, defaultForm, formToPlan, hoursUntil, planToForm, ratioLabel, scaleBuild } from "./plan.js";

const catalog = {
  styles: [
    { key: "levain_liquide", name: "Levain liquide", seed: "starter", defaults: { hydration_pct: 100, seed_ratio: 3, temperature_c: 26, flour: "t65", hours: null } },
    { key: "levain_dur", name: "Levain dur", seed: "starter", defaults: { hydration_pct: 55, seed_ratio: 3, temperature_c: 24, flour: "t65", hours: null } },
    { key: "poolish", name: "Poolish", seed: "yeast", defaults: { hydration_pct: 100, seed_ratio: 1000, temperature_c: 20, flour: "t55", hours: 12 } },
    { key: "type_iii", name: "Dried sourdough", seed: "dried", defaults: {} },
  ],
  flours: [{ key: "t65", name: "T65" }, { key: "t55", name: "T55" }, { key: "t150", name: "T150" }],
};

// Levain only: 1:3:3 from 20 g.
let f = defaultForm(catalog, "levain_liquide");
let { plan, errors } = formToPlan(f, catalog);
assert.deepEqual(errors, {});
assert.deepEqual(plan.levain, { seed_g: 20, flour_g: 60, water_g: 60, flour: { t65: 1 }, temperature_c: 26, hours: null });
assert.equal(plan.dough, null);

// Dough in baker's %: 500 g flour, 72 %, 2 % salt, 20 % levain at 100 % hydration.
f = { ...f, seedG: "30", doughOn: true, flour2: "t150", share2: "10", proof: "cold" };
({ plan, errors } = formToPlan(f, catalog));
assert.deepEqual(errors, {});
assert.deepEqual(plan.levain.flour, { t65: 0.9, t150: 0.1 });
assert.equal(plan.dough.levain_g, 100);
assert.equal(plan.dough.flour_g, 450); // 500 - 100 × 1/2
assert.equal(plan.dough.water_g, 310); // 360 - 100 × 1/2
assert.equal(plan.dough.salt_g, 10);
assert.deepEqual(plan.proof, { temperature_c: 4, hours: 14 });

// Round trip: plan -> form -> plan is stable.
assert.deepEqual(formToPlan(planToForm(plan, catalog), catalog).plan, plan);

// Stiff levain, custom grams, round trip keeps custom mode.
f = { ...defaultForm(catalog, "levain_dur"), custom: true, cSeed: "15", cFlour: "50", cWater: "27" };
({ plan } = formToPlan(f, catalog));
assert.equal(planToForm(plan, catalog).custom, true);
assert.deepEqual(formToPlan(planToForm(plan, catalog), catalog).plan, plan);

// Poolish: yeast seed from seed_ratio; dried: no levain, dough forced on.
({ plan } = formToPlan(defaultForm(catalog, "poolish"), catalog));
assert.equal(plan.levain.seed_g, 0.1);
assert.equal(plan.levain.hours, 12);
({ plan } = formToPlan(defaultForm(catalog, "type_iii"), catalog));
assert.equal(plan.levain, null);
assert.equal(plan.dough.flour_g, 500);
assert.equal(plan.dough.levain_g, null);

// Dough needing more levain than the build makes is an error; scaleBuild fixes it.
f = { ...defaultForm(catalog, "levain_liquide"), doughOn: true, levainPct: "40" }; // 200 g > 140 g
({ plan, errors } = formToPlan(f, catalog));
assert.equal(plan, null);
assert.ok(errors.levainPct);
f = scaleBuild(f, catalog, 200);
assert.equal(f.seedG, "29");
assert.deepEqual(formToPlan(f, catalog).errors, {});
f = scaleBuild({ ...f, custom: true }, catalog, 300);
assert.ok(formToPlan(f, catalog).info.levainG >= 300);

// Errors block the plan.
({ plan, errors } = formToPlan({ ...defaultForm(catalog, "levain_liquide"), seedG: "abc" }, catalog));
assert.equal(plan, null);
assert.ok(errors.seedG);

assert.equal(ratioLabel(3, 55), "1:3:1.65");
const start = new Date(2026, 8, 28, 22, 0).getTime();
assert.equal(hoursUntil(start, "07:00"), 9);
assert.equal(hoursUntil(start, "23:30"), 1.5);
const rows = [{ peak_h: { p50: 5 } }, { peak_h: { p50: null } }, { peak_h: { p50: 8.8 } }, { peak_h: { p50: 11 } }];
assert.equal(closestRow(rows, 9), 2);

console.log("plan.js ok");
