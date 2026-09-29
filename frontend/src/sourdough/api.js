// Sourdough API calls. Auth rides on auth.js's patched window.fetch, like
// every other call in the app.
import { apiOrigin as API_URL } from "../auth.js";

// Dev only: open the app with ?fixture to answer the three /sourdough routes
// from fixture.js (no backend needed). Vite drops this branch, and the
// fixture chunk with it, from production builds.
const FIXTURE = import.meta.env.DEV && new URLSearchParams(window.location.search).has("fixture");

// FastAPI detail: a string (4xx) or a list of {loc, msg} (422).
async function errorText(res) {
  const body = await res.json().catch(() => ({}));
  if (typeof body.detail === "string") return body.detail;
  if (Array.isArray(body.detail)) {
    return body.detail
      .map((d) => {
        const where = (d.loc || []).slice(1).join(".");
        const msg = String(d.msg).replace(/^Value error, /, "");
        return where ? `${where}: ${msg}` : msg;
      })
      .join("; ");
  }
  return `The server answered ${res.status}`;
}

async function request(path, { method = "GET", body, signal } = {}) {
  if (FIXTURE && path.startsWith("/sourdough/")) {
    const { fixtureAnswer } = await import("./fixture.js");
    return fixtureAnswer(path, body, signal);
  }
  let res;
  try {
    res = await fetch(`${API_URL}${path}`, {
      method,
      signal,
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch (e) {
    if (e.name === "AbortError") throw e;
    throw new Error("Could not reach the server");
  }
  if (!res.ok) throw new Error(await errorText(res));
  return res.status === 204 ? null : res.json();
}

// One catalog fetch for the whole app (planner, plan card, new-batch form).
let catalogPromise = null;
export function getCatalog() {
  catalogPromise ??= request("/sourdough/catalog").catch((e) => {
    catalogPromise = null;
    throw e;
  });
  return catalogPromise;
}

export const postPlan = (plan, signal) => request("/sourdough/plan", { method: "POST", body: plan, signal });
export const postFeedingChart = (body, signal) =>
  request("/sourdough/feeding-chart", { method: "POST", body, signal });

export const getCultures = () => request("/cultures");
export const postCulture = (body) => request("/cultures", { method: "POST", body });
export const postBatch = (body) => request("/batches", { method: "POST", body });
export const patchBatch = (id, body) => request(`/batches/${encodeURIComponent(id)}`, { method: "PATCH", body });
