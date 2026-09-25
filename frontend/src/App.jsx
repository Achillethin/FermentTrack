import { useEffect, useState } from "react";
import PredictionPanel from "./prediction/PredictionPanel.jsx";
import TemperatureEstimate from "./prediction/TemperatureEstimate.jsx";
import TemperatureField from "./prediction/TemperatureField.jsx";
import { parseTemperature } from "./prediction/temperature.js";
import { Button, Input, Select } from "./components/ui.jsx";

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
      <Button variant="secondary" size="sm" onClick={advance} disabled={busy}>
        {busy ? "Advancing…" : "Advance to next stage →"}
      </Button>
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
        <p className="mb-3 text-sm text-slate-500">No ingredients logged yet.</p>
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
              <p>
                <strong className="uppercase">{v.action}:</strong> {v.reason_text_en}
              </p>
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
          <label htmlFor="culture-select" className="mb-1 block text-xs text-slate-400">
            Existing culture
          </label>
          <Select
            id="culture-select"
            className="w-full"
            value={cultureId}
            onChange={(e) => setCultureId(e.target.value)}
          >
            <option value="">— start a new culture —</option>
            {cultures.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name} ({c.type})
              </option>
            ))}
          </Select>
        </div>
        {!cultureId && (
          <div className="flex gap-2">
            <Input
              label="New culture name"
              className="flex-1"
              placeholder="New culture name"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
            />
            <Select
              label="New culture substrate type"
              value={newType}
              onChange={(e) => setNewType(e.target.value)}
            >
              {SUBSTRATES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </Select>
          </div>
        )}
        <Input
          label="Batch target (optional)"
          className="w-full"
          placeholder="Target (optional)"
          value={target}
          onChange={(e) => setTarget(e.target.value)}
        />
        <TemperatureField type={selectedType} value={expectedTemp} onChange={setExpectedTemp} />
        {error && <p className="text-sm text-red-400">{error}</p>}
        <Button type="submit" size="lg" className="w-full" disabled={busy}>
          {busy ? "Starting…" : "Start batch"}
        </Button>
      </form>
    </Card>
  );
}

function timeAgo(iso) {
  const ms = Date.now() - new Date(iso).getTime();
  const days = ms / 86_400_000;
  if (days < 1) return "today";
  if (days < 2) return "yesterday";
  if (days < 30) return `${Math.floor(days)} days ago`;
  return new Date(iso).toLocaleDateString();
}

function BatchPicker({ onPick }) {
  const [query, setQuery] = useState("");
  const [type, setType] = useState("");
  const [outcome, setOutcome] = useState("in_progress");
  const [batches, setBatches] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [showIdField, setShowIdField] = useState(false);
  const [manualId, setManualId] = useState("");

  useEffect(() => {
    const t = setTimeout(() => {
      setLoading(true);
      setError(null);
      const params = new URLSearchParams();
      if (query.trim()) params.set("q", query.trim());
      if (type) params.set("type", type);
      if (outcome) params.set("outcome", outcome);
      fetch(`${API_URL}/batches?${params}`)
        .then((r) => {
          if (!r.ok) throw new Error(`Could not load batches (${r.status})`);
          return r.json();
        })
        .then(setBatches)
        .catch((e) => setError(e.message))
        .finally(() => setLoading(false));
    }, 250);
    return () => clearTimeout(t);
  }, [query, type, outcome]);

  return (
    <Card title="Find a batch">
      <div className="flex flex-wrap gap-2">
        <Input
          label="Search batches by culture name"
          className="min-w-[10rem] flex-1"
          placeholder="Search by culture name…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <Select label="Filter by substrate" value={type} onChange={(e) => setType(e.target.value)}>
          <option value="">all substrates</option>
          {SUBSTRATES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </Select>
        <Select
          label="Filter by outcome"
          value={outcome}
          onChange={(e) => setOutcome(e.target.value)}
        >
          <option value="">any outcome</option>
          <option value="in_progress">in progress</option>
          <option value="completed">completed</option>
          <option value="failed">failed</option>
        </Select>
      </div>

      {loading && <p className="mt-2 text-xs text-slate-500">Searching…</p>}
      {error && <p className="mt-2 text-sm text-red-400">{error}</p>}

      {!loading && batches.length === 0 && !error && (
        <p className="mt-2 text-sm text-slate-500">No batches match.</p>
      )}

      {batches.length > 0 && (
        <ul className="mt-2 max-h-72 divide-y divide-slate-800 overflow-y-auto rounded-lg border border-slate-800">
          {batches.map((b) => (
            <li key={b.id}>
              <button
                type="button"
                onClick={() => onPick(b.id)}
                className="flex w-full flex-wrap items-center justify-between gap-x-3 gap-y-0.5 px-3 py-2 text-left text-sm hover:bg-slate-800"
              >
                <span className="text-slate-200">{b.culture_name}</span>
                <span className="text-slate-500">{b.culture_type}</span>
                <span className="text-slate-500">{b.current_stage}</span>
                <span className="text-xs text-slate-600">{timeAgo(b.started_at)}</span>
              </button>
            </li>
          ))}
        </ul>
      )}

      <button
        type="button"
        onClick={() => setShowIdField((v) => !v)}
        className="mt-3 text-xs text-slate-500 hover:text-slate-300"
      >
        {showIdField ? "Hide" : "Have a batch ID instead?"}
      </button>
      {showIdField && (
        <form
          className="mt-2 flex gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            if (manualId.trim()) onPick(manualId.trim());
          }}
        >
          <Input
            label="Batch ID"
            className="flex-1"
            placeholder="Batch ID"
            value={manualId}
            onChange={(e) => setManualId(e.target.value)}
          />
          <Button type="submit" variant="secondary" size="lg">
            Load
          </Button>
        </form>
      )}
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

      <BatchPicker
        onPick={(id) => {
          setBatchId(id);
          loadPreview(id);
        }}
      />

      {loading && <p className="text-sm text-slate-500">Loading batch…</p>}
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
          <Timeline timeline={preview.timeline} />
          <Safety safety={preview.safety} />
        </>
      )}
    </main>
  );
}
