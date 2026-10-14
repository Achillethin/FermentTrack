import { useCallback, useEffect, useId, useReducer, useRef, useState } from "react";
import { Button } from "../components/ui.jsx";
import { getJob, getJobs, postDeepSearch } from "./api.js";
import {
  announceText,
  deepReducer,
  deepRequest,
  IDLE,
  isActive,
  nextPollIn,
  pollFailure,
  progressText,
  resumable,
} from "./deep.js";
import IdeaCard from "./IdeaCard.jsx";
import { searchSummary } from "./ideas.js";

const HIDDEN_KEY = "ft.deep-search.hidden"; // the finished search you hid, not offered again

function usePageVisible() {
  const [visible, setVisible] = useState(() => document.visibilityState === "visible");
  useEffect(() => {
    const on = () => setVisible(document.visibilityState === "visible");
    document.addEventListener("visibilitychange", on);
    return () => document.removeEventListener("visibilitychange", on);
  }, []);
  return visible;
}

const readHidden = () => {
  try {
    return localStorage.getItem(HIDDEN_KEY);
  } catch {
    return null;
  }
};

// Search deeper (design § 10.2): start (202, 200 or 409 → its job), poll every POLL_MS while the
// page is visible, stop once done or failed; on return, resume your newest search
// (GET /recommendations/jobs).
export function useDeepSearch() {
  const [state, dispatch] = useReducer(deepReducer, IDLE);
  const visible = usePageVisible();

  useEffect(() => {
    const ctrl = new AbortController();
    getJobs(ctrl.signal)
      .then((jobs) => {
        const job = resumable(jobs, { hidden: readHidden(), now: Date.now() });
        if (job) dispatch({ type: "resumed", job, at: Date.now() });
      })
      .catch(() => {}); // nothing to resume: the button is still there
    return () => ctrl.abort();
  }, []);

  useEffect(() => {
    const wait = nextPollIn(state, visible, Date.now());
    if (wait == null) return undefined;
    const ctrl = new AbortController();
    const timer = setTimeout(() => {
      getJob(state.jobId, ctrl.signal)
        .then((job) => dispatch({ type: "polled", job, at: Date.now() }))
        .catch((e) => e.name !== "AbortError" && dispatch(pollFailure(e, Date.now())));
    }, wait);
    return () => {
      clearTimeout(timer);
      ctrl.abort();
    };
  }, [state, visible]);

  const start = useCallback(async (query) => {
    dispatch({ type: "start", request: deepRequest(query) });
    try {
      const out = await postDeepSearch(deepRequest(query));
      dispatch({ type: "accepted", jobId: out.job_id, status: out.status });
    } catch (e) {
      if (e.status === 409 && e.detail?.job_id) {
        dispatch({ type: "accepted", jobId: e.detail.job_id, status: "queued", followed: true });
      } else dispatch({ type: "startFailed", message: e.message });
    }
  }, []);

  const hide = useCallback(() => {
    try {
      if (state.jobId) localStorage.setItem(HIDDEN_KEY, state.jobId);
    } catch {
      // not kept: it shows again on return
    }
    dispatch({ type: "reset" });
  }, [state.jobId]);

  const reset = useCallback(() => dispatch({ type: "reset" }), []);
  return { state, start, hide, reset };
}

// Under the results: the button, the waiting message and the confirmed cards, grouped by
// parent (those replacing a screened card of the same search are shown in its place).
// canStart: the results on screen may be searched deeper (no parent); sameAsResults: the job is
// the search the results on screen come from. onRetry: after an error, back to the button.
export function DeepSearchPanel({ deep, canStart, hasResults, sameAsResults, groups, onStart, onHide, onRetry }) {
  const { state } = deep;
  const headingId = useId();
  const job = state.job;
  const active = state.status === "starting" || isActive(state.status);
  const finished = state.status === "done" || state.status === "failed";
  const request = state.request ?? job?.request; // stable for a job (deep.js): cards depend on it
  const headingRef = useRef(null);
  const startRef = useRef(null);
  const noteRef = useRef(null);
  const startedHere = useRef(false);
  const retried = useRef(false);
  const [afterRetry, setAfterRetry] = useState(false); // "Try again" left no button to focus

  // The button unmounts once the search starts: focus moves to the panel's heading. After "Try
  // again", the button is back: focus moves to it; with no button (no results, or results from a
  // parent), to a status line saying why, never to <body>.
  useEffect(() => {
    if (startedHere.current && state.status !== "idle") {
      startedHere.current = false;
      headingRef.current?.focus();
    }
    if (retried.current && state.status === "idle") {
      retried.current = false;
      const button = startRef.current?.querySelector("button");
      if (button) button.focus();
      else setAfterRetry(true);
    }
  }, [state.status]);
  useEffect(() => {
    if (afterRetry) noteRef.current?.focus();
  }, [afterRetry]);
  useEffect(() => {
    if (state.status !== "idle" || canStart) setAfterRetry(false);
  }, [state.status, canStart]);

  // The button: with nothing searched yet, or once another request's search has finished.
  const offer = canStart && (state.status === "idle" || (finished && !sameAsResults));
  const startBlock = offer && (
    <div ref={startRef} className="rounded-xl border border-dashed border-slate-700 p-4">
      <p className="text-sm text-slate-300">Not what you wanted?</p>
      <Button
        variant="secondary"
        size="lg"
        className="mt-2 min-h-[44px]"
        onClick={() => {
          startedHere.current = true;
          onStart();
        }}
      >
        Search deeper — takes a few minutes
      </Button>
      <p className="mt-1 text-xs text-slate-400">
        Runs up to 20 live forecasts of untested combinations in the background. Results are kept: you can leave the page.
      </p>
    </div>
  );

  if (state.status === "idle") {
    if (startBlock) return startBlock;
    if (!afterRetry) return null;
    return (
      <p ref={noteRef} tabIndex={-1} role="status" className="rounded-xl border border-dashed border-slate-700 p-4 text-sm text-slate-300 focus:outline-none">
        {hasResults
          ? "Search deeper explores library recipes: set “Start from” back to library recipes, find ideas, then search deeper."
          : "Find ideas first, then you can search deeper."}
      </p>
    );
  }

  const count = groups.reduce((n, g) => n + g.cards.length, 0);
  return (
    <>
      {startBlock}
      <section aria-labelledby={headingId} aria-busy={active} className="space-y-4">
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
          <h2 ref={headingRef} tabIndex={-1} id={headingId} className="font-display text-lg font-bold text-slate-100 focus:outline-none">
            Search deeper <span className="text-sm font-normal text-slate-400">· Experimental, confirmed by live forecasts</span>
          </h2>
          {request && !sameAsResults && (
            <p className="mt-1 text-sm text-slate-300">
              {state.followed ? "Your search already running" : "Your earlier search"}: {searchSummary(request) || "—"}
            </p>
          )}
          {hasResults && !sameAsResults && active && (
            <p className="mt-1 text-xs text-slate-400">
              One deeper search runs at a time: once this one finishes, you can search deeper for the results above.
            </p>
          )}
          {state.status === "error" ? (
            <div role="alert" className="mt-2 text-sm text-red-400">
              <p>Could not search deeper: {state.error}</p>
              <Button
                variant="secondary"
                size="sm"
                className="mt-2 min-h-[40px]"
                onClick={() => {
                  retried.current = true;
                  onRetry();
                }}
              >
                Try again
              </Button>
            </div>
          ) : (
            <>
              <p className="mt-2 text-sm text-slate-200">{progressText(job)}</p>
              {job?.total > 0 && isActive(job.status) && (
                <progress
                  max={job.total}
                  value={job.done}
                  aria-label="Combinations explored"
                  className="mt-2 h-2 w-full overflow-hidden rounded [&::-moz-progress-bar]:bg-emerald-500 [&::-webkit-progress-bar]:bg-slate-800 [&::-webkit-progress-value]:bg-emerald-500"
                />
              )}
              {state.error && <p className="mt-1 text-xs text-amber-200">Could not check on the search ({state.error}); trying again.</p>}
            </>
          )}
          {/* What screen readers hear: news only, not every ETA tick. */}
          <p aria-live="polite" className="sr-only">
            {state.status === "error" ? "" : announceText(job)}
          </p>
          {finished && (
            <Button variant="secondary" size="sm" className="mt-3 min-h-[40px]" onClick={onHide}>
              Hide this search
            </Button>
          )}
        </div>
        {count > 0 &&
          groups.map((g) => (
            <section key={g.key} aria-label={`Variants of ${g.label}`} className="space-y-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Variants of {g.label}</p>
              {g.cards.map((card) => (
                <IdeaCard key={`deep-${card.id}`} card={card} query={request} />
              ))}
            </section>
          ))}
      </section>
    </>
  );
}
