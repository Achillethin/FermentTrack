// Recommender API calls. Auth rides on auth.js's patched window.fetch, like every other
// call in the app.
import { apiOrigin as API_URL } from "../auth.js";
import { errorText } from "./ideas.js";

// A failed call throws an Error with the API's text, plus `status` and the raw `detail` (a 409's
// job id, a refused publish's reasons).
export async function request(path, { method = "GET", body, signal } = {}) {
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
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw Object.assign(new Error(errorText(res.status, data)), { status: res.status, detail: data?.detail });
  }
  return res.status === 204 ? null : res.json();
}

export const getIngredients = (signal) => request("/ingredients", { signal });
export const postRecommendations = (body, signal) => request("/recommendations", { method: "POST", body, signal });
export const postForecast = (body, signal) => request("/recommendations/forecast", { method: "POST", body, signal });
// "Made from what you have": composed recipes, live, so apart from /recommendations
export const postPantry = (body, signal) => request("/recommendations/pantry", { method: "POST", body, signal });
export const postStartBatch = (body) => request("/batches/from-recommendation", { method: "POST", body });

// Experimental: your batches as parents (Q16), USDA foods for operator (v).
export const getMyBatches = (signal) => request("/batches?limit=200", { signal });
export const searchFoods = (q, signal) => request(`/foods?q=${encodeURIComponent(q)}&limit=20`, { signal });

// Search deeper (design § 10.2).
export const postDeepSearch = (body) => request("/recommendations/deep-search", { method: "POST", body });
export const getJob = (id, signal) => request(`/recommendations/jobs/${encodeURIComponent(id)}`, { signal });
export const getJobs = (signal) => request("/recommendations/jobs", { signal });

// The calibration gate's latest public report (design § 13.2): 404 before the first one.
export const getCalibration = (signal) => request("/recommendations/calibration", { signal });
