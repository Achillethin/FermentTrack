import { useEffect, useRef, useState } from "react";
import PredictionPanel from "./prediction/PredictionPanel.jsx";
import TemperatureEstimate from "./prediction/TemperatureEstimate.jsx";
import TemperatureField from "./prediction/TemperatureField.jsx";
import { parseTemperature } from "./prediction/temperature.js";

const API_URL = (import.meta.env.VITE_API_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");

// Mirrors fermenttrack.stages.STAGE_MACHINES (kombucha/sourdough/koji/cheese/
// lacto_ferment/miso/garum have real stage progressions) plus kefir/vinegar,
// which have Ingredient/BatchIngredient recipe logging but no stage machine
// yet (single "in_progress" pseudo-stage, no reminder automation).
const SUBSTRATES = [
  "kombucha",
  "sourdough",
  "koji",
  "cheese",
  "lacto_ferment",
  "miso",
  "garum",
  "kefir",
  "vinegar",
];

function urgencyColor(urgency) {
  return (
    {
      critical: "text-red-400 border-red-500/40 bg-red-950/40",
      high: "text-orange-400 border-orange-500/40 bg-orange-950/40",
      medium: "text-amber-400 border-amber-500/40 bg-amber-950/40",
      low: "text-slate-400 border-slate-600/40 bg-slate-800/40",
    }[urgency] || "text-slate-400 border-slate-600/40 bg-slate-800/40"
  );
}

function Card({ title, children }) {
  return (
    <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
        {title}
      </h2>
      {children}
    </section>
  );
}

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
      <button
        onClick={advance}
        disabled={busy}
        className="rounded-lg bg-slate-700 px-3 py-1.5 text-xs font-medium hover:bg-slate-600 disabled:opacity-50"
      >
        {busy ? "Advancing…" : "Advance to next stage →"}
      </button>
      {error && <p className="mt-1 text-xs text-red-400">{error}</p>}
    </div>
  );
}

function BatchHeader({ batchId, batch, culture, daysInStage, onAdvanced, onTemperatureSaved }) {
  return (
    <Card title="Batch">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <p className="text-lg font-medium">{culture.name}</p>
          <p className="text-sm text-slate-400">{culture.type}</p>
        </div>
        <div className="text-right">
          <p className="text-lg font-medium">{batch.current_stage}</p>
          <p className="text-sm text-slate-400">
            {daysInStage.toFixed(1)} day{daysInStage === 1 ? "" : "s"} in stage
          </p>
        </div>
      </div>
      {batch.target && <p className="mt-2 text-sm text-slate-300">Target: {batch.target}</p>}
      <TemperatureEstimate apiUrl={API_URL} batch={batch} type={culture.type} onSaved={onTemperatureSaved} />
      <p className="mt-2 text-xs text-slate-500">
        Started {new Date(batch.started_at).toLocaleString()} · outcome: {batch.outcome}
      </p>
      {batch.outcome === "in_progress" && (
        <StageControl batchId={batchId} onAdvanced={onAdvanced} />
      )}
    </Card>
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
          <select
            className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
            value={type}
            onChange={(e) => setType(e.target.value)}
          >
            {OBSERVATION_TYPES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
          {type === "other" && (
            <input
              className="flex-1 rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
              placeholder="type name"
              value={customType}
              onChange={(e) => setCustomType(e.target.value)}
            />
          )}
        </div>

        {isNote ? (
          <textarea
            className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
            placeholder="What did you observe?"
            rows={2}
            value={valueText}
            onChange={(e) => setValueText(e.target.value)}
          />
        ) : (
          <>
            <div className="flex gap-2">
              {isNumeric && (
                <input
                  className="w-24 rounded-lg border border-slate-700 bg-slate-900 px-2 py-2 text-sm"
                  placeholder="value"
                  value={valueNumeric}
                  onChange={(e) => setValueNumeric(e.target.value)}
                />
              )}
              <input
                className="flex-1 rounded-lg border border-slate-700 bg-slate-900 px-2 py-2 text-sm"
                placeholder="description (e.g. tangy, cloudy)"
                value={valueText}
                onChange={(e) => setValueText(e.target.value)}
              />
            </div>
            <input
              className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
              placeholder="Notes (optional)"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
            />
          </>
        )}

        {error && <p className="text-sm text-red-400">{error}</p>}
        <button
          type="submit"
          disabled={busy}
          className="w-full rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium hover:bg-emerald-500 disabled:opacity-50"
        >
          {busy ? "Logging…" : "Log observation"}
        </button>
      </form>
    </Card>
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
        <p className="mb-3 text-sm text-slate-500">No ingredients logged yet.</p>
      ) : (
        <ul className="mb-3 divide-y divide-slate-800">
          {recipe.map((item) => (
            <li key={item.id} className="flex justify-between py-2 text-sm">
              <span className="text-slate-200">
                {options.find((o) => o.id === item.ingredient_id)?.name ?? item.ingredient_id}{" "}
                {item.quantity ?? ""} {item.unit ?? ""}
              </span>
              <span className="text-slate-500">{item.role}</span>
            </li>
          ))}
        </ul>
      )}
      <form className="flex flex-wrap gap-2" onSubmit={submit}>
        <div className="w-full">
          {food ? (
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <span className="text-slate-200">USDA: {food.description}</span>
              <select
                className="rounded-lg border border-slate-700 bg-slate-900 px-2 py-1 text-sm"
                value={role}
                onChange={(e) => setRole(e.target.value)}
              >
                <option value="">default</option>
                {["base", "flavoring", "additive", "starter"].map((r) => (
                  <option key={r} value={r}>
                    {r}
                  </option>
                ))}
              </select>
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
              <input
                className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
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
        <select
          className="min-w-[9rem] flex-1 rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
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
        </select>
        <input
          className="w-20 rounded-lg border border-slate-700 bg-slate-900 px-2 py-2 text-sm"
          placeholder="qty"
          value={quantity}
          onChange={(e) => setQuantity(e.target.value)}
        />
        <select
          className="w-20 rounded-lg border border-slate-700 bg-slate-900 px-2 py-2 text-sm"
          value={unit}
          onChange={(e) => setUnit(e.target.value)}
        >
          <option value="">unit</option>
          {["g", "kg", "mg", "ml", "L"].map((u) => (
            <option key={u} value={u}>
              {u}
            </option>
          ))}
        </select>
        <button
          type="submit"
          disabled={busy || (!ingredientId && !food)}
          className="rounded-lg bg-emerald-600 px-3 py-2 text-sm font-medium hover:bg-emerald-500 disabled:opacity-50"
        >
          Add
        </button>
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

// detail is a string on 404/409 but a list on 422; network failures are TypeErrors.
async function apiError(res, fallback) {
  const body = await res.json().catch(() => ({}));
  return typeof body.detail === "string" ? body.detail : `${fallback} (${res.status})`;
}
const errText = (e) => (e instanceof TypeError ? "Could not reach the server" : e.message);

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

function Timeline({ timeline }) {
  if (timeline.length === 0) {
    return (
      <Card title="Timeline">
        <p className="text-sm text-slate-500">No events yet.</p>
      </Card>
    );
  }
  return (
    <Card title="Timeline">
      <ul className="space-y-2">
        {timeline
          .slice()
          .reverse()
          .map((event, i) => (
            <li key={i} className="text-sm">
              <span className="text-slate-500">
                {new Date(event.timestamp).toLocaleString()}
              </span>{" "}
              <span className="text-slate-300">· {event.kind}</span>
              <div className="text-slate-400">{JSON.stringify(event.detail)}</div>
            </li>
          ))}
      </ul>
    </Card>
  );
}

function Safety({ safety }) {
  const verdicts = [...safety.hard_stops, ...safety.warnings];
  return (
    <Card title="Safety Advisory">
      <p className={`mb-2 text-sm font-medium ${safety.safe ? "text-emerald-400" : "text-red-400"}`}>
        {safety.summary_en}
      </p>
      {verdicts.length > 0 && (
        <ul className="space-y-2">
          {verdicts.map((v) => (
            <li key={v.rule_id} className={`rounded-lg border p-2 text-sm ${urgencyColor(v.action)}`}>
              <p>{v.reason_text_en}</p>
              <p className="mt-1 text-xs opacity-70">{v.source_citation}</p>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function NewBatch({ onCreated }) {
  const [cultures, setCultures] = useState([]);
  const [cultureId, setCultureId] = useState("");
  const [newName, setNewName] = useState("");
  const [newType, setNewType] = useState("kombucha");
  const [target, setTarget] = useState("");
  const [expectedTemp, setExpectedTemp] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const selectedType = cultureId ? cultures.find((c) => c.id === cultureId)?.type : newType;

  useEffect(() => {
    fetch(`${API_URL}/cultures`)
      .then((r) => r.json())
      .then(setCultures)
      .catch(() => {});
  }, []);

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const temp = parseTemperature(expectedTemp);
      if (temp.error) throw new Error(temp.error);
      let id = cultureId;
      if (!id) {
        if (!newName.trim()) throw new Error("Pick a culture or name a new one");
        const res = await fetch(`${API_URL}/cultures`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name: newName, type: newType }),
        });
        if (!res.ok) throw new Error("Could not create culture");
        id = (await res.json()).id;
      }
      const res = await fetch(`${API_URL}/batches`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          culture_id: id,
          target: target || null,
          expected_temperature_c: temp.value,
        }),
      });
      if (!res.ok) throw new Error("Could not start batch");
      const batch = await res.json();
      onCreated(batch.id);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card title="Start a new batch">
      <form className="space-y-3" onSubmit={submit}>
        <div>
          <label className="mb-1 block text-xs text-slate-400">Existing culture</label>
          <select
            className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
            value={cultureId}
            onChange={(e) => setCultureId(e.target.value)}
          >
            <option value="">— start a new culture —</option>
            {cultures.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name} ({c.type})
              </option>
            ))}
          </select>
        </div>
        {!cultureId && (
          <div className="flex gap-2">
            <input
              className="flex-1 rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
              placeholder="New culture name"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
            />
            <select
              className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
              value={newType}
              onChange={(e) => setNewType(e.target.value)}
            >
              {SUBSTRATES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>
        )}
        <input
          className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
          placeholder="Target (optional)"
          value={target}
          onChange={(e) => setTarget(e.target.value)}
        />
        <TemperatureField type={selectedType} value={expectedTemp} onChange={setExpectedTemp} />
        {error && <p className="text-sm text-red-400">{error}</p>}
        <button
          type="submit"
          disabled={busy}
          className="w-full rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium hover:bg-emerald-500 disabled:opacity-50"
        >
          {busy ? "Starting…" : "Start batch"}
        </button>
      </form>
    </Card>
  );
}

export default function App() {
  const params = new URLSearchParams(window.location.search);
  const [batchId, setBatchId] = useState(params.get("batch") || "");
  const [preview, setPreview] = useState(null);
  const [composition, setComposition] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

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
      const url = new URL(window.location);
      url.searchParams.set("batch", id);
      window.history.replaceState({}, "", url);
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

  return (
    <main className="mx-auto max-w-2xl space-y-4 p-4">
      <h1 className="text-2xl font-bold">🧫 FermentTrack</h1>

      <NewBatch
        onCreated={(id) => {
          setBatchId(id);
          loadPreview(id);
        }}
      />

      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          loadPreview(batchId);
        }}
      >
        <input
          className="flex-1 rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
          placeholder="Batch ID"
          value={batchId}
          onChange={(e) => setBatchId(e.target.value)}
        />
        <button
          type="submit"
          className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium hover:bg-emerald-500"
        >
          {loading ? "Loading…" : "Load"}
        </button>
      </form>

      {error && <p className="text-sm text-red-400">{error}</p>}

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
          <PredictionPanel
            key={preview.batch.id}
            apiUrl={API_URL}
            batchId={preview.batch.id}
            startedAt={preview.batch.started_at}
          />
          <LogObservation batchId={batchId} onLogged={() => loadPreview(batchId)} />
          <Recipe
            batchId={batchId}
            substrate={preview.culture.type}
            recipe={preview.recipe}
            saltSuggestion={composition?.salt_suggestion}
            onAdded={() => loadPreview(batchId)}
          />
          <Composition data={composition} />
          <Biochemistry batchId={preview.batch.id} type={preview.culture.type} />
          <Timeline timeline={preview.timeline} />
          <Safety safety={preview.safety} />
        </>
      )}
    </main>
  );
}
