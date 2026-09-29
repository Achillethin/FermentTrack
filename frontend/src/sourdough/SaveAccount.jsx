import { useEffect, useId, useState } from "react";
import { currentUser, saveWithEmail } from "../auth.js";
import { Button, Input } from "../components/ui.jsx";

// Anonymous sessions live in this browser only: Safari even clears them after 7 days
// without a visit. Offer to attach an email before a baker invests in tracked bakes.
export default function SaveAccount() {
  const [user, setUser] = useState(null);
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);
  const id = useId();

  useEffect(() => {
    let live = true;
    currentUser()
      .then((u) => {
        if (live) setUser(u);
      })
      .catch(() => {});
    return () => {
      live = false;
    };
  }, []);

  if (!user?.is_anonymous) return null;

  async function save(e) {
    e.preventDefault();
    setBusy(true);
    setMsg(null);
    try {
      await saveWithEmail(email.trim());
      setMsg({ ok: true, text: `Check ${email.trim()} for a link to confirm. Your starters stay with you.` });
    } catch (err) {
      setMsg({ ok: false, text: err.message || "Could not save the account." });
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={save} className="rounded-xl border border-amber-500/30 bg-amber-950/20 p-4">
      <h2 className="text-base font-semibold text-amber-100">Keep your starters</h2>
      <p className="mt-1 text-sm text-slate-300">
        Your bakes are saved in this browser only. Add your email so clearing it or changing phone
        doesn’t lose them.
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
        {busy ? "Sending…" : "Save my account"}
      </Button>
      {msg && (
        <p role={msg.ok ? "status" : "alert"} className={`mt-2 text-sm ${msg.ok ? "text-emerald-300" : "text-red-400"}`}>
          {msg.text}
        </p>
      )}
    </form>
  );
}
