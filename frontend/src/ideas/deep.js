// "Search deeper" (design § 10.2): the job's state machine, when to poll, and the waiting
// message. Pure: `node src/ideas/deep.check.mjs` runs it.
import { parseApiDate } from "../prediction/format.js";

export const POLL_MS = 5000; // while the page is visible only
export const KEEP_SHOWING_MS = 24 * 3600 * 1000; // a finished search is offered again for a day
export const LEAVE_NOTE = "You can leave this page; results are kept.";

const ACTIVE = new Set(["queued", "running"]);
export const isActive = (status) => ACTIVE.has(status);

// status: idle → starting → queued | running | done | failed (the job's own, from each poll);
// error: the search could not start, or the job is gone. A failed poll keeps the job's status
// and retries.
export const IDLE = {
  status: "idle",
  jobId: null,
  job: null,
  request: null, // what was asked: kept the same object for a job, so cards' forecasts never restart
  requestOf: null, // the job whose own request `request` is (read once, on its first answer)
  error: null,
  followed: false, // a 409's job: your search already running, maybe for another request
  polledAt: 0,
  misses: 0,
};

export function deepReducer(state, ev) {
  switch (ev.type) {
    case "start":
      return { ...IDLE, status: "starting", request: ev.request };
    case "accepted": // 202 (queued), 200 (your finished job of this request) or 409 (followed)
      return { ...state, status: ev.status, jobId: ev.jobId, followed: Boolean(ev.followed), error: null };
    case "resumed": // GET /recommendations/jobs on return
      return {
        ...IDLE,
        status: ev.job.status,
        jobId: ev.job.job_id,
        job: ev.job,
        request: ev.job.request,
        requestOf: ev.job.job_id,
        polledAt: ev.at,
      };
    case "polled": {
      if (ev.job.job_id !== state.jobId) return state; // a late answer for a job left behind
      // Each poll parses a new request object: keep the first one of this job (a new identity
      // every 5 s would restart every deep card's slider forecast).
      const read = state.requestOf === ev.job.job_id;
      return {
        ...state,
        status: ev.job.status,
        job: ev.job,
        request: read ? state.request : (ev.job.request ?? state.request),
        requestOf: ev.job.job_id,
        error: null,
        polledAt: ev.at,
        misses: 0,
      };
    }
    case "pollFailed":
      if (ev.gone) return { ...state, status: "error", jobId: null, error: "This search is no longer available." };
      // signed out or not allowed (401/403): polling again cannot help
      if (ev.denied) return { ...state, status: "error", jobId: null, error: ev.message };
      return { ...state, error: ev.message, polledAt: ev.at, misses: state.misses + 1 };
    case "startFailed":
      return { ...state, status: "error", error: ev.message };
    case "reset":
      return IDLE;
    default:
      return state;
  }
}

// A job to read: not read yet, or still queued or running.
export const needsPoll = (state) => Boolean(state.jobId) && (!state.job || isActive(state.job.status));

// A poll's failure: a gone job (404) or a refusal (401/403) stops polling; anything else retries.
export const pollFailure = (err, at) => ({
  type: "pollFailed",
  message: err.message,
  gone: err.status === 404,
  denied: err.status === 401 || err.status === 403,
  at,
});

// The next poll: never while the page is hidden (null); the first read at once; then every
// POLL_MS, counted from the last answer (coming back to the page polls at once if it is due).
export function nextPollIn(state, visible, now) {
  if (!visible || !needsPoll(state)) return null;
  if (!state.job && state.misses === 0) return 0;
  return Math.max(0, POLL_MS - (now - state.polledAt));
}

// "about 3 min left", "less than a minute left"; null without an estimate.
export function etaText(seconds) {
  if (!Number.isFinite(seconds) || seconds < 0) return null;
  if (seconds < 60) return "less than a minute left";
  const min = Math.round(seconds / 60);
  if (min < 60) return `about ${min} min left`;
  const h = Math.floor(min / 60);
  const m = min % 60;
  return `about ${h} h${m ? ` ${m} min` : ""} left`;
}

const ideas = (n) => `${n} confirmed idea${n === 1 ? "" : "s"}`;
const sentence = (s) => (/[.!?…]$/.test(s) ? s : `${s}.`);

// The waiting message (shown) for a job.
export function progressText(job) {
  if (!job) return "Starting the search…";
  const found = job.results?.length ?? 0;
  if (job.status === "queued" || (job.status === "running" && !job.total)) return `Waiting for the model… ${LEAVE_NOTE}`;
  if (job.status === "running") {
    const eta = etaText(job.eta_s);
    return `Exploring ${job.done} / ${job.total} combinations${eta ? ` — ${eta}` : ""}. ${LEAVE_NOTE}`;
  }
  if (job.status === "done") return found ? `Search finished: ${ideas(found)}.` : "Search finished: no further idea passed the checks.";
  if (job.status === "failed") {
    const kept = found === 1 ? " The confirmed idea it found is kept." : found ? ` The ${ideas(found)} it found are kept.` : "";
    return `${sentence(job.error || "The search stopped")}${kept}`;
  }
  return "";
}

// What a screen reader hears (aria-live): the progress without the ETA, which changes on every
// poll, so it speaks when there is news only.
export function announceText(job) {
  if (!job) return "Starting the search.";
  if (job.status === "queued" || (job.status === "running" && !job.total)) return "Waiting for the model.";
  if (job.status === "running") return `Exploring ${job.done} of ${job.total} combinations.`;
  return progressText(job);
}

// The search to show on return (GET /recommendations/jobs, newest first): a running one, or one
// finished in the last day that was not hidden.
export function resumable(jobs, { hidden = null, now = Date.now() } = {}) {
  const job = jobs?.[0];
  if (!job) return null;
  if (isActive(job.status)) return job;
  if (job.job_id === hidden) return null;
  const at = parseApiDate(job.finished_at)?.getTime();
  return Number.isFinite(at) && now - at < KEEP_SHOWING_MS ? job : null;
}

// The deep search's body: POST /recommendations/deep-search refuses a parent (your batch's and a
// community recipe's variants already run live).
export function deepRequest(query) {
  const { parent_batch_id: _b, community_recipe_id: _c, ...rest } = query;
  return rest;
}
