import { useEffect, useMemo, useState } from "react";
import { Button, Select } from "../components/ui.jsx";
import { getCatalog, patchBatch } from "./api.js";
import PlanForm, { Section } from "./PlanForm.jsx";
import { defaultForm, describePlan, formToPlan, planToForm, styleOf } from "./plan.js";

// Batch view: shows batch.sourdough_plan and edits it (PATCH /batches/{id}).
export default function PlanCard({ batch, culture, onSaved }) {
  const [catalog, setCatalog] = useState(null);
  const [form, setForm] = useState(null); // non-null while editing
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const plan = batch.sourdough_plan;

  useEffect(() => {
    getCatalog()
      .then(setCatalog)
      .catch((e) => setError(e.message));
  }, []);

  const { plan: next, errors, info } = useMemo(
    () => (form && catalog ? formToPlan(form, catalog) : { plan: null, errors: {}, info: {} }),
    [form, catalog]
  );

  async function store(value) {
    setBusy(true);
    setError(null);
    try {
      await patchBatch(batch.id, { sourdough_plan: value });
      setForm(null);
      onSaved();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  const edit = () => {
    const style = styleOf(catalog, culture?.style) ? culture.style : styleOf(catalog, "home_starter") ? "home_starter" : undefined;
    setForm(plan ? planToForm(plan, catalog) : defaultForm(catalog, style));
  };

  if (form && catalog) {
    return (
      <div className="space-y-4">
        <PlanForm catalog={catalog} form={form} onChange={setForm} errors={errors} info={info} embedded />
        {error && (
          <p role="alert" className="text-sm text-red-400">
            {error}
          </p>
        )}
        <div className="flex flex-wrap gap-2">
          <Button size="lg" className="min-h-[48px] flex-1" disabled={busy || !next} onClick={() => store(next)}>
            {busy ? "Saving…" : "Save plan"}
          </Button>
          <Button variant="secondary" size="lg" className="min-h-[48px]" disabled={busy} onClick={() => setForm(null)}>
            Cancel
          </Button>
        </div>
        {!next && <p className="text-xs text-slate-400">Fix the highlighted fields to save.</p>}
      </div>
    );
  }

  return (
    <Section title="Bake plan">
      {!catalog && !error && <p className="text-sm text-slate-400">Loading…</p>}
      {catalog &&
        (plan ? (
          <>
            <ul className="space-y-1 text-sm text-slate-200">
              {describePlan(plan, catalog).map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
            <p className="mt-2 text-xs text-slate-400">
              The forecast follows this plan. Advance the stage when you mix (bulk ferment) and when you shape, so it uses
              your real times.
            </p>
          </>
        ) : (
          <p className="text-sm text-slate-400">
            No plan on this bake yet. Add one and the forecast times the levain peak and the bulk from it.
          </p>
        ))}
      {error && (
        <p role="alert" className="mt-2 text-sm text-red-400">
          {error}
        </p>
      )}
      {catalog && (
        <div className="mt-3 flex flex-wrap gap-2">
          <Button size="lg" className="min-h-[48px]" onClick={edit}>
            {plan ? "Edit plan" : "Add a plan"}
          </Button>
          {plan && (
            <Button
              variant="secondary"
              size="lg"
              className="min-h-[48px]"
              disabled={busy}
              onClick={() => window.confirm("Remove the plan from this bake?") && store(null)}
            >
              Remove plan
            </Button>
          )}
        </div>
      )}
    </Section>
  );
}

// NewBatch: the levain type of a new sourdough culture (optional).
export function StyleSelect({ value, onChange }) {
  const [styles, setStyles] = useState([]);
  useEffect(() => {
    getCatalog()
      .then((c) => setStyles(c.styles.filter((s) => s.seed === "starter")))
      .catch(() => {});
  }, []);
  if (!styles.length) return null;
  return (
    <Select label="Levain style" className="w-full" value={value} onChange={(e) => onChange(e.target.value)}>
      <option value="">Levain style (optional)</option>
      {styles.map((s) => (
        <option key={s.key} value={s.key}>
          {s.name}
        </option>
      ))}
    </Select>
  );
}
