import { useEffect, useId, useRef, useState } from "react";
import { Button } from "../components/ui.jsx";
import { getIngredients } from "./api.js";
import { AROMAS, FAMILY_GLOSS, LOW_RESOLUTION, MAX_INGREDIENTS, MAX_TARGETS, TASTES, toggleTarget } from "./ideas.js";

const MAX_MATCHES = 8;
const CHIP =
  "inline-flex min-h-[40px] items-center gap-1.5 rounded-full border px-3 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400";

function LowResBadge() {
  return (
    <>
      <span aria-hidden="true" className="rounded bg-slate-800 px-1 text-[10px] uppercase tracking-wide text-slate-300">
        low res
      </span>
      <span className="sr-only">, low resolution</span>
    </>
  );
}

// Must-include ingredients from the catalogue (GET /ingredients): type to filter, pick to add.
export function IngredientPicker({ value, onChange }) {
  const [names, setNames] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const [reload, setReload] = useState(0);
  const [query, setQuery] = useState("");
  const inputRef = useRef(null);
  const refocus = useRef(false);
  const id = useId();

  useEffect(() => {
    const ctrl = new AbortController();
    setLoadError(null);
    getIngredients(ctrl.signal)
      .then((rows) => setNames([...new Set(rows.map((r) => r.name))].sort((a, b) => a.localeCompare(b))))
      .catch((e) => e.name !== "AbortError" && setLoadError(e.message));
    return () => ctrl.abort();
  }, [reload]);

  // A removed chip takes focus with it: hand it to the search box once it is enabled again.
  useEffect(() => {
    if (refocus.current) inputRef.current?.focus();
    refocus.current = false;
  }, [value]);

  const q = query.trim().toLowerCase();
  const matches = q && names ? names.filter((n) => !value.includes(n) && n.toLowerCase().includes(q)).slice(0, MAX_MATCHES) : [];
  const full = value.length >= MAX_INGREDIENTS;

  function add(name) {
    if (!full) onChange([...value, name]);
    setQuery("");
    inputRef.current?.focus();
  }

  return (
    <div>
      <label htmlFor={`${id}-q`} className="mb-1 block text-sm font-medium text-slate-300">
        Ingredients you have <span className="font-normal text-slate-400">· optional</span>
      </label>
      <p id={`${id}-hint`} className="mb-2 text-xs text-slate-400">
        Every idea contains all of them, except staples (salt, water, sugar, flour, tea, starter cultures), which never
        narrow the search.
      </p>
      {value.length > 0 && (
        <ul aria-label="Chosen ingredients" className="mb-2 flex flex-wrap gap-2">
          {value.map((name) => (
            <li key={name}>
              <button
                type="button"
                onClick={() => {
                  refocus.current = true;
                  onChange(value.filter((n) => n !== name));
                }}
                aria-label={`Remove ${name}`}
                className={`${CHIP} border-emerald-500/40 bg-emerald-950/40 text-slate-100 hover:bg-emerald-900/40`}
              >
                {name}
                <span aria-hidden="true" className="text-slate-400">
                  ×
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {loadError ? (
        <div role="alert" className="rounded-lg border border-red-500/30 bg-red-950/30 p-3 text-sm text-red-300">
          <p>Could not load the ingredient catalogue: {loadError}</p>
          <Button type="button" variant="secondary" className="mt-2 min-h-[44px]" onClick={() => setReload((n) => n + 1)}>
            Try again
          </Button>
        </div>
      ) : (
        <>
          <input
            id={`${id}-q`}
            ref={inputRef}
            className="w-full rounded-lg border border-slate-600 bg-slate-950/50 px-3 py-2 text-base placeholder:text-slate-500 disabled:opacity-50 sm:text-sm"
            placeholder={names ? "Type to search, e.g. cabbage" : "Loading the catalogue…"}
            disabled={!names || full}
            value={query}
            autoComplete="off"
            aria-describedby={`${id}-hint ${id}-status`}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                if (matches[0]) add(matches[0]);
              }
              if (e.key === "Escape") setQuery("");
            }}
          />
          <p id={`${id}-status`} aria-live="polite" className="mt-1 min-h-[1rem] text-xs text-slate-400">
            {full
              ? `Up to ${MAX_INGREDIENTS} ingredients.`
              : q && names && matches.length === 0
                ? `No catalogue ingredient matches “${query.trim()}”.`
                : q && matches.length
                  ? `${matches.length} match${matches.length === 1 ? "" : "es"}: Enter adds the first.`
                  : ""}
          </p>
          {matches.length > 0 && (
            <ul aria-label="Matching ingredients" className="mt-1 divide-y divide-slate-800 overflow-hidden rounded-lg border border-slate-800">
              {matches.map((name) => (
                <li key={name}>
                  <button
                    type="button"
                    onClick={() => add(name)}
                    className="flex min-h-[44px] w-full items-center px-3 text-left text-sm hover:bg-slate-800 focus:outline-none focus-visible:bg-slate-800 focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-emerald-400"
                  >
                    <span className="sr-only">Add </span>
                    {name}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  );
}

// Up to 3 target aromas and tastes (design Q3, Q7), as toggle buttons.
export function TargetChips({ value, onChange }) {
  const full = value.length >= MAX_TARGETS;
  const id = useId();

  const chip = (key, kind) => {
    const on = value.some((t) => t.key === key);
    const blocked = full && !on;
    return (
      <button
        key={key}
        type="button"
        aria-pressed={on}
        aria-disabled={blocked || undefined}
        aria-describedby={blocked ? `${id}-count` : undefined}
        title={kind === "aroma" ? `Think ${FAMILY_GLOSS[key]}` : undefined}
        onClick={() => !blocked && onChange(toggleTarget(value, key, kind))}
        className={`${CHIP} ${
          on
            ? "border-emerald-400 bg-emerald-900/50 font-semibold text-slate-50"
            : blocked
              ? "cursor-not-allowed border-slate-800 text-slate-500"
              : "border-slate-600 text-slate-200 hover:bg-slate-800"
        }`}
      >
        {key}
        {LOW_RESOLUTION.has(key) && <LowResBadge />}
      </button>
    );
  };

  return (
    <fieldset>
      <legend className="mb-1 text-sm font-medium text-slate-300">
        Aromas and tastes to aim for <span className="font-normal text-slate-400">· up to {MAX_TARGETS}, optional</span>
      </legend>
      <p id={`${id}-count`} aria-live="polite" className="mb-2 text-xs text-slate-400">
        {value.length} of {MAX_TARGETS} chosen{full ? ": remove one to pick another." : "."}
      </p>
      <p id={`${id}-aromas`} className="mb-1 text-xs font-medium uppercase tracking-wide text-slate-400">
        Aromas
      </p>
      <div role="group" aria-labelledby={`${id}-aromas`} className="mb-3 flex flex-wrap gap-2">
        {AROMAS.map((key) => chip(key, "aroma"))}
      </div>
      <p id={`${id}-tastes`} className="mb-1 text-xs font-medium uppercase tracking-wide text-slate-400">
        Tastes
      </p>
      <div role="group" aria-labelledby={`${id}-tastes`} className="flex flex-wrap gap-2">
        {TASTES.map((key) => chip(key, "taste"))}
      </div>
      <p className="mt-2 text-xs text-slate-400">
        Low res: the model follows only one or two compounds for this aroma family, so its estimate is coarse.
      </p>
    </fieldset>
  );
}

// Proven only until the Experimental backend ships (B7): the other modes are shown, disabled.
export function ModeToggle() {
  const on = "bg-slate-700 font-semibold text-white";
  const base = "min-h-[40px] rounded-md px-3 text-sm";
  return (
    <fieldset>
      <legend className="mb-1 text-sm font-medium text-slate-300">Kind of idea</legend>
      <div className="inline-flex flex-wrap rounded-lg border border-slate-700 bg-slate-950/60 p-0.5">
        <button type="button" aria-pressed="true" className={`${base} ${on}`}>
          Proven
        </button>
        {["Experimental", "Both"].map((label) => (
          <button key={label} type="button" disabled className={`${base} text-slate-500`}>
            {label} <span className="text-xs">(coming soon)</span>
          </button>
        ))}
      </div>
      <p className="mt-1 text-xs text-slate-400">
        Proven: curated, cited recipes kept inside their documented ranges.
      </p>
    </fieldset>
  );
}
