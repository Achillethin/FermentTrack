import { useMemo, useRef, useState } from "react";
import { useWidth } from "./ForecastChart.jsx";
import { timeLabel } from "./format.js";
import { linear, nearestIndex } from "./scale.js";
import { AROMA_HEX, aromaBin, aromaRows, indexAt, stripColumns, topCompounds } from "./sensory.js";

const M = { left: 36, right: 10 }; // aligned with ForecastChart's plot area
const ROW = 36; // 14 px label + 20 px bars + 2 px gap
const THRESHOLD_LINE = [{ value: 0, label: "odour threshold", tone: "neutral" }];
const TIER_TEXT = {
  calibrated: "follows a published time course",
  reported: "reported in this ferment",
  plausible: "plausible: precursor and producer present, not yet reported",
  engine: "a main fermentation product",
};
const KIND_TEXT = { ingredient: "from", organism: "made by", chemistry: "chemistry:" };

/** P(noticeable) per aroma series over time: bar height = chance, colour = median strength. */
function AromaStrip({ rows, grid, nowH, horizonH, timeUnit, hoverIndex, onHover, series }) {
  const ref = useRef(null);
  const width = useWidth(ref);
  const innerW = Math.max(width - M.left - M.right, 10);
  const x = linear([0, horizonH], [M.left, M.left + innerW]);
  const cols = useMemo(() => stripColumns(grid), [grid]);
  const colW = Math.max(innerW / cols.length - 2, 1);
  const i = hoverIndex ?? indexAt(grid, nowH);
  const top = [...rows]
    .map((r) => ({ r, p: r.noticeable[i] ?? 0 }))
    .filter((x) => x.p >= 0.2)
    .sort((a, b) => b.p - a.p)
    .slice(0, 3);
  const move = (e) => {
    const px = e.clientX - e.currentTarget.getBoundingClientRect().left;
    onHover(nearestIndex(grid, x.invert(px)), "aroma");
  };
  const summary = `Aroma over time: ${rows
    .map((r) => `${r.label} most likely around ${timeLabel(r.peakT, timeUnit)} (${Math.round(r.peak * 100)} %)`)
    .join("; ")}. Model estimate.`;
  return (
    <div ref={ref}>
      <p className="mb-1 font-display text-sm font-bold text-slate-100">Aroma over time</p>
      {width > 0 && (
        <svg
          width={width}
          height={rows.length * ROW + 4}
          role="img"
          aria-label={summary}
          onPointerMove={move}
          onPointerLeave={() => onHover(null, "aroma")}
        >
          {rows.map((r, k) => (
            <g key={r.key} transform={`translate(0, ${k * ROW})`}>
              <text x={M.left} y={11} style={{ fill: "var(--viz-text-secondary)", fontSize: 11 }}>
                {r.label}
              </text>
              <line x1={M.left} x2={M.left + innerW} y1={34} y2={34} style={{ stroke: "var(--viz-axis)" }} />
              {cols.map((c) => {
                const p = r.noticeable[c] ?? 0;
                if (p < 0.01) return null;
                const bin = aromaBin(r.median[c] ?? -3);
                const h = p * 20;
                return (
                  <rect
                    key={c}
                    x={Math.min(Math.max(x(grid[c]) - colW / 2, M.left + 1), M.left + innerW - colW)}
                    y={34 - h}
                    width={colW}
                    height={h}
                    rx={1}
                    fill={AROMA_HEX[Math.max(bin, 1) - 1]}
                    fillOpacity={bin === 0 ? 0.45 : 1}
                  />
                );
              })}
            </g>
          ))}
          <line
            x1={x(nowH)}
            x2={x(nowH)}
            y1={0}
            y2={rows.length * ROW}
            style={{ stroke: "var(--viz-now)" }}
            strokeWidth={1}
          />
          {hoverIndex != null && (
            <line
              x1={x(grid[i])}
              x2={x(grid[i])}
              y1={0}
              y2={rows.length * ROW}
              style={{ stroke: "var(--viz-crosshair)" }}
              strokeDasharray="3 3"
            />
          )}
        </svg>
      )}
      <p className="text-xs text-slate-300" aria-live="polite">
        {timeLabel(grid[i] ?? 0, timeUnit)}:{" "}
        {top.length
          ? top
              .map(({ r, p }) => {
                const names = topCompounds(r, series, i, 2);
                return `${r.label} may be noticeable in ${Math.round(p * 100)} % of runs${
                  names.length ? ` (mostly ${names.join(", ")})` : ""
                }`;
              })
              .join("; ")
          : "no aroma likely above threshold"}
      </p>
      <p className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-slate-400">
        <span>Bar height = chance it is noticeable · colour = median strength:</span>
        {["×1", "×10", "×100", "×1000+"].map((t, k) => (
          <span key={t} className="inline-flex items-center gap-1">
            <span className="inline-block h-2 w-3 rounded-sm" style={{ background: AROMA_HEX[k] }} />
            {t}
          </span>
        ))}
        <span className="inline-flex items-center gap-1">
          <span className="inline-block h-2 w-3 rounded-sm" style={{ background: AROMA_HEX[0], opacity: 0.45 }} />
          median below threshold
        </span>
      </p>
      <details className="mt-1 text-xs text-slate-400">
        <summary className="cursor-pointer">Show as table</summary>
        <table className="ft-num mt-1">
          <thead>
            <tr>
              <th className="pr-3 text-left font-medium">Aroma</th>
              <th className="pr-3 text-right font-medium">Start</th>
              <th className="pr-3 text-right font-medium">Now</th>
              <th className="text-right font-medium">End</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.key}>
                <td className="pr-3">{r.label}</td>
                {[0, indexAt(grid, nowH), grid.length - 1].map((c, k) => (
                  <td key={k} className={k < 2 ? "pr-3 text-right" : "text-right"}>
                    {Math.round((r.noticeable[c] ?? 0) * 100)} %
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </div>
  );
}

function CompoundCard({ c }) {
  const thr = c.threshold;
  const lines = [];
  if (c.ph_corrected) lines.push("pH-corrected: only the un-ionised form is volatile.");
  if (c.tier === "calibrated" && ["shape", "semi"].includes(c.anchor))
    lines.push("The timing follows a published time course; the amount is a model estimate.");
  if (c.threshold_basis === "class" || c.threshold_basis === "est")
    lines.push("Threshold from a class range of similar compounds.");
  if (!thr) lines.push("No odour threshold known: shown as a concentration.");
  return (
    <li className="rounded-lg border border-slate-800 bg-slate-950/40 p-3 text-xs text-slate-300">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-sm font-medium text-slate-100">
          {c.pubchem ? (
            <a
              href={`https://pubchem.ncbi.nlm.nih.gov/compound/${c.pubchem}`}
              target="_blank"
              rel="noreferrer"
              className="underline decoration-slate-600 underline-offset-2 hover:decoration-slate-300"
            >
              {c.name}
            </a>
          ) : (
            c.name
          )}
        </p>
        <span className="rounded-full border border-slate-600 px-2 py-0.5 text-[10px] uppercase tracking-wide text-slate-300">
          {c.tier}
        </span>
      </div>
      <p className="mt-0.5 text-slate-400">
        {c.descriptor} · {TIER_TEXT[c.tier] || c.tier}
      </p>
      <ul className="mt-1 space-y-0.5">
        {c.routes.map((r) => (
          <li key={`${r.kind}-${r.name}-${r.via}`}>
            {KIND_TEXT[r.kind]} <span className="text-slate-100">{r.kind === "chemistry" ? r.via : r.name}</span>
            {r.kind !== "chemistry" && <span className="text-slate-400"> — {r.via}</span>}
          </li>
        ))}
      </ul>
      {thr && (
        <p className="ft-num mt-1 text-slate-400">
          Threshold in water ~{thr.p50} µg/kg (range {thr.lo}–{thr.hi})
          {c.peak_noticeable != null && ` · noticeable in up to ${Math.round(c.peak_noticeable * 100)} % of runs`}
        </p>
      )}
      {lines.map((l) => (
        <p key={l} className="mt-0.5 text-slate-400">
          {l}
        </p>
      ))}
      {c.sources.length > 0 && <p className="mt-1 text-[11px] text-slate-500">Sources: {c.sources.join(", ")}</p>}
    </li>
  );
}

/** One aroma series opened: its compounds' odour activity over time, then their cards. */
function Drilldown({ row, sensory, series, renderChart }) {
  const [showPlausible, setShowPlausible] = useState(false);
  const byKey = Object.fromEntries(sensory.compounds.map((c) => [c.key, c]));
  const bands = Object.fromEntries(series.map((s) => [s.key, s]));
  const members = row.compounds.map((k) => byKey[k]).filter(Boolean);
  const plausible = members.filter((c) => c.tier === "plausible");
  const shown = showPlausible ? members : members.filter((c) => c.tier !== "plausible");
  const lines = shown
    .map((c) => ({ c, band: bands[`odor:${c.key}`] }))
    .filter((x) => x.band)
    .sort((a, b) => Math.max(...b.band.p50) - Math.max(...a.band.p50))
    .slice(0, 7)
    .map(({ c, band }, k) => ({ ...band, slot: k + 1, dashed: c.tier === "plausible" }));
  const chart = {
    id: `aroma-${row.key}`,
    group: "aroma",
    unit: "× threshold",
    series: lines,
    observations: [],
    meta: { title: `${row.label}: compounds`, subtitle: "× odour threshold in water · log scale", logScale: true },
  };
  return (
    <div className="space-y-3 rounded-xl border border-slate-800 p-3">
      {lines.length > 0 && renderChart(chart, THRESHOLD_LINE)}
      {plausible.length > 0 && (
        <button
          type="button"
          onClick={() => setShowPlausible((v) => !v)}
          aria-pressed={showPlausible}
          className="min-h-[32px] rounded-full border border-slate-700 px-3 text-xs text-slate-300 hover:text-slate-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400"
        >
          {showPlausible ? "Hide" : "Show"} plausible compounds ({plausible.length}, dashed)
        </button>
      )}
      <ul className="grid gap-2 sm:grid-cols-2">
        {shown.map((c) => (
          <CompoundCard key={c.key} c={c} />
        ))}
      </ul>
    </div>
  );
}

/** The aroma strip over time and the drill-down of the open series. */
export default function Aroma({ sensory, series, nowH, horizonH, timeUnit, hoverIndex, onHover, openSeries, renderChart }) {
  const rows = aromaRows(sensory, series);
  if (!rows.length) return null;
  const grid = series.find((s) => s.key === `aroma:${rows[0].key}`)?.t_h || sensory.taste_phases?.t_h || [];
  const open = rows.find((r) => r.key === openSeries);
  return (
    <div className="space-y-4">
      <AromaStrip
        rows={rows}
        grid={grid}
        nowH={nowH}
        horizonH={horizonH}
        timeUnit={timeUnit}
        hoverIndex={hoverIndex}
        onHover={onHover}
        series={series}
      />
      {open && <Drilldown row={open} sensory={sensory} series={series} renderChart={renderChart} />}
    </div>
  );
}
