import { forwardRef, useEffect, useId, useRef, useState } from "react";
import { Button } from "../components/ui.jsx";
import { AROMAS, TASTES } from "../ideas/ideas.js";
import { parseApiDate } from "../prediction/format.js";
import { Card } from "../shared.jsx";
import { deleteTasting, getTastings, postTasting } from "./api.js";
import {
  LIKINGS,
  likingWord,
  NOTES_MAX,
  phLine,
  RATINGS,
  ratingSummary,
  recommendedTargets,
  TASTING_KEYS,
  tastedWhen,
  tastingPayload,
} from "./tasting.js";

const PILL =
  "flex min-h-[40px] cursor-pointer items-center rounded-md px-2.5 text-sm text-slate-300 hover:text-slate-100 peer-checked:bg-slate-700 peer-checked:font-semibold peer-checked:text-white peer-focus-visible:ring-2 peer-focus-visible:ring-emerald-400";

// A radio group as a row of pills (arrow keys move the choice). options: [[value, label]].
// extra: a control after the pills (outside the legend, which names the group).
function Pills({ legend, name, value, options, onChange, extra }) {
  return (
    <fieldset>
      <legend className="mb-1 text-sm font-medium text-slate-200">{legend}</legend>
      <div className="flex flex-wrap items-center gap-2">
        <div className="inline-flex flex-wrap rounded-lg border border-slate-700 bg-slate-950/60 p-0.5">
          {options.map(([v, label]) => (
            <label key={String(v)}>
              <input type="radio" name={name} checked={value === v} onChange={() => onChange(v)} className="peer sr-only" />
              <span className={PILL}>{label}</span>
            </label>
          ))}
        </div>
        {extra}
      </div>
    </fieldset>
  );
}

const RATING_OPTIONS = [[null, "skip"], ...RATINGS.map(([n, word]) => [n, `${n} ${word}`])];

// targets: the keys the batch was recommended for (the preview's recommendation_targets), rated first.
function TastingForm({ batchId, startedAt, type, reminder, targets, onSaved }) {
  const [recalled] = useState(() => recommendedTargets(targets)); // the card's targets
  const [keys, setKeys] = useState(recalled); // the keys being rated: targets first
  const [ratings, setRatings] = useState({});
  const [adding, setAdding] = useState("");
  const [liking, setLiking] = useState(null);
  const [makeAgain, setMakeAgain] = useState(null);
  const [notes, setNotes] = useState("");
  const [tastedAt, setTastedAt] = useState("");
  const [errors, setErrors] = useState([]);
  const [busy, setBusy] = useState(false);
  const id = useId();
  const errorsRef = useRef(null);
  const addRef = useRef(null);
  const ph = phLine(type, reminder);
  const left = TASTING_KEYS.filter((k) => !keys.includes(k));

  function add() {
    if (!adding) return;
    setKeys((ks) => [...ks, adding]);
    setAdding("");
  }

  function removeKey(key) {
    setKeys((ks) => ks.filter((k) => k !== key));
    setRatings(({ [key]: _gone, ...rest }) => rest);
    addRef.current?.focus();
  }

  async function submit(e) {
    e.preventDefault();
    if (busy) return;
    const { body, errors: found } = tastingPayload(
      { ratings, liking, makeAgain, notes, tastedAt },
      { startedAt, now: Date.now() }
    );
    setErrors(found);
    if (!body) {
      requestAnimationFrame(() => errorsRef.current?.focus());
      return;
    }
    setBusy(true);
    try {
      const saved = await postTasting(batchId, body);
      setKeys(recalled);
      setRatings({});
      setLiking(null);
      setMakeAgain(null);
      setNotes("");
      setTastedAt("");
      onSaved(saved);
    } catch (err) {
      setErrors([err.message]);
      requestAnimationFrame(() => errorsRef.current?.focus());
    } finally {
      setBusy(false);
    }
  }

  const ratingGroup = (key, removable) => (
    <Pills
      key={key}
      legend={<span className="capitalize">{key}</span>}
      name={`${id}-${key}`}
      value={ratings[key] ?? null}
      options={RATING_OPTIONS}
      onChange={(v) => setRatings((r) => ({ ...r, [key]: v }))}
      extra={
        removable ? (
          <button
            type="button"
            onClick={() => removeKey(key)}
            aria-label={`Stop rating ${key}`}
            className="min-h-[40px] rounded px-2 text-xs text-slate-400 underline hover:text-slate-200"
          >
            remove
          </button>
        ) : null
      }
    />
  );

  return (
    <form onSubmit={submit} noValidate className="space-y-4">
      {ph && (
        <p className="rounded-lg border border-amber-500/40 bg-amber-950/30 p-3 text-sm font-medium text-amber-100">
          <span aria-hidden="true">⚠ </span>
          {ph}
        </p>
      )}
      <p className="text-xs text-slate-400">
        Rate what you notice: 0 not noticed, 1 faint, 2 clear, 3 strong. Your ratings check the recommender’s estimates;
        nobody else sees them.
      </p>
      {recalled.length > 0 && (
        <div className="space-y-3">
          <p className="text-sm font-medium text-slate-300">The targets this batch was recommended for</p>
          {keys.filter((k) => recalled.includes(k)).map((k) => ratingGroup(k, false))}
        </div>
      )}
      <div className="space-y-3">
        {keys.filter((k) => !recalled.includes(k)).map((k) => ratingGroup(k, true))}
        <div className="flex flex-wrap items-end gap-2">
          <div>
            <label htmlFor={`${id}-add`} className="mb-1 block text-xs text-slate-300">
              {recalled.length ? "Rate another aroma or taste" : "Rate an aroma or taste"}
            </label>
            <select
              id={`${id}-add`}
              ref={addRef}
              value={adding}
              onChange={(e) => setAdding(e.target.value)}
              className="min-h-[44px] rounded-lg border border-slate-600 bg-slate-950/50 px-3 text-base sm:text-sm"
            >
              <option value="">Choose…</option>
              <optgroup label="Aromas">
                {AROMAS.filter((k) => left.includes(k)).map((k) => (
                  <option key={k} value={k}>
                    {k}
                  </option>
                ))}
              </optgroup>
              <optgroup label="Tastes">
                {TASTES.filter((k) => left.includes(k)).map((k) => (
                  <option key={k} value={k}>
                    {k}
                  </option>
                ))}
              </optgroup>
            </select>
          </div>
          <Button type="button" variant="secondary" className="min-h-[44px]" disabled={!adding} onClick={add}>
            Add
          </Button>
        </div>
      </div>
      <Pills
        legend="How much did you like it?"
        name={`${id}-liking`}
        value={liking}
        options={[[null, "skip"], ...LIKINGS.map(([n, word]) => [n, `${n} ${word}`])]}
        onChange={setLiking}
      />
      <Pills
        legend="Would you make it again?"
        name={`${id}-again`}
        value={makeAgain}
        options={[
          [null, "not sure"],
          [true, "yes"],
          [false, "no"],
        ]}
        onChange={setMakeAgain}
      />
      <div>
        <label htmlFor={`${id}-notes`} className="mb-1 block text-xs text-slate-300">
          Notes <span className="text-slate-400">· optional, only for you</span>
        </label>
        <textarea
          id={`${id}-notes`}
          rows={2}
          maxLength={NOTES_MAX}
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          aria-describedby={`${id}-notes-count`}
          className="w-full rounded-lg border border-slate-600 bg-slate-950/50 px-3 py-2 text-base sm:text-sm"
        />
        <p id={`${id}-notes-count`} className="text-right text-xs text-slate-400">
          {[...notes].length} / {NOTES_MAX}
        </p>
      </div>
      <div>
        <label htmlFor={`${id}-when`} className="mb-1 block text-xs text-slate-300">
          When you tasted it <span className="text-slate-400">· leave empty for now</span>
        </label>
        <input
          id={`${id}-when`}
          type="datetime-local"
          value={tastedAt}
          onChange={(e) => setTastedAt(e.target.value)}
          className="min-h-[44px] rounded-lg border border-slate-600 bg-slate-950/50 px-3 text-base sm:text-sm"
        />
      </div>
      <div ref={errorsRef} tabIndex={-1} role={errors.length ? "alert" : undefined} className="focus:outline-none">
        {errors.length > 0 && (
          <ul className="list-disc space-y-0.5 pl-5 text-sm text-red-400">
            {errors.map((e) => (
              <li key={e}>{e}</li>
            ))}
          </ul>
        )}
      </div>
      <Button type="submit" size="lg" className="min-h-[44px]" disabled={busy}>
        {busy ? "Saving…" : "Save tasting"}
      </Button>
    </form>
  );
}

const SECONDARY_SM =
  "min-h-[40px] rounded-lg bg-slate-700 px-3 py-1.5 text-xs font-medium hover:bg-slate-600 disabled:opacity-50";

function TastingRow({ t, busy, onDelete }) {
  const [confirming, setConfirming] = useState(false);
  const confirmRef = useRef(null);
  const deleteRef = useRef(null);
  const toggled = useRef(false);
  // Delete → the confirm button; Keep it → back to Delete (each unmounts the other).
  useEffect(() => {
    if (toggled.current) (confirming ? confirmRef : deleteRef).current?.focus();
  }, [confirming]);
  const ask = (on) => {
    toggled.current = true;
    setConfirming(on);
  };
  const summary = ratingSummary(t.ratings);
  const liked = likingWord(t.liking);
  return (
    <li className="py-2 text-sm">
      <p className="font-medium text-slate-100">Tasted {tastedWhen(t.t_h)}</p>
      {summary && <p className="text-slate-300">{summary}</p>}
      <p className="text-xs text-slate-400">
        {[liked && `liked ${liked}`, t.make_again != null && (t.make_again ? "would make again" : "would not make again")]
          .filter(Boolean)
          .join(" · ")}
      </p>
      {t.notes && <p className="mt-1 whitespace-pre-line break-words text-xs text-slate-300">{t.notes}</p>}
      {confirming ? (
        <div className="mt-2 flex flex-wrap gap-2">
          <button
            ref={confirmRef}
            type="button"
            disabled={busy}
            onClick={() => onDelete(t)}
            className="min-h-[40px] rounded-lg bg-red-700 px-3 text-xs font-medium text-white hover:bg-red-600 disabled:opacity-50"
          >
            {busy ? "Deleting…" : "Delete this tasting"}
          </button>
          <button type="button" className={SECONDARY_SM} disabled={busy} onClick={() => ask(false)}>
            Keep it
          </button>
        </div>
      ) : (
        <button
          ref={deleteRef}
          type="button"
          className={`mt-2 ${SECONDARY_SM}`}
          onClick={() => ask(true)}
          aria-label={`Delete the tasting ${tastedWhen(t.t_h)}`}
        >
          Delete
        </button>
      )}
    </li>
  );
}

// A batch's tastings (design § 11.2): the form and the list (delete included). Owner only: an
// admin's read-only view never shows it. headingRef: BatchView moves focus here when prompting.
// reminder: the due stop-by reminder (its pH line); upcoming: one not due yet, only mentioned.
// targets: the preview's recommendation_targets (null: not started from a card).
export const TastingsCard = forwardRef(function TastingsCard({ batch, type, reminder, upcoming, targets, onChange }, headingRef) {
  const [list, setList] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const [said, setSaid] = useState("");
  const [deleting, setDeleting] = useState(null);
  const [deleteError, setDeleteError] = useState(null);
  const listRef = useRef(null);

  useEffect(() => {
    const ctrl = new AbortController();
    getTastings(batch.id, ctrl.signal)
      .then(setList)
      .catch((e) => e.name !== "AbortError" && setLoadError(e.message));
    return () => ctrl.abort();
  }, [batch.id]);

  function saved(t) {
    const next = [...(list ?? []), t].sort((a, b) => a.t_h - b.t_h);
    setList(next);
    setSaid("Tasting saved.");
    onChange(next.length, { saved: true });
    requestAnimationFrame(() => listRef.current?.focus());
  }

  async function remove(t) {
    setDeleting(t.id);
    setDeleteError(null);
    try {
      await deleteTasting(batch.id, t.id);
      const next = list.filter((x) => x.id !== t.id);
      setList(next);
      setSaid("Tasting deleted.");
      onChange(next.length, { saved: false });
      requestAnimationFrame(() => listRef.current?.focus());
    } catch (e) {
      setDeleteError(e.message);
    } finally {
      setDeleting(null);
    }
  }

  return (
    <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 sm:p-5">
      <h2 ref={headingRef} tabIndex={-1} className="mb-3 scroll-mt-20 font-display text-lg font-bold text-slate-100 focus:outline-none">
        Tasting
      </h2>
      {upcoming && (
        <p className="mb-3 text-sm text-slate-300">
          Tasting due {parseApiDate(upcoming.due_at).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}{" "}
          (the stop-by time).
        </p>
      )}
      <TastingForm
        batchId={batch.id}
        startedAt={batch.started_at}
        type={type}
        reminder={reminder}
        targets={targets}
        onSaved={saved}
      />
      <h3 ref={listRef} tabIndex={-1} className="mt-5 text-sm font-semibold text-slate-200 focus:outline-none">
        Your tastings{list ? ` (${list.length})` : ""}
      </h3>
      <p role="status" className="text-sm text-emerald-300">
        {said}
      </p>
      {loadError && (
        <p role="alert" className="text-sm text-red-400">
          Could not load the tastings: {loadError}
        </p>
      )}
      {deleteError && (
        <p role="alert" className="text-sm text-red-400">
          Could not delete it: {deleteError}
        </p>
      )}
      {list?.length === 0 && <p className="text-sm text-slate-400">None yet.</p>}
      {list?.length > 0 && (
        <ul className="divide-y divide-slate-800">
          {list.map((t) => (
            <TastingRow key={t.id} t={t} busy={deleting === t.id} onDelete={remove} />
          ))}
        </ul>
      )}
    </section>
  );
});

// Above the tabs: the stop-by reminder, or a finished batch not tasted yet (design § 11.2).
export const TastingPrompt = forwardRef(function TastingPrompt({ reason, reminder, onOpen }, ref) {
  if (!reason) return null;
  return (
    <Card title={reason === "reminder" ? "Time to taste" : "How did it turn out?"}>
      <div ref={ref} tabIndex={-1} className="space-y-2 text-sm text-slate-200 focus:outline-none">
        {reason === "reminder" ? (
          <p>{reminder.action}</p>
        ) : (
          <p>
            This batch is finished. Rate it in the tasting form: it checks the recommender’s estimates, and sharing it as a
            community recipe needs one.
          </p>
        )}
        <Button size="lg" className="min-h-[44px]" onClick={onOpen}>
          Fill in the tasting form
        </Button>
      </div>
    </Card>
  );
});
