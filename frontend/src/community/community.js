// Community recipes (design § 10.3): publishing rules and review text. Pure: `node
// src/community/community.check.mjs` runs it.

// schemas.Pseudonym, exactly: stripped, 2–40 characters, `^\w[\w .'-]*$`, with pydantic's (Rust
// regex) Unicode \w: letters (Alphabetic), marks, digits (Nd), connectors (_) and joiners. So
// never an e-mail address or a link.
export const PSEUDONYM_MIN = 2;
export const PSEUDONYM_MAX = 40;
const W = String.raw`\p{Alphabetic}\p{M}\p{Nd}\p{Pc}\p{Join_Control}`;
const PSEUDONYM = new RegExp(`^[${W}][${W} .'-]*$`, "u");
const CHARACTERS = "letters, digits, spaces and . _ ' -, starting with a letter or digit";
export const PSEUDONYM_RULE = `${PSEUDONYM_MIN}–${PSEUDONYM_MAX} characters: ${CHARACTERS}.`;
export const TITLE_MAX = 120;
export const REASON_MAX = 500;
// recommender.community.PRIVACY_NOTICE, shown before publishing (the API's own copy comes back
// in the response, and is shown after).
export const PRIVACY_NOTICE = "Your recipe stays in the library if you delete your account; it is detached from you.";

const CONTROL = /[\x00-\x08\x0b\x0c\x0e-\x1f]/; // tab and line breaks aside (schemas.NoControlChars)
const length = (s) => [...s].length; // Python counts code points

// null when valid, else what to fix.
export function pseudonymError(raw) {
  const s = String(raw ?? "").trim();
  if (!s) return "Choose a pen name.";
  if (length(s) < PSEUDONYM_MIN || length(s) > PSEUDONYM_MAX) return `Use ${PSEUDONYM_MIN} to ${PSEUDONYM_MAX} characters.`;
  if (!PSEUDONYM.test(s)) return `Use ${CHARACTERS}.`;
  return null;
}

export function titleError(raw) {
  const s = String(raw ?? "").trim();
  if (!s) return "Give the recipe a title.";
  if (length(s) > TITLE_MAX) return `Use at most ${TITLE_MAX} characters.`;
  if (CONTROL.test(s)) return "Remove the control characters.";
  return null;
}

export function publishBody(batchId, title, pseudonym) {
  return { batch_id: batchId, title: String(title).trim(), pseudonym: String(pseudonym).trim() };
}

// A refused publish (POST /community-recipes): 422 {message, reasons[]} from the checks, 409 a
// string (already published), 422 a list (the fields). The reasons are the API's, verbatim.
export function refusal(err) {
  const d = err?.detail;
  if (d && typeof d === "object" && !Array.isArray(d) && Array.isArray(d.reasons)) {
    return { message: d.message || err.message, reasons: d.reasons.map(String) };
  }
  return { message: err?.message || "Could not publish the recipe.", reasons: [] };
}

// A rejection needs its reason (the API: 422 without one).
export function reasonError(raw) {
  const s = String(raw ?? "").trim();
  if (!s) return "Say why: the author reads it.";
  if (length(s) > REASON_MAX) return `Use at most ${REASON_MAX} characters.`;
  if (CONTROL.test(s)) return "Remove the control characters.";
  return null;
}

export const STATUS_TEXT = {
  pending: "waiting for review",
  approved: "approved: in the Ideas page's community section",
  rejected: "not approved",
};
export const statusText = (status) => STATUS_TEXT[status] ?? status;

// The reviewer's view of a recipe's forecast job (an approved recipe is served once it is done).
export function forecastJobText(job) {
  if (!job) return "Forecast: not queued yet (approving queues it).";
  switch (job.status) {
    case "queued":
      return "Forecast: queued.";
    case "running":
      return job.total ? `Forecast: running, ${job.done} / ${job.total}.` : "Forecast: running.";
    case "done":
      return "Forecast: done; the recipe can be served.";
    case "failed":
      return `Forecast: failed${job.error ? ` (${job.error})` : ""}. Approve again to retry it.`;
    default:
      return `Forecast: ${job.status}.`;
  }
}

const one = (x) => {
  const r = Math.round(x * 10) / 10;
  return Number.isInteger(r) ? String(r) : r.toFixed(1);
};
export const gPerKgText = (g) => `${one(g)} g/kg`;
export const durationText = (h) => (h < 48 ? `${Math.round(h)} h` : `${one(h / 24)} days`);
