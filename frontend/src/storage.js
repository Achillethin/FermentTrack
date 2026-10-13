// This app's keys on the device: localStorage entries named "ft.*" (the levain planner's form, a
// hidden deep search, ...). Pure: `node src/storage.check.mjs` runs it.
export const APP_PREFIX = "ft.";

// Removes this app's keys, on sign-out and when the session's user changes (claimAppKeys): the
// next account on this device starts clean. Supabase's own session keys (sb-*) are left to it.
// storage: localStorage (the default) or a stand-in. Never throws: a browser may refuse storage.
export function clearAppKeys(storage) {
  try {
    const s = storage ?? globalThis.localStorage;
    if (!s) return;
    const keys = [];
    for (let i = 0; i < s.length; i += 1) {
      const key = s.key(i);
      if (key?.startsWith(APP_PREFIX)) keys.push(key);
    }
    keys.forEach((key) => s.removeItem(key)); // collected first: removing shifts the indices
  } catch {
    // storage disabled or refused: nothing kept to clear
  }
}

// The user id this device's app keys belong to, kept with them (so cleared with them).
export const OWNER_KEY = `${APP_PREFIX}owner`;

// On every session (start, sign-in, a magic link to another account, a new guest after the old
// session ended): when this device's app keys belong to another user, they are cleared; then they
// are this user's. Keys found with no owner recorded (kept before this check existed) are adopted.
// A guest who adds an email keeps the same user id, so keeps the keys. Returns true when it
// cleared. Never throws.
export function claimAppKeys(userId, storage) {
  if (!userId) return false;
  try {
    const s = storage ?? globalThis.localStorage;
    if (!s) return false;
    const owner = s.getItem(OWNER_KEY);
    if (owner === userId) return false;
    if (owner !== null) clearAppKeys(s);
    s.setItem(OWNER_KEY, userId);
    return owner !== null;
  } catch {
    return false;
  }
}
