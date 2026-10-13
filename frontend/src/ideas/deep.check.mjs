// Self-check for deep.js (search deeper): node src/ideas/deep.check.mjs
import assert from "node:assert/strict";
import {
  announceText,
  deepReducer,
  deepRequest,
  etaText,
  IDLE,
  isActive,
  needsPoll,
  nextPollIn,
  POLL_MS,
  pollFailure,
  progressText,
  resumable,
} from "./deep.js";

// The waiting message (design § 10.2), queued and finished states.
assert.equal(
  progressText({ status: "running", done: 7, total: 20, eta_s: 180, results: [] }),
  "Exploring 7 / 20 combinations — about 3 min left. You can leave this page; results are kept."
);
assert.equal(progressText({ status: "queued", done: 0, total: 0, eta_s: 300, results: [] }), "Waiting for the model… You can leave this page; results are kept.");
assert.equal(progressText({ status: "running", done: 0, total: 0, eta_s: 300, results: [] }), "Waiting for the model… You can leave this page; results are kept.");
assert.equal(progressText({ status: "running", done: 3, total: 20, eta_s: null, results: [] }), "Exploring 3 / 20 combinations. You can leave this page; results are kept.");
assert.equal(progressText({ status: "done", results: [{}, {}] }), "Search finished: 2 confirmed ideas.");
assert.equal(progressText({ status: "done", results: [] }), "Search finished: no further idea passed the checks.");
assert.equal(
  progressText({ status: "failed", error: "The search stopped on an internal error.", results: [{}] }),
  "The search stopped on an internal error. The confirmed idea it found is kept."
);
assert.equal(progressText({ status: "failed", error: null, results: [{}, {}] }), "The search stopped. The 2 confirmed ideas it found are kept.");
assert.equal(progressText({ status: "failed", error: "Interrupted", results: [] }), "Interrupted.");
assert.equal(progressText(null), "Starting the search…");
// Screen readers hear news only (no ETA, which changes on every poll).
assert.equal(announceText({ status: "running", done: 7, total: 20, eta_s: 180 }), "Exploring 7 of 20 combinations.");
assert.equal(announceText({ status: "running", done: 7, total: 20, eta_s: 175 }), announceText({ status: "running", done: 7, total: 20, eta_s: 180 }));
assert.equal(announceText({ status: "queued", done: 0, total: 0 }), "Waiting for the model.");

// ETA text.
assert.equal(etaText(null), null);
assert.equal(etaText(undefined), null);
assert.equal(etaText(-1), null);
assert.equal(etaText(0), "less than a minute left");
assert.equal(etaText(59), "less than a minute left");
assert.equal(etaText(60), "about 1 min left");
assert.equal(etaText(89), "about 1 min left");
assert.equal(etaText(300), "about 5 min left");
assert.equal(etaText(3600), "about 1 h left");
assert.equal(etaText(3900), "about 1 h 5 min left");

// The state machine: 202 → queued → running → done; polling stops once finished.
const job = (status, extra = {}) => ({ job_id: "j1", status, done: 0, total: 0, eta_s: 60, results: [], request: { aromas: ["sour"] }, ...extra });
let s = deepReducer(IDLE, { type: "start", request: { aromas: ["sour"] } });
assert.equal(s.status, "starting");
assert.equal(needsPoll(s), false); // no job id yet
s = deepReducer(s, { type: "accepted", jobId: "j1", status: "queued" });
assert.equal(needsPoll(s), true);
assert.equal(nextPollIn(s, true, 1000), 0); // the first read at once
assert.equal(nextPollIn(s, false, 1000), null); // never while hidden
s = deepReducer(s, { type: "polled", job: job("queued"), at: 1000 });
assert.equal(nextPollIn(s, true, 1000), POLL_MS);
assert.equal(nextPollIn(s, true, 4000), 2000);
assert.equal(nextPollIn(s, true, 99_000), 0); // back on the page after a while: at once
assert.equal(nextPollIn(s, false, 99_000), null);
s = deepReducer(s, { type: "polled", job: job("running", { done: 2, total: 20 }), at: 6000 });
assert.equal(s.status, "running");
// A failed poll keeps the job and retries after POLL_MS.
s = deepReducer(s, { type: "pollFailed", message: "Could not reach the server", at: 11_000 });
assert.equal(s.status, "running");
assert.equal(s.error, "Could not reach the server");
assert.equal(nextPollIn(s, true, 11_000), POLL_MS);
s = deepReducer(s, { type: "polled", job: job("running", { done: 3, total: 20 }), at: 16_000 });
assert.equal(s.error, null);
// A late answer for another job is ignored.
assert.equal(deepReducer(s, { type: "polled", job: { ...job("done"), job_id: "j0" }, at: 17_000 }), s);
s = deepReducer(s, { type: "polled", job: job("done", { done: 20, total: 20, results: [{ id: "a" }] }), at: 21_000 });
assert.equal(s.status, "done");
assert.equal(needsPoll(s), false);
assert.equal(nextPollIn(s, true, 99_000), null);
s = deepReducer(s, { type: "polled", job: job("failed"), at: 0 });
assert.equal(needsPoll(s), false);
// 200 (your finished job of the same request): read once, then stop.
let d = deepReducer(deepReducer(IDLE, { type: "start", request: {} }), { type: "accepted", jobId: "j1", status: "done" });
assert.equal(nextPollIn(d, true, 0), 0);
d = deepReducer(d, { type: "polled", job: job("done"), at: 0 });
assert.equal(needsPoll(d), false);
// 409: follow detail.job_id.
const f = deepReducer(deepReducer(IDLE, { type: "start", request: {} }), { type: "accepted", jobId: "j9", status: "queued", followed: true });
assert.equal(f.jobId, "j9");
assert.equal(f.followed, true);
// A job that is gone (404) stops polling; a start that failed is an error.
const gone = deepReducer(s, { type: "pollFailed", gone: true, message: "Job not found", at: 0 });
assert.equal(gone.status, "error");
assert.equal(needsPoll(gone), false);
assert.equal(deepReducer(IDLE, { type: "startFailed", message: "x" }).status, "error");
assert.equal(deepReducer(s, { type: "reset" }), IDLE);
assert.ok(isActive("queued") && isActive("running") && !isActive("done") && !isActive("failed"));

// 401/403 stop polling too (polling again cannot help); a network error retries.
const running = deepReducer(deepReducer(IDLE, { type: "accepted", jobId: "j1", status: "queued" }), { type: "polled", job: job("running", { total: 20 }), at: 0 });
for (const status of [401, 403]) {
  const denied = deepReducer(running, pollFailure(Object.assign(new Error("Invalid or expired token"), { status }), 5000));
  assert.equal(denied.status, "error");
  assert.equal(denied.error, "Invalid or expired token");
  assert.equal(needsPoll(denied), false);
  assert.equal(nextPollIn(denied, true, 99_000), null);
}
const blip = deepReducer(running, pollFailure(new Error("Could not reach the server"), 5000));
assert.equal(blip.status, "running");
assert.equal(needsPoll(blip), true);
assert.equal(deepReducer(running, pollFailure(Object.assign(new Error("Job not found"), { status: 404 }), 5000)).error, "This search is no longer available.");

// The request object stays the same across polls of a job (cards' slider forecasts depend on it).
const p1 = deepReducer(running, { type: "polled", job: job("running", { done: 2, total: 20, request: { aromas: ["sour"] } }), at: 5000 });
const p2 = deepReducer(p1, { type: "polled", job: job("running", { done: 3, total: 20, request: { aromas: ["sour"] } }), at: 10_000 });
assert.equal(p1.request, running.request);
assert.equal(p2.request, p1.request);
// The first answer of a job sets it: a 409's job is another request than ours.
const ours = { aromas: ["fruity"] };
let f2 = deepReducer(deepReducer(IDLE, { type: "start", request: ours }), { type: "accepted", jobId: "j9", status: "queued", followed: true });
assert.equal(f2.request, ours);
const theirs = { aromas: ["sour"], ingredients: ["Napa cabbage"] };
f2 = deepReducer(f2, { type: "polled", job: { ...job("running"), job_id: "j9", request: theirs }, at: 1 });
assert.equal(f2.request, theirs);
assert.equal(deepReducer(f2, { type: "polled", job: { ...job("running"), job_id: "j9", request: { ...theirs } }, at: 2 }).request, theirs);
// A resumed job keeps its request through later polls.
const resumed = deepReducer(IDLE, { type: "resumed", job: { ...job("running"), job_id: "r1", request: theirs }, at: 0 });
assert.equal(deepReducer(resumed, { type: "polled", job: { ...job("running"), job_id: "r1", request: { ...theirs } }, at: 5 }).request, theirs);

// Resume on return: the newest job if running, or finished in the last day and not hidden.
const now = Date.parse("2026-10-13T12:00:00Z");
const fin = (id, at) => ({ job_id: id, status: "done", finished_at: at });
assert.equal(resumable([], { now }), null);
assert.equal(resumable(null, { now }), null);
assert.equal(resumable([{ job_id: "r", status: "running" }, fin("o", "2026-10-13T11:00:00")], { now }).job_id, "r");
assert.equal(resumable([{ job_id: "q", status: "queued" }], { hidden: "q", now }).job_id, "q"); // a running one is never hidden
assert.equal(resumable([fin("a", "2026-10-13T11:00:00")], { now }).job_id, "a"); // zone-less: UTC
assert.equal(resumable([fin("a", "2026-10-13T11:00:00Z")], { hidden: "a", now }), null);
assert.equal(resumable([fin("a", "2026-10-11T11:00:00Z")], { now }), null); // older than a day
assert.equal(resumable([{ job_id: "x", status: "failed", finished_at: "2026-10-13T10:00:00+00:00" }], { now }).job_id, "x");

// The deep search never sends a parent (422).
assert.deepEqual(
  deepRequest({ ingredients: ["Cabbage"], mode: "both", parent_batch_id: "b", community_recipe_id: "c", usda_fdc_ids: [1] }),
  { ingredients: ["Cabbage"], mode: "both", usda_fdc_ids: [1] }
);

console.log("deep.js ok");
