import { cellText, changeText } from "./sensory.js";

const ABV_LINE = [{ value: 0.5, label: "0.5 % ABV", tone: "neutral" }];
const INDENT = new Set(["sugars", "lactose", "free_amino_acids"]);

function Cell({ cell, unit, start }) {
  const { value, range } = cellText(cell, unit);
  const change = start ? changeText(start, cell) : null;
  return (
    <td className="px-2 py-1.5 text-right align-top">
      <span className="font-medium text-slate-100">{value}</span>
      {change && <span className="ml-1 text-[11px] text-slate-400">{change}</span>}
      {range && <span className="block text-[11px] text-slate-400">{range}</span>}
    </td>
  );
}

/** Nutrition lens: a label per 100 g at start / now / end of the window, then curves. */
export default function Nutrition({ sensory, charts, renderChart }) {
  return (
    <div className="space-y-5">
      <div className="overflow-x-auto">
        <table className="ft-num w-full text-sm">
          <caption className="mb-1 text-left text-xs text-slate-400">
            Per 100 g of what is in the jar · median, 90 % range below · ≥ = at least (some ingredients have no
            data) · – = unknown
          </caption>
          <thead>
            <tr className="border-b border-slate-800 text-xs text-slate-400">
              <th className="py-1 text-left font-medium">Per 100 g</th>
              <th className="px-2 text-right font-medium">Start</th>
              <th className="px-2 text-right font-medium">Now</th>
              <th className="px-2 text-right font-medium">End of window</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/70">
            {sensory.nutrition_label.map((r) => (
              <tr key={r.key}>
                <th scope="row" className={`py-1.5 text-left font-normal text-slate-300 ${INDENT.has(r.key) ? "pl-3" : ""}`}>
                  {r.label} <span className="text-slate-400">({r.unit})</span>
                </th>
                <Cell cell={r.start} unit={r.unit} />
                <Cell cell={r.now} unit={r.unit} start={r.start} />
                <Cell cell={r.end} unit={r.unit} start={r.start} />
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-slate-400">Model estimate, not a lab analysis; not for labelling products for sale.</p>
      {charts.map((c) => renderChart(c, c.unit === "% ABV" ? ABV_LINE : []))}
    </div>
  );
}
