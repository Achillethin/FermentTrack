// Community recipes' API (design § 10.3), through the recommender's request helper (auth rides
// on auth.js's patched fetch; a failed call carries the API's status and detail).
import { request } from "../ideas/api.js";

const id = encodeURIComponent;
export const publishRecipe = (body) => request("/community-recipes", { method: "POST", body });
export const getMyRecipes = (signal) => request("/me/community-recipes", { signal });
export const getReviewQueue = (status, signal) => request(`/admin/community-recipes?status=${id(status)}`, { signal });
export const approveRecipe = (recipeId) => request(`/admin/community-recipes/${id(recipeId)}/approve`, { method: "POST", body: {} });
export const rejectRecipe = (recipeId, reason) =>
  request(`/admin/community-recipes/${id(recipeId)}/reject`, { method: "POST", body: { reason } });
