// Auth: every visitor gets an anonymous Supabase session (no signup wall) so their
// batches are private to them from the first click; a guest can attach an email
// (saveWithEmail: same account) or sign in to an email account on another device
// (signInWithEmail). Patches window.fetch to attach the current access token to API
// calls, so no fetch(`${API_URL}/...`) call site needs to change.
import { createClient } from "@supabase/supabase-js";

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

export const supabase =
  supabaseUrl && supabaseAnonKey ? createClient(supabaseUrl, supabaseAnonKey) : null;

let signInPromise = null;

// Dev only: a token minted locally for a backend run with
// FERMENTTRACK_SUPABASE_JWT_SECRET (no Supabase project needed). The DEV
// guard folds this to undefined in production builds.
const devToken = import.meta.env.DEV ? import.meta.env.VITE_DEV_TOKEN : undefined;

// The current session. supabase-js keeps it refreshed (access tokens last ~1 h), so it
// is read on every call rather than cached here. With none yet, one anonymous sign-in
// (shared by concurrent callers); a failure is not remembered, so Retry works.
export async function ensureSession() {
  if (devToken) return { access_token: devToken };
  if (!supabase) return null;
  const { data } = await supabase.auth.getSession();
  if (data.session) return data.session;
  if (!signInPromise) {
    signInPromise = supabase.auth
      .signInAnonymously()
      .then(({ data: signedIn, error }) => {
        if (error) throw error;
        return signedIn.session;
      })
      .finally(() => {
        signInPromise = null;
      });
  }
  return signInPromise;
}

// Sign in to an existing (or new) email account on this device: Supabase emails a
// one-time link that comes back here signed in. Replaces this device's guest session.
export async function signInWithEmail(email) {
  if (!supabase) throw new Error("Accounts aren't set up on this server.");
  const here = window.location.origin + window.location.pathname;
  const { error } = await supabase.auth.signInWithOtp({
    email,
    options: { emailRedirectTo: here, shouldCreateUser: true },
  });
  if (error) throw error;
}

export async function signOut() {
  if (supabase) await supabase.auth.signOut();
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

// The signed-in Supabase user (null when auth isn't configured, e.g. local dev).
export async function currentUser() {
  if (!supabase) return null;
  await ensureSession();
  const { data } = await supabase.auth.getUser();
  return data.user ?? null;
}

// Anonymous -> permanent account: the same user id (no data moves); Supabase emails a
// confirmation link, after which the batches survive cleared storage or a new phone.
export async function saveWithEmail(email) {
  if (!supabase) throw new Error("Accounts aren't set up on this server.");
  const here = window.location.origin + window.location.pathname;
  const { error } = await supabase.auth.updateUser({ email }, { emailRedirectTo: here });
  if (error) throw error;
}
