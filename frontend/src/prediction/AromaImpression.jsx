import { useMemo, useRef } from "react";
import { useWidth } from "./ForecastChart.jsx";
import { timeLabel } from "./format.js";
import { linear, nearestIndex } from "./scale.js";
import { AROMA_HEX, aromaGrid, aromaImpression, aromaTimeline, impressionText, indexAt } from "./sensory.js";

const M = { left: 36, right: 10 }; // aligned with ForecastChart's plot area

/** Which families lead over time: one band, shaded by how far above threshold they are. */
function AromaTimeline({ spans, grid, nowH, horizonH, timeUnit, hoverIndex, onHover }) {
  const ref = useRef(null);
  const width = useWidth(ref);
  const innerW = Math.max(width - M.left - M.right, 10);
  const x = linear([0, horizonH], [M.left, M.left + innerW]);
  const summary = `Leading aroma over time: ${spans
    .map((s) => `${s.label} from ${timeLabel(s.start_h, timeUnit)}`)
    .join(", ")}. Model estimate.`;
  const move = (e) => {
    const px = e.clientX - e.currentTarget.getBoundingClientRect().left;
    onHover(nearestIndex(grid, x.invert(px)), "aroma");
  };
  return (
    <div ref={ref}>
      {width > 0 && (
        <svg
          width={width}
          height={46}
          role="img"
          aria-label={summary}
          onPointerMove={move}
          onPointerLeave={() => onHover(null, "aroma")}
        >
          {spans.map((s) => (
            <rect
              key={`${s.id}-${s.start_h}`}
              x={x(s.start_h)}
              y={2}
              height={22}
              width={Math.max(x(s.end_h) - x(s.start_h), 0.5)}
              fill={s.strength ? AROMA_HEX[s.strength - 1] : "var(--viz-grid)"}
            />
          ))}
          <line x1={x(nowH)} x2={x(nowH)} y1={0} y2={26} style={{ stroke: "var(--viz-now)" }} strokeWidth={1} />
          {hoverIndex != null && grid[hoverIndex] != null && (
            <line
              x1={x(grid[hoverIndex])}
              x2={x(grid[hoverIndex])}
              y1={0}
              y2={26}
              style={{ stroke: "var(--viz-crosshair)" }}
              strokeDasharray="3 3"
            />
          )}
          {spans.map((s) =>
            x(s.end_h) - x(s.start_h) > 7 * s.label.length ? (
              <text
                key={`t-${s.id}-${s.start_h}`}
                x={(x(s.start_h) + x(s.end_h)) / 2}
                y={40}
                textAnchor="middle"
                style={{ fill: "var(--viz-text-secondary)", fontSize: 11 }}
              >
                {s.label}
              </text>
            ) : null
          )}
        </svg>
      )}
      <p className="text-xs text-slate-300">
        {spans.map((s, k) => (
          <span key={`l-${s.id}-${s.start_h}`}>
            {k > 0 && <span className="text-slate-500"> → </span>}
            <span className="text-slate-400">{timeLabel(s.start_h, timeUnit)}</span> {s.label}
          </span>
        ))}
      </p>
    </div>
  );
}

/**
 * The aroma in everyday words: what this batch may come across as now and at the end of
 * the window, and which families lead over time. Compound-level estimate, not perception.
 */
export default function AromaImpression({ sensory, series, nowH, horizonH, timeUnit, hoverIndex, onHover }) {
  const grid = aromaGrid(sensory, series);
  const spans = useMemo(() => aromaTimeline(sensory, series), [sensory, series]);
  if (!grid.length || !sensory.aroma_series?.length) return null;
  const at = (t) => impressionText(aromaImpression(sensory, series, indexAt(grid, t)));
  const lines = [
    ["Now", sensory.now_h],
    ["End of window", sensory.end_h],
  ];
  const hovered = hoverIndex != null ? impressionText(aromaImpression(sensory, series, hoverIndex)) : null;
  return (
    <section aria-labelledby="ft-aroma-impression" className="space-y-2">
      <h3 id="ft-aroma-impression" className="font-display text-sm font-bold text-slate-100">
        Aroma impression · model estimate
      </h3>
      <dl className="space-y-1.5 text-sm">
        {lines.map(([label, t]) => (
          <div key={label} className="sm:flex sm:gap-3">
            <dt className="text-xs text-slate-400 sm:w-32 sm:shrink-0 sm:pt-0.5">
              {label} · {timeLabel(t, timeUnit)}
            </dt>
            <dd className="text-slate-100">
              {at(t) ? <>This batch may come across as {at(t)}.</> : "No aroma likely above threshold yet."}
            </dd>
          </div>
        ))}
      </dl>
      <AromaTimeline
        spans={spans}
        grid={grid}
        nowH={nowH}
        horizonH={horizonH}
        timeUnit={timeUnit}
        hoverIndex={hoverIndex}
        onHover={onHover}
      />
      <p className="text-xs text-slate-300" aria-live="polite">
        {hoverIndex != null &&
          `${timeLabel(grid[hoverIndex] ?? 0, timeUnit)}: ${hovered ? `may come across as ${hovered}` : "no aroma likely above threshold"}.`}
      </p>
    </section>
  );
}
