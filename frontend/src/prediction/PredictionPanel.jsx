import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import ForecastChart from "./ForecastChart.jsx";
import Milestones from "./Milestones.jsx";
import ModelDetails, { Warnings } from "./ModelDetails.jsx";
import WhatIfControls, { horizonLabel } from "./WhatIfControls.jsx";
import { axisUnit, describeMilestone, duration, parseApiDate, TEMP_SOURCE_TEXT, timeLabel } from "./format.js";
import { formatC } from "./temperature.js";
import "./prediction.css";

const DEBOUNCE_MS = 450;

// Canonical series order per group: slots are assigned in this order and then
// stick to the series key for the life of the panel (colour follows the entity).
const CANON = {
  ph: ["ph"],
  density: ["gravity", "brix"],
  substrates: ["sugars_total", "sucrose", "hexoses", "glucose", "fructose", "lactose", "maltose", "starch", "protein"],
  products: ["lactic_acid", "acetic_acid", "ethanol", "gluconic_acid", "co2", "soluble_protein", "amino_acids"],
  growth: ["mycelium", "amylase", "protease", "peptidase", "fish_enzyme"],
};

const GROUP_ORDER = ["ph", "density", "growth", "substrates", "products", "population"];

// Readings a user can log that the model calibrates on.
const MEASURABLE = { ph: "pH", gravity: "gravity", brix: "Brix" };

const NO_REF_LINES = [];

// The exploratory explanation arrives as model.confidence_note (older API versions
// sent it as an "Exploratory: …" warning); it is shown once, in the calm exploratory
// note, never in the warning box.
const isExploratoryWarning = (w) => /^exploratory\b/i.test(w);

function chartMeta(group, unit) {
  switch (group) {
    case "ph":
      return { title: "pH", subtitle: "lower is more acidic" };
    case "density":
      return unit === "SG"
        ? { title: "Specific gravity", subtitle: "SG" }
        : { title: "Brix", subtitle: unit || "" };
    case "substrates":
      return { title: "Substrates", subtitle: `${unit} · what the microbes consume`, tab: "Substrates" };
    case "products":
      return { title: "Products", subtitle: `${unit} · what they make`, tab: "Products" };
    case "population":
      return { title: "Microbes", subtitle: "CFU/g, log scale", tab: "Microbes", logScale: true };
    case "growth":
      return {
        title: "Koji & enzymes",
        subtitle: "% of a fully grown koji (fish enzymes: of fresh whole fish)",
        tab: "Enzymes",
      };
    default:
      return { title: group, subtitle: unit, tab: group };
  }
}

function Skeleton() {
  return (
    <div className="animate-pulse space-y-4 motion-reduce:animate-none" aria-hidden="true">
      <div className="h-4 w-2/3 rounded bg-slate-800" />
      <div className="h-12 rounded-lg bg-slate-800/70" />
      <div className="h-28 rounded-xl bg-slate-800/70" />
      <div className="h-10 rounded-lg bg-slate-800/60" />
      <div className="h-48 rounded-lg bg-slate-800/50" />
    </div>
  );
}

function EncodingKey({ hasUnused }) {
  const item = "inline-flex items-center gap-1.5";
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-400" aria-label="How to read the charts" role="note">
      <span className={item}>
        <svg width="16" height="8" aria-hidden="true">
          <line x1="1" x2="15" y1="4" y2="4" stroke="#cbd5e1" strokeWidth="2" strokeLinecap="round" />
        </svg>
        model median
      </span>
      <span className={item}>
        <svg width="16" height="10" aria-hidden="true">
          <rect x="0" y="0" width="16" height="10" rx="2" fill="#cbd5e1" fillOpacity="0.25" />
        </svg>
        90 % range
      </span>
      <span className={item}>
        <svg width="10" height="10" aria-hidden="true">
          <circle cx="5" cy="5" r="4" fill="#f8fafc" />
        </svg>
        your reading
      </span>
      {hasUnused && (
        <span className={item}>
          <svg width="10" height="10" aria-hidden="true">
            <circle cx="5" cy="5" r="3.5" fill="none" stroke="#f8fafc" strokeWidth="1.5" />
          </svg>
          not used by the model
        </span>
      )}
      <span className={item}>
        <svg width="8" height="12" aria-hidden="true">
          <line x1="4" x2="4" y1="0" y2="12" stroke="#cbd5e1" strokeWidth="1" />
        </svg>
        now: reconstructed before, forecast after
      </span>
    </div>
  );
}

function Tabs({ charts, selected, onSelect, idBase }) {
  const refs = useRef([]);
  function onKeyDown(e, i) {
    let j = null;
    if (e.key === "ArrowRight") j = (i + 1) % charts.length;
    if (e.key === "ArrowLeft") j = (i - 1 + charts.length) % charts.length;
    if (e.key === "Home") j = 0;
    if (e.key === "End") j = charts.length - 1;
    if (j != null) {
      e.preventDefault();
      onSelect(charts[j].id);
      refs.current[j]?.focus();
    }
  }
  return (
    <div role="tablist" aria-label="More forecast charts" className="flex gap-1 border-b border-slate-800">
      {charts.map((c, i) => {
        const on = c.id === selected;
        return (
          <button
            key={c.id}
            ref={(el) => (refs.current[i] = el)}
            role="tab"
            id={`${idBase}-tab-${i}`}
            aria-selected={on}
            aria-controls={`${idBase}-panel`}
            tabIndex={on ? 0 : -1}
            onClick={() => onSelect(c.id)}
            onKeyDown={(e) => onKeyDown(e, i)}
            className={`-mb-px min-h-[44px] min-w-0 flex-1 border-b-2 px-1 text-[13px] sm:flex-none sm:px-3 sm:text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-emerald-400 ${
              on ? "border-emerald-400 font-medium text-slate-100" : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            {c.meta.tab}
          </button>
        );
      })}
    </div>
  );
}

/**
 * Fermentation forecast for a loaded batch: milestones headline, what-if
 * temperature, forecast window, one chart per series group, model details.
 * Fetches on mount; App remounts it on every batch reload.
 */
export default function PredictionPanel({ apiUrl, batchId, startedAt: batchStartedAt }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [override, setOverride] = useState(null); // committed what-if °C (null = batch's own)
  const [sliderValue, setSliderValue] = useState(null);
  const [horizon, setHorizon] = useState(null); // null = type default
  const [defaultHorizon, setDefaultHorizon] = useState(null);
  const [base, setBase] = useState({ temp: null, source: null });
  const [hover, setHover] = useState({ index: null, source: null });
  const [announce, setAnnounce] = useState("");
  const [tab, setTab] = useState(null);
  const [reloadToken, setReloadToken] = useState(0);
  const seqRef = useRef(0);
  const debounceRef = useRef(null);
  const userChangeRef = useRef(false);
  const slotsRef = useRef(new Map());

  useEffect(() => {
    const ctrl = new AbortController();
    const seq = ++seqRef.current;
    setLoading(true);
    const qs = new URLSearchParams();
    if (override != null) qs.set("temperature_c", String(override));
    if (horizon != null) qs.set("horizon_h", String(horizon));
    const url = `${apiUrl}/batches/${encodeURIComponent(batchId)}/prediction${qs.toString() ? `?${qs}` : ""}`;
    fetch(url, { signal: ctrl.signal })
      .then(async (res) => {
        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          const detail = typeof body.detail === "string" ? body.detail : null;
          throw new Error(
            res.status === 404 ? detail || "Batch not found" : detail || `The forecast is unavailable right now (${res.status}).`
          );
        }
        return res.json();
      })
      .then((json) => {
        if (seq !== seqRef.current) return; // a newer request superseded this one
        // started_at anchors every wall-clock date; fall back to the batch's own.
        if (json.started_at == null) {
          const derived = new Date(Date.now() - (json.now_h ?? 0) * 3600 * 1000).toISOString();
          json = { ...json, started_at: batchStartedAt ?? derived };
        }
        setData(json);
        setError(null);
        if (json.temperature?.source !== "override") {
          setBase({ temp: json.temperature?.forecast_c ?? null, source: json.temperature?.source ?? null });
          setSliderValue((v) => (override == null ? json.temperature?.forecast_c ?? v : v));
        }
        if (horizon == null) setDefaultHorizon(json.horizon_h);
        if (userChangeRef.current) {
          userChangeRef.current = false;
          const next = (json.milestones || [])
            .map((m) => ({ m, d: describeMilestone(m, json.now_h, json.horizon_h, json.started_at ?? batchStartedAt) }))
            .filter((x) => x.d.state === "soon" || x.d.state === "upcoming")
            .sort((a, b) => a.d.sortKey - b.d.sortKey)[0];
          setAnnounce(
            `Forecast updated for ${formatC(json.temperature?.forecast_c)}, ${horizonLabel(json.horizon_h)} window.` +
              (next ? ` ${next.m.title ?? next.m.label} ${next.d.when}.` : "")
          );
        }
      })
      .catch((e) => {
        if (e.name === "AbortError" || seq !== seqRef.current) return;
        setError(e instanceof TypeError ? "Could not reach the server." : e.message);
      })
      .finally(() => {
        if (seq === seqRef.current) setLoading(false);
      });
    return () => ctrl.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiUrl, batchId, override, horizon, reloadToken]);

  useEffect(() => () => clearTimeout(debounceRef.current), []);

  // New data can come on a different time grid (horizon change): drop the crosshair.
  useEffect(() => setHover({ index: null, source: null }), [data]);

  const onSlider = (v) => {
    setSliderValue(v);
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      userChangeRef.current = true;
      setOverride(base.temp != null && Math.abs(v - base.temp) < 1e-9 ? null : v);
    }, DEBOUNCE_MS);
  };

  const resetWhatIf = () => {
    clearTimeout(debounceRef.current);
    userChangeRef.current = true;
    setSliderValue(base.temp);
    setOverride(null);
  };

  const onHover = useCallback((index, source) => {
    setHover((prev) => {
      if (index == null) return prev.source === source ? { index: null, source: null } : prev;
      if (prev.index === index && prev.source === source) return prev;
      return { index, source };
    });
  }, []);

  const charts = useMemo(() => {
    if (!data?.series?.length) return [];
    const organismsOrder = (data.organisms || []).map((o) => o.series_key).filter(Boolean);
    const byId = new Map();
    for (const s of data.series) {
      const id = `${s.group}:${s.unit}`;
      if (!byId.has(id)) byId.set(id, { id, group: s.group, unit: s.unit, series: [] });
      byId.get(id).series.push(s);
    }
    const out = [...byId.values()];
    for (const c of out) {
      const canon = c.group === "population" ? organismsOrder : CANON[c.group] || [];
      const rank = (k) => {
        const i = canon.indexOf(k);
        return i === -1 ? 999 : i;
      };
      c.series.sort((a, b) => rank(a.key) - rank(b.key) || a.label.localeCompare(b.label));
      const slots = slotsRef.current.get(c.id) || new Map();
      slotsRef.current.set(c.id, slots);
      for (const s of c.series) {
        if (!slots.has(s.key)) {
          const used = new Set(slots.values());
          let slot = 1;
          while (used.has(slot) && slot < 8) slot++;
          slots.set(s.key, slot);
        }
      }
      c.series = c.series.map((s) => ({ ...s, slot: slots.get(s.key) }));
      c.meta = chartMeta(c.group, c.unit);
      c.observations = (data.observations || []).filter((o) => c.series.some((s) => s.key === o.key));
    }
    const gi = (g) => {
      const i = GROUP_ORDER.indexOf(g);
      return i === -1 ? 99 : i;
    };
    return out.sort((a, b) => gi(a.group) - gi(b.group));
  }, [data]);

  // Always visible: pH and density (what you can measure). Without a pH chart
  // (koji), the chart holding the first milestone's series takes its place.
  const primaryIds = useMemo(() => {
    const ids = new Set(charts.filter((c) => c.group === "ph" || c.group === "density").map((c) => c.id));
    if (!charts.some((c) => c.group === "ph") && charts.length) {
      const key = (data?.milestones || []).map((m) => m.threshold?.series).find(Boolean);
      ids.add((charts.find((c) => c.series.some((x) => x.key === key)) || charts[0]).id);
    }
    return ids;
  }, [charts, data]);
  const primary = charts.filter((c) => primaryIds.has(c.id));
  const secondary = charts.filter((c) => !primaryIds.has(c.id));
  const selectedTab = secondary.find((c) => c.id === tab)?.id ?? secondary[0]?.id;

  const shell = (children) => (
    <section
      className="ft-viz rounded-xl border border-slate-800 bg-slate-900/60 p-4"
      aria-labelledby="forecast-heading"
      aria-busy={loading}
    >
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 id="forecast-heading" className="text-sm font-semibold uppercase tracking-wide text-slate-400">
          Fermentation forecast
        </h2>
        {data?.model?.confidence === "exploratory" ? (
          <span className="rounded-full border border-sky-400/40 bg-sky-950/40 px-2 py-0.5 text-[11px] font-medium text-sky-200">
            Exploratory model
          </span>
        ) : (
          <span className="hidden rounded-full border border-slate-600 px-2 py-0.5 text-[11px] font-medium text-slate-300 sm:inline-block">
            Model estimate
          </span>
        )}
      </div>
      {children}
      <p className="sr-only" aria-live="polite">
        {announce}
      </p>
    </section>
  );

  if (!data) {
    if (error) {
      return shell(
        <div role="alert" className="rounded-lg border border-red-500/30 bg-red-950/30 p-3 text-sm text-red-300">
          <p>Could not load the forecast. {error}</p>
          <button
            type="button"
            onClick={() => setReloadToken((n) => n + 1)}
            className="mt-2 inline-flex min-h-[40px] items-center rounded-lg bg-slate-700 px-3 text-sm font-medium text-slate-100 hover:bg-slate-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400"
          >
            Try again
          </button>
        </div>
      );
    }
    return shell(
      <>
        <p className="sr-only">Loading the forecast…</p>
        <Skeleton />
      </>
    );
  }

  const usedObs = (data.observations || []).filter((o) => o.used).length;
  const temp = data.temperature || {};
  const isWhatIf = temp.source === "override";
  const pendingWhatIf =
    sliderValue != null && base.temp != null && Math.abs(sliderValue - base.temp) > 1e-9;
  const timeUnit = axisUnit(data.horizon_h);
  const choices = data.horizon_options_h?.length ? data.horizon_options_h : [data.horizon_h];
  const beyond = data.now_h > data.horizon_h;
  const hasUnused = (data.observations || []).some((o) => !o.used);
  const refLines = data.reference_lines || NO_REF_LINES;
  const exploratory = data.model?.confidence === "exploratory";
  const warnings = (data.warnings || []).filter((w) => !exploratory || !isExploratoryWarning(w));
  const exploratoryText =
    data.model?.confidence_note ||
    (data.warnings || []).find(isExploratoryWarning)?.replace(/^exploratory\s*[:.-]?\s*/i, "") ||
    "There is little published kinetic data for this ferment. Read the curves as a sketch of the mechanism, not a calibrated forecast.";
  const measurable = [...new Set((data.series || []).map((x) => x.key).filter((k) => MEASURABLE[k]))];

  const chartRefs = (c) => {
    const mine = refLines.filter((r) => c.series.some((x) => x.key === r.series));
    return mine.length ? mine : NO_REF_LINES;
  };

  const renderChart = (c) => {
    const lastObs = [...c.observations].sort((a, b) => b.t_h - a.t_h)[0];
    return (
      <ForecastChart
        key={c.id}
        id={c.id.replace(/[^a-z0-9]/gi, "_")}
        title={c.meta.title}
        subtitle={
          // A single series in a group chart gets named, since there is no legend.
          c.series.length === 1 && c.meta.tab ? `${c.series[0].label} · ${c.meta.subtitle}` : c.meta.subtitle
        }
        unit={c.unit}
        series={c.series}
        observations={c.observations}
        refLines={chartRefs(c)}
        nowH={data.now_h}
        horizonH={data.horizon_h}
        startedAt={data.started_at}
        timeUnit={timeUnit}
        logScale={!!c.meta.logScale}
        hoverIndex={hover.index}
        hoverSource={hover.source}
        onHover={onHover}
        aside={
          lastObs ? (
            <span className="text-xs text-slate-400">
              Latest reading <span className="font-medium text-slate-200">{lastObs.value}</span> ·{" "}
              {duration(data.now_h - lastObs.t_h)} ago
            </span>
          ) : null
        }
      />
    );
  };

  return shell(
    <div className="space-y-4">
      <div>
        <p className="text-sm text-slate-300">
          {data.status === "calibrated" ? (
            <>
              <span className="font-medium text-emerald-300">Calibrated</span> on {usedObs} of your measurement
              {usedObs === 1 ? "" : "s"}
            </>
          ) : (
            <>
              <span className="font-medium text-slate-200">Not calibrated yet</span>: literature values only
            </>
          )}
          <span className={isWhatIf ? "text-amber-200" : "text-slate-400"}>
            {" "}
            · assumes {formatC(temp.forecast_c)} from now on ({TEMP_SOURCE_TEXT[temp.source] || temp.source})
            {temp.readings > 0 &&
              `; ${temp.readings} logged temperature${temp.readings === 1 ? "" : "s"} used for the past`}
          </span>
        </p>
        {data.status === "prior_only" && (
          <p className="mt-1 text-xs text-slate-400">
            It shows what the literature expects for a typical {data.fermentation_type.replace(/_/g, " ")} batch.{" "}
            {measurable.length
              ? `Log a ${measurable.map((k) => MEASURABLE[k]).join(" or ")} reading to fit it to yours.`
              : "None of the readings you can log (pH, gravity, Brix) are modelled for this ferment yet, so it cannot be fitted to your batch."}
          </p>
        )}
      </div>

      <p className="border-l-2 border-slate-500 pl-3 text-xs leading-relaxed text-slate-300 sm:text-sm">
        {data.disclaimer}
        {data.model?.validated === false && " The model has not yet been validated against real batches."}
      </p>

      {error && (
        <div
          role="alert"
          className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-red-500/30 bg-red-950/30 px-3 py-2 text-sm text-red-300"
        >
          <span>Could not update the forecast. {error} Showing the previous result.</span>
          <button
            type="button"
            onClick={() => setReloadToken((n) => n + 1)}
            className="inline-flex min-h-[40px] items-center rounded-lg bg-slate-700 px-3 text-sm font-medium text-slate-100 hover:bg-slate-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400"
          >
            Try again
          </button>
        </div>
      )}

      {exploratory && (
        <div className="rounded-lg border border-sky-400/30 bg-sky-950/30 px-3 py-2 text-sm text-sky-100">
          <p>
            <span className="font-semibold">Exploratory model.</span>{" "}
            <span className="text-sky-100/90">{exploratoryText.charAt(0).toUpperCase() + exploratoryText.slice(1)}</span>
          </p>
        </div>
      )}

      <Warnings warnings={warnings} />

      <div className={`space-y-4 transition-opacity duration-300 ${loading ? "opacity-50" : ""}`}>
        {beyond && (
          <p className="rounded-lg border border-slate-700 bg-slate-800/40 px-3 py-2 text-sm text-slate-300">
            This batch started {duration(data.now_h)} ago, after the end of the forecast window (
            {horizonLabel(data.horizon_h)}). Pick a longer window below to see the model up to now.
          </p>
        )}
        <Milestones data={data} whatIf={isWhatIf ? formatC(temp.forecast_c) : null} exploratory={exploratory} />
      </div>

      <div className="rounded-xl border border-slate-800 bg-slate-950/40 p-3 sm:p-4">
        <WhatIfControls
          temperature={temp}
          baseTemp={base.temp}
          baseSource={base.source}
          value={sliderValue ?? temp.forecast_c}
          onChange={onSlider}
          onReset={resetWhatIf}
          overrideActive={pendingWhatIf || isWhatIf}
          horizon={data.horizon_h}
          horizonChoices={choices}
          onHorizon={(h) => {
            userChangeRef.current = true;
            setHorizon(defaultHorizon != null && Math.abs(h - defaultHorizon) < 1e-6 ? null : h);
          }}
        />
        <p className="mt-1 min-h-[1rem] text-xs text-slate-400" aria-hidden="true">
          {loading ? "Updating forecast…" : ""}
        </p>
      </div>

      {charts.length === 0 ? (
        <p className="text-sm text-slate-400">The model returned no curves for this batch.</p>
      ) : (
        <div className={`space-y-5 transition-opacity duration-300 ${loading ? "opacity-50" : ""}`}>
          <EncodingKey hasUnused={hasUnused} />
          {primary.map(renderChart)}
          {secondary.length > 1 && (
            <div>
              <Tabs charts={secondary} selected={selectedTab} onSelect={setTab} idBase="ft-more" />
              <div
                role="tabpanel"
                id="ft-more-panel"
                aria-labelledby={`ft-more-tab-${secondary.findIndex((c) => c.id === selectedTab)}`}
                className="pt-3"
              >
                {renderChart(secondary.find((c) => c.id === selectedTab))}
              </div>
            </div>
          )}
          {secondary.length === 1 && renderChart(secondary[0])}
        </div>
      )}

      <ModelDetails data={data} />
      <p className="text-[11px] text-slate-400">
        Times are {timeUnit === "h" ? "hours" : "days"} since the batch started ({timeLabel(0, timeUnit)} ={" "}
        {parseApiDate(data.started_at).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}).
      </p>
    </div>
  );
}
