import { useMemo, useRef } from "react";
import { useWidth } from "./ForecastChart.jsx";
import { timeLabel } from "./format.js";
import { linear, nearestIndex } from "./scale.js";
import { indexAt, mixHex, phaseColor, phaseRuns, phaseSpans } from "./sensory.js";

const M = { left: 36, right: 10 }; // aligned with ForecastChart's plot area
const THRESHOLD_LINE = [{ value: 0, label: "detection threshold", tone: "neutral" }];

/**
 * The most likely taste phase over time, on the ordinal phase ramp. Where members
 * disagree (top phase < 60 %), the band blends the two leading phases' colours.
 */
function PhaseBand({ tp, nowH, horizonH, timeUnit, hoverIndex, onHover }) {
  const ref = useRef(null);
  const width = useWidth(ref);
  const runs = useMemo(() => phaseRuns(tp), [tp]);
  const spans = useMemo(() => phaseSpans(runs), [runs]);
  const n = tp.vocabulary.length;
  const innerW = Math.max(width - M.left - M.right, 10);
  const x = linear([0, horizonH], [M.left, M.left + innerW]);
  const i = hoverIndex ?? indexAt(tp.t_h, nowH);
  const split = tp.vocabulary
    .map((name) => ({ name, p: tp.prob[name][i] ?? 0 }))
    .filter((s) => s.p >= 0.05)
    .sort((a, b) => b.p - a.p);
  const fill = (r) =>
    r.p >= 0.6 ? phaseColor(r.k, n) : mixHex(phaseColor(r.k, n), phaseColor(r.k2, n), r.p2 / (r.p + r.p2));
  const summary = `Taste phase over time: ${spans
    .map((s) => `${s.name} from ${timeLabel(s.start_h, timeUnit)}`)
    .join(", ")}. Model estimate.`;
  const move = (e) => {
    const px = e.clientX - e.currentTarget.getBoundingClientRect().left;
    onHover(nearestIndex(tp.t_h, x.invert(px)), "phase");
  };
  return (
    <div ref={ref}>
      <p className="mb-1 font-display text-sm font-bold text-slate-100">Taste phase</p>
      {width > 0 && (
        <svg
          width={width}
          height={46}
          role="img"
          aria-label={summary}
          onPointerMove={move}
          onPointerLeave={() => onHover(null, "phase")}
        >
          {runs.slice(0, -1).map((r, j) => (
            <rect
              key={j}
              x={x(r.t_h)}
              y={2}
              height={22}
              width={Math.max(x(runs[j + 1].t_h) - x(r.t_h), 0.5)}
              fill={fill(r)}
            />
          ))}
          <line x1={x(nowH)} x2={x(nowH)} y1={0} y2={26} style={{ stroke: "var(--viz-now)" }} strokeWidth={1} />
          {spans.map((s) =>
            x(s.end_h) - x(s.start_h) > 48 ? (
              <text
                key={`${s.name}-${s.start_h}`}
                x={(x(s.start_h) + x(s.end_h)) / 2}
                y={40}
                textAnchor="middle"
                style={{ fill: "var(--viz-text-secondary)", fontSize: 11 }}
              >
                {s.name}
              </text>
            ) : null
          )}
        </svg>
      )}
      <p className="text-xs text-slate-300" aria-live="polite">
        {timeLabel(tp.t_h[i] ?? 0, timeUnit)}: {split.map((s) => `${s.name} ${Math.round(s.p * 100)} %`).join(", ")}
      </p>
      <details className="mt-1 text-xs text-slate-400">
        <summary className="cursor-pointer">Show as table</summary>
        <table className="ft-num mt-1">
          <thead>
            <tr>
              <th className="pr-3 text-left font-medium">Phase</th>
              <th className="text-left font-medium">Most likely from</th>
            </tr>
          </thead>
          <tbody>
            {spans.map((s) => (
              <tr key={`${s.name}-${s.start_h}`}>
                <td className="pr-3">{s.name}</td>
                <td>{timeLabel(s.start_h, timeUnit)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </div>
  );
}

/** Taste & aroma lens: the phase band and the taste chart (aroma joins in increment B). */
export default function TasteAroma({ data, charts, renderChart, hoverIndex, onHover, timeUnit }) {
  const s = data.sensory;
  return (
    <div className="space-y-5">
      <p className="border-l-2 border-slate-500 pl-3 text-xs leading-relaxed text-slate-300">{s.disclaimer}</p>
      {s.taste_phases && (
        <PhaseBand
          tp={s.taste_phases}
          nowH={data.now_h}
          horizonH={data.horizon_h}
          timeUnit={timeUnit}
          hoverIndex={hoverIndex}
          onHover={onHover}
        />
      )}
      {charts.map((c) => renderChart(c, THRESHOLD_LINE))}
      <p className="text-xs text-slate-400">Aroma compounds are coming next; bitterness and fizz are not modelled.</p>
    </div>
  );
}
