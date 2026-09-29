import { useId, useState } from "react";
import { Button, Input, Select } from "../components/ui.jsx";
import { PRESETS, applyStyle, flourLabel, ratioLabel, scaleBuild, seedKind, styleOf } from "./plan.js";

// Same look as App's Card (not exported there; App.jsx stays untouched).
export function Section({ title, aside, children }) {
  return (
    <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 sm:p-5">
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <h2 className="font-display text-lg font-bold text-slate-100">{title}</h2>
        {aside}
      </div>
      {children}
    </section>
  );
}

const g = (v) => (Number.isFinite(v) ? `${Math.round(v * 10) / 10} g` : "–");

// Visible label, 16 px text on phones (no iOS zoom), 44 px tall, error below.
function Field({ label, suffix, hint, error, className = "", ...props }) {
  const id = useId();
  return (
    <div className={`min-w-0 ${className}`}>
      <label htmlFor={id} className="mb-1 block text-xs text-slate-300">
        {label}
      </label>
      <div className="flex items-center gap-2">
        <Input
          id={id}
          type="text"
          inputMode="decimal"
          autoComplete="off"
          aria-invalid={error ? "true" : undefined}
          aria-describedby={error || hint ? `${id}-note` : undefined}
          className={`min-h-[44px] w-full min-w-0 text-base tabular-nums sm:text-sm ${error ? "border-red-500/70" : ""}`}
          {...props}
        />
        {suffix && (
          <span className="shrink-0 text-sm text-slate-400" aria-hidden="true">
            {suffix}
          </span>
        )}
      </div>
      {(error || hint) && (
        <p id={`${id}-note`} className={`mt-1 text-xs ${error ? "text-red-400" : "text-slate-400"}`}>
          {error || hint}
        </p>
      )}
    </div>
  );
}

function Choice({ label, value, options, onChange }) {
  return (
    <fieldset className="min-w-0">
      <legend className="mb-1 text-xs text-slate-300">{label}</legend>
      <div className="flex flex-wrap gap-1.5">
        {options.map(([v, text]) => (
          <button
            key={v}
            type="button"
            aria-pressed={value === v}
            onClick={() => onChange(v)}
            className={`min-h-[48px] rounded-lg border px-3 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400 ${
              value === v
                ? "border-emerald-400 bg-emerald-950/60 font-semibold text-slate-50"
                : "border-slate-600 text-slate-300 hover:bg-slate-800"
            }`}
          >
            {text}
          </button>
        ))}
      </div>
    </fieldset>
  );
}

export function Toggle({ label, checked, onChange, disabled }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className="inline-flex min-h-[48px] items-center gap-3 rounded-lg text-sm font-medium text-slate-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400 disabled:opacity-60"
    >
      <span
        aria-hidden="true"
        className={`relative h-7 w-12 shrink-0 rounded-full transition-colors ${checked ? "bg-emerald-600" : "bg-slate-700"}`}
      >
        <span
          className={`absolute top-1 h-5 w-5 rounded-full bg-slate-50 transition-transform ${
            checked ? "translate-x-6" : "translate-x-1"
          }`}
        />
      </span>
      {label}
    </button>
  );
}

const TYPE_TEXT = { I: "Type I", II: "Type II", III: "Type III", 0: "Type 0 · yeasted" };

function StyleCard({ s, on, onPick }) {
  return (
    <button
      type="button"
      aria-pressed={on}
      onClick={onPick}
      className={`w-full rounded-lg border p-3 text-left focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400 ${
        on ? "border-emerald-400 bg-emerald-950/40" : "border-slate-700 hover:bg-slate-800/60"
      }`}
    >
      <span className="flex items-start justify-between gap-2">
        <span className="min-w-0">
          <span className="block font-display font-bold text-slate-100">{s.name}</span>
          {s.native_name && s.native_name !== s.name && (
            <span className="block text-xs italic text-slate-400">{s.native_name}</span>
          )}
        </span>
        <span className="shrink-0 rounded border border-slate-600 px-1.5 py-0.5 text-[11px] text-slate-300">
          {TYPE_TEXT[s.type] ?? `Type ${s.type}`}
        </span>
      </span>
      {s.description && <span className="mt-1 block text-sm text-slate-300">{s.description}</span>}
    </button>
  );
}

function StylePicker({ catalog, value, onPick }) {
  const [open, setOpen] = useState(false);
  const current = styleOf(catalog, value);
  if (!open && current) {
    return (
      <div className="space-y-2">
        <StyleCard s={current} on onPick={() => setOpen(true)} />
        <Button variant="secondary" size="lg" className="min-h-[44px]" onClick={() => setOpen(true)}>
          Change style
        </Button>
      </div>
    );
  }
  return (
    <div className="grid gap-2 sm:grid-cols-2" role="group" aria-label="Levain styles">
      {catalog.styles.map((s) => (
        <StyleCard
          key={s.key}
          s={s}
          on={s.key === value}
          onPick={() => {
            onPick(s.key);
            setOpen(false);
          }}
        />
      ))}
    </div>
  );
}

function FlourSelect({ catalog, label, value, onChange, extra }) {
  const id = useId();
  return (
    <div className="min-w-0">
      <label htmlFor={id} className="mb-1 block text-xs text-slate-300">
        {label}
      </label>
      <Select id={id} className="min-h-[44px] w-full text-base sm:text-sm" value={value} onChange={(e) => onChange(e.target.value)}>
        {extra}
        {catalog.flours.map((f) => (
          <option key={f.key} value={f.key}>
            {flourLabel(f)}
          </option>
        ))}
      </Select>
    </div>
  );
}

/**
 * The plan form (style, levain build, optional dough and proof). Controlled:
 * `form` comes from plan.js (defaultForm / planToForm), every edit calls
 * onChange(nextForm). `errors`/`info` are formToPlan's. `embedded` (batch
 * view) drops the starter picker; the feed clock shows only with onStartAt.
 * `afterLevain` renders between the levain and dough sections (feeding chart).
 */
export default function PlanForm({
  catalog,
  form,
  onChange,
  errors = {},
  info = {},
  pro = false,
  embedded = false,
  cultures = [],
  startAt,
  onStartAt,
  afterLevain,
}) {
  const set = (patch) => onChange({ ...form, ...patch });
  const kind = seedKind(catalog, form.style);
  const hyd = Number.parseFloat(form.hydration);
  const startId = useId();
  const cultureId = useId();
  const ratios = PRESETS.includes(form.ratio) ? PRESETS : [...PRESETS, form.ratio].sort((a, b) => a - b);

  const levain = kind !== "dried" && (
    <Section title={kind === "yeast" ? "Pre-ferment" : "Levain build"}>
      <div className="space-y-4">
        {!embedded && cultures.length > 0 && (
          <div>
            <label htmlFor={cultureId} className="mb-1 block text-xs text-slate-300">
              Which starter?
            </label>
            <Select
              id={cultureId}
              className="min-h-[44px] w-full text-base sm:text-sm"
              value={form.cultureId}
              onChange={(e) => {
                const c = cultures.find((x) => x.id === e.target.value);
                let next = { ...form, cultureId: e.target.value };
                if (c?.style && c.style !== form.style && styleOf(catalog, c.style)) next = applyStyle(next, catalog, c.style);
                onChange(next);
              }}
            >
              <option value="">A typical starter of this style</option>
              {cultures.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </Select>
            <p className="mt-1 text-xs text-slate-400">
              {form.cultureId
                ? "Timings use what your tracked bakes taught about this starter."
                : "Track bakes with a named starter and its timings learn from them."}
            </p>
          </div>
        )}

        {kind === "starter" && (
          <Choice
            label="Your starter right now"
            value={form.starter}
            onChange={(v) => set({ starter: v })}
            options={[
              ["ripe", "Ripe, at room temperature"],
              ["refrigerated", "Straight from the fridge"],
            ]}
          />
        )}

        {kind === "starter" && (
          <fieldset>
            <legend className="mb-1 text-xs text-slate-300">Feed ratio (starter : flour : water)</legend>
            <div className="flex flex-wrap gap-1.5">
              {ratios.map((r) => {
                const on = !form.custom && form.ratio === r;
                return (
                  <button
                    key={r}
                    type="button"
                    aria-pressed={on}
                    onClick={() => set({ ratio: r, custom: false })}
                    className={`min-h-[48px] min-w-[4.5rem] rounded-lg border px-2 text-sm tabular-nums focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400 ${
                      on ? "border-emerald-400 bg-emerald-950/60 font-semibold text-slate-50" : "border-slate-600 text-slate-300 hover:bg-slate-800"
                    }`}
                  >
                    {ratioLabel(r, Number.isFinite(hyd) ? hyd : 100)}
                  </button>
                );
              })}
              <button
                type="button"
                aria-pressed={form.custom}
                onClick={() => set({ custom: true })}
                className={`min-h-[48px] rounded-lg border px-3 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400 ${
                  form.custom ? "border-emerald-400 bg-emerald-950/60 font-semibold text-slate-50" : "border-slate-600 text-slate-300 hover:bg-slate-800"
                }`}
              >
                Custom grams
              </button>
            </div>
            {errors.ratio && <p className="mt-1 text-xs text-red-400">{errors.ratio}</p>}
          </fieldset>
        )}

        {kind === "starter" && form.custom && (
          <div className="grid grid-cols-3 gap-2">
            <Field label="Starter" suffix="g" value={form.cSeed} error={errors.cSeed} onChange={(e) => set({ cSeed: e.target.value })} />
            <Field label="Flour" suffix="g" value={form.cFlour} error={errors.cFlour} onChange={(e) => set({ cFlour: e.target.value })} />
            <Field label="Water" suffix="g" value={form.cWater} error={errors.cWater} onChange={(e) => set({ cWater: e.target.value })} />
          </div>
        )}
        {kind === "starter" && !form.custom && (
          <div className="grid grid-cols-2 gap-2">
            <Field label="Starter" suffix="g" value={form.seedG} error={errors.seedG} onChange={(e) => set({ seedG: e.target.value })} />
            <Field label="Hydration" suffix="%" value={form.hydration} error={errors.hydration} hint="water per 100 g flour" onChange={(e) => set({ hydration: e.target.value })} />
          </div>
        )}
        {kind === "yeast" && (
          <div className="grid grid-cols-3 gap-2">
            <Field label="Flour" suffix="g" value={form.pFlour} error={errors.pFlour} onChange={(e) => set({ pFlour: e.target.value })} />
            <Field label="Yeast" suffix="g" value={form.pYeast} error={errors.pYeast} onChange={(e) => set({ pYeast: e.target.value })} />
            <Field label="Hydration" suffix="%" value={form.hydration} error={errors.hydration} onChange={(e) => set({ hydration: e.target.value })} />
          </div>
        )}
        {Number.isFinite(info.levainG) && (
          <p className="text-sm text-slate-300">
            {kind === "yeast" ? "Makes" : "Builds"} <span className="font-semibold text-slate-100">{g(info.levainG)}</span>
            {form.custom && Number.isFinite(info.levainHydration) && ` at ${Math.round(info.levainHydration)} % hydration`}
            {!form.custom && kind === "starter" && (
              <span className="text-slate-400">
                {" "}
                ({form.seedG} g starter + {g(Number.parseFloat(form.seedG) * form.ratio)} flour +{" "}
                {g((Number.parseFloat(form.seedG) * form.ratio * hyd) / 100)} water)
              </span>
            )}
          </p>
        )}

        <div className="grid gap-2 sm:grid-cols-2">
          <FlourSelect catalog={catalog} label="Flour" value={form.flour} onChange={(v) => set({ flour: v })} />
          {form.flour2 ? (
            <div className="grid grid-cols-[1fr_auto] items-end gap-2">
              <FlourSelect catalog={catalog} label="Second flour" value={form.flour2} onChange={(v) => set({ flour2: v })} />
              <Button variant="secondary" size="lg" className="min-h-[44px]" onClick={() => set({ flour2: "" })} aria-label="Remove the second flour">
                Remove
              </Button>
              <Field
                label="Second flour share"
                suffix="% of the flour"
                value={form.share2}
                error={errors.share2}
                className="col-span-2"
                onChange={(e) => set({ share2: e.target.value })}
              />
            </div>
          ) : (
            <div className="flex items-end">
              <Button
                variant="secondary"
                size="lg"
                className="min-h-[44px]"
                onClick={() => set({ flour2: catalog.flours.find((f) => f.key !== form.flour)?.key ?? "" })}
              >
                Add a second flour
              </Button>
            </div>
          )}
        </div>

        <div className="grid grid-cols-2 gap-2">
          <Field
            label={kind === "yeast" ? "Temperature" : "Levain temperature"}
            suffix="°C"
            value={form.levainTemp}
            error={errors.levainTemp}
            hint="where the jar sits"
            onChange={(e) => set({ levainTemp: e.target.value })}
          />
          {pro && (
            <Field
              label="Use it after"
              suffix="h"
              placeholder="at peak"
              value={form.levainHours}
              error={errors.levainHours}
              hint="empty: mix at the peak"
              onChange={(e) => set({ levainHours: e.target.value })}
            />
          )}
        </div>

        {onStartAt && (
          <div>
            <label htmlFor={startId} className="mb-1 block text-xs text-slate-300">
              {kind === "yeast" ? "Mix it at" : "Feed it at"}
            </label>
            <Input
              id={startId}
              type="datetime-local"
              className="min-h-[44px] w-full text-base sm:w-auto sm:text-sm"
              value={startAt}
              onChange={(e) => e.target.value && onStartAt(e.target.value)}
            />
          </div>
        )}
      </div>
    </Section>
  );

  const doughFields = (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-2">
        <Field label="Total flour" suffix="g" value={form.totalFlour} error={errors.totalFlour} hint={kind === "dried" ? null : "levain flour included"} onChange={(e) => set({ totalFlour: e.target.value })} />
        <Field label="Water" suffix="%" value={form.doughHydration} error={errors.doughHydration} hint="of total flour" onChange={(e) => set({ doughHydration: e.target.value })} />
        <Field label="Salt" suffix="%" value={form.saltPct} error={errors.saltPct} onChange={(e) => set({ saltPct: e.target.value })} />
        {kind === "dried" ? (
          <Field label="Dried sourdough" suffix="g" value={form.driedG} error={errors.driedG} onChange={(e) => set({ driedG: e.target.value })} />
        ) : (
          <Field label={kind === "yeast" ? "Pre-ferment" : "Levain"} suffix="%" value={form.levainPct} error={errors.levainPct} hint="of total flour" onChange={(e) => set({ levainPct: e.target.value })} />
        )}
        <Field label="Bulk until it rises" suffix="%" value={form.targetRise} error={errors.targetRise} onChange={(e) => set({ targetRise: e.target.value })} />
        <Field label="Dough temperature" suffix="°C" value={form.doughTemp} error={errors.doughTemp} onChange={(e) => set({ doughTemp: e.target.value })} />
        <Field
          label={kind === "dried" ? "Baker's yeast" : "Baker's yeast (optional)"}
          suffix="g"
          value={form.yeastG}
          error={errors.yeastG}
          hint={kind === "dried" ? "dried sourdough does not rise on its own" : null}
          onChange={(e) => set({ yeastG: e.target.value })}
        />
        {pro && (
          <Field label="Bulk time" suffix="h" placeholder="until the rise" value={form.bulkHours} error={errors.bulkHours} hint="empty: until the rise above" onChange={(e) => set({ bulkHours: e.target.value })} />
        )}
      </div>
      {Number.parseFloat(form.yeastG) > 0 && (
        <Choice label="Yeast" value={form.yeastType} onChange={(v) => set({ yeastType: v })} options={[["instant", "Instant (dry)"], ["fresh", "Fresh"]]} />
      )}
      <FlourSelect
        catalog={catalog}
        label="Dough flour"
        value={form.doughFlour}
        onChange={(v) => set({ doughFlour: v })}
        extra={kind === "dried" ? null : <option value="">Same as the {kind === "yeast" ? "pre-ferment" : "levain"}</option>}
      />
      {Number.isFinite(info.doughFlourG) && (
        <p className="text-sm text-slate-300">
          Mix <span className="font-semibold text-slate-100">{g(info.doughFlourG)}</span> flour,{" "}
          <span className="font-semibold text-slate-100">{g(info.doughWaterG)}</span> water,{" "}
          <span className="font-semibold text-slate-100">{g(info.saltG)}</span> salt
          {kind !== "dried" && (
            <>
              {" "}
              and <span className="font-semibold text-slate-100">{g(info.doughLevainG)}</span>{" "}
              {kind === "yeast" ? "pre-ferment" : "levain"}
            </>
          )}
          .
        </p>
      )}
      {info.short > 0 && (
        <div role="status" className="rounded-lg border border-amber-500/30 bg-amber-950/30 px-3 py-2 text-sm text-amber-200">
          <p>
            The dough needs {g(info.doughLevainG)} of {kind === "yeast" ? "pre-ferment" : "levain"} but the build makes{" "}
            {g(info.levainG)}.
          </p>
          <Button size="lg" className="mt-2 min-h-[44px]" onClick={() => onChange(scaleBuild(form, catalog, info.doughLevainG))}>
            Build enough
          </Button>
        </div>
      )}

      <Choice
        label="After bulk"
        value={form.proof}
        onChange={(v) =>
          set({ proof: v, ...(v === "room" ? { proofTemp: "24", proofHours: "2" } : v === "cold" ? { proofTemp: "4", proofHours: "14" } : {}) })
        }
        options={[
          ["none", "Stop at bulk"],
          ["room", "Room proof"],
          ["cold", "Cold retard"],
        ]}
      />
      {form.proof !== "none" && (
        <div className="grid grid-cols-2 gap-2">
          <Field label={form.proof === "cold" ? "Fridge temperature" : "Proof temperature"} suffix="°C" value={form.proofTemp} error={errors.proofTemp} onChange={(e) => set({ proofTemp: e.target.value })} />
          <Field label="For" suffix="h" value={form.proofHours} error={errors.proofHours} onChange={(e) => set({ proofHours: e.target.value })} />
        </div>
      )}
    </div>
  );

  return (
    <div className="space-y-4">
      <Section title="Style">
        <StylePicker catalog={catalog} value={form.style} onPick={(key) => onChange(applyStyle(form, catalog, key))} />
      </Section>
      {levain}
      {afterLevain}
      <Section title="Dough">
        <Toggle
          label={kind === "dried" ? "Dried sourdough goes straight into a dough" : "Plan the dough too"}
          checked={form.doughOn}
          disabled={kind === "dried"}
          onChange={(v) => set({ doughOn: v })}
        />
        {form.doughOn && <div className="mt-3">{doughFields}</div>}
      </Section>
    </div>
  );
}
