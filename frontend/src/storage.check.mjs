// Self-check for storage.js: node src/storage.check.mjs
import assert from "node:assert/strict";
import { APP_PREFIX, claimAppKeys, clearAppKeys, OWNER_KEY } from "./storage.js";

// A localStorage stand-in (length, key(i), getItem, setItem, removeItem).
function memory(entries) {
  const m = new Map(entries);
  return {
    get length() {
      return m.size;
    },
    key: (i) => [...m.keys()][i] ?? null,
    getItem: (k) => m.get(k) ?? null,
    setItem: (k, v) => m.set(k, String(v)),
    removeItem: (k) => m.delete(k),
    keys: () => [...m.keys()],
  };
}

assert.equal(APP_PREFIX, "ft.");

// Sign-out clears every ft.* key, the session's own (sb-*) and other sites' keys stay.
const s = memory([
  ["ft.levain.form.v1", "{}"],
  ["sb-abc-auth-token", "session"],
  ["ft.deep-search.hidden", "job-1"],
  ["ft.levain.pro", "1"],
  ["ft.tasting-targets.b1", '["sour"]'], // written by earlier builds
  ["other", "x"],
  ["xft.not-ours", "y"],
]);
clearAppKeys(s);
assert.deepEqual(s.keys(), ["sb-abc-auth-token", "other", "xft.not-ours"]);

clearAppKeys(memory([])); // nothing to clear
clearAppKeys(null); // no localStorage here (node): never throws
const refusing = {
  get length() {
    throw new Error("SecurityError");
  },
  getItem() {
    throw new Error("SecurityError");
  },
};
clearAppKeys(refusing); // storage refused: never throws

// The session's user changes: the keys of the user they belong to go first (sb-* stay).
assert.equal(OWNER_KEY, "ft.owner");
const device = memory([
  ["ft.levain.form.v1", "{}"],
  ["ft.deep-search.hidden", "job-1"],
  ["sb-abc-auth-token", "session"],
]);
assert.equal(claimAppKeys("guest-1", device), false); // keys with no owner yet: adopted, kept
assert.deepEqual(device.keys(), ["ft.levain.form.v1", "ft.deep-search.hidden", "sb-abc-auth-token", "ft.owner"]);
assert.equal(device.getItem(OWNER_KEY), "guest-1");
assert.equal(claimAppKeys("guest-1", device), false); // the same user (a guest who added an email): kept
assert.equal(device.getItem("ft.levain.form.v1"), "{}");
assert.equal(claimAppKeys("email-2", device), true); // a magic link to another account: cleared
assert.deepEqual(device.keys(), ["sb-abc-auth-token", "ft.owner"]);
assert.equal(device.getItem(OWNER_KEY), "email-2");
device.setItem("ft.levain.pro", "1"); // email-2's own
assert.equal(claimAppKeys("email-2", device), false);
assert.equal(device.getItem("ft.levain.pro"), "1");
clearAppKeys(device); // sign-out: the owner goes with the keys
assert.deepEqual(device.keys(), ["sb-abc-auth-token"]);
assert.equal(claimAppKeys("guest-3", device), false); // the next guest starts clean
assert.equal(device.getItem(OWNER_KEY), "guest-3");
assert.equal(claimAppKeys(null, device), false); // no user: nothing changes
assert.equal(claimAppKeys(undefined, device), false);
assert.equal(device.getItem(OWNER_KEY), "guest-3");
assert.equal(claimAppKeys("x", refusing), false); // storage refused: never throws

console.log("storage.js ok");
