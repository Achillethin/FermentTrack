import { useId } from "react";
import { TYPICAL_TEMPERATURE_C, parseTemperature, typicalHint } from "./temperature.js";

// Labelled, optional °C input with the ferment type's typical value as hint
// and placeholder. `value` is the raw text; parse it with parseTemperature().
export default function TemperatureField({
  type,
  value,
  onChange,
  label = "Estimated fermentation temperature (°C)",
  autoFocus = false,
  inputRef,
  laterHint = true,
}) {
  const id = useId();
  const typical = TYPICAL_TEMPERATURE_C[type];
  const parsed = parseTemperature(value);
  const hint = typicalHint(type);

  return (
    <div>
      <label htmlFor={id} className="mb-1 block text-xs text-slate-400">
        {label} <span className="text-slate-400">· optional</span>
      </label>
      <div className="flex items-center gap-2">
        <input
          id={id}
          ref={inputRef}
          type="text"
          inputMode="decimal"
          autoComplete="off"
          autoFocus={autoFocus}
          placeholder={typical ? String(typical.typical) : "e.g. 21"}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          aria-invalid={parsed.error ? "true" : undefined}
          aria-describedby={`${id}-hint ${parsed.error ? `${id}-err` : ""}`}
          className={`w-28 rounded-lg border bg-slate-900 px-3 py-2 text-base tabular-nums sm:text-sm ${
            parsed.error ? "border-red-500/70" : "border-slate-700"
          }`}
        />
        <span className="text-sm text-slate-400" aria-hidden="true">
          °C
        </span>
      </div>
      <p id={`${id}-hint`} className="mt-1 text-xs text-slate-400">
        {hint ? `${hint}. ` : ""}Used for the fermentation forecast{laterHint ? "; you can change it later" : ""}.
      </p>
      {parsed.error && (
        <div className="mt-1">
          <p id={`${id}-err`} className="text-xs text-red-400" role="alert">
            {parsed.error}
          </p>
          {parsed.fahrenheitAsC != null && (
            <button
              type="button"
              className="mt-1 inline-flex min-h-[40px] items-center rounded-lg border border-slate-600 px-3 text-sm text-slate-100 hover:bg-slate-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400"
              onClick={() => onChange(String(parsed.fahrenheitAsC))}
            >
              Use {parsed.fahrenheitAsC} °C
            </button>
          )}
        </div>
      )}
    </div>
  );
}
