import SaveAccount from "./SaveAccount.jsx";
import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import { Button, Input } from "../components/ui.jsx";
import ForecastChart from "../prediction/ForecastChart.jsx";
import ModelDetails, { Warnings } from "../prediction/ModelDetails.jsx";
import { groupCharts } from "../prediction/PredictionPanel.jsx";
import { axisUnit, duration } from "../prediction/format.js";
import { valueAt } from "../prediction/scale.js";
import { formatC } from "../prediction/temperature.js";
import "../prediction/prediction.css";
import { getCatalog, getCultures, postBatch, postCulture, postFeedingChart, postPlan } from "./api.js";
import PlanForm, { Section, Toggle } from "./PlanForm.jsx";
import {
  CHART_RATIOS,
  blendOf,
  clock,
  closestRow,
  defaultForm,
  formToPlan,
  hoursUntil,
  num,
  seedKind,
  styleOf,
  toLocalInput,
} from "./plan.js";
import { buildIcs, planEvents, sharedForm, shareUrl } from "./share.js";

const DEBOUNCE_MS = 600;
const FORM_KEY = "ft.levain.form.v1";
const PRO_KEY = "ft.levain.pro";

// Per-viewer conveniences only: the page works the same without storage.
const load = (k) => {
  try {
    return window.localStorage.getItem(k);
  } catch {
    return null;
  }
};
const save = (k, v) => {
  try {
    window.localStorage.setItem(k, v);
  } catch {
    /* private mode: nothing to remember */
  }
};

export function useHash() {
  const [hash, setHash] = useState(window.location.hash);
  useEffect(() => {
    const f = () => setHash(window.location.hash);
    window.addEventListener("hashchange", f);
    return () => window.removeEventListener("hashchange", f);
  }, []);
  return hash;
}

// Start-screen entry point.
export function PlannerLink() {
  return (
    <a
      href="#/levain"
      className="flex min-h-[56px] items-center justify-between gap-3 rounded-xl border border-emerald-500/30 bg-emerald-950/30 px-4 py-3 hover:bg-emerald-950/50 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400"
    >
      <span>
        <span className="block font-display text-lg font-bold text-slate-100">Levain planner</span>
        <span className="block text-sm text-slate-300">
          When your levain peaks, which feed to use for your time, when bulk is done.
        </span>
      </span>
      <span aria-hidden="true" className="text-2xl text-emerald-300">
        →
      </span>
    </a>
  );
}

// Debounced POST that keeps the last good answer on screen while the next one loads.
function useDebounced(fetcher, body, reload) {
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const key = body ? JSON.stringify(body) : null;
  useEffect(() => {
    if (!key) {
      setBusy(false);
      return undefined;
    }
    const ctrl = new AbortController();
    setBusy(true);
    const t = setTimeout(() => {
      fetcher(JSON.parse(key), ctrl.signal)
        .then((json) => {
          setData(json);
          setError(null);
        })
        .catch((e) => e.name !== "AbortError" && setError(e.message))
        .finally(() => !ctrl.signal.aborted && setBusy(false));
    }, DEBOUNCE_MS);
    return () => {
      clearTimeout(t);
      ctrl.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, reload]);
  return { data, busy, error };
}

function Retry({ error, onRetry, what }) {
  return (
    <div role="alert" className="rounded-lg border border-red-500/30 bg-red-950/30 p-3 text-sm text-red-300">
      <p>
        Could not {what}: {error}
      </p>
      <Button variant="secondary" size="lg" className="mt-2 min-h-[44px]" onClick={onRetry}>
        Try again
      </Button>
    </div>
  );
}

// ── results ──────────────────────────────────────────────────────────────

function Headline({ label, when, range, sub }) {
  return (
    <div className="rounded-xl border border-emerald-500/25 bg-gradient-to-b from-emerald-950/50 to-slate-900/0 p-4">
      <p className="text-sm font-medium text-emerald-300/90">{label}</p>
      <p className="mt-0.5 font-display text-4xl font-extrabold tabular-nums tracking-tight text-white">{when}</p>
      {range && <p className="mt-1 text-sm text-slate-300">{range}</p>}
      {sub && <p className="mt-1 text-xs text-slate-400">{sub}</p>}
    </div>
  );
}

// Milestone band -> the headline's clock and range, in baker wording (Pro: model range).
function when(m, startMs, horizonH, pro, slower) {
  const t = m?.t_h || {};
  const c = (h) => clock(startMs, h);
  if (t.p50 == null) {
    return { when: `Not within ${duration(horizonH)}`, range: `It may not get there at this temperature. ${slower}` };
  }
  let range;
  if (t.p05 != null && t.p95 != null) range = pro ? `model range ${c(t.p05)}–${c(t.p95)} (90 %)` : `likely between ${c(t.p05)} and ${c(t.p95)}`;
  else if (t.p95 == null) range = pro ? `model range ${c(t.p05 ?? 0)} to beyond ${duration(horizonH)}` : `could run later than ${c(horizonH)}`;
  return { when: c(t.p50), range };
}

const PHASE_COLORS = ["bg-emerald-500", "bg-sky-600", "bg-slate-400", "bg-amber-600"];

function Phases({ phases, startMs }) {
  const t0 = phases[0].start_h;
  const total = phases[phases.length - 1].end_h - t0 || 1;
  return (
    <div>
      <div className="flex h-3 gap-0.5 overflow-hidden rounded-full" aria-hidden="true">
        {phases.map((p, i) => (
          <div
            key={p.key}
            className={PHASE_COLORS[i % PHASE_COLORS.length]}
            style={{ width: `${((p.end_h - p.start_h) / total) * 100}%` }}
          />
        ))}
      </div>
      <ol className="mt-2 divide-y divide-slate-800">
        {phases.map((p, i) => (
          <li key={p.key} className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5 py-2 text-sm">
            <span className="flex items-center gap-2">
              <span aria-hidden="true" className={`h-2.5 w-2.5 rounded-full ${PHASE_COLORS[i % PHASE_COLORS.length]}`} />
              <span className="font-medium text-slate-100">{p.label}</span>
              <span className="text-slate-400">{formatC(p.temperature_c)}</span>
            </span>
            <span className="tabular-nums text-slate-200">
              {clock(startMs, p.start_h)} → {clock(startMs, p.end_h)}
              <span className="text-slate-400"> · {duration(p.end_h - p.start_h)}</span>
            </span>
          </li>
        ))}
      </ol>
    </div>
  );
}

const SUMMARY_LABELS = [
  ["seed_ratio", "Feed ratio", ""],
  ["levain_hydration_pct", "Levain hydration", " %"],
  ["levain_pct_of_flour", "Levain, % of flour", " %"],
  ["dough_hydration_pct", "Dough hydration", " %"],
  ["salt_pct_of_flour", "Salt, % of flour", " %"],
  ["total_flour_g", "Total flour", " g"],
];

function Results({ data, startMs, pro, kind, busy }) {
  const [hover, setHover] = useState({ index: null, source: null });
  const slots = useRef(new Map());
  const charts = useMemo(() => groupCharts(data, slots.current), [data]);
  const onHover = useCallback((index, source) => {
    setHover((prev) => (index == null ? (prev.source === source ? { index: null, source: null } : prev) : { index, source }));
  }, []);
  useEffect(() => setHover({ index: null, source: null }), [data]);

  const ms = Object.fromEntries((data.milestones || []).map((m) => [m.key, m]));
  const phase = Object.fromEntries((data.phases || []).map((p) => [p.key, p]));
  const horizonH = data.horizon_h;
  const c = (h) => clock(startMs, h);
  const name = kind === "yeast" ? "Pre-ferment" : "Levain";
  const cards = [];
  if (ms.levain_peak) {
    const w = when(ms.levain_peak, startMs, horizonH, pro, "A warmer spot or a smaller feed speeds it up.");
    const doubled = ms.levain_doubled?.t_h?.p50;
    cards.push(
      <Headline key="peak" label={`${name} peaks at`} {...w} sub={doubled != null ? `Doubled by about ${c(doubled)}` : null} />
    );
  }
  if (ms.bulk_target) {
    const w = when(ms.bulk_target, startMs, horizonH, pro, "A warmer dough or more levain speeds it up.");
    const mix = phase.bulk?.start_h;
    const target = ms.bulk_target.threshold?.value;
    cards.push(
      <Headline
        key="bulk"
        label="Bulk done at"
        {...w}
        sub={[mix != null && `Mix at ${c(mix)}`, target != null && `at +${Math.round(target)} % rise`].filter(Boolean).join(" · ")}
      />
    );
  }
  if (phase.proof) {
    cards.push(
      <Headline
        key="bake"
        label="Into the oven around"
        when={c(phase.proof.end_h)}
        sub={`after ${duration(phase.proof.end_h - phase.proof.start_h)} ${phase.proof.label.toLowerCase()} at ${formatC(phase.proof.temperature_c)}`}
      />
    );
  }

  const shown = charts.filter((ch) => pro || ch.group === "rise" || ch.group === "ph");
  const startIso = new Date(startMs).toISOString();
  const timeUnit = axisUnit(horizonH);

  // Pro: what the levain is like when you use it.
  const atPeak = [];
  const peakH = ms.levain_peak?.t_h?.p50;
  if (pro && peakH != null) {
    for (const [key, label, unit, d] of [
      ["ph", "pH", "", 2],
      ["tta", "TTA", " mL", 1],
      ["fq", "Lactic : acetic", "", 1],
      ["rise", "Rise", " %", 0],
    ]) {
      const s = data.series.find((x) => x.key === key);
      if (s) atPeak.push([label, `${valueAt(s.t_h, s.p50, peakH).toFixed(d)}${unit}`]);
    }
  }

  return (
    <div className={`space-y-4 transition-opacity duration-300 ${busy ? "opacity-60" : ""}`}>
      {cards.length > 0 && <div className="grid gap-3 sm:grid-cols-2">{cards}</div>}
      <Warnings warnings={data.warnings} />
      <p className="border-l-2 border-slate-500 pl-3 text-xs leading-relaxed text-slate-300 sm:text-sm">
        {data.disclaimer}
        {data.model?.validated === false && " The model has not yet been checked against real bakes."}
      </p>
      {data.phases?.length > 0 && (
        <Section title="Timeline">
          <Phases phases={data.phases} startMs={startMs} />
        </Section>
      )}
      <section className="ft-viz space-y-5 rounded-xl border border-slate-800 bg-slate-900/60 p-4" aria-label="Charts">
        <p className="text-xs text-slate-400">
          Line: most likely. Shaded: {pro ? "model range (90 %)" : "where it will probably be"}. Hours from{" "}
          {kind === "yeast" ? "mixing" : "feeding"} at {c(0)}.
        </p>
        {shown.map((ch) => (
          <ForecastChart
            key={ch.id}
            id={`plan_${ch.id.replace(/[^a-z0-9]/gi, "_")}`}
            title={ch.meta.title}
            subtitle={ch.series.length === 1 && ch.meta.tab ? `${ch.series[0].label} · ${ch.meta.subtitle}` : ch.meta.subtitle}
            unit={ch.unit}
            series={ch.series}
            phases={data.phases || []}
            nowH={-1} // a plan has no "now": hides the now marker
            horizonH={horizonH}
            startedAt={startIso}
            timeUnit={timeUnit}
            logScale={!!ch.meta.logScale}
            hoverIndex={hover.index}
            hoverSource={hover.source}
            onHover={onHover}
          />
        ))}
      </section>
      {pro && (
        <Section title="Pro details">
          {atPeak.length > 0 && (
            <>
              <h3 className="text-sm font-medium text-slate-200">At the {name.toLowerCase()} peak ({c(peakH)})</h3>
              <dl className="mt-1 grid grid-cols-2 gap-x-4 gap-y-1 text-sm sm:grid-cols-4">
                {atPeak.map(([k, v]) => (
                  <div key={k}>
                    <dt className="text-xs text-slate-400">{k}</dt>
                    <dd className="tabular-nums text-slate-100">{v}</dd>
                  </div>
                ))}
              </dl>
            </>
          )}
          {data.summary && (
            <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1 text-sm sm:grid-cols-3">
              {SUMMARY_LABELS.filter(([k]) => data.summary[k] != null).map(([k, label, unit]) => (
                <div key={k}>
                  <dt className="text-xs text-slate-400">{label}</dt>
                  <dd className="tabular-nums text-slate-100">
                    {data.summary[k]}
                    {unit}
                  </dd>
                </div>
              ))}
            </dl>
          )}
          <h3 className="mt-4 text-sm font-medium text-slate-200">Milestones</h3>
          <ul className="divide-y divide-slate-800 text-sm">
            {(data.milestones || []).map((m) => {
              const t = m.t_h;
              return (
                <li key={m.key} className="flex flex-wrap justify-between gap-x-3 py-2">
                  <span className="text-slate-200">
                    {m.title}
                    {m.note && <span className="block text-xs text-slate-400">{m.note}</span>}
                  </span>
                  <span className="tabular-nums text-slate-100">
                    {t.p50 == null ? `not within ${duration(horizonH)}` : c(t.p50)}
                    {t.p50 != null && (
                      <span className="block text-right text-xs text-slate-400">
                        {t.p05 != null ? c(t.p05) : "…"}–{t.p95 != null ? c(t.p95) : "later"}
                      </span>
                    )}
                  </span>
                </li>
              );
            })}
          </ul>
          <div className="mt-3">
            <ModelDetails data={data} />
          </div>
        </Section>
      )}
    </div>
  );
}

// ── feeding chart ────────────────────────────────────────────────────────

function FeedingChart({ form, hydration, startMs, pro, onUse }) {
  const [reload, setReload] = useState(0);
  const [readyBy, setReadyBy] = useState("");
  const readyId = useId();
  const temp = num(form.levainTemp);
  const tempOk = temp >= 5 && temp <= 40;
  const hydOk = hydration >= 20 && hydration <= 300;
  const body =
    tempOk && hydOk
      ? {
          style: form.style,
          flour: blendOf(form),
          hydration_pct: Math.round(hydration * 10) / 10,
          temperature_c: temp,
          starter: form.starter,
          culture_id: form.cultureId || null,
          ratios: CHART_RATIOS,
        }
      : null;
  const { data, busy, error } = useDebounced(postFeedingChart, body, reload);
  const target = hoursUntil(startMs, readyBy);
  const best = data && target != null ? closestRow(data.rows, target) : -1;
  const bestRow = data?.rows[best];
  const c = (h) => clock(startMs, h);

  return (
    <Section
      title="Feeding chart"
      aside={
        <span aria-live="polite" className="text-xs text-slate-400">
          {busy ? "Updating…" : ""}
        </span>
      }
    >
      <p className="text-sm text-slate-300">
        Fed at <span className="font-semibold text-slate-100">{c(0)}</span>
        {tempOk && ` and kept at ${formatC(temp)}`}, each feed peaks around:
      </p>
      {!tempOk && <p className="mt-2 text-sm text-amber-200">The chart covers 5–40 °C.</p>}
      <div className="mt-3">
        <label htmlFor={readyId} className="mb-1 block text-xs text-slate-300">
          I want it ready by
        </label>
        <Input
          id={readyId}
          type="time"
          className="min-h-[44px] w-40 text-base sm:text-sm"
          value={readyBy}
          onChange={(e) => setReadyBy(e.target.value)}
        />
      </div>
      {bestRow && (
        <p className="mt-3 rounded-lg border border-emerald-500/30 bg-emerald-950/40 px-3 py-2 text-sm text-slate-100" aria-live="polite">
          Feed at {c(0)}, ready by {c(target)}: <span className="font-bold">use {bestRow.label}</span> (peaks around{" "}
          {c(bestRow.peak_h.p50)}).
          {Math.abs(bestRow.peak_h.p50 - target) > 1.5 && (
            <span className="block text-xs text-amber-200">
              None of these lands within 1.5 h of your time at {formatC(temp)}: a warmer or cooler spot shifts them all.
            </span>
          )}
        </p>
      )}
      {error && <div className="mt-3"><Retry error={error} what="load the feeding chart" onRetry={() => setReload((n) => n + 1)} /></div>}
      {!data && busy && <p className="mt-3 text-sm text-slate-400">Working out each feed…</p>}
      {data && (
        <div className={`mt-3 overflow-x-auto transition-opacity ${busy ? "opacity-60" : ""}`}>
          <table className="w-full text-left text-sm tabular-nums">
            <caption className="sr-only">Peak time for each feed ratio</caption>
            <thead className="text-xs text-slate-400">
              <tr>
                <th scope="col" className="py-1 pr-2 font-medium">Feed</th>
                <th scope="col" className="py-1 pr-2 font-medium">Peaks</th>
                <th scope="col" className="py-1 pr-2 font-medium">{pro ? "Range" : "Likely"}</th>
                {pro && <th scope="col" className="py-1 pr-2 font-medium">pH</th>}
                {pro && <th scope="col" className="py-1 pr-2 font-medium">Rise</th>}
                <th scope="col" className="py-1 font-medium"><span className="sr-only">Use</span></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {data.rows.map((r, i) => {
                const current = !form.custom && Math.abs(form.ratio - r.ratio) < 1e-9;
                return (
                  <tr key={r.ratio} className={i === best ? "bg-emerald-950/50" : undefined} aria-current={i === best ? "true" : undefined}>
                    <th scope="row" className="py-2 pr-2 font-semibold text-slate-100">
                      {r.label}
                      {i === best && <span className="block text-[11px] font-medium text-emerald-300">best for {readyBy}</span>}
                    </th>
                    <td className="py-2 pr-2 font-semibold text-slate-100">{r.peak_h.p50 == null ? "after 48 h" : c(r.peak_h.p50)}</td>
                    <td className="py-2 pr-2 text-xs text-slate-300">
                      {r.peak_h.p50 == null ? "–" : `${r.peak_h.p05 != null ? c(r.peak_h.p05) : "…"}–${r.peak_h.p95 != null ? c(r.peak_h.p95) : "later"}`}
                    </td>
                    {pro && <td className="py-2 pr-2 text-slate-300">{r.ph_at_peak.toFixed(2)}</td>}
                    {pro && <td className="py-2 pr-2 text-slate-300">{Math.round(r.rise_at_peak_pct)} %</td>}
                    <td className="py-1 text-right">
                      {current ? (
                        <span className="text-xs text-slate-400">yours</span>
                      ) : (
                        <Button variant="secondary" className="min-h-[44px] min-w-[3.5rem]" aria-label={`Use ${r.label}`} onClick={() => onUse(r.ratio)}>
                          Use
                        </Button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </Section>
  );
}

// ── track this bake ─────────────────────────────────────────────────────

function TrackBake({ plan, form, cultures, catalog, startMs, onOpenBatch }) {
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const nameId = useId();
  const culture = cultures.find((c) => c.id === form.cultureId);
  const offset = Math.abs(startMs - Date.now()) > 15 * 60_000;

  async function track() {
    setBusy(true);
    setError(null);
    try {
      let id = form.cultureId;
      if (!id) {
        if (!name.trim()) throw new Error("Give your starter a name");
        id = (await postCulture({ name: name.trim(), type: "sourdough", style: form.style })).id;
      }
      const batch = await postBatch({
        culture_id: id,
        sourdough_plan: plan,
        expected_temperature_c: plan.levain?.temperature_c ?? plan.dough?.temperature_c ?? null,
      });
      onOpenBatch(batch.id);
    } catch (e) {
      setError(e.message);
      setBusy(false);
    }
  }

  return (
    <Section title="Track this bake">
      <p className="text-sm text-slate-300">
        Log jar rise, pH or temperature as you go and the timings adjust to your {styleOf(catalog, form.style)?.seed === "starter" ? "starter" : "dough"}.
      </p>
      {culture ? (
        <p className="mt-2 text-sm text-slate-200">
          Saved under <span className="font-semibold">{culture.name}</span>.
        </p>
      ) : (
        <div className="mt-3">
          <label htmlFor={nameId} className="mb-1 block text-xs text-slate-300">
            Name your starter
          </label>
          <Input
            id={nameId}
            className="min-h-[44px] w-full text-base sm:text-sm"
            placeholder="e.g. Rye mother"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </div>
      )}
      {offset && (
        <p className="mt-2 text-xs text-amber-200">
          The bake’s clock starts when you tap; the planned time ({clock(startMs, 0)}) is only used on this page.
        </p>
      )}
      {error && (
        <p role="alert" className="mt-2 text-sm text-red-400">
          {error}
        </p>
      )}
      <Button size="lg" className="mt-3 min-h-[48px] w-full" disabled={busy || !plan} onClick={track}>
        {busy ? "Starting…" : "Start tracking now"}
      </Button>
      {!plan && <p className="mt-1 text-xs text-slate-400">Fix the highlighted fields first.</p>}
    </Section>
  );
}

// ── share and remind ────────────────────────────────────────────────────

function ShareBar({ plan, data, startMs, kind }) {
  const [msg, setMsg] = useState(null);
  useEffect(() => setMsg(null), [plan]);
  const events = data ? planEvents(data, startMs, kind === "yeast" ? "Pre-ferment" : "Levain") : [];

  async function share() {
    const url = shareUrl(plan, window.location);
    if (navigator.share) {
      try {
        await navigator.share({ title: "Levain plan", text: "My levain plan on FermentTrack", url });
        return;
      } catch (e) {
        if (e.name === "AbortError") return; // the baker closed the share sheet
      }
    }
    try {
      await navigator.clipboard.writeText(url);
      setMsg({ text: "Link copied." });
    } catch {
      setMsg({ text: "Copy this link:", url });
    }
  }

  function calendar() {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([buildIcs(events, startMs)], { type: "text/calendar;charset=utf-8" }));
    a.download = "levain-plan.ics";
    document.body.append(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 10_000);
  }

  return (
    <Section title="Share and remind">
      <p className="text-sm text-slate-300">
        Send this plan to a friend (the link holds the recipe only, not your starter or times), or put the timings in your
        calendar with an alert 15 minutes before each.
      </p>
      <div className="mt-3 grid gap-2 sm:grid-cols-2">
        <Button variant="secondary" size="lg" className="min-h-[48px]" onClick={share}>
          Share this plan
        </Button>
        <Button variant="secondary" size="lg" className="min-h-[48px]" disabled={!events.length} onClick={calendar}>
          Add to calendar
        </Button>
      </div>
      <div aria-live="polite" className="mt-2 text-sm text-slate-300">
        {msg?.text}
        {msg?.url && (
          <Input readOnly aria-label="Plan link" className="mt-1 w-full text-base sm:text-sm" value={msg.url} onFocus={(e) => e.target.select()} />
        )}
      </div>
    </Section>
  );
}

// ── screen ───────────────────────────────────────────────────────────────

function restoreForm(catalog) {
  try {
    const saved = JSON.parse(load(FORM_KEY) || "null");
    if (saved && styleOf(catalog, saved.style)) return { ...defaultForm(catalog, saved.style), ...saved, cultureId: "" };
  } catch {
    /* stale or corrupt: start fresh */
  }
  return null;
}

export default function Planner({ onOpenBatch }) {
  const [catalog, setCatalog] = useState(null);
  const [catalogError, setCatalogError] = useState(null);
  const [catalogReload, setCatalogReload] = useState(0);
  const [form, setForm] = useState(null);
  const [cultures, setCultures] = useState([]);
  const [pro, setPro] = useState(() => load(PRO_KEY) === "1");
  const [startAt, setStartAt] = useState(() => toLocalInput(new Date()));
  const [reload, setReload] = useState(0);
  const [opened, setOpened] = useState(false);
  const resultsRef = useRef(null);
  const hash = useHash();

  // braces: newer Chrome's scrollTo returns a Promise, which React would take for a cleanup
  useEffect(() => {
    window.scrollTo(0, 0);
  }, []);
  useEffect(() => {
    setCatalogError(null);
    getCatalog()
      .then((c) => {
        setCatalog(c);
        setForm((f) => f ?? restoreForm(c) ?? defaultForm(c, styleOf(c, "home_starter") ? "home_starter" : undefined));
      })
      .catch((e) => setCatalogError(e.message));
    getCultures()
      .then((cs) => setCultures(cs.filter((c) => c.type === "sourdough")))
      .catch(() => {});
  }, [catalogReload]);
  useEffect(() => {
    if (form) save(FORM_KEY, JSON.stringify(form));
  }, [form]);
  // A shared link (#/levain?p=...) replaces the form once, then leaves the URL so a
  // reload keeps the baker's own edits. Malformed links are ignored.
  useEffect(() => {
    if (!catalog || !hash.includes("?")) return;
    const shared = sharedForm(hash, catalog);
    if (shared) {
      setForm(shared);
      setOpened(true);
    }
    window.location.replace("#/levain");
  }, [hash, catalog]);

  const { plan, errors, info } = useMemo(
    () => (form && catalog ? formToPlan(form, catalog) : { plan: null, errors: {}, info: {} }),
    [form, catalog]
  );
  const { data, busy, error } = useDebounced(postPlan, plan, reload);
  const startMs = new Date(startAt).getTime();
  const kind = catalog && form ? seedKind(catalog, form.style) : "starter";
  const hydration = form?.custom ? info.levainHydration : num(form?.hydration);
  const peak = data?.milestones?.find((m) => m.key === "levain_peak")?.t_h?.p50;
  const bulk = data?.milestones?.find((m) => m.key === "bulk_target")?.t_h?.p50;

  const header = (
    <header className="flex items-center justify-between gap-3">
      <div className="min-w-0">
        <a href="#" className="inline-flex min-h-[44px] items-center text-sm text-slate-300 hover:text-slate-100">
          ← FermentTrack
        </a>
        <h1 className="font-display text-2xl font-extrabold tracking-tight">Levain planner</h1>
      </div>
      <Toggle
        label="Pro"
        checked={pro}
        onChange={(v) => {
          setPro(v);
          save(PRO_KEY, v ? "1" : "0");
        }}
      />
    </header>
  );

  if (!catalog || !form) {
    return (
      <main className="mx-auto max-w-2xl space-y-4 px-4 pb-16 pt-3">
        {header}
        {catalogError ? (
          <Retry error={catalogError} what="load the levain styles" onRetry={() => setCatalogReload((n) => n + 1)} />
        ) : (
          <p className="text-sm text-slate-400">Loading levain styles… the server can take a few seconds to wake up.</p>
        )}
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-2xl space-y-4 px-4 pb-28 pt-3">
      {header}
      <p className="max-w-[60ch] text-slate-300">
        Pick your style, say how you feed it, and see when it peaks and when the dough is ready, on the clock.
      </p>
      {opened && (
        <p role="status" className="rounded-lg border border-emerald-500/30 bg-emerald-950/40 px-3 py-2 text-sm text-slate-100">
          Opened a shared plan. Set when you feed it below.
        </p>
      )}

      <PlanForm
        catalog={catalog}
        form={form}
        onChange={setForm}
        errors={errors}
        info={info}
        pro={pro}
        cultures={cultures}
        startAt={startAt}
        onStartAt={setStartAt}
        afterLevain={
          kind === "starter" && (
            <FeedingChart
              form={form}
              hydration={hydration}
              startMs={startMs}
              pro={pro}
              onUse={(r) => setForm({ ...form, ratio: r, custom: false })}
            />
          )
        }
      />

      <div ref={resultsRef} className="scroll-mt-4 space-y-4">
        <h2 className="font-display text-xl font-bold text-slate-100">Your timings</h2>
        <p aria-live="polite" className="min-h-[1.25rem] text-sm text-slate-400">
          {!plan ? "Fix the highlighted fields to update the timings." : busy ? (data ? "Updating…" : "Working out your timings… the first one can take a few seconds.") : ""}
        </p>
        {error && <Retry error={error} what="work out the timings" onRetry={() => setReload((n) => n + 1)} />}
        {data && <Results data={data} startMs={startMs} pro={pro} kind={kind} busy={busy} />}
      </div>

      {plan && <ShareBar plan={plan} data={busy || error ? null : data} startMs={startMs} kind={kind} />}

      {plan && <TrackBake plan={plan} form={form} cultures={cultures} catalog={catalog} startMs={startMs} onOpenBatch={onOpenBatch} />}
      <SaveAccount />

      {/* Phone: the answer stays in view while editing the form. */}
      {data && (peak != null || bulk != null) && (
        <button
          type="button"
          onClick={() => resultsRef.current?.scrollIntoView({ behavior: "smooth" })}
          className="fixed inset-x-0 bottom-0 z-20 flex min-h-[56px] items-center justify-center gap-4 border-t border-slate-700 bg-slate-950/95 px-4 text-sm backdrop-blur focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-emerald-400"
        >
          {peak != null && (
            <span>
              <span className="text-slate-400">Peak </span>
              <span className="font-bold tabular-nums text-slate-50">{clock(startMs, peak)}</span>
            </span>
          )}
          {bulk != null && (
            <span>
              <span className="text-slate-400">Bulk done </span>
              <span className="font-bold tabular-nums text-slate-50">{clock(startMs, bulk)}</span>
            </span>
          )}
          <span className={busy ? "text-slate-400" : "text-emerald-300"}>{busy ? "updating…" : "details ↓"}</span>
        </button>
      )}
    </main>
  );
}
