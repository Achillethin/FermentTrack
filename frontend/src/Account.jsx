import { useEffect, useId, useState } from "react";
import { currentUser, signInWithEmail, signOut } from "./auth.js";
import { Button, Input } from "./components/ui.jsx";
import { API_URL, Card } from "./shared.jsx";
import SaveAccount from "./sourdough/SaveAccount.jsx";

// Who you are, how to keep your data (email), and how to sign in on another device.
// Also the fallback screen when a guest session cannot be created (e.g. anonymous
// sign-ins disabled in Supabase): `blocked` carries that error.
export default function Account({ blocked = null }) {
  const [user, setUser] = useState(null);
  const [me, setMe] = useState(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (blocked) return undefined;
    let live = true;
    currentUser()
      .then((u) => live && setUser(u))
      .catch(() => {});
    fetch(`${API_URL}/me`)
      .then((r) => (r.ok ? r.json() : null))
      .then((j) => live && setMe(j))
      .catch(() => {});
    return () => {
      live = false;
    };
  }, [blocked]);

  async function copyId() {
    try {
      await navigator.clipboard.writeText(me.user_id);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  }

  const guest = !user || user.is_anonymous;
  return (
    <div className="space-y-4">
      {blocked && (
        <p role="alert" className="rounded-lg border border-amber-500/30 bg-amber-950/30 p-3 text-sm text-amber-200">
          Could not start a guest session ({blocked}). Sign in with your email to continue.
        </p>
      )}
      {!blocked && (
        <Card title="Your account">
          <p className="text-sm text-slate-300">
            {user?.email && !user.is_anonymous
              ? `Signed in as ${user.email}.`
              : "Guest on this device: your data lives in this browser until you add an email."}
            {me?.admin && <span className="ml-2 rounded border border-emerald-600 px-1.5 text-xs text-emerald-300">admin</span>}
          </p>
          {me && (
            <p className="mt-2 break-all text-xs text-slate-400">
              Account id: <code className="text-slate-300">{me.user_id}</code>{" "}
              <button type="button" className="underline hover:text-slate-200" onClick={copyId}>
                {copied ? "copied" : "copy"}
              </button>
            </p>
          )}
          {user && !guest && (
            <Button
              variant="secondary"
              className="mt-3 min-h-[44px]"
              onClick={async () => {
                await signOut();
                window.location.hash = "#/today";
                window.location.reload();
              }}
            >
              Sign out
            </Button>
          )}
        </Card>
      )}
      {!blocked && guest && <SaveAccount />}
      {guest && <EmailSignIn />}
    </div>
  );
}

function EmailSignIn() {
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);
  const id = useId();

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setMsg(null);
    try {
      await signInWithEmail(email.trim());
      setMsg({ ok: true, text: `Check ${email.trim()}: the link in that email signs you in here.` });
    } catch (err) {
      setMsg({ ok: false, text: err.message || "Could not send the sign-in link." });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card title="Sign in with email">
      <form onSubmit={submit}>
        <p className="text-sm text-slate-300">
          Already saved your starters with an email, or using another phone? We’ll email you a sign-in link.
        </p>
        <label htmlFor={id} className="mb-1 mt-3 block text-xs text-slate-300">
          Email
        </label>
        <Input
          id={id}
          type="email"
          autoComplete="email"
          required
          className="min-h-[44px] w-full text-base sm:text-sm"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <Button type="submit" className="mt-3 min-h-[44px] w-full" disabled={busy || !email.trim()}>
          {busy ? "Sending…" : "Email me a sign-in link"}
        </Button>
        {msg && (
          <p role={msg.ok ? "status" : "alert"} className={`mt-2 text-sm ${msg.ok ? "text-emerald-300" : "text-red-400"}`}>
            {msg.text}
          </p>
        )}
      </form>
    </Card>
  );
}
