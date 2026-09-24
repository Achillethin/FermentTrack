import { useId, useLayoutEffect, useMemo, useRef, useState } from "react";
import { linear, nearestIndex, niceTicks, timeTicks, valueAt } from "./scale.js";
import { fmtValue, timeLabel, unitSuffix, wallClock } from "./format.js";

const SUP = { "-": "⁻", 0: "⁰", 1: "¹", 2: "²", 3: "³", 4: "⁴", 5: "⁵", 6: "⁶", 7: "⁷", 8: "⁸", 9: "⁹" };
const pow10 = (n) => `10${String(n).replace(/./g, (c) => SUP[c] ?? c)}`;

export const seriesColor = (slot) => `var(--viz-s${slot})`;

// "Leuconostoc mesenteroides" -> "L. mesenteroides"; "CO₂ (cumulative)" -> "CO₂"
export function shortLabel(s) {
  const base = s.label.replace(/\s*\(.*\)\s*$/, "");
  if (s.key.startsWith("pop:")) {
    const parts = base.split(/\s+/);
    if (parts.length >= 2) return `${parts[0][0]}. ${parts.slice(1).join(" ")}`;
  }
  return base;
}

function useWidth(ref) {
  const [width, setWidth] = useState(0);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return undefined;
    setWidth(el.getBoundingClientRect().width);
    const ro = new ResizeObserver((entries) => setWidth(entries[0].contentRect.width));
    ro.observe(el);
    return () => ro.disconnect();
  }, [ref]);
  return width;
}

function pathFor(xs, ys, x, y, from = 0, to = xs.length - 1) {
  let d = "";
  for (let i = from; i <= to; i++) d += `${i === from ? "M" : "L"}${x(xs[i]).toFixed(1)},${y(ys[i]).toFixed(1)}`;
  return d;
}

function bandPath(xs, lo, hi, x, y) {
  let d = "";
  for (let i = 0; i < xs.length; i++) d += `${i ? "L" : "M"}${x(xs[i]).toFixed(1)},${y(hi[i]).toFixed(1)}`;
  for (let i = xs.length - 1; i >= 0; i--) d += `L${x(xs[i]).toFixed(1)},${y(lo[i]).toFixed(1)}`;
  return `${d}Z`;
}

const HALO = {
  paintOrder: "stroke",
  stroke: "var(--viz-surface)",
  strokeWidth: 3,
  strokeLinejoin: "round",
};

/**
 * One forecast chart: median line + 90 % band per series, observed points,
 * "now" split, optional reference lines, shared crosshair and tooltip.
 *
 * series: [{ key, label, unit, t_h, p05, p50, p95, slot }] (same t_h grid)
 */
export default function ForecastChart({
  id,
  title,
  subtitle,
  unit,
  series,
  observations = [],
  refLines = [],
  nowH,
  horizonH,
  startedAt,
  timeUnit,
  logScale = false,
  hoverIndex,
  hoverSource,
  onHover,
  aside,
}) {
  const wrapRef = useRef(null);
  const tipRef = useRef(null);
  const [tipW, setTipW] = useState(170);
  const width = useWidth(wrapRef);
  const titleId = useId();
  const summaryId = useId();
  const [hidden, setHidden] = useState(() => new Set());
  const [kbText, setKbText] = useState("");
  const multi = series.length > 1;
  const visible = series.filter((s) => !hidden.has(s.key));
  const grid = series[0]?.t_h ?? [];
  const nowClamped = Math.min(Math.max(nowH, 0), horizonH);

  const height = width > 520 ? 220 : 196;
  const margin = { top: 22, right: 10, bottom: 24, left: 36 };

  const yInfo = useMemo(() => {
    let lo = Infinity;
    let hi = -Infinity;
    for (const s of visible) {
      for (const v of s.p05) if (v < lo) lo = v;
      for (const v of s.p95) if (v > hi) hi = v;
    }
    for (const o of observations) {
      if (visible.some((s) => s.key === o.key)) {
        lo = Math.min(lo, o.value);
        hi = Math.max(hi, o.value);
      }
    }
    for (const r of refLines) {
      if (r.value > lo - (hi - lo) * 0.4 && r.value < hi + (hi - lo) * 0.4) {
        lo = Math.min(lo, r.value);
        hi = Math.max(hi, r.value);
      }
    }
    if (!Number.isFinite(lo)) return niceTicks(0, 1);
    if (!logScale && unit !== "" && unit !== "SG" && lo >= 0 && lo < (hi - lo) * 0.5) lo = 0;
    if (unit === "%" && hi > 95 && hi <= 102) hi = 100; // don't let 100.03 % open a 125 % axis
    const t = niceTicks(lo, hi, width > 520 ? 5 : 4);
    if (logScale && t.step < 1) return niceTicks(Math.floor(lo), Math.ceil(hi), 4);
    return t;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visible.map((s) => s.key).join("|"), series, observations, refLines, width, logScale, unit]);

  // One precision per chart (from all series, stable across legend toggles),
  // so values in the same tooltip line up: 2.4 / 1.8, not 2.4 / 1.80.
  const valueSpan = useMemo(() => {
    let lo = Infinity;
    let hi = -Infinity;
    for (const s of series) {
      for (const v of s.p05) if (v < lo) lo = v;
      for (const v of s.p95) if (v > hi) hi = v;
    }
    return Number.isFinite(hi - lo) ? hi - lo : 10;
  }, [series]);

  const tickText = (v) => {
    if (logScale && Number.isInteger(v)) return pow10(v);
    // Enough decimals to show the step exactly (2.5 -> "2.5", not "3"); SG always 3.
    let dec = 0;
    while (dec < 4 && Math.abs(Math.round(yInfo.step * 10 ** dec) - yInfo.step * 10 ** dec) > 1e-6) dec++;
    if (unit === "SG") dec = Math.max(dec, 3);
    return v.toFixed(dec);
  };
  margin.left = Math.max(28, Math.max(...yInfo.ticks.map((v) => tickText(v).length)) * 6.6 + 12);

  const innerW = Math.max(10, width - margin.left - margin.right);
  const innerH = height - margin.top - margin.bottom;
  const x = linear([0, horizonH], [margin.left, margin.left + innerW]);
  const y = linear(yInfo.domain, [margin.top + innerH, margin.top]);
  const xNow = x(nowClamped);
  const xTicks = timeTicks(horizonH, timeUnit, Math.max(3, Math.floor(innerW / 56)));
  const nowIdx = grid.length ? nearestIndex(grid, nowClamped) : 0;
  // Last grid index at or before now, for splitting the past/forecast lines.
  let splitIdx = 0;
  while (splitIdx + 1 < grid.length && grid[splitIdx + 1] <= nowClamped) splitIdx++;

  const clipId = `clip-${id}`;
  const showTooltip = hoverIndex != null && hoverSource === id && width > 0;
  const hoverT = hoverIndex != null ? grid[Math.min(hoverIndex, grid.length - 1)] : null;

  function indexFromEvent(e) {
    const rect = e.currentTarget.getBoundingClientRect();
    const px = e.clientX - rect.left;
    return nearestIndex(grid, x.invert(px));
  }

  function readout(i) {
    const t = grid[i];
    const parts = visible.map((s) => {
      const span = valueSpan;
      return `${s.label} ${fmtValue(s.p50[i], s.unit, span)}${unitSuffix(s.unit)}, range ${fmtValue(
        s.p05[i],
        s.unit,
        span
      )} to ${fmtValue(s.p95[i], s.unit, span)}`;
    });
    return `${timeLabel(t, timeUnit)}, ${t > nowH ? "forecast" : "reconstructed"}: ${parts.join("; ")}`;
  }

  function onKeyDown(e) {
    if (!grid.length) return;
    const cur = hoverIndex ?? nowIdx;
    let next = null;
    const big = Math.max(1, Math.round(grid.length / 12));
    if (e.key === "ArrowRight") next = Math.min(grid.length - 1, cur + (e.shiftKey ? big : 1));
    else if (e.key === "ArrowLeft") next = Math.max(0, cur - (e.shiftKey ? big : 1));
    else if (e.key === "Home") next = 0;
    else if (e.key === "End") next = grid.length - 1;
    else if (e.key === "Escape") {
      onHover(null, id);
      return;
    }
    if (next != null) {
      e.preventDefault();
      onHover(next, id);
      setKbText(readout(next));
    }
  }

  // Direct end labels for 2-4 visible series, skipped where they would collide.
  const endLabels = useMemo(() => {
    if (!multi || visible.length > 4 || width < 10) return [];
    const placed = [];
    const last = grid.length - 1;
    const sorted = [...visible].sort((a, b) => b.p50[last] - a.p50[last]);
    for (const s of sorted) {
      const lineY = y(s.p50[last]);
      // Above the line end; below it when the line runs along the top edge.
      const yy = lineY - 7 < margin.top + 10 ? lineY + 15 : lineY - 7;
      if (placed.some((p) => Math.abs(p.y - yy) < 13)) continue;
      placed.push({ key: s.key, y: yy, text: shortLabel(s), italic: s.key.startsWith("pop:") });
    }
    return placed;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visible.map((s) => s.key).join("|"), width, yInfo, series]);

  const obsHere = observations.filter((o) => visible.some((s) => s.key === o.key) && o.t_h <= horizonH);
  // Dense streams (e.g. a hydrometer logging every few hours) get smaller dots
  // so they read as a trace instead of a chain of overlapping rings.
  const obsDense = useMemo(() => {
    const xs = obsHere.map((o) => o.t_h).sort((a, b) => a - b);
    if (xs.length < 6) return false;
    const gaps = xs.slice(1).map((t, i) => t - xs[i]).sort((a, b) => a - b);
    return (gaps[gaps.length >> 1] / horizonH) * innerW < 10;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [observations, horizonH, innerW, hidden]);
  const lastObs = [...observations].sort((a, b) => b.t_h - a.t_h)[0];

  const summary = useMemo(() => {
    if (!grid.length) return "";
    const end = grid.length - 1;
    const bits = series.map((s) => {
      const f = (v) => fmtValue(v, s.unit, valueSpan);
      return `${s.label}: median ${f(s.p50[0])} at start, ${f(s.p50[nowIdx])} now (90 % range ${f(
        s.p05[nowIdx]
      )} to ${f(s.p95[nowIdx])}), ${f(s.p50[end])} at ${timeLabel(grid[end], timeUnit)} (range ${f(s.p05[end])} to ${f(
        s.p95[end]
      )})`;
    });
    const obs = observations.length
      ? ` ${observations.length} of your measurements are shown as dots${
          lastObs ? `; the latest is ${lastObs.value} at ${timeLabel(lastObs.t_h, timeUnit)}` : ""
        }.`
      : "";
    const refs = refLines.map((r) => ` A reference line marks ${r.label} at ${r.value}.`).join("");
    return `Model estimate${unit ? ` in ${unit}` : ""}. ${bits.join(". ")}.${obs}${refs}`;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [series, observations, nowIdx, timeUnit]);

  function toggle(key) {
    setHidden((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else if (series.length - next.size > 1) next.add(key);
      return next;
    });
  }

  // Tooltip beside the crosshair, on whichever side it fits, never past the chart.
  useLayoutEffect(() => {
    if (tipRef.current) setTipW(tipRef.current.offsetWidth);
  });
  const tipX = (() => {
    if (hoverT == null) return 0;
    const cx = x(hoverT);
    if (cx + 10 + tipW <= width) return cx + 10;
    if (cx - 10 - tipW >= 0) return cx - 10 - tipW;
    return Math.max(0, Math.min(width - tipW, cx - tipW / 2));
  })();
  const hoverObs =
    hoverT != null
      ? obsHere.find((o) => Math.abs(o.t_h - hoverT) <= Math.max(1, (grid[1] - grid[0]) * 0.75))
      : null;

  return (
    <figure className="min-w-0" aria-labelledby={titleId}>
      <figcaption className="mb-2 flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
        <span id={titleId} className="text-sm font-semibold text-slate-100">
          {title}
          {subtitle && <span className="ml-2 text-xs font-normal text-slate-400">{subtitle}</span>}
        </span>
        {aside}
      </figcaption>

      {multi && (
        <div className="-mx-1 mb-1 flex flex-wrap" role="group" aria-label={`Show or hide series in ${title}`}>
          {series.map((s) => {
            const on = !hidden.has(s.key);
            return (
              <button
                key={s.key}
                type="button"
                aria-pressed={on}
                onClick={() => toggle(s.key)}
                className={`group inline-flex min-h-[40px] items-center gap-2 rounded-lg px-2 text-xs focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400 ${
                  on ? "text-slate-200 hover:bg-slate-800/60" : "text-slate-400 line-through decoration-slate-500 hover:bg-slate-800/40"
                }`}
              >
                <span
                  aria-hidden="true"
                  className="inline-block h-[3px] w-4 rounded-full"
                  style={{ background: on ? seriesColor(s.slot) : "#475569" }}
                />
                <span className={s.key.startsWith("pop:") ? "italic" : undefined}>{s.label}</span>
              </button>
            );
          })}
        </div>
      )}

      <div
        ref={wrapRef}
        className="relative rounded-lg focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400"
        style={{ height, touchAction: "pan-y" }}
        tabIndex={0}
        role="img"
        aria-label={`${title} chart (model estimate). Arrow keys read values over time.`}
        aria-describedby={summaryId}
        onKeyDown={onKeyDown}
        onFocus={(e) => {
          // Keyboard focus only: a tap/click already placed the crosshair.
          if (!e.currentTarget.matches(":focus-visible")) return;
          if (hoverIndex == null || hoverSource !== id) {
            onHover(nowIdx, id);
            setKbText(readout(nowIdx));
          }
        }}
        onBlur={() => hoverSource === id && onHover(null, id)}
      >
        {width > 0 && grid.length > 0 && (
          <svg width={width} height={height} className="block select-none" aria-hidden="true">
            <defs>
              <clipPath id={clipId}>
                <rect x={margin.left} y={margin.top - 2} width={innerW} height={innerH + 4} />
              </clipPath>
            </defs>

            {/* reconstructed-past wash */}
            {nowClamped > 0 && (
              <rect
                x={margin.left}
                y={margin.top}
                width={Math.max(0, xNow - margin.left)}
                height={innerH}
                style={{ fill: "var(--viz-past-wash)" }}
              />
            )}

            {/* y grid */}
            {yInfo.ticks.map((v) => (
              <g key={v}>
                <line
                  x1={margin.left}
                  x2={margin.left + innerW}
                  y1={y(v)}
                  y2={y(v)}
                  style={{ stroke: v === yInfo.domain[0] ? "var(--viz-axis)" : "var(--viz-grid)" }}
                  strokeWidth={1}
                  shapeRendering="crispEdges"
                />
                <text
                  x={margin.left - 6}
                  y={y(v)}
                  dy="0.32em"
                  textAnchor="end"
                  className="ft-num"
                  style={{ fill: "var(--viz-text-muted)", fontSize: 11 }}
                >
                  {tickText(v)}
                </text>
              </g>
            ))}

            {/* x ticks */}
            {xTicks.map((t, i) => {
              const isLast = i === xTicks.length - 1 && x(t) > margin.left + innerW - 20;
              const val = timeUnit === "h" ? t : t / 24;
              return (
                <text
                  key={t}
                  x={x(t)}
                  y={height - 6}
                  textAnchor={i === 0 ? "start" : isLast ? "end" : "middle"}
                  className="ft-num"
                  style={{ fill: "var(--viz-text-muted)", fontSize: 11 }}
                >
                  {isLast || i === xTicks.length - 1 ? `${val} ${timeUnit === "h" ? "h" : "d"}` : val}
                </text>
              );
            })}

            <g clipPath={`url(#${clipId})`}>
              {/* 90 % bands */}
              {visible.map((s) => (
                <path
                  key={`b-${s.key}`}
                  className="ft-band"
                  d={bandPath(grid, s.p05, s.p95, x, y)}
                  style={{ fill: seriesColor(s.slot), fillOpacity: multi ? 0.13 : 0.2 }}
                />
              ))}

              {/* reference lines (e.g. pH 4.6) */}
              {refLines.map((r) =>
                r.value >= yInfo.domain[0] && r.value <= yInfo.domain[1] ? (
                  <line
                    key={`r-${r.value}`}
                    x1={margin.left}
                    x2={margin.left + innerW}
                    y1={y(r.value)}
                    y2={y(r.value)}
                    style={{ stroke: "var(--viz-ref)" }}
                    strokeOpacity={0.85}
                    strokeWidth={1.25}
                    strokeDasharray="5 4"
                  />
                ) : null
              )}

              {/* median lines: reconstructed past dimmed, forecast full strength */}
              {visible.map((s) => (
                <g key={`l-${s.key}`} className="ft-line" style={{ stroke: seriesColor(s.slot) }}>
                  <path
                    d={pathFor(grid, s.p50, x, y, 0, Math.min(splitIdx + 1, grid.length - 1))}
                    fill="none"
                    strokeWidth={2}
                    strokeOpacity={nowClamped > 0 ? 0.5 : 1}
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                  {splitIdx < grid.length - 1 && (
                    <path
                      d={pathFor(grid, s.p50, x, y, splitIdx, grid.length - 1)}
                      fill="none"
                      strokeWidth={2}
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  )}
                </g>
              ))}
            </g>

            {/* reference line labels, on top of the data with a halo */}
            {refLines.map((r) =>
              r.value >= yInfo.domain[0] && r.value <= yInfo.domain[1] ? (
                <text
                  key={`rl-${r.value}`}
                  x={margin.left + innerW - 4}
                  y={y(r.value) - 5}
                  textAnchor="end"
                  style={{ ...HALO, fill: "var(--viz-text-secondary)", fontSize: 11 }}
                >
                  {r.label}
                </text>
              ) : null
            )}

            {/* now marker, with the region labels beside it in the top margin */}
            {nowH >= 0 && nowH <= horizonH && (
              <g>
                <line
                  x1={xNow}
                  x2={xNow}
                  y1={margin.top - 5}
                  y2={margin.top + innerH}
                  style={{ stroke: "var(--viz-now)" }}
                  strokeWidth={1}
                  shapeRendering="crispEdges"
                />
                <text
                  x={xNow}
                  y={margin.top - 9}
                  textAnchor={xNow < margin.left + 18 ? "start" : xNow > margin.left + innerW - 18 ? "end" : "middle"}
                  style={{ fill: "var(--viz-text-primary)", fontSize: 11, fontWeight: 600 }}
                >
                  now
                </text>
                {xNow - margin.left > 128 && (
                  <text
                    x={xNow - 18}
                    y={margin.top - 9}
                    textAnchor="end"
                    style={{ fill: "var(--viz-text-muted)", fontSize: 10, letterSpacing: "0.05em" }}
                  >
                    ← RECONSTRUCTED
                  </text>
                )}
                {margin.left + innerW - xNow > 96 && (
                  <text
                    x={xNow + (xNow < margin.left + 18 ? 30 : 18)}
                    y={margin.top - 9}
                    style={{ fill: "var(--viz-text-muted)", fontSize: 10, letterSpacing: "0.05em" }}
                  >
                    FORECAST →
                  </text>
                )}
              </g>
            )}

            {/* direct end labels (multi-series) */}
            {endLabels.map((l) => (
              <text
                key={`el-${l.key}`}
                x={margin.left + innerW - 2}
                y={l.y}
                textAnchor="end"
                fontStyle={l.italic ? "italic" : undefined}
                style={{ ...HALO, fill: "var(--viz-text-secondary)", fontSize: 11 }}
              >
                {l.text}
              </text>
            ))}

            {/* observations: measured points wear ink with a surface ring */}
            {obsHere.map((o, i) => (
              <circle
                key={`o-${i}`}
                cx={x(o.t_h)}
                cy={y(o.value)}
                r={obsDense ? 2.25 : 4.5}
                style={{
                  fill: o.used ? "var(--viz-obs)" : "var(--viz-surface)",
                  stroke: o.used ? "var(--viz-surface)" : "var(--viz-obs)",
                }}
                strokeWidth={obsDense ? (o.used ? 0.75 : 1.25) : 2}
              />
            ))}

            {/* crosshair (shared across charts) */}
            {hoverT != null && (
              <g pointerEvents="none">
                <line
                  x1={x(hoverT)}
                  x2={x(hoverT)}
                  y1={margin.top}
                  y2={margin.top + innerH}
                  style={{ stroke: "var(--viz-crosshair)" }}
                  strokeOpacity={hoverSource === id ? 0.7 : 0.35}
                  strokeWidth={1}
                  shapeRendering="crispEdges"
                />
                {visible.map((s) => (
                  <circle
                    key={`h-${s.key}`}
                    cx={x(hoverT)}
                    cy={y(s.p50[hoverIndex])}
                    r={4}
                    style={{ fill: seriesColor(s.slot), stroke: "var(--viz-surface)" }}
                    strokeWidth={2}
                  />
                ))}
              </g>
            )}

            {/* hit layer: whole plot, pan-y keeps vertical page scroll on touch */}
            <rect
              x={margin.left}
              y={0}
              width={innerW}
              height={height}
              fill="transparent"
              style={{ touchAction: "pan-y", cursor: "crosshair" }}
              onPointerDown={(e) => onHover(indexFromEvent(e), id)}
              onPointerMove={(e) => {
                if (e.pointerType === "mouse" || e.buttons || e.pressure > 0) onHover(indexFromEvent(e), id);
              }}
              onPointerLeave={(e) => e.pointerType === "mouse" && onHover(null, id)}
            />
          </svg>
        )}

        {showTooltip && hoverT != null && (
          <div
            ref={tipRef}
            aria-hidden="true"
            className="pointer-events-none absolute z-10 w-max min-w-[9rem] max-w-[min(18rem,92%)] rounded-lg border border-slate-700 bg-slate-900/95 px-2.5 py-2 text-xs shadow-lg shadow-black/40 backdrop-blur"
            style={{ left: tipX, top: margin.top + 2 }}
          >
            <div className="mb-1 flex items-center justify-between gap-3">
              <span className="font-medium text-slate-200">{timeLabel(hoverT, timeUnit)}</span>
              <span className="text-[10px] uppercase tracking-wide text-slate-400">
                {hoverT > nowH ? "forecast" : "reconstructed"}
              </span>
            </div>
            <div className="mb-1.5 text-[11px] text-slate-400">{wallClock(startedAt, hoverT)}</div>
            <ul className="space-y-1">
              {visible.map((s) => {
                const span = valueSpan;
                return (
                  <li key={s.key} className="flex items-center gap-2">
                    <span
                      aria-hidden="true"
                      className="inline-block h-[3px] w-3 shrink-0 rounded-full"
                      style={{ background: seriesColor(s.slot) }}
                    />
                    <span className="ft-num whitespace-nowrap font-semibold text-slate-50">
                      {fmtValue(s.p50[hoverIndex], s.unit, span)}
                    </span>
                    <span className="ft-num whitespace-nowrap text-slate-400">
                      {fmtValue(s.p05[hoverIndex], s.unit, span)}–{fmtValue(s.p95[hoverIndex], s.unit, span)}
                    </span>
                    {(multi || s.label !== title) && (
                      <span className={`min-w-0 truncate text-slate-300 ${s.key.startsWith("pop:") ? "italic" : ""}`}>
                        {shortLabel(s)}
                      </span>
                    )}
                  </li>
                );
              })}
            </ul>
            {hoverObs && (
              <div className="mt-1.5 flex items-center gap-2 border-t border-slate-700/70 pt-1.5 text-slate-300">
                <span
                  aria-hidden="true"
                  className={`inline-block h-2 w-2 shrink-0 rounded-full ${
                    hoverObs.used ? "bg-slate-50" : "border border-slate-50"
                  }`}
                />
                <span>
                  Your reading <span className="ft-num font-semibold text-slate-50">{hoverObs.value}</span>
                  {!hoverObs.used && <span className="text-slate-400"> · not used by the model</span>}
                </span>
              </div>
            )}
          </div>
        )}
      </div>

      <p id={summaryId} className="sr-only">
        {summary}
      </p>
      <p className="sr-only" aria-live="polite">
        {kbText}
      </p>

      <ChartTable
        series={series}
        grid={grid}
        nowH={nowH}
        horizonH={horizonH}
        timeUnit={timeUnit}
        observations={observations}
        title={title}
        valueSpan={valueSpan}
      />
    </figure>
  );
}

function ChartTable({ series, grid, nowH, horizonH, timeUnit, observations, title, valueSpan }) {
  // Axis ticks plus "now"; a tick within 2 % of the window of now is replaced by it.
  const nowT = nowH > 0 && nowH < horizonH ? nowH : null;
  const times = useMemo(() => {
    let ts = timeTicks(horizonH, timeUnit, 7);
    if (nowT != null) ts = [...ts.filter((t) => Math.abs(t - nowT) > horizonH * 0.02), nowT];
    return ts.sort((a, b) => a - b);
  }, [horizonH, timeUnit, nowT]);

  return (
    <details className="group mt-1">
      <summary className="inline-flex min-h-[40px] cursor-pointer items-center gap-1 rounded text-xs text-slate-400 hover:text-slate-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400">
        <span aria-hidden="true" className="transition-transform group-open:rotate-90">
          ›
        </span>
        Table view
      </summary>
      <div className="overflow-x-auto">
        <table className="ft-num w-full min-w-max text-left text-xs">
          <caption className="sr-only">{title}: model median and 90 % range</caption>
          <thead className="text-slate-400">
            <tr>
              <th scope="col" className="py-1 pr-3 font-medium">
                Time
              </th>
              {series.map((s) => (
                <th key={s.key} scope="col" className="py-1 pr-3 font-medium">
                  {shortLabel(s)}
                  {s.unit && s.unit !== "SG" ? ` (${s.unit})` : ""}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800 text-slate-300">
            {times.map((t) => (
              <tr key={t} className={t === nowT ? "text-slate-100" : undefined}>
                <th scope="row" className="py-1 pr-3 font-normal text-slate-400">
                  {t === nowT ? `now (${timeLabel(t, timeUnit)})` : timeLabel(t, timeUnit)}
                </th>
                {series.map((s) => {
                  const f = (arr) => fmtValue(valueAt(grid, arr, t), s.unit, valueSpan);
                  return (
                    <td key={s.key} className="py-1 pr-3">
                      {f(s.p50)} <span className="text-slate-400">({f(s.p05)}–{f(s.p95)})</span>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
        {observations.length > 0 && (
          <p className="mt-1 text-xs text-slate-400">
            Your readings:{" "}
            {observations
              .map((o) => `${o.value} at ${timeLabel(o.t_h, timeUnit)}${o.used ? "" : " (not used)"}`)
              .join(", ")}
          </p>
        )}
      </div>
    </details>
  );
}
