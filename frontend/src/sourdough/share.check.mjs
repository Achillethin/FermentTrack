// Self-check for share.js (no test runner in this frontend): node src/sourdough/share.check.mjs
import assert from "node:assert/strict";
import { defaultForm, formToPlan } from "./plan.js";
import { buildIcs, decodePlan, encodePlan, foldLine, icsText, planEvents, sharedForm, shareUrl } from "./share.js";

const catalog = {
  styles: [
    { key: "levain_liquide", name: "Levain liquide", seed: "starter", defaults: { hydration_pct: 100, seed_ratio: 3, temperature_c: 26, flour: "t65", hours: null } },
    { key: "poolish", name: "Poolish", seed: "yeast", defaults: { hydration_pct: 100, seed_ratio: 1000, temperature_c: 20, flour: "t55", hours: 12 } },
  ],
  flours: [{ key: "t65", name: "T65" }, { key: "t55", name: "T55" }, { key: "t150", name: "T150" }],
};
const hashOf = (plan) => `#/levain?p=${encodePlan(plan)}`;

// Round trip: form -> plan -> link -> form -> the same plan, minus the sender's starter id.
const f = { ...defaultForm(catalog, "levain_liquide"), cultureId: "c0ffee", doughOn: true, flour2: "t150", share2: "10", proof: "cold" };
const { plan } = formToPlan(f, catalog);
assert.equal(plan.culture_id, "c0ffee");
const back = sharedForm(hashOf(plan), catalog);
assert.deepEqual(formToPlan(back, catalog).plan, { ...plan, culture_id: null });
assert.equal(decodePlan(encodePlan(plan)).culture_id, null);
const poolish = formToPlan(defaultForm(catalog, "poolish"), catalog).plan;
assert.deepEqual(formToPlan(sharedForm(hashOf(poolish), catalog), catalog).plan, poolish);

// The link: base64url only, origin + path (no ?batch=), well under URL limits.
const url = shareUrl(plan, { origin: "https://x.github.io", pathname: "/FermentTrack/", search: "?batch=secret" });
assert.match(url, /^https:\/\/x\.github\.io\/FermentTrack\/#\/levain\?p=[A-Za-z0-9_-]+$/);
assert.ok(url.length < 1200, url.length);

// Malformed input is ignored, never thrown.
const b64 = (s) => Buffer.from(s).toString("base64url");
for (const h of [
  "", "#/levain", "#/levain?p=", "#/levain?p=%%%", "#/levain?p=!!", "#/levain?q=abc", "#/batch/1?p=" + encodePlan(plan),
  `#/levain?p=${b64("not json")}`, `#/levain?p=${b64("[1,2]")}`, `#/levain?p=${b64('{"v":2,"plan":{}}')}`,
  `#/levain?p=${b64('{"v":1,"plan":null}')}`, `#/levain?p=${Buffer.from([0xff, 0xfe]).toString("base64url")}`,
  `#/levain?p=${"A".repeat(5000)}`,
]) assert.equal(sharedForm(h, catalog), null, h);

// Hostile but well-formed: unknown keys dropped, junk types nulled, unknown flours/styles defaulted.
const junk = { style: "nope", starter: "<script>", culture_id: "x", extra: 1,
  levain: { seed_g: "20", flour_g: 60, water_g: 1e400, flour: { t65: 0.5, "__proto__": 0.5, evil: 1 }, temperature_c: 24, hours: {} },
  dough: [], proof: { temperature_c: 4, hours: 14 } };
const jf = sharedForm(`#/levain?p=${b64(JSON.stringify({ v: 1, plan: junk }))}`, catalog);
assert.equal(jf.style, "levain_liquide");
assert.equal(jf.starter, "ripe");
assert.equal(jf.flour, "t65");
assert.equal(jf.doughOn, false);
const jr = formToPlan(jf, catalog);
assert.equal(jr.plan, null); // "20" (a string) and Infinity are not numbers: the form flags them
assert.ok(Object.keys(jr.errors).length > 0);

// Calendar events from an API answer (feed 22:00 local).
const start = new Date(2026, 8, 28, 22, 0).getTime();
const data = {
  milestones: [
    { key: "levain_peak", t_h: { p05: 6.5, p50: 8.7, p95: 11 } },
    { key: "bulk_target", t_h: { p05: 12, p50: 13.5, p95: null } },
  ],
  phases: [
    { key: "levain", start_h: 0, end_h: 8.7 },
    { key: "bulk", start_h: 8.7, end_h: 13.5 },
    { key: "proof", start_h: 13.5, end_h: 27.5 },
  ],
};
const ev = planEvents(data, start);
assert.deepEqual(ev.map((e) => e.key), ["peak", "bulk", "bake"]); // mix == peak: one alarm
assert.equal(ev[0].at.getTime(), new Date(2026, 8, 29, 6, 40).getTime());
assert.match(ev[0].description, /^Likely between \S+ 04:30 and \S+ 09:00\. Model estimate/);
assert.doesNotMatch(ev[1].description, /Likely/); // open-ended band: no range claimed
assert.deepEqual(planEvents({ ...data, phases: [{ key: "bulk", start_h: 10 }] }, start).map((e) => e.key), ["peak", "mix", "bulk"]);
assert.deepEqual(planEvents({ milestones: [{ key: "levain_peak", t_h: { p50: null } }] }, start), []);

// .ics: CRLF, UTC stamps, escaping, folding at 75 octets without splitting a character.
const ics = buildIcs(ev, start, new Date(Date.UTC(2026, 8, 28, 20, 0, 5)));
assert.ok(ics.startsWith("BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:"));
assert.ok(ics.endsWith("END:VCALENDAR\r\n"));
assert.equal(ics.split("\r\n").filter((l) => l === "BEGIN:VEVENT").length, 3);
assert.ok(!/[^\r]\n/.test(ics), "bare LF");
assert.ok(ics.includes(`DTSTART:${ev[0].at.toISOString().replace(/[-:]/g, "").replace(".000", "")}\r\n`));
assert.ok(ics.includes("DTSTAMP:20260928T200005Z\r\n"));
assert.ok(ics.includes(`UID:${start}-peak@fermenttrack\r\n`));
for (const l of ics.split("\r\n")) assert.ok(Buffer.byteLength(l) <= 75, l);
assert.equal(icsText("a,b;c\\d\ne"), "a\\,b\\;c\\\\d\\ne");
const long = "DESCRIPTION:" + "é°".repeat(40) + "🍞".repeat(10);
const folded = foldLine(long);
assert.equal(folded.split("\r\n ").join(""), long); // unfolding restores it exactly
for (const l of folded.split("\r\n")) assert.ok(Buffer.byteLength(l) <= 75);
assert.equal(foldLine("SUMMARY:short"), "SUMMARY:short");

console.log("share.js ok");
