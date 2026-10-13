import { useEffect, useId, useRef, useState } from "react";
import { Button } from "../components/ui.jsx";
import { parseApiDate } from "../prediction/format.js";
import { formatC } from "../prediction/temperature.js";
import { Card, humanize } from "../shared.jsx";
import { approveRecipe, getReviewQueue, rejectRecipe } from "./api.js";
import { durationText, forecastJobText, gPerKgText, REASON_MAX, reasonError, statusText } from "./community.js";

const STATUSES = [
  ["pending", "Pending"],
  ["approved", "Approved"],
  ["rejected", "Rejected"],
];
const when = (iso) => parseApiDate(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });

function Review({ item, onChanged }) {
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState("");
  const [tried, setTried] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [said, setSaid] = useState("");
  const id = useId();
  const saidRef = useRef(null);
  const reasonRef = useRef(null);
  const rejectRef = useRef(null);
  const toggled = useRef(false);
  const reasonErr = reasonError(reason);

  // Reject… → the reason box; Cancel → back to Reject… (each unmounts the other).
  useEffect(() => {
    if (!toggled.current) return;
    toggled.current = false;
    (rejecting ? reasonRef : rejectRef).current?.focus();
  }, [rejecting]);
  const ask = (on) => {
    toggled.current = true;
    setRejecting(on);
  };

  async function act(fn, done) {
    setBusy(true);
    setError(null);
    try {
      const out = await fn();
      onChanged(out);
      setSaid(done(out));
      setRejecting(false);
      setReason("");
      setTried(false);
      requestAnimationFrame(() => saidRef.current?.focus());
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  const approve = () => act(() => approveRecipe(item.id), (out) => `Approved. ${forecastJobText(out.forecast_job)}`);
  function reject(e) {
    e.preventDefault();
    setTried(true);
    if (reasonErr) return;
    act(() => rejectRecipe(item.id, reason.trim()), () => "Rejected: its author reads your reason.");
  }

  return (
    <article aria-labelledby={`${id}-h`} className="space-y-2 rounded-lg border border-slate-800 bg-slate-950/40 p-3">
      <h3 id={`${id}-h`} className="font-display text-base font-bold text-slate-100">
        {item.title} <span className="text-sm font-normal text-slate-400">by {item.pseudonym}</span>
      </h3>
      <p className="text-sm text-slate-300">
        {humanize(item.fermentation_type)} · {formatC(item.temperature_c)} · {durationText(item.duration_h)} · sent{" "}
        {when(item.created_at)} · {statusText(item.status)}
      </p>
      <ul aria-label="Ingredients per kg" className="divide-y divide-slate-800/70 text-sm">
        {item.ingredients.map((i, n) => (
          <li key={`${i.name}-${n}`} className="flex justify-between gap-3 py-1">
            <span>
              {i.name} <span className="text-xs text-slate-400">{humanize(i.role)}</span>
              {i.label && <span className="block text-xs text-amber-200">{i.label}</span>}
            </span>
            <span className="tabular-nums text-slate-200">{gPerKgText(i.g_per_kg)}</span>
          </li>
        ))}
      </ul>
      <p className="text-xs text-slate-300">{forecastJobText(item.forecast_job)}</p>
      {item.reason && <p className="text-xs text-slate-300">Reason given: {item.reason}</p>}
      {item.source_batch_id ? (
        <a href={`#/batch/${item.source_batch_id}`} className="text-sm text-emerald-400 underline hover:text-emerald-300">
          Open the source batch (read-only)
        </a>
      ) : (
        <p className="text-xs text-slate-400">Its author deleted their account: the source batch is gone.</p>
      )}
      <p ref={saidRef} tabIndex={-1} role="status" className="text-sm text-emerald-300 focus:outline-none">
        {said}
      </p>
      {error && (
        <p role="alert" className="text-sm text-red-400">
          {error}
        </p>
      )}
      {rejecting ? (
        <form onSubmit={reject} noValidate className="space-y-2">
          <label htmlFor={`${id}-reason`} className="block text-xs text-slate-300">
            Why it is rejected (required; its author reads it)
          </label>
          <textarea
            id={`${id}-reason`}
            ref={reasonRef}
            rows={2}
            maxLength={REASON_MAX + 50}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            aria-invalid={tried && reasonErr ? "true" : undefined}
            aria-describedby={tried && reasonErr ? `${id}-reason-err` : undefined}
            className="w-full rounded-lg border border-slate-600 bg-slate-950/50 px-3 py-2 text-base sm:text-sm"
          />
          {tried && reasonErr && (
            <p id={`${id}-reason-err`} className="text-xs text-red-400">
              {reasonErr}
            </p>
          )}
          <div className="flex flex-wrap gap-2">
            <Button type="submit" className="min-h-[44px] bg-red-700 hover:bg-red-600" disabled={busy}>
              {busy ? "Rejecting…" : "Reject"}
            </Button>
            <Button type="button" variant="secondary" className="min-h-[44px]" disabled={busy} onClick={() => ask(false)}>
              Cancel
            </Button>
          </div>
        </form>
      ) : (
        <div className="flex flex-wrap gap-2">
          {item.status !== "approved" || item.forecast_job?.status === "failed" ? (
            <Button className="min-h-[44px]" disabled={busy} onClick={approve}>
              {busy ? "Approving…" : item.status === "approved" ? "Approve again (retry the forecast)" : "Approve"}
            </Button>
          ) : null}
          {item.status !== "rejected" && (
            <button
              ref={rejectRef}
              type="button"
              disabled={busy}
              onClick={() => ask(true)}
              className="min-h-[44px] rounded-lg bg-slate-700 px-3 py-2 text-sm font-medium hover:bg-slate-600 disabled:opacity-50"
            >
              Reject…
            </button>
          )}
        </div>
      )}
    </article>
  );
}

// #/admin/community (admins only): the community review queue (design § 10.3).
export default function AdminCommunity() {
  const [status, setStatus] = useState("pending");
  const [items, setItems] = useState(null);
  const [error, setError] = useState(null);
  const [reload, setReload] = useState(0);
  const id = useId();

  useEffect(() => {
    const ctrl = new AbortController();
    setError(null);
    getReviewQueue(status, ctrl.signal)
      .then(setItems)
      .catch((e) => e.name !== "AbortError" && setError(e.message));
    return () => ctrl.abort();
  }, [status, reload]);

  const changed = (out) => setItems((list) => list.map((x) => (x.id === out.id ? out : x)));

  return (
    <Card title="Community recipes: review">
      <p className="mb-3 text-sm text-slate-400">
        Approve to queue its forecasts and serve it under “Community — not proven”; reject with a reason its author reads.
        The automatic checks (safety gate, pH, tasting, mass balance) already passed when it was sent.
      </p>
      <fieldset className="mb-3">
        <legend className="mb-1 text-xs text-slate-400">Show</legend>
        <div className="inline-flex flex-wrap rounded-lg border border-slate-700 bg-slate-950/60 p-0.5">
          {STATUSES.map(([value, label]) => (
            <label key={value}>
              <input
                type="radio"
                name={`${id}-status`}
                value={value}
                checked={status === value}
                onChange={() => {
                  setItems(null);
                  setStatus(value);
                }}
                className="peer sr-only"
              />
              <span className="flex min-h-[40px] cursor-pointer items-center rounded-md px-3 text-sm text-slate-300 peer-checked:bg-slate-700 peer-checked:font-semibold peer-checked:text-white peer-focus-visible:ring-2 peer-focus-visible:ring-emerald-400">
                {label}
              </span>
            </label>
          ))}
        </div>
        <Button variant="secondary" size="sm" className="ml-2 min-h-[40px]" onClick={() => setReload((n) => n + 1)}>
          Refresh
        </Button>
      </fieldset>
      {error && (
        <p role="alert" className="text-sm text-red-400">
          Could not load the queue: {error}
        </p>
      )}
      {!items && !error && <p className="text-sm text-slate-400">Loading…</p>}
      {items?.length === 0 && <p className="text-sm text-slate-400">Nothing {status} right now.</p>}
      {items?.length > 0 && (
        <div className="space-y-3">
          {items.map((item) => (
            <Review key={item.id} item={item} onChanged={changed} />
          ))}
        </div>
      )}
    </Card>
  );
}
