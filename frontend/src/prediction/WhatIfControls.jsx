import { useId } from "react";
import { formatC } from "./temperature.js";
import { TEMP_SOURCE_TEXT } from "./format.js";

export function horizonLabel(h) {
  if (h < 72) return `${Math.round(h * 10) / 10} h`;
  const d = h / 24;
  if (Math.abs(d - Math.round(d)) < 1e-6) return `${Math.round(d)} d`;
  return `${d < 10 ? Math.round(d * 10) / 10 : Math.round(d * 2) / 2} d`;
}

// Slider bounds: the type's typical range widened on both sides, always
// containing the current base temperature, clamped to the API's -5..60 °C.
export function sliderBounds(rangeC, base) {
  const lo0 = Math.min(rangeC?.[0] ?? base, base);
  const hi0 = Math.max(rangeC?.[1] ?? base, base);
  const pad = Math.max(6, (hi0 - lo0) * 0.5);
  return [Math.max(-5, Math.floor(lo0 - pad)), Math.min(60, Math.ceil(hi0 + pad))];
}

export default function WhatIfControls({
  temperature,
  baseTemp,
  baseSource,
  value,
  onChange,
  onReset,
  overrideActive,
  horizon,
  horizonChoices,
  onHorizon,
}) {
  const sliderId = useId();
  const hintId = useId();
  const [min, max] = sliderBounds(temperature.range_c, baseTemp ?? temperature.forecast_c);
  const range = temperature.range_c || [min, max];
  const pctOf = (v) => `${(((v - min) / (max - min)) * 100).toFixed(2)}%`;
  const baseLabel = baseSource === "expected" ? "your estimate" : TEMP_SOURCE_TEXT[baseSource] || "the default";

  return (
    <div className="grid gap-4 sm:grid-cols-[1fr_auto] sm:items-start sm:gap-6">
      <div className="min-w-0">
        <div className="flex items-baseline justify-between gap-3">
          <label htmlFor={sliderId} className="text-xs font-medium uppercase tracking-wide text-slate-400">
            What if it ferments at
          </label>
          <output
            htmlFor={sliderId}
            className={`text-lg font-semibold tabular-nums ${overrideActive ? "text-amber-200" : "text-slate-100"}`}
          >
            {formatC(value)}
          </output>
        </div>
        <input
          id={sliderId}
          type="range"
          min={min}
          max={max}
          step={0.5}
          value={value}
          onChange={(e) => onChange(parseFloat(e.target.value))}
          aria-describedby={hintId}
          aria-valuetext={`${formatC(value)}${overrideActive ? ", what-if" : ""}`}
          className={`ft-range ${overrideActive ? "is-override" : ""}`}
          style={{ "--band-lo": pctOf(Math.max(min, range[0])), "--band-hi": pctOf(Math.min(max, range[1])) }}
        />
        <div className="relative -mt-1 h-4 text-[11px] text-slate-400" aria-hidden="true">
          <span className="absolute left-0 tabular-nums">{min} °C</span>
          <span
            className="absolute -translate-x-1/2 whitespace-nowrap text-emerald-300/90"
            style={{ left: `calc(${pctOf((Math.max(min, range[0]) + Math.min(max, range[1])) / 2)})` }}
          >
            typical {range[0]}–{range[1]}
          </span>
          <span className="absolute right-0 tabular-nums">{max} °C</span>
        </div>
        <div id={hintId} className="mt-2 flex min-h-[40px] flex-wrap items-center gap-x-3 gap-y-1 text-xs">
          {overrideActive ? (
            <>
              <span className="rounded-full border border-amber-400/40 bg-amber-950/40 px-2 py-0.5 font-medium text-amber-200">
                What-if · not saved
              </span>
              <button
                type="button"
                onClick={onReset}
                className="inline-flex min-h-[40px] items-center rounded-lg px-2 font-medium text-emerald-400 hover:text-emerald-300 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400"
              >
                Reset to {baseLabel}
                {baseTemp != null ? ` (${formatC(baseTemp)})` : ""}
              </button>
            </>
          ) : (
            <span className="text-slate-400">
              Using {formatC(baseTemp ?? temperature.forecast_c)} ({baseLabel}). Drag to explore; nothing is saved.
            </span>
          )}
        </div>
      </div>

      {horizonChoices.length > 1 && (
        <fieldset className="min-w-0">
          <legend className="mb-1.5 text-xs font-medium uppercase tracking-wide text-slate-400">Forecast window</legend>
          <div className="inline-flex rounded-lg border border-slate-700 bg-slate-950/60 p-0.5">
            {horizonChoices.map((h) => {
              const on = Math.abs(h - horizon) < 1e-6;
              return (
                <button
                  key={h}
                  type="button"
                  aria-pressed={on}
                  onClick={() => onHorizon(h)}
                  className={`min-h-[40px] min-w-[3.25rem] rounded-md px-2.5 text-sm tabular-nums focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400 ${
                    on ? "bg-slate-700 font-semibold text-white" : "text-slate-300 hover:bg-slate-800 hover:text-white"
                  }`}
                >
                  {horizonLabel(h)}
                </button>
              );
            })}
          </div>
        </fieldset>
      )}
    </div>
  );
}
