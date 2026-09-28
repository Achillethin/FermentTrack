import { useEffect, useRef, useState } from "react";
import PredictionPanel from "./prediction/PredictionPanel.jsx";
import TemperatureEstimate from "./prediction/TemperatureEstimate.jsx";
import { Button, Input, Select, TabBar } from "./components/ui.jsx";
import { API_URL, urgencyColor, humanize, Card, apiError, errText } from "./shared.jsx";

function StageControl({ batchId, onAdvanced }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  async function advance() {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`${API_URL}/batches/${batchId}/stage`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `Could not advance stage (${res.status})`);
      }
      onAdvanced();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mt-2">
      <Button variant="secondary" size="sm" onClick={advance} disabled={busy}>
        {busy ? "Advancing…" : "Advance to next stage"}
      </Button>
      {error && <p className="mt-1 text-xs text-red-400">{error}</p>}
    </div>
  );
}

function RepeatBatch({ batchId }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const inflight = useRef(false);
  const alive = useRef(true);

  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);

  async function repeat() {
    if (inflight.current) return;
    inflight.current = true;
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`${API_URL}/batches/${batchId}/repeat`, { method: "POST" });
      if (!res.ok) throw new Error(await apiError(res, "Could not start a new batch"));
      const created = await res.json();
      // App remounts BatchView for the new id; stay busy until it does.
      window.location.hash = `#/batch/${created.id}`;
    } catch (e) {
      inflight.current = false;
      if (alive.current) {
        setError(errText(e));
        setBusy(false);
      }
    }
  }

  return (
    <div>
      <Button
        variant="secondary"
        size="sm"
        onClick={repeat}
        disabled={busy}
        aria-label="Start a new batch like this one"
      >
        {busy ? "Starting…" : "Repeat this batch"}
      </Button>
      {error && (
        <p role="alert" className="mt-1 text-xs text-red-400">
          {error}
        </p>
      )}
    </div>
  );
}

function Figure({ value, unit, caption }) {
  return (
    <div>
      <p className="font-display text-2xl font-bold leading-none">
        {value}
        <span className="ml-1 text-base font-semibold text-ink/70">{unit}</span>
      </p>
      <p className="mt-1 text-xs text-ink/75">{caption}</p>
    </div>
  );
}

const fmtDays = (d) => (d < 10 ? d.toFixed(1) : String(Math.round(d)));

// The batch reads like a paper label stuck on the jar; its controls sit on the
// dark strip below it.
function BatchHeader({ batchId, batch, culture, daysInStage, onAdvanced, onTemperatureSaved }) {
  const ageDays = Math.max(0, (Date.now() - new Date(batch.started_at).getTime()) / 86_400_000);
  const finished = batch.outcome !== "in_progress";
  return (
    <section>
      <div className="ft-label rounded-t-lg p-5 text-ink">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 className="break-words font-display text-[1.75rem] font-extrabold leading-tight">
              {culture.name}
            </h2>
            <p className="mt-0.5 text-sm capitalize text-ink/75">{humanize(culture.type)}</p>
          </div>
          <div className="flex shrink-0 flex-col items-end gap-1.5">
            <span className="-rotate-2 rounded-md border-2 border-ink/80 px-2.5 py-0.5 font-display text-sm font-bold capitalize">
              {humanize(batch.current_stage)}
            </span>
            {finished && (
              <span className="rounded-md bg-ink px-2 py-0.5 text-xs font-bold capitalize text-paper">
                {humanize(batch.outcome)}
              </span>
            )}
          </div>
        </div>
        <div className="mt-5 grid grid-cols-2 gap-4 border-t border-ink/30 pt-3">
          <Figure value={fmtDays(ageDays)} unit="d" caption="since it started" />
          <Figure value={fmtDays(daysInStage)} unit="d" caption="in this stage" />
        </div>
        {batch.target && <p className="mt-3 text-sm">Target: {batch.target}</p>}
      </div>
      <div className="rounded-b-lg border border-t-0 border-slate-800 bg-slate-900/60 px-4 pb-4 pt-2 sm:px-5">
        <TemperatureEstimate apiUrl={API_URL} batch={batch} type={culture.type} onSaved={onTemperatureSaved} />
        <p className="mt-2 text-xs text-slate-400">
          Started {new Date(batch.started_at).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}
        </p>
        {!finished && <StageControl batchId={batchId} onAdvanced={onAdvanced} />}
      </div>
    </section>
  );
}

const OBSERVATION_TYPES = [
  "pH",
  "temperature",
  "gravity",
  "brix",
  "smell",
  "taste",
  "appearance",
  "note",
  "other",
];

function LogObservation({ batchId, onLogged }) {
  const [type, setType] = useState("pH");
  const [customType, setCustomType] = useState("");
  const [valueNumeric, setValueNumeric] = useState("");
  const [valueText, setValueText] = useState("");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const isNote = type === "note";
  const isNumeric = ["pH", "temperature", "gravity", "brix"].includes(type);

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      let res;
      if (isNote) {
        if (!valueText.trim()) throw new Error("Write the note text");
        res = await fetch(`${API_URL}/batches/${batchId}/note`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text: valueText }),
        });
      } else {
        const effectiveType = type === "other" ? customType.trim() : type;
        if (!effectiveType) throw new Error("Pick or name an observation type");
        res = await fetch(`${API_URL}/batches/${batchId}/measure`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            type: effectiveType,
            value_numeric: valueNumeric ? parseFloat(valueNumeric) : null,
            value_text: valueText || null,
            notes: notes || null,
          }),
        });
      }
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `Could not log observation (${res.status})`);
      }
      setCustomType("");
      setValueNumeric("");
      setValueText("");
      setNotes("");
      onLogged();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card title="Log an observation">
      <form className="space-y-2" onSubmit={submit}>
        <div className="flex gap-2">
          <Select label="Observation type" value={type} onChange={(e) => setType(e.target.value)}>
            {OBSERVATION_TYPES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </Select>
          {type === "other" && (
            <Input
              label="Custom observation type name"
              className="flex-1"
              placeholder="type name"
              value={customType}
              onChange={(e) => setCustomType(e.target.value)}
            />
          )}
        </div>

        {isNote ? (
          <textarea
            aria-label="Observation note text"
            className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm placeholder:text-slate-500"
            placeholder="What did you observe?"
            rows={2}
            value={valueText}
            onChange={(e) => setValueText(e.target.value)}
          />
        ) : (
          <>
            <div className="flex gap-2">
              {isNumeric && (
                <Input
                  label="Observation numeric value"
                  size="sm"
                  className="w-24"
                  placeholder="value"
                  value={valueNumeric}
                  onChange={(e) => setValueNumeric(e.target.value)}
                />
              )}
              <Input
                label="Observation description"
                size="sm"
                className="flex-1"
                placeholder="description (e.g. tangy, cloudy)"
                value={valueText}
                onChange={(e) => setValueText(e.target.value)}
              />
            </div>
            <Input
              label="Additional notes"
              className="w-full"
              placeholder="Notes (optional)"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
            />
          </>
        )}

        {error && <p className="text-sm text-red-400">{error}</p>}
        <Button type="submit" size="lg" className="w-full" disabled={busy}>
          {busy ? "Logging…" : "Log observation"}
        </Button>
      </form>
    </Card>
  );
}

const ROLES = ["base", "flavoring", "additive", "starter"];

function RecipeRow({ batchId, item, ingredientName, onChanged }) {
  const [editing, setEditing] = useState(false);
  const [quantity, setQuantity] = useState(item.quantity ?? "");
  const [unit, setUnit] = useState(item.unit ?? "");
  const [role, setRole] = useState(item.role);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  async function save() {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`${API_URL}/batches/${batchId}/ingredients/${item.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          quantity: quantity === "" ? null : parseFloat(quantity),
          unit: unit || null,
          role,
        }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `Could not update ingredient (${res.status})`);
      }
      setEditing(false);
      onChanged();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!window.confirm(`Remove ${ingredientName} from this recipe?`)) return;
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`${API_URL}/batches/${batchId}/ingredients/${item.id}`, {
        method: "DELETE",
      });
      if (!res.ok && res.status !== 204) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `Could not remove ingredient (${res.status})`);
      }
      onChanged();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  if (editing) {
    return (
      <li className="py-2 text-sm">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-slate-200">{ingredientName}</span>
          <Input
            label="Edit ingredient quantity"
            size="xs"
            className="w-20"
            placeholder="qty"
            value={quantity}
            onChange={(e) => setQuantity(e.target.value)}
          />
          <Select
            label="Edit ingredient unit"
            size="xs"
            className="w-20"
            value={unit}
            onChange={(e) => setUnit(e.target.value)}
          >
            <option value="">unit</option>
            {["g", "kg", "mg", "ml", "L"].map((u) => (
              <option key={u} value={u}>
                {u}
              </option>
            ))}
          </Select>
          <Select
            label="Edit ingredient role"
            size="xs"
            value={role}
            onChange={(e) => setRole(e.target.value)}
          >
            {ROLES.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </Select>
          <Button size="xs" disabled={busy} onClick={save}>
            {busy ? "Saving…" : "Save"}
          </Button>
          <Button variant="secondary" size="xs" disabled={busy} onClick={() => setEditing(false)}>
            Cancel
          </Button>
        </div>
        {error && <p className="mt-1 text-xs text-red-400">{error}</p>}
      </li>
    );
  }

  return (
    <li className="flex items-center justify-between gap-2 py-2 text-sm">
      <span className="text-slate-200">
        {ingredientName} {item.quantity ?? ""} {item.unit ?? ""}
      </span>
      <span className="flex items-center gap-2">
        <span className="text-slate-500">{item.role}</span>
        <button
          type="button"
          onClick={() => setEditing(true)}
          className="text-xs text-slate-400 hover:text-slate-200"
        >
          edit
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={remove}
          className="text-xs text-red-400 hover:text-red-300 disabled:opacity-50"
        >
          remove
        </button>
      </span>
      {error && <p className="text-xs text-red-400">{error}</p>}
    </li>
  );
}

function Recipe({ batchId, substrate, recipe, saltSuggestion, onAdded }) {
  const [options, setOptions] = useState([]);
  const [ingredientId, setIngredientId] = useState("");
  const [quantity, setQuantity] = useState("");
  const [unit, setUnit] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [food, setFood] = useState(null);
  const [role, setRole] = useState("");

  useEffect(() => {
    fetch(`${API_URL}/ingredients?substrate=${encodeURIComponent(substrate)}&include_retired=true`)
      .then((r) => r.json())
      .then(setOptions)
      .catch(() => {});
  }, [substrate, recipe.length]);

  useEffect(() => {
    const q = query.trim();
    if (q.length < 2) {
      setResults([]);
      return;
    }
    const t = setTimeout(() => {
      fetch(`${API_URL}/foods?q=${encodeURIComponent(q)}`)
        .then((r) => (r.ok ? r.json() : []))
        .then(setResults)
        .catch(() => {});
    }, 250);
    return () => clearTimeout(t);
  }, [query]);

  async function submit(e) {
    e.preventDefault();
    if (!ingredientId && !food) return;
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`${API_URL}/batches/${batchId}/ingredients`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...(food
            ? { fdc_id: food.fdc_id, ...(role ? { role } : {}) }
            : { ingredient_id: ingredientId }),
          quantity: quantity ? parseFloat(quantity) : null,
          unit: unit || null,
        }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `Could not add ingredient (${res.status})`);
      }
      setIngredientId("");
      setQuantity("");
      setUnit("");
      setFood(null);
      setQuery("");
      setResults([]);
      setRole("");
      onAdded();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card title="Recipe">
      {recipe.length === 0 ? (
        <p className="mb-3 text-sm text-slate-400">
          No ingredients yet. Add them with quantities and the forecast will start from your recipe.
        </p>
      ) : (
        <ul className="mb-3 divide-y divide-slate-800">
          {recipe.map((item) => (
            <RecipeRow
              key={item.id}
              batchId={batchId}
              item={item}
              ingredientName={
                options.find((o) => o.id === item.ingredient_id)?.name ?? item.ingredient_id
              }
              onChanged={onAdded}
            />
          ))}
        </ul>
      )}
      <form className="flex flex-wrap gap-2" onSubmit={submit}>
        <div className="w-full">
          {food ? (
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <span className="text-slate-200">USDA: {food.description}</span>
              <Select
                label="Ingredient role"
                size="xs"
                value={role}
                onChange={(e) => setRole(e.target.value)}
              >
                <option value="">default</option>
                {ROLES.map((r) => (
                  <option key={r} value={r}>
                    {r}
                  </option>
                ))}
              </Select>
              <button
                type="button"
                className="text-xs text-slate-400 hover:text-slate-200"
                onClick={() => setFood(null)}
              >
                clear
              </button>
            </div>
          ) : (
            <>
              <Input
                label="Search USDA foods"
                className="w-full"
                placeholder="Search all USDA foods…"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && e.preventDefault()}
              />
              {results.length > 0 && (
                <ul className="mt-1 max-h-60 divide-y divide-slate-800 overflow-y-auto rounded-lg border border-slate-800">
                  {results.map((f) => (
                    <li key={f.fdc_id}>
                      <button
                        type="button"
                        className="flex w-full justify-between px-3 py-2 text-left text-sm hover:bg-slate-800"
                        onClick={() => {
                          setFood(f);
                          setIngredientId("");
                          setResults([]);
                        }}
                      >
                        <span>{f.description}</span>
                        <span className="ml-2 shrink-0 text-xs text-slate-500">{f.data_type}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}
        </div>
        <Select
          label="Add ingredient"
          className="min-w-[9rem] flex-1"
          value={ingredientId}
          onChange={(e) => {
            const id = e.target.value;
            setIngredientId(id);
            setFood(null);
            const picked = options.find((o) => o.id === id);
            if (picked?.name === "Salt" && saltSuggestion && quantity === "") {
              setQuantity(String(saltSuggestion.grams));
              setUnit("g");
            }
          }}
        >
          <option value="">Add ingredient…</option>
          {options.filter((o) => o.is_active).map((o) => (
            <option key={o.id} value={o.id}>
              {o.name}
            </option>
          ))}
        </Select>
        <Input
          label="Ingredient quantity"
          size="sm"
          className="w-20"
          placeholder="qty"
          value={quantity}
          onChange={(e) => setQuantity(e.target.value)}
        />
        <Select
          label="Ingredient unit"
          size="sm"
          className="w-20"
          value={unit}
          onChange={(e) => setUnit(e.target.value)}
        >
          <option value="">unit</option>
          {["g", "kg", "mg", "ml", "L"].map((u) => (
            <option key={u} value={u}>
              {u}
            </option>
          ))}
        </Select>
        <Button type="submit" disabled={busy || (!ingredientId && !food)}>
          Add
        </Button>
      </form>
      {saltSuggestion && (
        <p className="mt-2 text-xs text-slate-500">
          Suggested salt: {saltSuggestion.grams} g ({saltSuggestion.pct}% of{" "}
          {Math.round(saltSuggestion.basis_g)} g base). Pick Salt to pre-fill it — edit the
          amount, or log 0 g for a deliberately unsalted batch.
        </p>
      )}
      {error && <p className="mt-2 text-sm text-red-400">{error}</p>}
    </Card>
  );
}

const NUTRIENT_LABELS = {
  sugars_total: "Sugars (total)",
  sucrose: "Sucrose",
  glucose: "Glucose",
  fructose: "Fructose",
  lactose: "Lactose",
  starch: "Starch",
  protein: "Protein",
  fat: "Fat",
  alcohol: "Alcohol",
};

function Composition({ data }) {
  if (!data || (data.total_mass_g === 0 && data.unquantified.length === 0)) return null;
  const rows = data.nutrients.filter((n) => NUTRIENT_LABELS[n.nutrient]);

  return (
    <Card title="Starting composition">
      <p className="mb-3 text-xs text-slate-500">
        {Math.round(data.total_mass_g)} g total · {Math.round(data.coverage * 100)}% of mass has
        reference data (USDA FoodData Central)
        {data.coverage < 1 && " — figures are lower bounds"}
      </p>
      <ul className="divide-y divide-slate-800 text-sm">
        {data.salt_pct != null && (
          <li className="flex justify-between py-1.5">
            <span>Added salt (% of total mass)</span>
            <span>{data.salt_pct.toFixed(2)} %</span>
          </li>
        )}
        {rows.map((n) => (
          <li key={n.nutrient} className="flex justify-between py-1.5">
            <span>{NUTRIENT_LABELS[n.nutrient]}</span>
            <span>
              {n.missing_from.length > 0 && "≥ "}
              {n.grams.toFixed(1)} g · {n.per_100g.toFixed(2)} g/100 g
            </span>
          </li>
        ))}
      </ul>
      {data.unmapped.length > 0 && (
        <p className="mt-2 text-xs text-slate-500">No reference data: {data.unmapped.join(", ")}</p>
      )}
      {data.unquantified.length > 0 && (
        <p className="mt-1 text-xs text-slate-500">
          Not counted (no quantity or unit): {data.unquantified.join(", ")}
        </p>
      )}
    </Card>
  );
}

// Known gaps in the curated default sets (curation record §7, §8.3). Frontend
// constant until the API carries this; shown for every batch of the type
// because attaching an organism never removes the defaults.
const THIN_NOTES = {
  cheese: "Known gap: proteases such as chymosin are not in this reference set yet.",
  garum:
    "Known gap: fish digestive proteases are not modeled. The default organisms describe koji garum (Aspergillus oryzae is included); traditional garum uses no koji.",
  kefir:
    "Known gap: some default organisms (Lactobacillus kefiri, L. kefiranofaciens) have no enzymes recorded.",
};

const COMPOUND_GROUPS = [
  ["acid", "Acids"],
  ["alcohol", "Alcohols"],
  ["gas", "Gases"],
  ["flavor", "Flavor compounds"],
  ["other", "Other"],
];

function KeggLink({ href, label }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      title={label}
      aria-label={`${label} (opens kegg.jp in a new tab)`}
      className="px-1 py-1 text-xs text-sky-400 underline"
    >
      KEGG
    </a>
  );
}

function Biochemistry({ batchId, type }) {
  const base = `${API_URL}/batches/${batchId}`;
  const [data, setData] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const [reload, setReload] = useState(0);
  const [status, setStatus] = useState("");
  const [actionError, setActionError] = useState(null);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState(null); // null = no result yet
  const [searchError, setSearchError] = useState(null);
  const [picked, setPicked] = useState(null);
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [confirmId, setConfirmId] = useState(null);
  const [removingId, setRemovingId] = useState(null);
  const addRef = useRef(null);
  const searchRef = useRef(null);
  const headRef = useRef(null);

  // Own fetch only: keep old data on screen, swap on success, abort stale requests.
  useEffect(() => {
    const ac = new AbortController();
    fetch(`${base}/biochemistry`, { signal: ac.signal })
      .then(async (res) => {
        if (!res.ok) throw new Error(await apiError(res, "Could not load biochemistry"));
        setData(await res.json());
        setLoadError(null);
      })
      .catch((e) => e.name !== "AbortError" && setLoadError(errText(e)));
    return () => ac.abort();
  }, [base, reload]);

  useEffect(() => {
    setResults(null);
    setSearchError(null);
    const q = query.trim();
    if (q.length < 2) return;
    const ac = new AbortController();
    const t = setTimeout(() => {
      fetch(`${API_URL}/organisms?q=${encodeURIComponent(q)}&limit=20`, { signal: ac.signal })
        .then(async (res) => {
          if (!res.ok) throw new Error(await apiError(res, "Search failed"));
          setResults(await res.json());
        })
        .catch((e) => {
          if (e.name === "AbortError") return;
          setSearchError(errText(e));
          setResults([]);
        });
    }, 250);
    return () => {
      clearTimeout(t);
      ac.abort();
    };
  }, [query]);

  // Focus the search box when the form opens and after "clear".
  useEffect(() => {
    if (open && !picked) searchRef.current?.focus();
  }, [open, picked]);

  function closeForm() {
    setOpen(false);
    setQuery("");
    setPicked(null);
    setNotes("");
    setActionError(null);
    setStatus("");
  }

  async function attach(e) {
    e.preventDefault();
    if (!picked) return;
    setBusy(true);
    setActionError(null);
    setStatus("");
    try {
      const res = await fetch(`${base}/organisms`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          organism_id: picked.id,
          ...(notes.trim() ? { notes: notes.trim() } : {}),
        }),
      });
      if (!res.ok) throw new Error(await apiError(res, "Could not attach organism"));
      setStatus(`${picked.name} attached.`);
      closeForm();
      addRef.current?.focus();
    } catch (err) {
      setActionError(errText(err));
    } finally {
      setBusy(false);
      setReload((n) => n + 1);
    }
  }

  async function remove(o) {
    setRemovingId(o.id);
    setActionError(null);
    setStatus("");
    try {
      const res = await fetch(`${base}/organisms/${o.id}`, { method: "DELETE" });
      if (!res.ok) throw new Error(await apiError(res, "Could not remove organism"));
      setStatus(`Custom attachment for ${o.name} removed.`);
      headRef.current?.focus();
    } catch (err) {
      setActionError(errText(err));
    } finally {
      setRemovingId(null);
      setConfirmId(null);
      setReload((n) => n + 1);
    }
  }

  const q = query.trim();
  let searchStatus = "Type at least 2 letters.";
  if (searchError) searchStatus = searchError;
  else if (q.length >= 2 && results === null) searchStatus = "Searching…";
  else if (results?.length === 0)
    searchStatus = `No organism matching "${q}" in the reference set. Only organisms already in the reference set can be attached.`;
  else if (results) searchStatus = `${results.length} organism${results.length === 1 ? "" : "s"} found.`;

  let content = null;
  if (data) {
    const { organisms, enzymes, compounds } = data;
    const hasCustom = organisms.some((o) => o.source === "custom");
    const byId = Object.fromEntries(organisms.map((o) => [o.id, o]));
    const carried = new Set(enzymes.flatMap((z) => z.organism_ids));
    const groups = COMPOUND_GROUPS.map(([cat, label]) => [
      label,
      compounds.filter((c) => (COMPOUND_GROUPS.some(([k]) => k === c.category) ? c.category : "other") === cat),
    ]).filter(([, list]) => list.length > 0);

    content = (
      <>
        <p className="mb-3 text-xs text-slate-400">
          {organisms.length === 0
            ? "Reference data only; nothing is recorded for this type."
            : `Reference data for a ${type} batch: not measured in this batch and not a forecast. Organisms and their enzymes are hand-curated, typical rather than exhaustive, and have not been expert-reviewed; enzyme and compound identities are from KEGG. Compounds come from representative reactions, not full pathways.${hasCustom ? " Organisms marked custom were attached to this batch by you." : ""}`}
        </p>

        <h3 ref={headRef} tabIndex={-1} className="text-sm font-medium text-slate-200">
          Organisms
        </h3>
        {organisms.length === 0 ? (
          <p className="mt-1 text-sm text-slate-400">
            No reference organisms are recorded for this type. You can attach one.
          </p>
        ) : (
          <ul className="divide-y divide-slate-800">
            {organisms.map((o) => {
              const custom = o.source === "custom";
              return (
                <li key={o.id} className="py-2 text-sm">
                  <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                    <span className="italic text-slate-200">{o.name}</span>
                    <span className="text-xs text-slate-400">{o.kingdom}</span>
                    <span
                      className={`rounded border px-1.5 py-0.5 text-xs ${
                        custom
                          ? "border-sky-500/40 bg-sky-950/40 text-sky-400"
                          : "border-slate-600 text-slate-300"
                      }`}
                    >
                      {custom ? "custom" : "type default"}
                    </span>
                  </div>
                  {custom && o.notes && (
                    <p className="mt-1 break-words text-xs text-slate-300">Note: {o.notes}</p>
                  )}
                  {!carried.has(o.id) && (
                    <p className="mt-1 text-xs text-slate-400">No enzymes recorded for this organism.</p>
                  )}
                  {custom &&
                    (confirmId === o.id ? (
                      <div className="mt-2 flex flex-wrap gap-2">
                        <button
                          type="button"
                          disabled={removingId === o.id}
                          onClick={() => remove(o)}
                          aria-label={`Confirm remove ${o.name}`}
                          className="rounded-lg bg-red-700 px-3 py-2 text-xs font-medium hover:bg-red-600 disabled:opacity-50"
                        >
                          {removingId === o.id ? "Removing…" : "Confirm remove"}
                        </button>
                        <button
                          type="button"
                          disabled={removingId === o.id}
                          onClick={() => setConfirmId(null)}
                          className="rounded-lg bg-slate-700 px-3 py-2 text-xs font-medium hover:bg-slate-600"
                        >
                          Cancel
                        </button>
                      </div>
                    ) : (
                      <button
                        type="button"
                        onClick={() => setConfirmId(o.id)}
                        aria-label={`Remove ${o.name}`}
                        className="mt-2 rounded-lg bg-slate-700 px-3 py-2 text-xs font-medium hover:bg-slate-600"
                      >
                        Remove
                      </button>
                    ))}
                </li>
              );
            })}
          </ul>
        )}

        {organisms.length > 0 && (
          <>
            <h3 className="mt-4 text-sm font-medium text-slate-200">Compounds involved</h3>
            {groups.length === 0 ? (
              <p className="mt-1 text-sm text-slate-400">
                No compounds recorded in this reference set for the organisms listed above.
              </p>
            ) : (
              groups.map(([label, list]) => (
                <div key={label} className="mt-2">
                  <p className="text-xs text-slate-400">{label}</p>
                  <ul className="mt-1 flex flex-wrap gap-1.5">
                    {list.map((c) => (
                      <li
                        key={c.id}
                        className="flex items-center gap-1 rounded border border-slate-700 px-2 py-1 text-sm text-slate-200"
                      >
                        {c.name}
                        {c.kegg_compound_id && (
                          <KeggLink
                            href={`https://www.kegg.jp/entry/${encodeURIComponent(c.kegg_compound_id)}`}
                            label={`KEGG COMPOUND entry ${c.kegg_compound_id}: structure, reactions and pathways`}
                          />
                        )}
                      </li>
                    ))}
                  </ul>
                </div>
              ))
            )}

            {enzymes.length === 0 ? (
              <>
                <h3 className="mt-4 text-sm font-medium text-slate-200">Enzymes (0)</h3>
                <p className="mt-1 text-sm text-slate-400">
                  No enzymes recorded in this reference set for the organisms listed above.
                </p>
              </>
            ) : (
              <details className="mt-4">
                <summary className="cursor-pointer py-1 text-sm font-medium text-slate-200">
                  Enzymes ({enzymes.length})
                </summary>
                <ul className="divide-y divide-slate-800">
                  {enzymes.map((z) => {
                    const names = z.organism_ids.map((id) => byId[id]?.name).filter(Boolean);
                    return (
                      <li key={z.id} className="py-2 text-sm">
                        <div className="flex flex-wrap items-center justify-between gap-x-3">
                          <span className="text-slate-200">{z.name}</span>
                          <span className="flex items-center gap-1">
                            <span className="font-mono text-xs text-slate-300">EC {z.ec_number}</span>
                            <KeggLink
                              href={`https://www.kegg.jp/entry/ec:${encodeURIComponent(z.ec_number)}`}
                              label={`KEGG ENZYME entry for EC ${z.ec_number}: reaction, systematic name and references`}
                            />
                          </span>
                        </div>
                        {names.length > 0 && (
                          <p className="text-xs text-slate-400">
                            Carried by: <span className="italic">{names.join(", ")}</span>
                          </p>
                        )}
                      </li>
                    );
                  })}
                </ul>
              </details>
            )}

            {THIN_NOTES[type] && <p className="mt-3 text-xs text-slate-400">{THIN_NOTES[type]}</p>}
            <p className="mt-2 text-xs text-slate-400">
              KEGG is a public biochemistry database; links open kegg.jp in a new tab. Enzyme links
              show the reaction and references; compound links show structure and pathways.
            </p>
            <details className="mt-2">
              <summary className="cursor-pointer py-1 text-xs text-slate-400">What this shows</summary>
              <p className="text-xs text-slate-400">
                Compounds involved lists substrates and products of the curated reactions; the data
                does not say which is which. Amylases and proteases have no compound rows (starch
                and protein are not KEGG compounds). Organism names are the widely used
                pre-reclassification forms. Gluconacetobacter xylinus, Lactobacillus kefiri and L.
                kefiranofaciens have no enzymes recorded.
              </p>
            </details>
          </>
        )}
      </>
    );
  }

  return (
    <Card title="Biochemistry">
      {!data && !loadError && <p className="text-sm text-slate-400">Loading biochemistry…</p>}
      {loadError && (
        <p role="alert" className="mb-3 text-sm text-red-400">
          {loadError}{" "}
          <button
            type="button"
            onClick={() => {
              setLoadError(null);
              setReload((n) => n + 1);
            }}
            className="ml-1 rounded-lg bg-slate-700 px-3 py-2 text-xs font-medium text-slate-100 hover:bg-slate-600"
          >
            Retry
          </button>
        </p>
      )}
      {content}
      {data && (
        <div className="mt-4">
          <button
            ref={addRef}
            type="button"
            onClick={() => (open ? closeForm() : setOpen(true))}
            className="rounded-lg bg-slate-700 px-3 py-3 text-sm font-medium hover:bg-slate-600"
          >
            {open ? "Cancel" : "Add organism"}
          </button>
          {open && (
            <form className="mt-3 space-y-2" onSubmit={attach}>
              <p className="text-xs text-slate-300">
                Adds to the default organisms for {type}; it does not replace them.
              </p>
              {picked ? (
                <div className="flex flex-wrap items-center gap-2 text-sm">
                  <span className="italic text-slate-200">{picked.name}</span>
                  <button
                    type="button"
                    className="px-2 py-2 text-xs text-slate-400 hover:text-slate-200"
                    onClick={() => setPicked(null)}
                  >
                    clear
                  </button>
                  {data.organisms.some((o) => o.id === picked.id && o.source === "default") && (
                    <p className="w-full text-xs text-slate-400">
                      Already a {type} default; attaching it records your note and shows it as custom.
                    </p>
                  )}
                </div>
              ) : (
                <div>
                  <label htmlFor="bio-search" className="sr-only">
                    Search organisms
                  </label>
                  <input
                    id="bio-search"
                    ref={searchRef}
                    type="search"
                    className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-base"
                    placeholder="Search organisms…"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && e.preventDefault()}
                  />
                  <p aria-live="polite" className="mt-1 text-xs text-slate-400">
                    {searchStatus}
                  </p>
                  {results?.length > 0 && (
                    <ul className="mt-1 max-h-60 divide-y divide-slate-800 overflow-y-auto rounded-lg border border-slate-800">
                      {results.map((o) => {
                        const existing = data.organisms.find((x) => x.id === o.id);
                        const taken = existing?.source === "custom";
                        return (
                          <li key={o.id}>
                            <button
                              type="button"
                              disabled={taken}
                              onClick={() => setPicked(o)}
                              className="flex w-full flex-wrap justify-between gap-x-2 px-3 py-3 text-left text-sm hover:bg-slate-800 disabled:opacity-50"
                            >
                              <span className="italic">{o.name}</span>
                              <span className="text-xs text-slate-400">
                                {taken ? "already attached" : existing ? `type default · ${o.kingdom}` : o.kingdom}
                              </span>
                            </button>
                          </li>
                        );
                      })}
                    </ul>
                  )}
                </div>
              )}
              {picked && (
                <div>
                  <label htmlFor="bio-notes" className="block text-xs text-slate-300">
                    Note (optional, max 500 characters)
                  </label>
                  <input
                    id="bio-notes"
                    className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-base"
                    placeholder="e.g. Fermentis SafAle US-05"
                    maxLength={500}
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                  />
                </div>
              )}
              <button
                type="submit"
                disabled={busy || !picked}
                className="rounded-lg bg-emerald-600 px-3 py-3 text-sm font-medium hover:bg-emerald-500 disabled:opacity-50"
              >
                {busy ? "Attaching…" : "Attach"}
              </button>
            </form>
          )}
        </div>
      )}
      {actionError && (
        <p role="alert" className="mt-2 text-sm text-red-400">
          {actionError}
        </p>
      )}
      <p aria-live="polite" className="mt-2 text-sm text-emerald-400">
        {status}
      </p>
    </Card>
  );
}

// Timeline events carry {type, value_numeric, value_text, notes}; notes are stored as type "note".
function eventLine(event) {
  const d = event.detail || {};
  const isNote = event.kind === "note";
  const value = [d.value_numeric, d.value_text].filter((v) => v != null && v !== "").join(" · ");
  const type = String(d.type ?? "");
  const title = isNote ? "Note" : type === "pH" ? type : type.charAt(0).toUpperCase() + type.slice(1);
  return { title, value, extra: isNote ? null : d.notes };
}

function Timeline({ timeline }) {
  if (timeline.length === 0) {
    return (
      <Card title="History">
        <p className="text-sm text-slate-400">Nothing logged yet. Observations and notes you add appear here.</p>
      </Card>
    );
  }
  return (
    <Card title="History">
      <ol className="ml-1.5 border-l border-slate-700">
        {timeline
          .slice()
          .reverse()
          .map((event, i) => {
            const { title, value, extra } = eventLine(event);
            return (
              <li key={i} className="relative pb-4 pl-5 last:pb-0">
                <span className="absolute -left-[5px] top-1.5 h-2.5 w-2.5 rounded-full border-2 border-slate-900 bg-emerald-400" />
                <p className="text-sm text-slate-100">
                  <span className="font-medium">{title}</span>
                  {value && <span className="text-slate-300">: {value}</span>}
                </p>
                {extra && <p className="text-sm text-slate-300">{extra}</p>}
                <p className="text-xs text-slate-400">
                  {new Date(event.timestamp).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}
                </p>
              </li>
            );
          })}
      </ol>
    </Card>
  );
}

function SafetyIcon({ ok, hard }) {
  return (
    <svg viewBox="0 0 16 16" className="mt-0.5 h-4 w-4 shrink-0" fill="none" aria-hidden="true">
      {ok ? (
        <>
          <circle cx="8" cy="8" r="6.25" stroke="currentColor" strokeWidth="1.5" />
          <path d="M5.2 8.2l1.9 1.9 3.7-3.9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </>
      ) : hard ? (
        <>
          <path d="M5.2 1.8h5.6l3.4 3.4v5.6l-3.4 3.4H5.2L1.8 10.8V5.2z" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" />
          <path d="M8 4.8v3.6M8 10.6v.1" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
        </>
      ) : (
        <>
          <path d="M8 2.2l6.2 11H1.8L8 2.2z" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" />
          <path d="M8 6.5v3M8 11.4v.1" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
        </>
      )}
    </svg>
  );
}

// Shown above the tabs so a hard stop is never hidden on another tab. With no
// verdicts it collapses to a single quiet line.
function Safety({ safety }) {
  const verdicts = [...safety.hard_stops, ...safety.warnings];
  if (verdicts.length === 0) {
    return (
      <p
        className={`flex gap-2 rounded-xl border px-4 py-2.5 text-sm ${
          safety.safe
            ? "border-emerald-500/25 bg-emerald-950/30 text-emerald-200"
            : "border-red-500/40 bg-red-950/40 text-red-300"
        }`}
      >
        <SafetyIcon ok={safety.safe} hard />
        <span>{safety.summary_en}</span>
      </p>
    );
  }
  return (
    <Card title="Safety">
      <p className={`mb-3 text-sm font-medium ${safety.safe ? "text-emerald-300" : "text-red-300"}`}>
        {safety.summary_en}
      </p>
      <ul className="space-y-2">
        {verdicts.map((v) => (
          <li key={v.rule_id} className={`flex gap-2 rounded-lg border p-3 text-sm ${urgencyColor(v.action)}`}>
            <SafetyIcon hard={safety.hard_stops.includes(v)} />
            <div>
              <p>
                <strong className="capitalize">{humanize(v.action)}:</strong> {v.reason_text_en}
              </p>
              <p className="mt-1 text-xs opacity-75">{v.source_citation}</p>
            </div>
          </li>
        ))}
      </ul>
    </Card>
  );
}

export default function BatchView({ batchId }) {
  const [preview, setPreview] = useState(null);
  const [composition, setComposition] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [tab, setTab] = useState("forecast");

  async function loadPreview(id) {
    if (!id) return;
    setLoading(true);
    setError(null);
    setPreview(null);
    setComposition(null);
    try {
      const res = await fetch(`${API_URL}/batches/${id}/preview`);
      if (!res.ok) throw new Error(res.status === 404 ? "Batch not found" : `API error (${res.status})`);
      setPreview(await res.json());
      const comp = await fetch(`${API_URL}/batches/${id}/composition`);
      setComposition(comp.ok ? await comp.json() : null);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (batchId) loadPreview(batchId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const TABS = [
    { id: "forecast", label: "Forecast" },
    { id: "log", label: "Log" },
    { id: "recipe", label: "Recipe" },
    { id: "biochemistry", label: "Biochemistry" },
  ];
  const panel = (id, children) => (
    <div
      role="tabpanel"
      id={`bt-panel-${id}`}
      aria-labelledby={`bt-tab-${id}`}
      hidden={tab !== id}
      className="space-y-4 pt-4"
    >
      {children}
    </div>
  );

  return (
    <>
      {loading && <p className="text-sm text-slate-400">Loading batch…</p>}
      {error && (
        <p role="alert" className="rounded-lg border border-red-500/40 bg-red-950/40 px-3 py-2 text-sm text-red-300">
          {error === "Batch not found" ? "Batch not found. Check the ID, or pick a batch from the list." : error}
        </p>
      )}

      {preview && (
        <>
          <BatchHeader
            batchId={batchId}
            batch={preview.batch}
            culture={preview.culture}
            daysInStage={preview.days_in_stage}
            onAdvanced={() => loadPreview(batchId)}
            onTemperatureSaved={() => loadPreview(preview.batch.id)}
          />
          <RepeatBatch batchId={batchId} />
          <Safety safety={preview.safety} />

          <div className="sticky top-0 z-20 -mx-4 bg-slate-950/95 px-4 backdrop-blur">
            <TabBar tabs={TABS} selected={tab} onSelect={setTab} idBase="bt" label="Batch sections" />
          </div>

          {panel(
            "forecast",
            <PredictionPanel
              key={preview.batch.id}
              apiUrl={API_URL}
              batchId={preview.batch.id}
              startedAt={preview.batch.started_at}
            />
          )}
          {panel(
            "log",
            <>
              <LogObservation batchId={batchId} onLogged={() => loadPreview(batchId)} />
              <Timeline timeline={preview.timeline} />
            </>
          )}
          {panel(
            "recipe",
            <>
              <Recipe
                batchId={batchId}
                substrate={preview.culture.type}
                recipe={preview.recipe}
                saltSuggestion={composition?.salt_suggestion}
                onAdded={() => loadPreview(batchId)}
              />
              <Composition data={composition} />
            </>
          )}
          {panel("biochemistry", <Biochemistry batchId={preview.batch.id} type={preview.culture.type} />)}
        </>
      )}
    </>
  );
}
