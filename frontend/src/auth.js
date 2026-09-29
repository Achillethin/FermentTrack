// Stage 0 auth: every visitor gets an anonymous Supabase session (no signup
// wall) so their batches are private to them from the first click. Patches
// window.fetch to attach the session's access token to API calls, so none of
// App.jsx's existing fetch(`${API_URL}/...`) call sites need to change.
//
// ponytail: anonymous-only for now — no "claim this account with an email"
// flow yet, so clearing browser storage loses access to the batches. Add
// supabase.auth.updateUser({ email }) behind a "save my batches" prompt when
// that matters.
import { createClient } from "@supabase/supabase-js";

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

export const supabase =
  supabaseUrl && supabaseAnonKey ? createClient(supabaseUrl, supabaseAnonKey) : null;

let sessionPromise = null;

// Dev only: a token minted locally for a backend run with
// FERMENTTRACK_SUPABASE_JWT_SECRET (no Supabase project needed). The DEV
// guard folds this to undefined in production builds.
const devToken = import.meta.env.DEV ? import.meta.env.VITE_DEV_TOKEN : undefined;

async function ensureSession() {
  if (devToken) return { access_token: devToken };
  if (!supabase) return null;
  if (!sessionPromise) {
    sessionPromise = supabase.auth.getSession().then(async ({ data }) => {
      if (data.session) return data.session;
      const { data: signedIn, error } = await supabase.auth.signInAnonymously();
      if (error) throw error;
      return signedIn.session;
    });
  }
  return sessionPromise;
}

export const apiOrigin = (import.meta.env.VITE_API_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");
const nativeFetch = window.fetch.bind(window);

window.fetch = async (input, init = {}) => {
  const url = typeof input === "string" ? input : input.url;
  if (!url.startsWith(apiOrigin)) return nativeFetch(input, init);

  const session = await ensureSession();
  if (!session) return nativeFetch(input, init);

  const headers = new Headers(init.headers || (typeof input !== "string" ? input.headers : undefined));
  headers.set("Authorization", `Bearer ${session.access_token}`);
  return nativeFetch(input, { ...init, headers });
};
