import { useEffect, useState } from "react";
import { parseApiDate } from "../prediction/format.js";
import { Card } from "../shared.jsx";
import { getMyRecipes } from "./api.js";
import { PRIVACY_NOTICE, statusText } from "./community.js";

const TONE = {
  pending: "border-amber-500/40 text-amber-200",
  approved: "border-emerald-500/40 text-emerald-200",
  rejected: "border-red-500/40 text-red-300",
};
const day = (iso) => parseApiDate(iso).toLocaleDateString(undefined, { dateStyle: "medium" });

// Account: the recipes you published (GET /me/community-recipes), every status, newest first.
export default function MyRecipes({ admin = false }) {
  const [items, setItems] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    const ctrl = new AbortController();
    getMyRecipes(ctrl.signal)
      .then(setItems)
      .catch((e) => e.name !== "AbortError" && setError(e.message));
    return () => ctrl.abort();
  }, []);

  return (
    <Card title="Your community recipes">
      {error && (
        <p role="alert" className="text-sm text-red-400">
          Could not load them: {error}
        </p>
      )}
      {!items && !error && <p className="text-sm text-slate-400">Loading…</p>}
      {items?.length === 0 && (
        <p className="text-sm text-slate-400">
          None yet. A finished batch can be shared from its Recipe tab, once you have tasted it.
        </p>
      )}
      {items?.length > 0 && (
        <ul className="divide-y divide-slate-800">
          {items.map((r) => (
            <li key={r.id} className="py-2 text-sm">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <span className="font-medium text-slate-100">{r.title}</span>
                <span className={`rounded-full border px-2 py-0.5 text-xs ${TONE[r.status] ?? TONE.pending}`}>{statusText(r.status)}</span>
              </div>
              <p className="text-xs text-slate-400">
                by {r.pseudonym} · sent {day(r.created_at)}
                {r.reviewed_at ? ` · reviewed ${day(r.reviewed_at)}` : ""}
              </p>
              {r.reason && <p className="mt-1 text-xs text-slate-300">Reviewer’s note: {r.reason}</p>}
            </li>
          ))}
        </ul>
      )}
      <p className="mt-3 text-xs text-slate-400">{PRIVACY_NOTICE}</p>
      {admin && (
        <a href="#/admin/community" className="mt-3 inline-flex min-h-[44px] items-center text-sm text-emerald-400 underline hover:text-emerald-300">
          Review community recipes (admin)
        </a>
      )}
    </Card>
  );
}
