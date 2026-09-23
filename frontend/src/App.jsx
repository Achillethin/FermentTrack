import { useEffect, useState } from "react";

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

function BatchHeader({ batchId, batch, culture, daysInStage, onAdvanced }) {
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
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

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
        body: JSON.stringify({ culture_id: id, target: target || null }),
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
          <Timeline timeline={preview.timeline} />
          <Safety safety={preview.safety} />
        </>
      )}
    </main>
  );
}
