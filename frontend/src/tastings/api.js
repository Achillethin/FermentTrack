// A batch's tastings (design § 11.2) and the reminders that prompt them, through the
// recommender's request helper (auth rides on auth.js's patched fetch).
import { request } from "../ideas/api.js";

const id = encodeURIComponent;
export const getTastings = (batchId, signal) => request(`/batches/${id(batchId)}/tastings`, { signal });
export const postTasting = (batchId, body) => request(`/batches/${id(batchId)}/tastings`, { method: "POST", body });
export const deleteTasting = (batchId, tastingId) =>
  request(`/batches/${id(batchId)}/tastings/${id(tastingId)}`, { method: "DELETE" });
export const getReminders = (signal) => request("/reminders", { signal });
