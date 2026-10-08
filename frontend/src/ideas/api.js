// Recommender API calls. Auth rides on auth.js's patched window.fetch, like every other
// call in the app.
import { apiOrigin as API_URL } from "../auth.js";
import { errorText } from "./ideas.js";

async function request(path, { method = "GET", body, signal } = {}) {
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
  if (!res.ok) throw new Error(errorText(res.status, await res.json().catch(() => ({}))));
  return res.json();
}

export const getIngredients = (signal) => request("/ingredients", { signal });
export const postRecommendations = (body, signal) => request("/recommendations", { method: "POST", body, signal });
export const postForecast = (body, signal) => request("/recommendations/forecast", { method: "POST", body, signal });
export const postStartBatch = (body) => request("/batches/from-recommendation", { method: "POST", body });
