import { useState } from "react";
import { timeLabel } from "./format.js";
import { AROMA_HEX, paletteSeries, paletteSources } from "./sensory.js";

const KIND_LABEL = { ingredient: "ingredient", organism: "microbe", chemistry: "chemistry" };
const CHIP = "rounded-full border border-slate-600 px-2 py-0.5 text-[11px] text-slate-300";

/** Peak chance as bar length; the fill is the median strength at its peak (orange ramp). */
function PeakBar({ peak, strength }) {
  const fill = strength ? AROMA_HEX[strength - 1] : "transparent";
  return (
    <div className="h-2 w-full rounded-full" style={{ background: "var(--viz-grid)" }} aria-hidden="true">
      <div
        className="h-2 rounded-full"
        style={{
          width: `${Math.max(Math.round(peak * 100), 2)}%`,
          background: fill,
          boxShadow: strength ? "none" : `inset 0 0 0 1px ${AROMA_HEX[3]}`,
        }}
      />
    </div>
  );
}

function SeriesRow({ r, timeUnit, open, onOpen }) {
  return (
    <li className="grid grid-cols-[6.5rem_1fr] items-start gap-x-3 gap-y-1">
      <button
        type="button"
        onClick={() => onOpen(open ? null : r.key)}
        aria-expanded={open}
        className="min-h-[32px] rounded text-left text-sm font-medium text-slate-100 underline-offset-2 hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400"
      >
        {r.label}
      </button>
      <div className="min-w-0 pt-2">
        <PeakBar peak={r.peak} strength={r.strength} />
        <p className="mt-1 text-xs text-slate-300">
          <span className="font-medium text-slate-100">{r.chance}</span> · {Math.round(r.peak * 100)} % of runs ·
          strongest around {timeLabel(r.peakT, timeUnit)}
        </p>
        <p className="mt-1 flex flex-wrap gap-1">
          {r.origins.map((o) => (
            <span key={o} className={CHIP}>
              {o}
            </span>
          ))}
        </p>
      </div>
    </li>
  );
}

/**
 * The aroma palette: what this batch can smell of, and where each aroma comes from
 * (ingredients, microbes, chemistry). By source is the view a recipe builder grows from.
 */
export default function AromaPalette({ sensory, series, timeUnit, openSeries, onOpen }) {
  const [view, setView] = useState("aroma");
  const rows = paletteSeries(sensory, series);
  const nm = sensory.not_modelled_aroma;
  if (!rows.length) {
    return (
      <section aria-labelledby="ft-aroma-palette">
        <h3 id="ft-aroma-palette" className="font-display text-sm font-bold text-slate-100">
          Aroma
        </h3>
        <p className="mt-1 text-xs text-slate-400">
          {nm?.notes?.[0] || "Aroma is not modelled for this batch yet."}
        </p>
      </section>
    );
  }
  const likely = rows.filter((r) => r.chance !== "unlikely");
  const faint = rows.filter((r) => r.chance === "unlikely");
  const sources = paletteSources(sensory);
  return (
    <section aria-labelledby="ft-aroma-palette" className="space-y-3">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h3 id="ft-aroma-palette" className="font-display text-sm font-bold text-slate-100">
            Aromas this batch can develop
          </h3>
          <p className="text-xs text-slate-400">
            From your ingredients and microbes · chance each is noticeable at its strongest
          </p>
        </div>
        <div role="group" aria-label="Group aromas" className="inline-flex rounded-full border border-slate-700 p-0.5">
          {[
            ["aroma", "By aroma"],
            ["source", "By source"],
          ].map(([id, label]) => (
            <button
              key={id}
              type="button"
              aria-pressed={view === id}
              onClick={() => setView(id)}
              className={`min-h-[32px] whitespace-nowrap rounded-full px-3 text-xs font-medium focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400 ${
                view === id ? "bg-slate-700 text-slate-100" : "text-slate-300 hover:text-slate-100"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {view === "aroma" ? (
        <>
          <ul className="space-y-2">
            {likely.map((r) => (
              <SeriesRow key={r.key} r={r} timeUnit={timeUnit} open={openSeries === r.key} onOpen={onOpen} />
            ))}
          </ul>
          {faint.length > 0 && (
            <details className="text-xs text-slate-400">
              <summary className="cursor-pointer">Present but probably below threshold ({faint.length})</summary>
              <ul className="mt-2 space-y-2">
                {faint.map((r) => (
                  <SeriesRow key={r.key} r={r} timeUnit={timeUnit} open={openSeries === r.key} onOpen={onOpen} />
                ))}
              </ul>
            </details>
          )}
          <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-slate-400">
            <span>Bar length = chance it is noticeable · colour = how far above threshold:</span>
            {["×1", "×10", "×100", "×1000+"].map((t, i) => (
              <span key={t} className="inline-flex items-center gap-1">
                <span className="inline-block h-2 w-3 rounded-sm" style={{ background: AROMA_HEX[i] }} />
                {t}
              </span>
            ))}
          </p>
        </>
      ) : (
        <ul className="grid gap-2 sm:grid-cols-2">
          {sources.map((g) => (
            <li key={`${g.kind}-${g.name}`} className="rounded-lg border border-slate-800 bg-slate-950/40 p-3">
              <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">{KIND_LABEL[g.kind]}</p>
              <p className="text-sm font-medium text-slate-100">{g.name}</p>
              <p className="mt-0.5 text-xs text-slate-400">{g.vias.join(" · ")}</p>
              <p className="mt-2 flex flex-wrap gap-1">
                {g.series.map((s) => (
                  <span key={s.key} className={CHIP}>
                    {s.label} <span className="text-slate-400">· {s.chance}</span>
                  </span>
                ))}
              </p>
            </li>
          ))}
        </ul>
      )}

      {nm?.ingredients?.length > 0 && (
        <p className="text-xs text-slate-400">No aroma data yet for: {nm.ingredients.join(", ")}.</p>
      )}
      {nm?.notes?.length > 0 && (
        <details className="text-xs text-slate-400">
          <summary className="cursor-pointer">Not modelled yet ({nm.notes.length})</summary>
          <ul className="mt-1 list-disc space-y-0.5 pl-4">
            {nm.notes.map((n) => (
              <li key={n}>{n}</li>
            ))}
          </ul>
        </details>
      )}
      <p className="border-l-2 border-slate-500 pl-3 text-xs leading-relaxed text-slate-300">
        Aroma shows compounds that may be above their odour threshold (in water), not how the ferment will smell:
        odours mask and boost each other. Spoilage odours are not modelled — trust your nose and pH.
      </p>
    </section>
  );
}
