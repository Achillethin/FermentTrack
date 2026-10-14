// Self-check for community.js: node src/community/community.check.mjs
import assert from "node:assert/strict";
import {
  durationText,
  forecastJobText,
  gPerKgText,
  PRIVACY_NOTICE,
  PSEUDONYM_RULE,
  publishBody,
  pseudonymError,
  reasonError,
  refusal,
  statusText,
  titleError,
} from "./community.js";

// The pseudonym rule mirrors schemas.Pseudonym: stripped, 2–40, ^\w[\w .'-]*$ (Unicode). Each
// case below was run through the API's own validator (pydantic) with the same verdict.
for (const ok of ["Jo", "kimchi_fan", "Anne-Marie O'Neil", "J. Doe", "Zoë", "Ægir", "李小龍", "42", "_x", "  padded  ", "a".repeat(40), "Zoe\u0308x", "\u216bab"]) {
  assert.equal(pseudonymError(ok), null, ok);
}
for (const bad of ["", "   ", "x", " x ", "a".repeat(41), "-dash", ".dot", "'quote", " ", "me@example.com", "http://x", "a/b", "tab\there", "semi;colon", "émoji😀", "x²", "a\u00a0b"]) {
  assert.notEqual(pseudonymError(bad), null, JSON.stringify(bad));
}
assert.equal(pseudonymError("x"), "Use 2 to 40 characters.");
assert.equal(pseudonymError("me@x"), "Use letters, digits, spaces and . _ ' -, starting with a letter or digit.");
assert.equal(pseudonymError("😀😀"), "Use letters, digits, spaces and . _ ' -, starting with a letter or digit."); // 2 code points
assert.equal(PSEUDONYM_RULE, "2–40 characters: letters, digits, spaces and . _ ' -, starting with a letter or digit.");

// Title: 1–120 after stripping, no control characters.
assert.equal(titleError("My kraut"), null);
assert.equal(titleError("  "), "Give the recipe a title.");
assert.equal(titleError("x".repeat(121)), "Use at most 120 characters.");
assert.equal(titleError("x".repeat(120)), null);
assert.equal(titleError("bad\u0000"), "Remove the control characters.");
assert.deepEqual(publishBody("b1", "  Kraut ", " Jo "), { batch_id: "b1", title: "Kraut", pseudonym: "Jo" });

// Refusal reasons are the API's, verbatim.
const checks = Object.assign(new Error("This batch cannot be published yet."), {
  status: 422,
  detail: { message: "This batch cannot be published yet.", reasons: ["fill in the batch's tasting form first (at least one tasting)", "log a pH ≤ 4.6"] },
});
assert.deepEqual(refusal(checks), {
  message: "This batch cannot be published yet.",
  reasons: ["fill in the batch's tasting form first (at least one tasting)", "log a pH ≤ 4.6"],
});
assert.deepEqual(refusal(Object.assign(new Error("This batch is already published."), { status: 409, detail: "This batch is already published." })), {
  message: "This batch is already published.",
  reasons: [],
});
assert.deepEqual(refusal(Object.assign(new Error("pseudonym: String should match pattern"), { detail: [{ loc: ["body", "pseudonym"] }] })).reasons, []);
assert.equal(refusal(null).message, "Could not publish the recipe.");

// A rejection needs a reason.
assert.equal(reasonError(""), "Say why: the author reads it.");
assert.equal(reasonError("  "), "Say why: the author reads it.");
assert.equal(reasonError("Salt too low"), null);
assert.equal(reasonError("x".repeat(501)), "Use at most 500 characters.");

assert.equal(statusText("pending"), "waiting for review");
assert.equal(statusText("other"), "other");
assert.equal(forecastJobText(null), "Forecast: not queued yet (approving queues it).");
assert.equal(forecastJobText({ status: "running", done: 1, total: 3 }), "Forecast: running, 1 / 3.");
assert.equal(forecastJobText({ status: "running", done: 0, total: 0 }), "Forecast: running.");
assert.equal(forecastJobText({ status: "failed", error: "boom" }), "Forecast: failed (boom). Approve again to retry it.");
assert.equal(forecastJobText({ status: "done" }), "Forecast: done; the recipe can be served.");
assert.equal(gPerKgText(17.25), "17.3 g/kg");
assert.equal(durationText(36), "36 h");
assert.equal(durationText(120), "5 days");
assert.match(PRIVACY_NOTICE, /stays in the library if you delete your account/);

console.log("community.js ok");
