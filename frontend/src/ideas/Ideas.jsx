import { useId, useState } from "react";
import { Button } from "../components/ui.jsx";
import TemperatureField from "../prediction/TemperatureField.jsx";
import { parseTemperature } from "../prediction/temperature.js";
import { Card } from "../shared.jsx";
import { postRecommendations } from "./api.js";
import IdeaCard from "./IdeaCard.jsx";
import { targetBody } from "./ideas.js";
import { IngredientPicker, ModeToggle, TargetChips } from "./Pickers.jsx";

const MODE = "proven"; // Experimental and Both arrive with B7
const MAX_BATCH_G = 200_000; // the API's limit

function parseBatch(text) {
  const v = Number(String(text).trim().replace(",", "."));
  return Number.isFinite(v) && v > 0 && v <= MAX_BATCH_G ? v : null;
}

function Results({ result }) {
  const { status, data, query, error, seq } = result;
  const cards = data?.proven.cards ?? [];
  let said = "";
  if (status === "loading") said = "Finding ideas…";
  else if (status === "done") said = cards.length ? `${cards.length} proven idea${cards.length === 1 ? "" : "s"}.` : "";

  return (
    <section aria-label="Ideas found" aria-busy={status === "loading"} className="space-y-4">
      <p role="status" aria-live="polite" className="min-h-[1.25rem] text-sm text-slate-300">
        {said}
      </p>
      {status === "error" && (
        <div role="alert" className="rounded-lg border border-red-500/30 bg-red-950/30 p-3 text-sm text-red-300">
          Could not find ideas: {error}
        </div>
      )}
      {data && (
        <div className={`space-y-4 ${status === "loading" ? "opacity-60" : ""}`}>
          {data.notes.map((n, i) => (
            <p key={i} className="text-sm text-slate-400">
              {n}
            </p>
          ))}
          {cards.length === 0 ? (
            <Card title="No proven recipe matches">
              {data.proven.message && <p className="text-sm text-slate-300">{data.proven.message}</p>}
              <p className="mt-1 text-sm text-slate-400">Try fewer ingredients, or other aromas and tastes.</p>
            </Card>
          ) : (
            cards.map((card) => <IdeaCard key={`${seq}-${card.id}`} card={card} query={query} />)
          )}
        </div>
      )}
    </section>
  );
}

// #/ideas: ingredients and/or target aromas in, Proven recipe cards out (design §§ 5, 11).
export default function Ideas() {
  const [ingredients, setIngredients] = useState([]);
  const [targets, setTargets] = useState([]);
  const [tempText, setTempText] = useState("");
  const [batchText, setBatchText] = useState("1000");
  const [result, setResult] = useState({ status: "idle", seq: 0 });
  const batchId = useId();

  const temp = parseTemperature(tempText);
  const batchG = parseBatch(batchText);
  const empty = ingredients.length === 0 && targets.length === 0;
  const loading = result.status === "loading";

  async function submit(e) {
    e.preventDefault();
    if (empty || temp.error || batchG == null || loading) return;
    const query = { ingredients, ...targetBody(targets), mode: MODE, temperature_c: temp.value, batch_g: batchG };
    setResult((r) => ({ ...r, status: "loading" }));
    try {
      const data = await postRecommendations(query);
      setResult((r) => ({ status: "done", data, query, seq: r.seq + 1 }));
    } catch (err) {
      // The previous query's cards would read as answers to this one: drop them.
      setResult((r) => ({ status: "error", error: err.message, seq: r.seq }));
    }
  }

  return (
    <div className="space-y-4">
      <Card title="Ideas">
        <p className="mb-4 text-sm text-slate-300">
          Start from what you have, what you would like to notice, or both. Ideas are model-guided: timings and aroma
          levels are model estimates, not validated.
        </p>
        <form className="space-y-5" onSubmit={submit} noValidate>
          <IngredientPicker value={ingredients} onChange={setIngredients} />
          <TargetChips value={targets} onChange={setTargets} />
          <ModeToggle />
          <div className="flex flex-wrap gap-x-6 gap-y-3">
            <TemperatureField
              value={tempText}
              onChange={setTempText}
              label="Your kitchen temperature (°C)"
              laterHint={false}
            />
            <div>
              <label htmlFor={batchId} className="mb-1 block text-xs text-slate-400">
                Batch size (g)
              </label>
              <input
                id={batchId}
                type="text"
                inputMode="decimal"
                autoComplete="off"
                value={batchText}
                onChange={(e) => setBatchText(e.target.value)}
                aria-invalid={batchG == null ? "true" : undefined}
                aria-describedby={`${batchId}-hint`}
                className={`w-28 rounded-lg border bg-slate-900 px-3 py-2 text-base tabular-nums sm:text-sm ${
                  batchG == null ? "border-red-500/70" : "border-slate-700"
                }`}
              />
              <p id={`${batchId}-hint`} className={`mt-1 text-xs ${batchG == null ? "text-red-400" : "text-slate-400"}`}>
                {batchG == null ? `Use a weight above 0 and up to ${MAX_BATCH_G / 1000} kg.` : "Recipes are scaled to it."}
              </p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <Button type="submit" size="lg" className="min-h-[44px]" disabled={empty || loading || Boolean(temp.error) || batchG == null}>
              {loading ? "Finding ideas…" : "Find ideas"}
            </Button>
            {empty && <p className="text-xs text-slate-400">Pick at least one ingredient, aroma or taste.</p>}
          </div>
        </form>
      </Card>
      <Results result={result} />
    </div>
  );
}
