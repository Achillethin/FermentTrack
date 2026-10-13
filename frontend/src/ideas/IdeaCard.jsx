import { useEffect, useId, useRef, useState } from "react";
import { Button } from "../components/ui.jsx";
import "../prediction/prediction.css"; // .ft-range, the app's slider
import { formatC } from "../prediction/temperature.js";
import { humanize } from "../shared.jsx";
import { postForecast, postStartBatch } from "./api.js";
import {
  aromaTempText,
  basisText,
  cardSource,
  chipText,
  fmtGrams,
  isTemperatureVariant,
  levelsLegend,
  likingText,
  madeText,
  plannerHref,
  scheduleText,
  targetLine,
  tierText,
  windowRows,
  withForecast,
} from "./ideas.js";

const DEBOUNCE_MS = 600;
const ACTION =
  "inline-flex min-h-[44px] items-center rounded-lg bg-emerald-700 px-4 text-sm font-medium text-white hover:bg-emerald-600";

const TAG_TONES = {
  neutral: "border-slate-700 text-slate-300",
  warn: "border-amber-500/40 text-amber-200",
  accent: "border-emerald-500/40 text-emerald-200",
};

function Tag({ tone = "neutral", children }) {
  return <span className={`inline-block rounded-full border px-2 py-0.5 text-xs ${TAG_TONES[tone]}`}>{children}</span>;
}

function Part({ title, children }) {
  return (
    <div>
      <h4 className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-slate-400">{title}</h4>
      {children}
    </div>
  );
}

const LEVEL_TONE = {
  High: "border-emerald-400/60 bg-emerald-950/50 text-emerald-100",
  Med: "border-slate-500 bg-slate-800/60 text-slate-100",
  Low: "border-slate-700 text-slate-300",
};

function Level({ level }) {
  if (!level) return null;
  return <span className={`rounded-md border px-1.5 py-0.5 text-xs font-semibold ${LEVEL_TONE[level]}`}>{level}</span>;
}

function Ingredients({ recipe }) {
  return (
    <ul className="divide-y divide-slate-800/70 text-sm">
      {recipe.ingredients.map((i, n) => (
        <li key={`${i.name}-${n}`} className="flex items-baseline justify-between gap-3 py-1.5">
          <span className="min-w-0">
            <span className="text-slate-100">{i.name}</span>{" "}
            <span className="text-xs text-slate-400">{humanize(i.role)}</span>{" "}
            {i.required === "optional" && <Tag>optional</Tag>}{" "}
            {!i.in_catalogue && <Tag tone="warn">not in the catalogue yet: Start batch skips it</Tag>}
            {i.label && <span className="block text-xs text-slate-400">{i.label}</span>}
          </span>
          <span className="shrink-0 tabular-nums text-slate-200">{fmtGrams(i.grams)}</span>
        </li>
      ))}
    </ul>
  );
}

function Facts({ recipe }) {
  const rows = [
    recipe.salt_pct != null && ["Salt", `${recipe.salt_pct} % of the batch`],
    recipe.sugar_pct != null && ["Sugar", `${recipe.sugar_pct} % of the batch`],
    recipe.starters.length > 0 && ["Starter", recipe.starters.join(", ")],
    ["Temperature", recipe.temp_schedule.length ? scheduleText(recipe.temp_schedule) : formatC(recipe.temperature_c)],
    recipe.stages && ["Stages", recipe.stages],
    recipe.aerobic && ["Vessel", "open to air (aerobic)"],
  ].filter(Boolean);
  return (
    <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
      {rows.map(([k, v]) => (
        <div key={k} className="contents">
          <dt className="text-slate-400">{k}</dt>
          <dd className="text-slate-200">{v}</dd>
        </div>
      ))}
    </dl>
  );
}

function TemperatureSlider({ min, max, value, moved, disabled = false, onChange, onReset }) {
  const id = useId();
  const inputRef = useRef(null);
  return (
    <div>
      <div className="flex items-baseline justify-between gap-3">
        <label htmlFor={id} className="text-sm font-medium text-slate-300">
          What if it ferments at
        </label>
        <output htmlFor={id} className={`text-lg font-semibold tabular-nums ${moved ? "text-amber-200" : "text-slate-100"}`}>
          {formatC(value)}
        </output>
      </div>
      <input
        ref={inputRef}
        id={id}
        type="range"
        min={min}
        max={max}
        step={0.1}
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        aria-valuetext={formatC(value)}
        className={`ft-range ${moved ? "is-override" : ""}`}
        style={{ "--band-lo": "0%", "--band-hi": "100%" }}
      />
      <div className="flex justify-between text-[11px] tabular-nums text-slate-400" aria-hidden="true">
        <span>{formatC(min)}</span>
        <span>{formatC(max)}</span>
      </div>
      {moved && (
        <button
          type="button"
          onClick={() => {
            onReset();
            inputRef.current?.focus(); // the button unmounts: keep focus on the slider
          }}
          className="mt-1 inline-flex min-h-[40px] items-center rounded-lg px-2 text-xs font-medium text-emerald-400 hover:text-emerald-300"
        >
          Back to the recipe as served
        </button>
      )}
    </div>
  );
}

const SECTION_TAG = {
  proven: ["accent", "Proven"],
  experimental: ["warn", "Experimental"],
  community: ["neutral", "Community — not proven"],
};

// An Experimental card's changes (design § 11.1): static chips, read in order.
function OperatorChips({ operators }) {
  if (!operators?.length) return null;
  return (
    <ul aria-label="Changes to the recipe" className="mt-2 flex flex-wrap gap-1.5">
      {operators.map((op) => (
        <li key={op.key} className="rounded-md border border-amber-500/40 bg-amber-950/20 px-2 py-0.5 text-sm text-amber-100">
          {chipText(op)}
        </li>
      ))}
    </ul>
  );
}

// "screened" until a live forecast confirms it; then "interaction detected" when flagged (§ 8.5).
function VariantStatus({ view }) {
  if (view.section !== "experimental") return null;
  if (view.screened) {
    return (
      <p className="text-xs text-amber-200">
        <Tag tone="warn">screened</Tag> Combined from single-change forecasts: confirm it with a live forecast.
      </p>
    );
  }
  if (view.interaction_detected) {
    return (
      <p className="text-xs text-amber-200">
        <Tag tone="warn">interaction detected</Tag> The live forecast is well below the screened estimate: the changes
        don’t add up as the screening assumed.
      </p>
    );
  }
  if (view.confirmed) {
    return (
      <p className="text-xs text-slate-300">
        <Tag>confirmed</Tag> Checked with a live forecast.
      </p>
    );
  }
  return null;
}

function CommunityLine({ community }) {
  const liking = likingText(community.mean_liking);
  return (
    <p className="mt-1 text-sm text-slate-300">
      by <span className="font-medium text-slate-100">{community.pseudonym}</span> · {madeText(community.made)}
      {liking ? ` · ${liking}` : ""}
    </p>
  );
}

// One idea card (design § 11.1): Proven, Experimental (a variant: operator chips, "screened"
// until confirmed) or Community. `query` is the request that produced it: the slider, the
// confirmation and Start batch reuse its targets, batch size and mode. onUseAsParent: a
// community card's "Use as a starting point".
export default function IdeaCard({ card, query, onUseAsParent }) {
  const [base, setBase] = useState(card); // the card as served (confirmed, once it is)
  const [tempC, setTempC] = useState(null); // null: the card as served
  const [view, setView] = useState(card);
  const [updating, setUpdating] = useState(false);
  const [forecastError, setForecastError] = useState(null);
  const [confirming, setConfirming] = useState(false);
  const [confirmError, setConfirmError] = useState(null);
  const [said, setSaid] = useState("");
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState(null);
  const [started, setStarted] = useState(null);
  const headingId = useId();
  const openBatchRef = useRef(null);
  const saidRef = useRef(null);
  const source = cardSource(card);

  useEffect(() => {
    if (tempC == null) return undefined;
    const ctrl = new AbortController();
    setUpdating(true);
    setForecastError(null);
    const t = setTimeout(() => {
      const body = { ...cardSource(base), aromas: query.aromas, tastes: query.tastes, temperature_c: tempC, batch_g: query.batch_g };
      postForecast(body, ctrl.signal)
        .then((fc) => !ctrl.signal.aborted && setView(withForecast(base, fc)))
        .catch((e) => e.name !== "AbortError" && setForecastError(e.message))
        .finally(() => !ctrl.signal.aborted && setUpdating(false));
    }, DEBOUNCE_MS);
    return () => {
      clearTimeout(t);
      ctrl.abort();
    };
  }, [tempC, base, query]);

  // Start batch unmounts once it succeeds: focus moves to the link that replaces it.
  useEffect(() => {
    if (started) openBatchRef.current?.focus();
  }, [started]);

  // Confirm requests in flight: aborted if the card goes away (a forecast changes nothing on the
  // server). mounted: Start batch's state updates only.
  const pending = useRef(new Set());
  const mounted = useRef(true);
  useEffect(() => {
    const inFlight = pending.current;
    mounted.current = true;
    return () => {
      mounted.current = false;
      inFlight.forEach((c) => c.abort());
    };
  }, []);
  const track = () => {
    const ctrl = new AbortController();
    pending.current.add(ctrl);
    return ctrl;
  };
  const untrack = (ctrl, settle) => {
    pending.current.delete(ctrl);
    if (!ctrl.signal.aborted) settle();
  };

  function reset() {
    setTempC(null);
    setView(base);
    setUpdating(false);
    setForecastError(null);
  }

  // Opening the forecast confirms a screened card (POST /recommendations/forecast, design § 10.1).
  async function confirm() {
    const ctrl = track();
    setConfirming(true);
    setConfirmError(null);
    try {
      const fc = await postForecast(
        {
          ...source,
          aromas: query.aromas,
          tastes: query.tastes,
          temperature_c: query.temperature_c,
          batch_g: query.batch_g,
        },
        ctrl.signal
      );
      const next = withForecast(base, fc);
      setBase(next);
      setView(next);
      setSaid(
        next.interaction_detected
          ? "Confirmed by a live forecast: interaction detected."
          : "Confirmed by a live forecast."
      );
      saidRef.current?.focus(); // the Confirm button is gone
    } catch (e) {
      if (e.name !== "AbortError") setConfirmError(e.message);
    } finally {
      untrack(ctrl, () => setConfirming(false));
    }
  }

  async function start() {
    setStarting(true);
    setStartError(null);
    try {
      // No AbortSignal: aborting would not cancel the server, which creates the batch anyway (a
      // remounted card would then offer Start batch again: a duplicate). Only state updates wait
      // for the card to be mounted.
      const out = await postStartBatch({
        ...source,
        aromas: query.aromas,
        tastes: query.tastes,
        temperature_c: tempC ?? query.temperature_c,
        batch_g: query.batch_g,
        // a variant is Experimental whatever the request's mode (search deeper runs from any)
        mode: card.section === "experimental" && query.mode === "proven" ? "experimental" : query.mode,
      });
      if (!mounted.current) return;
      if (out.skipped_ingredients.length) setStarted(out);
      else window.location.hash = `#/batch/${out.batch.id}`;
    } catch (e) {
      if (mounted.current) setStartError(e.message);
    } finally {
      if (mounted.current) setStarting(false);
    }
  }

  const section = card.section ?? "proven";
  const [tone, sectionLabel] = SECTION_TAG[section] ?? SECTION_TAG.proven;
  const planner = card.handoff === "planner";
  const plannerUrl = planner ? plannerHref(view.planner_link, window.location) : null;
  const slider = planner ? null : card.temperature.slider;
  const w = view.window;
  const basis = w && basisText(w, view.temperature);
  const aromaAt = aromaTempText(view.temperature);
  const stale = updating || confirming ? "opacity-60" : "";

  return (
    <article aria-labelledby={headingId} className="space-y-4 rounded-xl border border-slate-800 bg-slate-900/60 p-4 sm:p-5">
      <header>
        <div className="mb-1 flex flex-wrap items-center gap-1.5">
          <Tag tone={tone}>{sectionLabel}</Tag>
          <Tag>{humanize(card.fermentation_type)}</Tag>
          {card.style_region && <span className="text-xs text-slate-400">{card.style_region}</span>}
        </div>
        <h3 id={headingId} className="font-display text-lg font-bold text-slate-100">
          {card.name}
        </h3>
        {card.parent && <p className="text-sm text-slate-300">Variant of {card.parent.label}</p>}
        {card.community && <CommunityLine community={card.community} />}
        <OperatorChips operators={card.operators} />
        <div className="mt-2 space-y-1">
          <VariantStatus view={view} />
        </div>
        <p ref={saidRef} tabIndex={-1} role="status" className="text-xs text-slate-200 focus:outline-none">
          {said}
        </p>
      </header>

      {view.safety_lines.length > 0 && (
        <div className="rounded-lg border border-amber-500/40 bg-amber-950/30 p-3">
          <h4 className="mb-1 text-sm font-semibold text-amber-200">
            <span aria-hidden="true">⚠ </span>Safety
          </h4>
          <ul className="list-disc space-y-1 pl-5 text-sm text-amber-100">
            {view.safety_lines.map((line, i) => (
              <li key={i}>{line}</li>
            ))}
          </ul>
        </div>
      )}

      <Part title={`Recipe for ${fmtGrams(view.recipe.batch_g)}`}>
        <Ingredients recipe={view.recipe} />
        <Facts recipe={view.recipe} />
        {card.to_buy.length > 0 && <p className="mt-2 text-sm text-slate-300">To buy: {card.to_buy.join(", ")}</p>}
      </Part>

      <Part title={planner ? "When the levain is ready" : "When to taste"}>
        <div className={stale}>
          {w ? (
            <>
              <dl className="grid grid-cols-3 gap-2">
                {windowRows(w, planner).map((r) => (
                  <div key={r.label} className="rounded-lg border border-slate-800 bg-slate-950/40 px-2 py-2 text-center">
                    <dt className="text-xs text-slate-400">{r.label}</dt>
                    <dd className="font-display text-base font-bold tabular-nums text-slate-100">{r.text}</dd>
                  </div>
                ))}
              </dl>
              {basis && <p className="mt-1.5 text-xs text-slate-400">{basis}</p>}
              {w.notes.map((n, i) => (
                <p key={i} className={`text-xs text-slate-400 ${!basis && i === 0 ? "mt-1.5" : ""}`}>
                  {n}
                </p>
              ))}
            </>
          ) : (
            <p className="text-sm text-slate-300">{planner ? "Open the planner for the timing." : "No window at this temperature."}</p>
          )}
        </div>
        <div className="mt-3">
          {slider ? (
            <TemperatureSlider
              min={slider.min_c}
              max={slider.max_c}
              value={tempC ?? card.temperature.served_c}
              moved={tempC != null}
              disabled={confirming}
              onChange={setTempC}
              onReset={reset}
            />
          ) : (
            <p className="text-xs text-slate-400">
              {planner
                ? "The levain planner re-times the build at your temperature."
                : isTemperatureVariant(card)
                  ? "No temperature slider: this idea is itself a change of temperature."
                  : "No temperature slider: the documented range and safety limits leave no room to explore."}
            </p>
          )}
          {view.screened && !planner && tempC == null && (
            <Button
              variant="secondary"
              className="mt-2 min-h-[44px]"
              disabled={confirming || updating}
              onClick={confirm}
            >
              {confirming ? "Running the live forecast…" : "Open the forecast to confirm it"}
            </Button>
          )}
          <p aria-live="polite" className="min-h-[1rem] text-xs text-slate-300">
            {updating
              ? `Updating the forecast at ${formatC(tempC)}… this takes a few seconds.`
              : confirming
                ? "Running a live forecast to confirm this idea… this takes a few seconds."
                : ""}
          </p>
          {confirmError && (
            <p role="alert" className="text-xs text-red-400">
              Could not confirm it: {confirmError}. It is still the screened estimate; try again.
            </p>
          )}
          {forecastError && (
            <p role="alert" className="text-xs text-red-400">
              Could not update the forecast: {forecastError}. Still showing {formatC(view.temperature.served_c)}. Start
              batch waits for a forecast: move the slider again, or go back to the recipe as served.
            </p>
          )}
        </div>
      </Part>

      {view.targets.length > 0 && (
        <Part title="Your targets at the peak">
          <ul className={`space-y-1.5 text-sm ${stale}`}>
            {view.targets.map((t) => {
              const line = targetLine(t, view);
              return (
                <li key={t.key}>
                  <span className="flex flex-wrap items-center gap-1.5">
                    <span className="font-medium text-slate-100">{t.key}</span>
                    {t.low_resolution && <Tag>low resolution</Tag>}
                    {line.number ? (
                      <span className="font-semibold tabular-nums text-slate-100">{line.number}</span>
                    ) : (
                      <Level level={line.level} />
                    )}
                    <span className="text-slate-300">{line.text}</span>
                  </span>
                  {t.top_compound && (
                    <span className="block text-xs text-slate-400">
                      Led by {t.top_compound.name} ({tierText(t.top_compound.tier)})
                    </span>
                  )}
                </li>
              );
            })}
          </ul>
          <p className="mt-1.5 text-xs text-slate-400">
            {levelsLegend(view)}
            {aromaAt ? ` ${aromaAt}` : ""}
          </p>
        </Part>
      )}
      {card.not_modelled.length > 0 && (
        <p className="text-xs text-slate-400">No aroma data for: {card.not_modelled.join(", ")}.</p>
      )}

      <Part title="How far to trust this">
        <ul className="flex flex-wrap gap-1.5">
          {view.trust.labels.map((l) => (
            <li key={l}>
              <Tag>{l}</Tag>
            </li>
          ))}
        </ul>
        <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
          <dt className="text-slate-400">Provenance</dt>
          <dd className="text-slate-200">{humanize(card.trust.provenance)}</dd>
          <dt className="text-slate-400">Model confidence</dt>
          <dd className="text-slate-200">{card.trust.profile_confidence}</dd>
          {card.trust.sources.length > 0 && (
            <>
              <dt className="text-slate-400">Sources</dt>
              <dd className="break-words text-slate-200">{card.trust.sources.join(", ")}</dd>
            </>
          )}
        </dl>
        {view.notes.length > 0 && (
          <ul className="mt-2 space-y-0.5 text-xs text-slate-400">
            {view.notes.map((n, i) => (
              <li key={i}>{n}</li>
            ))}
          </ul>
        )}
      </Part>

      <div className="space-y-2 border-t border-slate-800 pt-3">
        {/* Mounted before it has text, so screen readers announce the message when it arrives. */}
        <p role="status" className="text-sm text-slate-200">
          {started
            ? `Batch started. Not booked, because they are not in the catalogue yet: ${started.skipped_ingredients.join(", ")}.`
            : ""}
        </p>
        <div className="flex flex-wrap items-center gap-3">
          {planner ? (
            plannerUrl ? (
              <a href={plannerUrl} className={ACTION}>
                Open in planner
              </a>
            ) : (
              <>
                <a href="#/levain" className={ACTION}>
                  Open the planner
                </a>
                <p className="text-xs text-slate-400">This recipe could not be passed on: pick {card.name} in the planner.</p>
              </>
            )
          ) : started ? (
            <a ref={openBatchRef} href={`#/batch/${started.batch.id}`} className={ACTION}>
              Open the batch
            </a>
          ) : (
            <Button
              size="lg"
              className="min-h-[44px]"
              disabled={starting || updating || confirming || Boolean(forecastError)}
              onClick={start}
            >
              {starting ? "Starting…" : tempC != null ? `Start batch at ${formatC(tempC)}` : "Start batch"}
            </Button>
          )}
          {card.community && onUseAsParent && (
            <Button variant="secondary" size="lg" className="min-h-[44px]" onClick={() => onUseAsParent(card.community)}>
              Use as a starting point
            </Button>
          )}
          {startError && (
            <p role="alert" className="text-sm text-red-400">
              Could not start the batch: {startError}
            </p>
          )}
        </div>
      </div>
    </article>
  );
}
